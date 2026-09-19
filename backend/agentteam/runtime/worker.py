"""AgentRunner: one agent session = independent conversation state + tool loop through the gateway."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from ..config.loader import platform_policy_text
from ..contracts import TaskResult, TaskState
from ..providers.base import LLMRequest, LLMResponse, ProviderError
from ..providers.pricing import price_for
from .context import SessionContext
from .policy import Cancelled, PolicyViolation
from .tools import ToolGateway
from .delivery import verify_delivery, failures


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
- Original user attachments are read with read_input_file by exact name. They are not published artifacts and have no revision.
- If you cannot proceed, call report_blocker. If an action needs a human decision, call request_approval.
- Keep tool calls purposeful; there are hard limits on model calls, tool calls, messages and budget.
"""


def consecutive_no_tool_turns(previous: int, tool_calls: list) -> int:
    """A real tool turn breaks the no-tool streak; the run still has global limits."""
    return 0 if tool_calls else previous + 1


# The first tool a role needs when it has only narrated its intent. Names are offered only if the agent has them.
_FIRST_TOOLS = {
    "reviewer": ("read_artifact", "run_check", "submit_review", "finish_task"),
    "builder": ("workspace_write", "publish_artifact", "finish_task"),
    "researcher": ("web_fetch", "workspace_write", "publish_artifact", "finish_task"),
}


def no_tool_nudge(role: str, available: list[str], streak: int) -> str:
    """Smaller models announce a plan ("I will read the file…") and end the turn. Name the exact next call."""
    steps = [t for t in _FIRST_TOOLS.get(role, ()) if t in available]
    base = ("You ended without a tool call. If your work is done, call finish_task; if you are stuck, "
            "call report_blocker; otherwise continue with tools.")
    if not steps:
        return base
    text = f"{base} Text alone changes nothing: describing a step does not perform it. Your next message must be a tool call, starting with {steps[0]}."
    if len(steps) > 1:
        text += " Order: " + " → ".join(steps) + "."
    if streak >= 2:
        text += " This is the last reminder; another turn without a tool call ends this task unverified."
    return text


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
    if rt.run.inputs.delivery_requirements:
        lines.append('\n## Mandatory delivery contracts supplied by the requester\nThese apply independently of the master plan and model review. '
                     'The runtime checks final artifact bytes against these JSON Schemas and refuses completion on failure.\n' +
                     json.dumps([r.model_dump() for r in rt.run.inputs.delivery_requirements], ensure_ascii=False))
        lines.append("\nFor the readiness contract: `evidence_quote` is the exact English source quotation and must not be translated; `implemented` and `remaining` are separate Japanese summaries. Never copy an English evidence_quote into remaining.")
        lines.append("For a published artifact, run_check(kind=json_schema, artifact_id=..., revision=...) may omit args.schema; the gateway uses the exact persisted requester schema for that logical path. Do not hand-write a replacement schema.")
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
    if spec.output_paths == ["*"]:
        lines.append("\n## Output\nYou are the only agent on this request: no planner, no reviewer. Produce every deliverable the "
                     "request asks for, verify it yourself (run_check / sandbox_run where possible), publish each file with "
                     "publish_artifact (paths of your choice), then call finish_task stating what you verified and what you did not.")
    elif spec.output_paths:
        lines.append("\n## Output paths you must publish\n" + "\n".join(f"- {p}" for p in spec.output_paths))
    else:
        lines.append("\n## Output\nNo file outputs declared; deliver via submit_review / send_message as your role requires.")
    if ctx.agent.role == "reviewer":
        for dep in spec.depends_on:
            t = rt.tasks.get(dep)
            if t and t.spec.owner != ctx.agent.agent_id:
                lines.append(f"\n## Review target: task {dep} (owner {t.spec.owner})\nObjective: {t.spec.objective}\nAcceptance criteria to verify:")
                lines += [f"- {c.id} [{c.check_kind}]: {c.description}" for c in t.spec.acceptance]
                lines.append("Verify against the published revisions listed above. For run_check use artifact_id and revision; "
                             "path refers only to your own workspace, not the producer’s workspace. "
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
        lines.append("\n## User-provided inputs\nAttachment contents are included inline below. They are not "
                     "published artifacts or files in your workspace unless separately listed there. "
                     "Use read_input_file(name=...) to retrieve an original attachment again or beyond the inline excerpt. "
                     "Use the original inputs to check factual claims, including assumptions in the plan.")
        if inp.text:
            lines.append(inp.text[:20000])
        for u in inp.urls:
            lines.append(f"- URL: {u}")
        for f in inp.files:
            lines.append(f"\n### Attachment {f.get('name')}\n{str(f.get('content', ''))[:20000]}")
    # Human directions are durable events. Pass only received directions to a
    # newly started task session; the plan itself remains unchanged and auditable.
    instructions = [e for e in await rt.events.list(rt.run_id)
                    if e.type == "instruction.received" and e.payload.get("state") == "received"]
    if instructions:
        lines.append("\n## Human instructions received during this run")
        lines.append("Apply these directions to this task where relevant. They are user input, not acceptance criteria; do not claim that the plan was replanned.")
        for e in instructions[-20:]:
            lines.append(f"- #{e.seq} [{e.payload.get('kind', 'change')}] {e.payload.get('text', '')}")
    lines.append(f"\nRemaining budget: model calls {rt.config.limits.max_model_calls - rt.policy.usage.model_calls}, "
                 f"peer messages for this task {rt.config.limits.max_peer_messages_per_task - rt.policy.peer_messages.get(spec.id, 0)}, "
                 f"wall clock {int(rt.remaining_seconds())}s.")
    return "\n".join(lines)


async def auto_finish_if_outputs_published(ctx: SessionContext, reason: str) -> SessionOutcome | None:
    """If a task session ends without finish_task but every declared output path was published by this task,
    accept the work and record that the finish was inferred (weaker models often skip the final tool call)."""
    rt = ctx.rt
    if ctx.mode != "task" or ctx.task is None or ctx.agent.role == "reviewer" or not ctx.task.spec.output_paths:
        return None
    published = {m.logical_path: m for m in await rt.artifacts.list(rt.run_id, latest_only=True) if m.task_id == ctx.task.spec.id}
    missing = [p for p in ctx.task.spec.output_paths if p not in published and p != "*"]
    if missing or (ctx.task.spec.output_paths == ["*"] and not published):
        return None
    if failures(await verify_delivery(rt, task_id=ctx.task.spec.id, actor_id=ctx.agent.agent_id)):
        return None
    ctx.finished = TaskResult(summary=f"[auto-finished by runtime] all output paths published; agent ended without finish_task ({reason})",
                              unverified=["agent did not state what it verified"], published=[m.ref() for m in published.values()])
    await rt.events.append(rt.run_id, "task.updated", {"action": "auto_finish", "reason": reason, "published": list(published)},
                           actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=ctx.causation_id)
    return SessionOutcome("finished", ctx.finished.summary)


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
        is_cli = getattr(provider, "supports_sessions", False)
        attempts = 0
        while True:
            attempts += 1
            if is_cli:
                cap = min(rt.config.limits.max_session_cost_usd, max(0.05, rt.policy.remaining_budget()))
                res = rt.policy.reserve_amount(cap)
                req.metadata["max_budget_usd"] = cap
                req.metadata["timeout"] = max(30.0, rt.remaining_seconds() - 5)
            else:
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
            if is_cli:
                cost = rt.policy.settle_amount(res, float(getattr(resp, "cost_usd", 0.0) or 0.0), resp.usage)
            else:
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

    async def _compact_delivery_repair(self) -> None:
        """Drop an overlong failed-turn transcript before asking for a repair.

        Local models can spend an entire context window explaining a JSON
        Schema error instead of calling a tool. The source files and published
        revisions remain durable, so a short repair instruction is safer and
        more useful than replaying that explanation.
        """
        rt, ctx = self.rt, self.ctx
        latest = await rt.artifacts.list(rt.run_id, latest_only=True)
        target = next((m for m in latest if m.logical_path == "readiness.json"), None)
        revision = f" revision {target.revision}" if target else ""
        self.messages = [{"role": "user", "content": [{"type": "text", "text": (
            "前回の応答は長すぎてツール呼出し前に上限へ達しました。説明は禁止し、直ちにツールを使ってください。"
            f"readiness.json{revision}をread_artifactで読み、必要ならPRODUCTION_PLAN.mdをread_input_fileで読み直してください。"
            "Schema検査に失敗したフィールドだけをworkspace_writeで修正し、publish_artifact、run_check(kind=json_schema)、"
            "finish_taskの順で完了してください。production_readyは資料どおり必ずfalseのままにし、remainingを空にしたり、"
            "資料にないverified/next_stepsフィールドを追加したりしないでください。"
            "要約欄では英語原語や「アクター監査」を使わず、staleは「陳腐化」、artifactは「アーティファクト」、"
            "actor-scopedは「操作主体ごとの」、drillは「ドリル」、advisoryは「アドバイザリ」としてください。"
            "Dataのimplementedは、例えば「ageによる暗号化、スナップショット復元、再開可能なランの検証を確認しました。」"
            "のように、日本語の文中へageと「再開可能」を同時に含めてください。"
            "Audit / monitoringのimplementedは、例えば「監査者が独立収集のカーソルを用い、メトリクスと復旧を確認しました。」"
            "のように、「監査者」と「カーソル」を同時に含めてください。"
            "検査結果に does not match と出た必須語は削除せず、同じフィールドへ上記の正確な語を追加してください。"
            "summaryは120文字以内、各implemented/remainingは40〜120文字の短い日本語一文に圧縮してください。"
            "Identityのtoken revocationは「トークン失効」または「トークン取消」、Latencyは「レイテンシ」または「遅延」、"
            "acceptance thresholdは「受入閾値」と書き、「リバイス」「ラテンシー」「収容閾値」などの類推語は禁止です。"
        )}]}]
        self.nudges = 0

    async def run(self, user_message: str) -> SessionOutcome:
        rt, ctx = self.rt, self.ctx
        system = build_system_prompt(ctx)
        self.messages = [{"role": "user", "content": [{"type": "text", "text": user_message}]}]
        tools = self.gateway.specs()
        rt.active_sessions[ctx.agent.agent_id] = rt.active_sessions.get(ctx.agent.agent_id, 0) + 1
        try:
            provider = rt.providers.adapter(ctx.agent.connection_id)
            if getattr(provider, "supports_sessions", False):
                return await self._run_cli_session(provider, system, user_message)
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
                self.nudges = consecutive_no_tool_turns(self.nudges, resp.tool_calls)
                if not resp.tool_calls:
                    if ctx.mode == "reply" and ctx.replied:
                        return SessionOutcome("finished", "replied")
                    if resp.stop_reason == "max_tokens":
                        if ctx.mode == "task" and rt.run.inputs.delivery_requirements:
                            await self._compact_delivery_repair()
                            continue
                        nudge = "Your previous output hit the token limit. Continue with tool calls; keep text short."
                    else:
                        nudge = no_tool_nudge(ctx.agent.role, [t.name for t in tools], self.nudges)
                    if self.nudges > 2:
                        auto = await auto_finish_if_outputs_published(ctx, "ended three consecutive turns without finish_task")
                        return auto or SessionOutcome("ended", "agent ended its turn repeatedly without finish_task")
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


    async def _run_cli_session(self, provider, system: str, user_message: str) -> SessionOutcome:
        """Claude Code owns the loop; our tools are served through the session broker. One CLI process per attempt,
        plus at most one continuation if the agent ended without finish_task."""
        from .session_broker import get_broker

        rt, ctx = self.rt, self.ctx
        broker = await get_broker()
        token = broker.register(self.gateway)
        prompt = user_message
        try:
            for round_no in range(2):
                rt.policy.check_cancel()
                if rt.remaining_seconds() <= 0:
                    return SessionOutcome("failed", "timeout: run wall-clock limit reached")
                cap = min(rt.config.limits.max_session_cost_usd, max(0.05, rt.policy.remaining_budget()))
                try:
                    res_v = rt.policy.reserve_amount(cap)
                except PolicyViolation as e:
                    return SessionOutcome("failed", f"{e.code}: {e}")
                t0 = time.monotonic()
                result = await provider.run_session(
                    system=system, prompt=prompt, gateway_url=broker.url(token), tool_names=[t.name for t in self.gateway.specs()],
                    model=ctx.agent.model, effort=ctx.agent.effort, max_turns=rt.config.limits.max_session_turns,
                    max_budget_usd=cap, timeout=max(30.0, rt.remaining_seconds() - 5), cancel_event=rt.policy.cancel_event,
                    cwd=str(ctx.workspace) if ctx.workspace else None)
                cost = rt.policy.settle_amount(res_v, result.cost_usd, result.usage, extra_calls=max(0, result.num_turns - 1))
                await rt.events.append(rt.run_id, "model.called",
                                       {"connection_id": ctx.agent.connection_id, "driver": ctx.agent.driver, "provider_kind": "real",
                                        "model_requested": ctx.agent.model, "model_reported": result.model_reported or "unknown",
                                        "models": {k: {"costUSD": v.get("costUSD"), "inputTokens": v.get("inputTokens"), "outputTokens": v.get("outputTokens")}
                                                   for k, v in (result.models or {}).items()},
                                        "request_id": result.session_id, "stop_reason": result.terminal_reason or "end_turn",
                                        "usage": {"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens,
                                                  "cache_read_tokens": result.usage.cache_read_tokens, "cache_write_tokens": result.usage.cache_write_tokens},
                                        "cost_usd": round(cost, 6), "latency_ms": int((time.monotonic() - t0) * 1000),
                                        "text_preview": (result.text or "")[:600], "num_turns": result.num_turns,
                                        "permission_denials": result.permission_denials[:10], "cli_session": True,
                                        "mode": ctx.mode, "attempt": ctx.attempt, "round": round_no + 1,
                                        "error": rt.redactor.text(result.error) if result.error else None},
                                       actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=ctx.causation_id)
                await rt.persist_usage()
                if result.terminal_reason == "cancelled" or rt.policy.cancelled:
                    return SessionOutcome("cancelled", "cancelled by user")
                if ctx.finished:
                    return SessionOutcome("finished", ctx.finished.summary)
                if ctx.blocked:
                    return SessionOutcome("blocked", ctx.blocked["reason"])
                if ctx.approval_pending:
                    return SessionOutcome("approval_pending", ctx.approval_pending.approval_id)
                if ctx.mode == "reply" and ctx.replied:
                    return SessionOutcome("finished", "replied")
                if not result.ok and "timeout" in (result.error or ""):
                    return SessionOutcome("failed", f"timeout: {result.error}")
                budget_hit = "max_budget" in (result.error or "") or "budget" in (result.terminal_reason or "")
                if not result.ok and not budget_hit and result.terminal_reason not in ("completed", "max_turns", None):
                    return SessionOutcome("failed", f"provider_cli: {result.error}")
                if budget_hit and round_no == 1:
                    return SessionOutcome("failed", f"provider_cli: session budget cap hit twice ({result.error})")
                prompt = (user_message + "\n\n[runtime] Your previous session ended without calling finish_task"
                          + (" because it hit its per-session budget cap; work more economically (fewer, smaller reads)" if budget_hit else "")
                          + (f" (reason: {result.terminal_reason})" if result.terminal_reason else "")
                          + ". Published artifacts and delivered messages are kept. Continue from the current state: check "
                            "list_artifacts / read_messages, finish remaining work, then call finish_task (or report_blocker).")
            auto = await auto_finish_if_outputs_published(ctx, "cli session ended twice without finish_task")
            return auto or SessionOutcome("ended", "agent ended its session twice without finish_task")
        except Cancelled:
            return SessionOutcome("cancelled", "cancelled by user")
        except PolicyViolation as e:
            return SessionOutcome("failed", f"{e.code}: {e}")
        finally:
            broker.unregister(token)
