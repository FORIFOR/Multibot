"""AgentRunner: one agent session = independent conversation state + tool loop through the gateway."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from ..config.loader import platform_policy_text
from ..contracts import TaskState
from ..providers.base import LLMRequest, LLMResponse, ProviderError
from ..providers.pricing import price_for
from .context import SessionContext
from .policy import Cancelled, PolicyViolation
from .tools import ToolGateway


class WorkerFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class SessionOutcome:
    kind: str  # finished | blocked | review | approval_pending | failed | cancelled | ended
    detail: str = ""


RUNTIME_RULES = """
## Runtime rules (enforced by the platform, not negotiable)
- Deliverables exist only as published artifacts: write files with workspace_write, then publish_artifact. Chat text is not a deliverable.
- When every output path of your task is published, call finish_task. Do not narrate; act with tools.
- Messages to other agents are real deliveries (send_message). Only send request / question / answer / handoff / finding / decision. No acknowledgements, thanks or encouragement.
- To wait for an answer, call read_messages with wait_seconds. To hand off, reference artifacts by id and revision.
- Timestamps, revisions, hashes and permissions are decided by the runtime. Do not invent them.
- If you cannot proceed, call report_blocker. If an action needs a human decision, call request_approval.
- Keep tool calls purposeful; there are hard limits on model calls, tool calls, messages and budget.
"""


def build_system_prompt(ctx: SessionContext) -> str:
    agent = ctx.agent
    parts = [platform_policy_text().strip(), "\n---\n", agent.system_prompt.strip(), "\n---\n", RUNTIME_RULES.strip()]
    if agent.skills:
        parts.append("\n\n## Enabled skills (call read_skill to load the body only when relevant)\n" + "\n".join(
            f"- {s['name']}: {s['description']}" for s in agent.skills))
    parts.append(f"\n\n## Identity\nYou are agent `{agent.agent_id}` (role: {agent.role}). Team language: {ctx.rt.config.defaults.language}.")
    return "".join(parts)


def _artifact_line(m) -> str:
    return f"- {m.artifact_id} (revision {m.revision}, sha256 {m.sha256[:12]}…, {m.media_type}, path {m.logical_path}, by {m.agent_id})"


async def build_task_message(ctx: SessionContext, task: TaskState, review_feedback: str | None = None) -> str:
    rt = ctx.rt
    spec = task.spec
    lines = [f"# Task {spec.id} (attempt {ctx.attempt}) — owner: you", f"Run goal: {rt.run.goal}"]
    if rt.run.plan and rt.run.plan.assumptions:
        lines.append("Assumptions recorded by the master: " + "; ".join(rt.run.plan.assumptions))
    lines += ["", f"## Objective\n{spec.objective}", "", "## Acceptance criteria"]
    lines += [f"- {c.id} [{c.check_kind}]: {c.description}" for c in spec.acceptance]
    inputs = []
    for ref in spec.input_artifacts:
        m = await rt.artifacts.get(rt.run_id, ref.artifact_id, ref.revision)
        if m:
            inputs.append(_artifact_line(m))
    for dep in spec.depends_on:
        for m in await rt.artifacts.list(rt.run_id, latest_only=True):
            if m.task_id == dep and _artifact_line(m) not in inputs:
                inputs.append(_artifact_line(m))
    lines.append("\n## Input artifacts (read with read_artifact)\n" + ("\n".join(inputs) if inputs else "(none)"))
    if spec.output_paths:
        lines.append("\n## Output paths you must publish\n" + "\n".join(f"- {p}" for p in spec.output_paths))
    else:
        lines.append("\n## Output\nNo file outputs declared; deliver via submit_review / send_message as your role requires.")
    if ctx.agent.role == "reviewer":
        for dep in spec.depends_on:
            t = rt.tasks.get(dep)
            if t and t.spec.owner != ctx.agent.agent_id:
                lines.append(f"\n## Review target: task {dep} (owner {t.spec.owner})\nObjective: {t.spec.objective}\nAcceptance criteria to verify:")
                lines += [f"- {c.id} [{c.check_kind}]: {c.description}" for c in t.spec.acceptance]
                lines.append("Verify against the published revisions listed above. Run run_check/sandbox_run where possible. "
                             "Then submit_review, send a finding/handoff message to the owner if anything fails, and finish_task.")
    if ctx.attempt > 1 and task.result:
        lines.append(f"\n## Your previous attempt\n{task.result.summary}")
    if review_feedback:
        lines.append(f"\n## Review feedback on your previous revision (fix these, publish new revisions)\n{review_feedback}")
    msgs = await rt.bus.read(ctx.agent.agent_id, ctx.owned_task_ids(), unread_only=True)
    if msgs:
        await rt.bus.mark_read(msgs, ctx.agent.agent_id)
        lines.append("\n## Inbox")
        for m in msgs:
            refs = ", ".join(f"{r.artifact_id}@r{r.revision}" for r in m.artifact_refs) or "-"
            lines.append(f"[{m.message_id}] from={m.from_agent_id} purpose={m.purpose} artifacts={refs}\n{m.text}")
    inp = rt.run.inputs
    if inp.text or inp.urls or inp.files:
        lines.append("\n## User-provided inputs")
        if inp.text:
            lines.append(inp.text[:20000])
        for u in inp.urls:
            lines.append(f"- URL: {u}")
        for f in inp.files:
            lines.append(f"\n### Attachment {f.get('name')}\n{str(f.get('content', ''))[:20000]}")
    lines.append(f"\nRemaining budget: model calls {rt.config.limits.max_model_calls - rt.policy.usage.model_calls}, "
                 f"peer messages for this task {rt.config.limits.max_peer_messages_per_task - rt.policy.peer_messages.get(spec.id, 0)}, "
                 f"wall clock {int(rt.remaining_seconds())}s.")
    return "\n".join(lines)


class AgentRunner:
    def __init__(self, ctx: SessionContext):
        self.ctx = ctx
        self.rt = ctx.rt
        self.gateway = ToolGateway(ctx)
        self.messages: list[dict[str, Any]] = []
        self.nudges = 0

    async def _call_model(self, req: LLMRequest, causation_id: str | None) -> LLMResponse:
        rt, ctx = self.rt, self.ctx
        conn = rt.config.connection(ctx.agent.connection_id)
        price = price_for(ctx.agent.model, rt.config.pricing, driver=ctx.agent.driver)
        est_in = (len(req.system) + sum(len(json.dumps(m, ensure_ascii=False)) for m in req.messages)
                  + sum(len(json.dumps(t.input_schema)) + len(t.description) for t in req.tools)) // 3 + 200
        provider = rt.providers.adapter(ctx.agent.connection_id)
        attempts = 0
        while True:
            attempts += 1
            res = rt.policy.reserve_model_call(price, est_in, req.max_tokens)
            t0 = time.monotonic()
            try:
                resp = await provider.complete(req)
            except ProviderError as e:
                rt.policy.release(res)
                rt.policy.usage.model_calls -= 1 if attempts > 1 and e.retryable else 0
                await rt.events.append(rt.run_id, "model.failed",
                                       {"connection_id": ctx.agent.connection_id, "model_requested": ctx.agent.model,
                                        "kind": e.kind, "status": e.status, "message": str(e), "retryable": e.retryable,
                                        "attempt": attempts},
                                       actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=causation_id)
                if e.retryable and attempts < 3 and rt.remaining_seconds() > 30:
                    await asyncio.sleep(min(e.retry_after or (2 ** attempts), 30))
                    continue
                raise WorkerFailure(f"provider_{e.kind}", str(e))
            cost = rt.policy.settle_model_call(res, price, resp.usage)
            await rt.events.append(rt.run_id, "model.called",
                                   {"connection_id": ctx.agent.connection_id, "driver": ctx.agent.driver,
                                    "provider_kind": getattr(provider, "kind", "real"),
                                    "model_requested": ctx.agent.model, "model_reported": resp.model_reported or "unknown",
                                    "request_id": resp.request_id, "stop_reason": resp.stop_reason,
                                    "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                                              "cache_read_tokens": resp.usage.cache_read_tokens,
                                              "cache_write_tokens": resp.usage.cache_write_tokens},
                                    "cost_usd": round(cost, 6), "latency_ms": int((time.monotonic() - t0) * 1000),
                                    "text_preview": resp.text[:600], "tool_calls": [c.name for c in resp.tool_calls],
                                    "mode": ctx.mode, "attempt": ctx.attempt, "refusal": resp.refusal},
                                   actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=causation_id)
            await rt.persist_usage()
            if resp.refusal is not None:
                raise WorkerFailure("refusal", f"provider refused the request: {resp.refusal}")
            return resp

    async def run(self, user_message: str) -> SessionOutcome:
        rt, ctx = self.rt, self.ctx
        system = build_system_prompt(ctx)
        self.messages = [{"role": "user", "content": [{"type": "text", "text": user_message}]}]
        tools = self.gateway.specs()
        rt.active_sessions[ctx.agent.agent_id] = rt.active_sessions.get(ctx.agent.agent_id, 0) + 1
        try:
            while True:
                rt.policy.check_cancel()
                if rt.remaining_seconds() <= 0:
                    raise WorkerFailure("timeout", "run wall-clock limit reached")
                req = LLMRequest(model=ctx.agent.model, system=system, messages=self.messages, tools=tools,
                                 max_tokens=rt.config.limits.max_output_tokens, effort=ctx.agent.effort,
                                 metadata={"agent_id": ctx.agent.agent_id, "task_id": ctx.task_id, "mode": ctx.mode,
                                           "attempt": ctx.attempt, "role": ctx.agent.role})
                resp = await self._call_model(req, ctx.causation_id)
                self.messages.append({"role": "assistant", "content": resp.raw_content or [{"type": "text", "text": resp.text or "…"}]})
                if not resp.tool_calls:
                    if ctx.mode == "reply" and ctx.replied:
                        return SessionOutcome("finished", "replied")
                    if resp.stop_reason == "max_tokens":
                        nudge = "Your previous output hit the token limit. Continue with tool calls; keep text short."
                    else:
                        nudge = ("You ended without a tool call. If your work is done, call finish_task; if you are stuck, "
                                 "call report_blocker; otherwise continue with tools.")
                    self.nudges += 1
                    if self.nudges > 2:
                        return SessionOutcome("ended", "agent ended its turn repeatedly without finish_task")
                    self.messages.append({"role": "user", "content": [{"type": "text", "text": nudge}]})
                    continue
                results = []
                for call in resp.tool_calls:
                    out = await self.gateway.call(call.name, call.arguments, causation_id=ctx.causation_id)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": out,
                                    "is_error": out.startswith(("ERROR", "DENIED", "REJECTED", "NOT FOUND"))})
                    if ctx.finished or ctx.blocked or ctx.approval_pending:
                        break
                content: list[dict[str, Any]] = results
                if not (ctx.finished or ctx.blocked or ctx.approval_pending):
                    unread = await rt.bus.unread_count(ctx.agent.agent_id)
                    if unread:
                        content = results + [{"type": "text", "text": f"[runtime] You have {unread} unread message(s). Call read_messages."}]
                self.messages.append({"role": "user", "content": content})
                if ctx.finished:
                    return SessionOutcome("finished", ctx.finished.summary)
                if ctx.blocked:
                    return SessionOutcome("blocked", ctx.blocked["reason"])
                if ctx.approval_pending:
                    return SessionOutcome("approval_pending", ctx.approval_pending.approval_id)
        except Cancelled:
            return SessionOutcome("cancelled", "cancelled by user")
        except PolicyViolation as e:
            return SessionOutcome("failed", f"{e.code}: {e}")
        except WorkerFailure as e:
            return SessionOutcome("failed", f"{e.code}: {e}")
        finally:
            rt.active_sessions[ctx.agent.agent_id] = max(0, rt.active_sessions.get(ctx.agent.agent_id, 1) - 1)
