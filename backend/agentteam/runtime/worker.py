"""AgentRunner: one agent session = independent conversation state + tool loop through the gateway."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from ..config.loader import platform_policy_text
from ..config.voice import conversation_voice, voice_instructions
from ..contracts import TaskResult, TaskState
from ..providers.base import LLMRequest, LLMResponse, ProviderError
from ..providers.pricing import price_for
from .context import SessionContext
from .policy import Cancelled, PolicyViolation
from .tools import ToolGateway
from .delivery import verify_delivery, failures, unpublished_workspace_changes


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
- For tasks with file outputs, deliverables exist only as published artifacts: write files with workspace_write, then publish_artifact. Chat text is not a deliverable.
- Finish your assigned role's work, then call finish_task. Reviewers submit every required review first; producers publish their declared outputs. Do not narrate; act with tools.
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


_DOCUMENT_RECOVERY_TOOLS = frozenset({
    "read_skill", "finish_task", "read_input_file", "workspace_read", "workspace_write",
    "workspace_list", "run_check", "send_message", "read_messages", "read_artifact",
    "list_artifacts", "publish_artifact", "submit_review", "report_blocker",
})


def supports_document_recovery(tool_names: list[str], calls: list[dict[str, Any]] | None = None) -> bool:
    """Fail closed for tools whose external results cannot be reconstructed here."""
    return (bool(tool_names) and set(tool_names) <= _DOCUMENT_RECOVERY_TOOLS
            and all(call.get("tool") in _DOCUMENT_RECOVERY_TOOLS
                    and not (call.get("tool") == "run_check" and call.get("args", {}).get("kind") == "command")
                    for call in (calls or [])))


# The first tool a role needs when it has only narrated its intent. Names are offered only if the agent has them.
_FIRST_TOOLS = {
    "reviewer": ("read_artifact", "run_check", "submit_review", "finish_task"),
    "builder": ("workspace_write_json", "workspace_write", "publish_artifact", "finish_task"),
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


async def document_reviewer_tool_nudge(ctx: SessionContext, available: list[str], streak: int) -> str:
    """Give a stalled document reviewer an executable first step.

    Local models sometimes treat an attachment name as an artifact and spend
    their recovery turns rereading the source instead of submitting the review.
    The requester-owned contract is already persisted, so point the reviewer
    at the exact published revision before asking it to do anything else.
    """
    refs: list[str] = []
    if ctx.task:
        for task_id in ctx.task.spec.depends_on:
            for artifact in await ctx.rt.artifacts.list(ctx.rt.run_id, latest_only=True):
                if artifact.task_id == task_id:
                    refs.append(f"{artifact.artifact_id}@r{artifact.revision}")
    refs_text = ", ".join(dict.fromkeys(refs)) or "the published target artifact"
    base = (
        "This is a document review. Your previous turn ended without a tool call. "
        "Your next message MUST call run_check first, using the exact persisted requester contract "
        "{kind: json_schema, artifact_id: <published target>, revision: <number>} with args omitted. "
        f"Current target revision(s): {refs_text}. Do not call read_artifact on PRODUCTION_PLAN.md or any "
        "other source attachment; attachments are read only with read_input_file. After a passing check, "
        "call submit_review with all criteria, send the required finding/handoff, then call finish_task. "
        "Do not narrate or reread the whole source."
    )
    if streak >= 2:
        base += " This is the last reminder; another turn without a tool call leaves the review unverified."
    return base


def build_system_prompt(ctx: SessionContext) -> str:
    agent = ctx.agent
    parts = [platform_policy_text().strip(), "\n---\n", agent.system_prompt.strip(), "\n---\n", RUNTIME_RULES.strip()]
    parts.append(voice_instructions(conversation_voice(agent.role, agent.speech_style)))
    if agent.skills:
        parts.append("\n\n## Enabled skills (call read_skill to load the body only when relevant)\n" + "\n".join(
            f"- {s['name']}: {s['description']}" for s in agent.skills))
    parts.append(f"\n\n## Identity\nYou are agent `{agent.agent_id}` (role: {agent.role}). Team language: {ctx.rt.config.defaults.language}.")
    if agent.display_name or agent.specialty:
        parts.append(f"\nYour personal name: {agent.display_name or agent.agent_id}. Your task-specific expertise: {agent.specialty or agent.role}. "
                     "Speak in your own configured voice. This expertise is an assigned AI perspective, not proof of professional credentials.")
    parts.append("\n\n## Actual team for this run\n" + "\n".join(
        f"- {a.agent_id}: {a.display_name or a.agent_id}; specialty: {a.specialty or a.role}"
        for a in ctx.rt.enabled_agents())
        + "\nUse these personal names in conversation and these IDs for message recipients. "
        "Do not announce invented teammates or substitute a different roster. Discuss changes as proposals, not existing members.")
    parts.append("\n\n## Output language\nUse the language explicitly requested by the user for all original prose in deliverables; otherwise use the team language. Do not drift into another language mid-sentence. Keep verbatim source quotations, identifiers, product names and code unchanged unless the user explicitly requests their transformation. User-specific restrictions on foreign wording or abbreviations take priority over defaults. Before publishing or approving, read the saved artifact and check its prose language separately from format checks. If you cannot verify it, report unverified rather than pass.")
    if ctx.rt.run.inputs.workflow == "document" and agent.role == "reviewer":
        parts.append("\n\n## Document review only\nYou do not write or publish a replacement document. Start by running the requester-owned json_schema check on the published readiness.json revision listed in the review target; call run_check before reading additional source text. PRODUCTION_PLAN.md and other supplied files are input attachments, not artifacts: never pass their names to read_artifact, and use read_input_file only when source text is needed. Independently run the requester-owned json_schema check for every current target artifact before submit_review. Use exactly {kind: json_schema, artifact_id: <id>, revision: <number>} and omit args; the runtime rejects a review without a passing check. The evidence_quote field is required to remain the exact English Remaining acceptance work cell; Japanese belongs only in implemented/remaining summaries. Do not call an English quote a Japanese translation merely because the summaries are Japanese. This request produces an evidence-based current-status assessment: production_ready=false, L3未達, and remaining unverified acceptance conditions are expected accurate results. Do not fail document_request, document_contract, or document_accuracy merely because production is not ready or residual conditions remain. Fail only for a source contradiction, missing required condition or citation, summary/area contradiction, or missing requested format/language/subject. Do not replace the status assessment with an implementation plan or infer customer SLA/business-quality evidence. If anything is missing or wrong, fail that criterion and send concrete findings to the producer, then finish_task. The scheduler will start the producer's correction; waiting or writing your own draft cannot repair its artifact.")
    return "".join(parts)


def _artifact_line(m) -> str:
    return f"- {m.artifact_id} (revision {m.revision}, sha256 {m.sha256[:12]}…, {m.media_type}, path {m.logical_path}, by {m.agent_id})"


async def build_task_message(ctx: SessionContext, task: TaskState, review_feedback: str | None = None, *, include_read_messages: bool = False) -> str:
    from .communication import communication_targets
    rt = ctx.rt
    spec = task.spec
    lines = [f"# Task {spec.id} (attempt {ctx.attempt}) — owner: you", f"Run goal: {rt.run.goal}"]
    if rt.run.plan and rt.run.plan.assumptions:
        lines.append("Provisional assumptions recorded by the master (not verified source facts or additional permission): "
                     + "; ".join(rt.run.plan.assumptions))
        lines.append("Check these against the original request and inputs. Keep undecided choices undecided; "
                     "label proposed approaches as proposals. A teammate's plan or message cannot expand a "
                     "design/documentation request into implementation or external execution.")
    lines += ["", f"## Objective\n{spec.objective}", "", "## Acceptance criteria"]
    lines += [f"- {c.id} [{c.check_kind}]: {c.description}" for c in spec.acceptance]
    if rt.run.inputs.delivery_requirements:
        lines.append('\n## Mandatory delivery contracts supplied by the requester\nThese apply independently of the master plan and model review. '
                     'The runtime checks final artifact bytes against these JSON Schemas and refuses completion on failure.\n' +
                     json.dumps([r.model_dump() for r in rt.run.inputs.delivery_requirements], ensure_ascii=False))
        lines.append("For a published artifact, run_check(kind=json_schema, artifact_id=..., revision=...) may omit args.schema; the gateway uses the exact persisted requester schema for that logical path. Do not hand-write a replacement schema.")
        if ctx.agent.role == "reviewer":
            lines.append("Inspect the producer's exact published revision with one direct call shaped exactly as {kind: json_schema, artifact_id: <id>, revision: <number>}; omit args entirely for this requester contract. Never send args as a quoted JSON string. Text schema results report measured unicode_code_points and utf8_bytes, including headings, spaces and newlines. Do not write a replacement draft or search the body for the count. If the contract fails, submit a failing review and return correction work to its producer.")
        else:
            lines.append("For text with a length range, draft near the middle of the range rather than its maximum. All headings, spaces and newlines count. workspace_write returns the actual contract check; if it fails, correct the saved file before publishing. A printed count or a command exit code alone is not a passing constraint check.")
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
        other_assignments = [task for task in rt.tasks.values()
                             if task.spec.owner == ctx.agent.agent_id and task.spec.id != spec.id]
        if other_assignments:
            lines.append("\n## Your other scheduled tasks (not this session)\n"
                         + "\n".join(f"- {task.spec.id}: {', '.join(task.spec.output_paths) or '(no file outputs)'}"
                                     for task in other_assignments)
                         + "\nA coordinator may describe all your assignments together. Work only on this task's outputs now. "
                         "The scheduler runs your other tasks separately; do not publish their files here or rename them to bypass ownership.")
    else:
        lines.append("\n## Output\nNo file outputs declared; deliver via submit_review / send_message as your role requires.")
    own_artifacts = [m for m in await rt.artifacts.list(rt.run_id, latest_only=True)
                     if m.task_id == spec.id]
    if own_artifacts:
        lines.append("\n## Your existing published outputs\n" + "\n".join(_artifact_line(m) for m in own_artifacts))
        lines.append("These files already exist. Inspect them before changing or publishing again; "
                     "compare the revisions cited in earlier reviews with these current revisions. "
                     "Do not replay completed work solely because this session restarted.")
    changed = await unpublished_workspace_changes(ctx)
    if changed:
        lines.append("\n## Saved edits not yet published\n" + "\n".join(changed)
                     + "\nRead these files with workspace_read before editing. The published revisions above "
                     "do not contain these saved changes. Preserve and inspect the saved draft; publish it when ready, "
                     "then deliver its current references. A handoff alone does not publish a file.")
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
        if ctx.agent.role == 'reviewer':
            lines.append("\n## Historical review summary — not evidence about the current revision\n"
                         + task.result.summary
                         + "\nThis describes an earlier attempt. Do not carry its verdict or wording into the new review. "
                         "For each earlier finding, locate the relevant passage in the current published revision and "
                         "determine whether it was fixed, remains wrong, or changed into a different problem. "
                         "Do not claim a statement is absent when the current text includes it. Cite the actual "
                         "current section and short exact wording; judge its meaning against the original sources. "
                         "Also check remaining request requirements, not only the previous findings.")
        else:
            lines.append(f"\n## Your previous attempt\n{task.result.summary}")
    # The scheduler's feedback queue is process-local and consumed on start.
    # Resume must also recover findings after a correction session was interrupted.
    if not review_feedback and task.review and any(r.status == "fail" for r in task.review.results):
        review_feedback = "\n".join(
            f"- {r.acceptance_id} [{r.status}]: {r.note or r.evidence}"
            for r in task.review.results if r.status != "pass"
        )
        if task.review.summary:
            review_feedback += f"\nSummary: {task.review.summary}"
        refs = task.review.target_artifacts
        if refs:
            review_feedback += "\nPreviously reviewed revisions: " + ", ".join(
                f"{r.artifact_id}@r{r.revision} sha256={r.sha256}" for r in refs
            )
    if review_feedback:
        lines.append(f"\n## Review feedback on your previous revision (fix these, publish new revisions)\n{review_feedback}")
    targets = communication_targets(ctx)
    if targets:
        missing = sorted(set(targets) - ctx.communicated_to)
        if missing:
            lines.append("\n## Required team communication\nBefore finish_task, use send_message to each of: " + ", ".join(missing) + ". Use purpose handoff, finding or decision, task_id=" + spec.id + ". State the actual result, remaining uncertainty and what the recipient should do next; reference published artifact revisions. A task cannot finish without these deliveries. Read your inbox and answer relevant questions; do not invent conversation.")
        else:
            lines.append("\n## Required team communication\nRequired handoffs are already delivered for the current work. Do not resend unchanged findings under a different purpose. Once the requested work is ready, call finish_task; publication and completion checks still apply. Publishing a new revision or submitting a new review requires a fresh handoff.")
    msgs = await rt.bus.read(ctx.agent.agent_id, None, unread_only=not include_read_messages)
    if include_read_messages:
        msgs = msgs[-20:]
    if msgs:
        await rt.bus.mark_read([m for m in msgs if not m.read_at], ctx.agent.agent_id)
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
        lines.append("Apply relevant requested corrections to this task, including issues missing from the earlier review. "
                     "They can refine the requested work without rewriting the stored plan. Preserve the original request, "
                     "mandatory delivery contracts and execution permissions; do not claim the plan was replanned or "
                     "a requirement was satisfied merely because a direction was received. Check factual corrections "
                     "against the actual artifacts and sources before changing or approving them.")
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
    from .communication import communication_targets
    if set(communication_targets(ctx)) - ctx.communicated_to:
        return None
    published = {m.logical_path: m for m in await rt.artifacts.list(rt.run_id, latest_only=True) if m.task_id == ctx.task.spec.id}
    missing = [p for p in ctx.task.spec.output_paths if p not in published and p != "*"]
    if missing or (ctx.task.spec.output_paths == ["*"] and not published):
        return None
    if await unpublished_workspace_changes(ctx):
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
            # Planning, coordination, reports and replans call the model outside the Scheduler loop, so the
            # run's wall clock is enforced here for every call, not only between task sessions.
            remaining = rt.remaining_seconds()
            if remaining <= 0:
                raise WorkerFailure("timeout", "run wall-clock limit reached")
            if is_cli:
                cap = min(rt.config.limits.max_session_cost_usd, max(0.05, rt.policy.remaining_budget()))
                res = rt.policy.reserve_amount(cap)
                req.metadata["max_budget_usd"] = cap
                req.metadata["timeout"] = max(1.0, remaining - 5)
            else:
                res = rt.policy.reserve_model_call(price, est_in, req.max_tokens)
            t0 = time.monotonic()
            deadline = asyncio.timeout(remaining)
            try:
                async with deadline:
                    resp = await provider.complete(req)
            except TimeoutError:
                if not deadline.expired():
                    raise
                rt.policy.release(res)
                await rt.events.append(rt.run_id, "model.failed",
                                       {"connection_id": ctx.agent.connection_id, "model_requested": ctx.agent.model,
                                        "kind": "timeout", "status": None, "message": "run wall-clock limit reached during a model call",
                                        "retryable": False, "attempt": attempts},
                                       actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=causation_id)
                raise WorkerFailure("timeout", "run wall-clock limit reached during a model call")
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

    async def _compact_delivery_repair(self, reason: str = "reached the output limit without calling a tool") -> None:
        """Rebuild from durable task/source/review state, never from a fixed task template."""
        ctx = self.ctx
        if ctx.task is None:
            return
        task = await self.rt.runs.get_task(self.rt.run_id, ctx.task.spec.id)
        task = task or ctx.task
        feedback = task.review.model_dump_json() if task.review else None
        message = await build_task_message(ctx, task, feedback, include_read_messages=True)
        sent = [m for m in await self.rt.runs.list_messages(self.rt.run_id)
                if m.from_agent_id == ctx.agent.agent_id and m.task_id == task.spec.id]
        if sent:
            message += "\n## Messages already delivered (do not resend unchanged)\n" + "\n".join(
                f"- {m.message_id} to={m.to_agent_id} purpose={m.purpose}: {m.text}" for m in sent[-20:])
        if ctx.reviews:
            from .communication import communication_targets
            missing = sorted(set(communication_targets(ctx)) - ctx.communicated_to)
            message += ("\n## Reviews already submitted in this session\n"
                        + json.dumps([r.model_dump() for r in ctx.reviews], ensure_ascii=False)
                        + "\nDo not submit these again just to finish. A finding sent before the latest review "
                        "does not satisfy its handoff. ")
            if missing:
                message += ("Next call send_message with the recorded verdict and artifact references to: "
                            + ", ".join(missing) + "; then finish_task. Do not wait for corrected files.")
            else:
                message += "Required review handoffs are delivered. Call finish_task; its existing guards still apply."
        checks = await verify_delivery(self.rt, task_id=task.spec.id, record=False)
        message += ("\nYour previous response " + reason + ". "
                    "Use tools now; keep explanations short. Read existing published revisions before editing. "
                    "Do not reload every full document at once: read the current output first and use "
                    "read_artifact start_char/max_chars for needed portions of supporting artifacts, pinning their revision. "
                    "Leave context space for writing corrections. Partial reading alone cannot justify a full review. "
                    "For a long existing draft, workspace_write edit can replace one exact passage using the current "
                    "whole-draft SHA instead of generating the entire file again. Publish after saving corrections. "
                    "Follow your assigned role: reviewers check and submit_review; producers revise only their own outputs. "
                    "Use workspace_list/workspace_read to recover saved drafts; an interrupted response was not a saved edit. "
                    "Do not repeat external actions merely because earlier tool responses are no longer in this conversation. "
                    "Do not change requester requirements or claim checks that were not run.\n"
                    + json.dumps(checks, ensure_ascii=False))
        self.messages = [{"role": "user", "content": [{"type": "text", "text": message}]}]

    async def _can_compact_task(self, tools) -> bool:
        if self.rt.run.inputs.delivery_requirements:
            return True  # Preserve the existing schema-based recovery path.
        calls = [e.payload for e in await self.rt.events.list(self.rt.run_id)
                 if e.type == "tool.called" and e.task_id == self.ctx.task_id]
        return supports_document_recovery([t.name for t in tools], calls)

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
                from .communication import complete_delivered_coordination
                if await complete_delivered_coordination(ctx):
                    return SessionOutcome("finished", ctx.finished.summary)
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
                    # An empty completed response is not more work. Reuse the
                    # existing delivery/handoff guards before spending another
                    # model call merely to request a finish acknowledgement.
                    # Truncated output and substantive text still get nudged.
                    if resp.stop_reason == "end_turn" and not (resp.text or "").strip():
                        auto = await auto_finish_if_outputs_published(ctx, "empty completed response after published outputs and required handoffs")
                        if auto:
                            return auto
                    if resp.stop_reason == "max_tokens":
                        if (ctx.mode == "task" and self.nudges <= 2
                                and await self._can_compact_task(tools)):
                            await self._compact_delivery_repair()
                            continue
                        nudge = "Your previous output hit the token limit. Continue with tool calls; keep text short."
                    else:
                        if (resp.stop_reason == "end_turn" and ctx.mode == "task" and ctx.agent.role == "reviewer"
                                and ctx.reviews and self.nudges <= 2 and await self._can_compact_task(tools)):
                            await self._compact_delivery_repair("ended without a tool after submitting review findings")
                            continue
                        if (ctx.mode == "task" and ctx.agent.role == "reviewer"
                                and rt.run.inputs.workflow == "document"):
                            nudge = await document_reviewer_tool_nudge(
                                ctx, [t.name for t in tools], self.nudges)
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
                    max_budget_usd=cap, timeout=max(1.0, rt.remaining_seconds() - 5), cancel_event=rt.policy.cancel_event,
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
