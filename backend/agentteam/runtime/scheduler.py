"""TaskScheduler: DAG execution, review/revision loop, peer reply sessions, master exception handling."""
from __future__ import annotations

import asyncio
from typing import Any

from ..contracts import (DONE_FOR_DEPENDENTS, Message, Review, RunStatus, TaskSpec, TaskState, TaskStatus,
                         TERMINAL_TASK_STATES)
from ..ids import now_iso
from .context import RunRuntime, SessionContext
from .planner import handle_exception, milestone_replan
from .worker import AgentRunner, SessionOutcome, build_task_message

REPLY_TOOLS = ["read_messages", "send_message", "read_artifact", "list_artifacts", "web_fetch", "web_search", "read_skill", "finish_task"]


class Scheduler:
    def __init__(self, rt: RunRuntime):
        self.rt = rt
        rt.scheduler = self
        self._running: dict[str, asyncio.Task] = {}
        self._replies: set[asyncio.Task] = set()
        self._feedback: dict[str, str] = {}
        self._exception_handled: dict[str, int] = {}
        self._pause_for_approval = False
        self._fatal: str | None = None
        self._replans = 0
        rt.bus.on_deliver(self._on_message)

    # ------------------------------------------------------------ setup
    async def init_from_plan(self) -> None:
        plan = self.rt.run.plan
        assert plan is not None
        for spec in plan.tasks:
            t = TaskState(run_id=self.rt.run_id, spec=spec, status=TaskStatus.queued, updated_at=now_iso())
            await self.rt.save_task(t)
            await self.rt.events.append(self.rt.run_id, "task.created", {"owner": spec.owner, "objective": spec.objective,
                                                                          "depends_on": spec.depends_on,
                                                                          "output_paths": spec.output_paths,
                                                                          "acceptance": [c.model_dump() for c in spec.acceptance]},
                                        task_id=spec.id)

    def role_of(self, agent_id: str) -> str:
        a = self.rt.agents.get(agent_id)
        return a.role if a else "unknown"

    def is_review_task(self, t: TaskState) -> bool:
        return self.role_of(t.spec.owner) == "reviewer" and bool(t.spec.depends_on)

    def review_tasks_for(self, task_id: str, *, pending_only: bool = False) -> list[TaskState]:
        out = [t for t in self.rt.tasks.values() if self.is_review_task(t) and task_id in t.spec.depends_on]
        if pending_only:
            out = [t for t in out if t.status not in TERMINAL_TASK_STATES]
        return out

    def _deps_state(self, t: TaskState) -> str:
        """'ready' | 'wait' | 'dead'"""
        for d in t.spec.depends_on:
            dep = self.rt.tasks.get(d)
            if dep is None:
                return "dead"
            if self.is_review_task(t) and self.role_of(dep.spec.owner) != "reviewer":
                # review targets are reviewable when finished (review_pending) or already accepted (e.g. a reviewer
                # task added at a milestone for work that was accepted without review)
                if dep.status in (TaskStatus.review_pending, TaskStatus.accepted):
                    continue
                if dep.status in (TaskStatus.failed, TaskStatus.cancelled, TaskStatus.partial):
                    return "dead"
                return "wait"
            if dep.status in DONE_FOR_DEPENDENTS:
                continue
            if dep.status in (TaskStatus.failed, TaskStatus.cancelled):
                return "dead"
            return "wait"
        return "ready"

    async def _set(self, t: TaskState, status: TaskStatus, event: str | None = None, payload: dict[str, Any] | None = None,
                   causation_id: str | None = None) -> None:
        t.status = status
        await self.rt.save_task(t)
        if event:
            await self.rt.events.append(self.rt.run_id, event, payload or {}, task_id=t.spec.id, causation_id=causation_id)

    # ------------------------------------------------------------ master tools
    async def add_task(self, spec: TaskSpec, causation_id: str | None = None) -> str | None:
        rt = self.rt
        if spec.id in rt.tasks:
            return f"REJECTED: task {spec.id} already exists"
        if len(rt.tasks) >= rt.config.limits.max_tasks:
            return f"REJECTED: max_tasks {rt.config.limits.max_tasks} reached"
        owner = rt.agents.get(spec.owner)
        if owner is None or not owner.enabled:
            return f"REJECTED: owner {spec.owner} is not an enabled agent"
        if owner.role == "reviewer" and not spec.depends_on:
            return "REJECTED: a reviewer task must depend on the production task it reviews"
        if rt.config.defaults.require_independent_review and owner.role in ("master", "reporter"):
            return "REJECTED: assign production to a builder or researcher; master/reporter do not own deliverables"
        for d in spec.depends_on:
            if d not in rt.tasks:
                return f"REJECTED: unknown dependency {d}"
        for other in rt.tasks.values():
            for p in spec.output_paths:
                if p in other.spec.output_paths:
                    return f"REJECTED: output path {p} already produced by {other.spec.id}"
        if owner.role != "reviewer" and not spec.output_paths:
            return "REJECTED: a non-reviewer task needs output_paths"
        t = TaskState(run_id=rt.run_id, spec=spec, status=TaskStatus.queued, updated_at=now_iso())
        await rt.save_task(t)
        if rt.run.plan is not None:
            rt.run.plan.tasks.append(spec)
            if spec.owner not in rt.run.plan.agents:
                rt.run.plan.agents.append(spec.owner)
            await rt.runs.update_run(rt.run_id, plan=rt.run.plan)
        await rt.events.append(rt.run_id, "task.created", {"owner": spec.owner, "objective": spec.objective, "depends_on": spec.depends_on,
                                                           "output_paths": spec.output_paths, "created_by": "master",
                                                           "acceptance": [c.model_dump() for c in spec.acceptance]},
                               actor_id="master", actor_kind="agent", task_id=spec.id, causation_id=causation_id)
        return None

    async def decide(self, task_id: str, action: str, note: str, causation_id: str | None = None) -> str | None:
        t = self.rt.tasks.get(task_id)
        if t is None:
            return f"REJECTED: unknown task {task_id}"
        if t.status in (TaskStatus.running, TaskStatus.waiting):
            return f"REJECTED: task {task_id} is running"
        if action == "retry":
            if t.status in (TaskStatus.accepted,):
                return "REJECTED: task already accepted"
            t.blocked_reason = None
            await self._set(t, TaskStatus.queued, "task.updated", {"action": "retry", "note": note, "by": "master"}, causation_id)
        elif action == "accept_partial":
            await self._set(t, TaskStatus.partial, "task.partial", {"reason": "master accepted partial result", "note": note}, causation_id)
        elif action == "cancel":
            await self._set(t, TaskStatus.cancelled, "task.cancelled", {"reason": "cancelled by master", "note": note}, causation_id)
        else:
            return f"REJECTED: unknown action {action}"
        return None

    # ------------------------------------------------------------ peer replies
    async def _on_message(self, m: Message) -> None:
        rt = self.rt
        if m.purpose != "question":
            return
        if rt.active_sessions.get(m.to_agent_id, 0) > 0:
            return  # the running session will be nudged to read its mailbox
        agent = rt.agents.get(m.to_agent_id)
        if agent is None or not agent.enabled or rt.policy.cancelled:
            return
        task = asyncio.create_task(self._reply_session(m))
        self._replies.add(task)
        task.add_done_callback(self._replies.discard)

    async def _reply_session(self, m: Message) -> None:
        rt = self.rt
        agent = rt.agents[m.to_agent_id]
        tools = [t for t in REPLY_TOOLS if t in agent.tools]
        ctx = SessionContext(rt=rt, agent=agent, mode="reply", task=rt.tasks.get(m.task_id), attempt=1, tools=tools,
                             causation_id=f"{rt.run_id}:{m.seq}")
        ctx.task = None  # replies have no workspace; keep task_id via message
        owned = rt.owned_tasks(agent.agent_id)
        published = [a for a in await rt.artifacts.list(rt.run_id, latest_only=True) if a.agent_id == agent.agent_id]
        refs = ", ".join(f"{r.artifact_id}@r{r.revision}" for r in m.artifact_refs) or "-"
        text = (f"# Question from {m.from_agent_id} about task {m.task_id}\n[{m.message_id}] purpose={m.purpose} artifacts={refs}\n{m.text}\n\n"
                f"Your tasks: " + (", ".join(f"{t.spec.id} ({t.status}): {t.spec.objective}" for t in owned) or "none") + "\n"
                f"Your published artifacts: " + (", ".join(f"{a.artifact_id}@r{a.revision}" for a in published) or "none") + "\n\n"
                f"Answer from what you actually know or can read (read_artifact). Reply with send_message(to='{m.from_agent_id}', "
                f"task_id='{m.task_id}', purpose='answer', reply_to='{m.message_id}'), then call finish_task. If you do not know, say so.")
        await rt.events.append(rt.run_id, "task.started", {"mode": "reply", "in_reply_to": m.message_id}, actor_id=agent.agent_id,
                               actor_kind="agent", task_id=m.task_id, causation_id=ctx.causation_id)
        outcome = await AgentRunner(ctx).run(text)
        await rt.events.append(rt.run_id, "task.updated", {"mode": "reply", "outcome": outcome.kind, "detail": outcome.detail[:500]},
                               actor_id=agent.agent_id, actor_kind="agent", task_id=m.task_id, causation_id=ctx.causation_id)

    # ------------------------------------------------------------ task sessions
    async def _run_task(self, t: TaskState) -> tuple[str, SessionContext, SessionOutcome]:
        rt = self.rt
        agent = rt.agents[t.spec.owner]
        ctx = SessionContext(rt=rt, agent=agent, mode="task", task=t, attempt=t.attempt, tools=agent.tools)
        user = await build_task_message(ctx, t, review_feedback=self._feedback.pop(t.spec.id, None))
        outcome = await AgentRunner(ctx).run(user)
        return t.spec.id, ctx, outcome

    async def _start(self, t: TaskState) -> None:
        t.attempt += 1
        await self._set(t, TaskStatus.running, "task.started", {"attempt": t.attempt, "owner": t.spec.owner})
        self._running[t.spec.id] = asyncio.create_task(self._run_task(t))

    async def _handle(self, task_id: str, ctx: SessionContext, outcome: SessionOutcome) -> None:
        rt = self.rt
        t = rt.tasks[task_id]
        kind = outcome.kind
        if kind == "finished":
            t.result = ctx.finished
            if self.is_review_task(t) and ctx.reviews:
                await self._set(t, TaskStatus.accepted, "task.accepted", {"attempt": t.attempt, "summary": ctx.finished.summary if ctx.finished else "",
                                                                          "reviewed": [r.target_task_id for r in ctx.reviews]})
                for review in list(ctx.reviews):
                    await self._apply_review(t, review)
                return
            if self.review_tasks_for(task_id, pending_only=True):
                await self._set(t, TaskStatus.review_pending, "task.review_pending",
                                {"attempt": t.attempt, "published": [p.model_dump() for p in (ctx.finished.published if ctx.finished else [])]})
            else:
                await self._set(t, TaskStatus.accepted, "task.accepted",
                                {"attempt": t.attempt, "summary": ctx.finished.summary if ctx.finished else "",
                                 "published": [p.model_dump() for p in (ctx.finished.published if ctx.finished else [])],
                                 "unverified": ctx.finished.unverified if ctx.finished else []})
            return
        if kind == "cancelled":
            await self._set(t, TaskStatus.cancelled, "task.cancelled", {"reason": outcome.detail})
            return
        if kind == "approval_pending":
            t.blocked_reason = f"approval {outcome.detail} pending"
            await self._set(t, TaskStatus.approval_required, "task.blocked", {"reason": t.blocked_reason, "approval_id": outcome.detail})
            self._pause_for_approval = True
            return
        # blocked / failed / ended
        t.blocked_reason = outcome.detail
        status = TaskStatus.blocked if kind == "blocked" else TaskStatus.failed
        await self._set(t, status, "task.blocked" if kind == "blocked" else "task.failed", {"reason": outcome.detail, "attempt": t.attempt})
        fatal = outcome.detail.startswith(("budget", "max_model_calls", "max_tool_calls", "timeout", "provider_auth"))
        if fatal:
            self._fatal = outcome.detail
            return
        n = self._exception_handled.get(task_id, 0)
        if n >= 1 or rt.policy.cancelled:
            return
        self._exception_handled[task_id] = n + 1
        await handle_exception(rt, t, kind, outcome.detail)

    async def _apply_review(self, review_task: TaskState, review: Review) -> None:
        rt = self.rt
        target = rt.tasks.get(review.target_task_id)
        if target is None:
            return
        target.review = review
        fails = [r for r in review.results if r.status == "fail"]
        if not fails:
            unverified = [r.acceptance_id for r in review.results if r.status != "pass"]
            target.blocked_reason = ("review left criteria unverified: " + ", ".join(unverified)) if unverified else None
            await self._set(target, TaskStatus.partial if unverified else TaskStatus.accepted,
                            "task.partial" if unverified else "task.accepted",
                            {"attempt": target.attempt, "review_by": review_task.spec.owner, "review_task": review_task.spec.id,
                             "target_artifacts": [a.model_dump() for a in review.target_artifacts],
                             "unverified": unverified, "reason": target.blocked_reason})
            return
        rnd = rt.policy.next_revision_round(target.spec.id)
        if rnd is None:
            await self._set(target, TaskStatus.partial, "task.partial",
                            {"reason": f"revision rounds exhausted ({rt.config.limits.max_revision_rounds})",
                             "failed_criteria": [r.acceptance_id for r in fails], "review_task": review_task.spec.id})
            return
        self._feedback[target.spec.id] = "\n".join(f"- {r.acceptance_id} [{r.status}]: {r.note or r.evidence}" for r in review.results if r.status != "pass") \
            + (f"\nSummary: {review.summary}" if review.summary else "")
        await self._set(target, TaskStatus.queued, "task.updated",
                        {"action": "revise", "revision_round": rnd, "failed_criteria": [r.acceptance_id for r in fails],
                         "review_task": review_task.spec.id})
        await self._set(review_task, TaskStatus.queued, "task.updated", {"action": "re-review", "revision_round": rnd, "target": target.spec.id})

    # ------------------------------------------------------------ main loop
    async def _cancel_all(self) -> None:
        for tid, fut in list(self._running.items()):
            fut.cancel()
        for fut in list(self._replies):
            fut.cancel()
        for tid, fut in list(self._running.items()):
            try:
                await fut
            except (asyncio.CancelledError, Exception):
                pass
            t = self.rt.tasks[tid]
            if t.status in (TaskStatus.running, TaskStatus.waiting):
                await self._set(t, TaskStatus.interrupted, "task.interrupted", {"reason": "run cancelled or interrupted"})
        self._running.clear()

    async def checkpoint(self) -> None:
        seq = await self.rt.events.last_seq(self.rt.run_id)
        snap = {"tasks": {tid: {"status": str(t.status), "attempt": t.attempt} for tid, t in self.rt.tasks.items()},
                "policy": self.rt.policy.snapshot()}
        await self.rt.runs.save_checkpoint(self.rt.run_id, seq, snap)
        await self.rt.events.append(self.rt.run_id, "checkpoint.saved", {"at_seq": seq, "tasks": snap["tasks"]})

    def final_status(self) -> RunStatus:
        statuses = [t.status for t in self.rt.tasks.values()]
        if statuses and all(s == TaskStatus.accepted for s in statuses):
            if self.unreviewed_final_tasks():
                return RunStatus.partial
            return RunStatus.completed
        if any(s in (TaskStatus.accepted, TaskStatus.partial) for s in statuses):
            return RunStatus.partial
        return RunStatus.failed

    def unreviewed_final_tasks(self) -> list[str]:
        rt = self.rt
        if rt.config.defaults.team_mode != "team" or not rt.config.defaults.require_independent_review:
            return []
        return [t.spec.id for t in rt.tasks.values()
                if t.spec.output_paths and self.role_of(t.spec.owner) != "reviewer" and t.review is None
                and not any(t.spec.id in other.spec.depends_on and self.role_of(other.spec.owner) != "reviewer"
                            for other in rt.tasks.values())]

    async def run(self) -> RunStatus:
        rt = self.rt
        while True:
            if rt.policy.cancelled:
                await self._cancel_all()
                return RunStatus.cancelled
            if rt.remaining_seconds() <= 0:
                await self._cancel_all()
                rt.run.blocked_reason = "wall-clock limit reached"
                return RunStatus.interrupted
            if self._fatal:
                await self._cancel_all()
                return self.final_status()
            # a task waiting for review whose review tasks all ended without a verdict is partial, not stuck
            for t in list(rt.tasks.values()):
                if t.status == TaskStatus.review_pending and t.review is None and not self.review_tasks_for(t.spec.id, pending_only=True):
                    await self._set(t, TaskStatus.partial, "task.partial",
                                    {"reason": "review task ended without a verdict; outputs are published but unverified",
                                     "unverified": [c.id for c in t.spec.acceptance]})
            # promote queued tasks
            for t in list(rt.tasks.values()):
                if t.status != TaskStatus.queued:
                    continue
                st = self._deps_state(t)
                if st == "dead":
                    await self._set(t, TaskStatus.cancelled, "task.cancelled", {"reason": "a dependency failed or was cancelled"})
                elif st == "ready":
                    await self._set(t, TaskStatus.ready, "task.ready", {})
            active = len(self._running) + len(self._replies)
            if not self._pause_for_approval:
                for t in list(rt.tasks.values()):
                    if t.status == TaskStatus.ready and active < rt.config.limits.max_active_workers:
                        await self._start(t)
                        active += 1
            pending = self._running or self._replies
            if not pending:
                if self._pause_for_approval:
                    return RunStatus.approval_required
                queued = [t for t in rt.tasks.values() if t.status in (TaskStatus.queued, TaskStatus.ready)]
                if queued:
                    for t in queued:  # unsatisfiable dependencies
                        await self._set(t, TaskStatus.blocked, "task.blocked", {"reason": "dependencies can never be satisfied"})
                # milestone: let the Master extend the plan if the goal is not yet met (bounded by max_replans)
                can_replan = (self._replans < rt.config.limits.max_replans and not rt.policy.cancelled
                              and any(t.status in (TaskStatus.accepted, TaskStatus.partial) for t in rt.tasks.values())
                              and rt.remaining_seconds() > 60)
                # a replan that cannot afford a single agent session would only add tasks that fail on budget
                # (seen twice in the research scenario re-runs: milestone-added tasks ended the run partial at the cap)
                calls_left = rt.config.limits.max_model_calls - rt.policy.usage.model_calls
                short = None
                if can_replan and rt.policy.remaining_budget() < rt.config.limits.max_session_cost_usd:
                    short = (f"remaining budget {rt.policy.remaining_budget():.2f} USD is below one agent session "
                             f"({rt.config.limits.max_session_cost_usd:.2f} USD)")
                elif can_replan and calls_left < rt.config.limits.max_session_turns:
                    short = f"remaining model calls {calls_left} are below one agent session ({rt.config.limits.max_session_turns} turns)"
                if short:
                    await rt.events.append(rt.run_id, "plan.milestone", {"round": self._replans + 1, "skipped": "limits",
                                                                          "reason": short + "; the Master was not asked to extend the plan"})
                    can_replan = False
                if can_replan:
                    self._replans += 1
                    try:
                        res = await milestone_replan(rt, self._replans)
                    except Exception as e:  # never let a replan crash the run
                        await rt.events.append(rt.run_id, "plan.milestone", {"round": self._replans, "error": rt.redactor.text(str(e))[:300]})
                        res = {"added": []}
                    if res.get("added"):
                        await self.checkpoint()
                        continue
                return self.final_status()
            done, _ = await asyncio.wait(set(self._running.values()) | set(self._replies), return_when=asyncio.FIRST_COMPLETED, timeout=1.0)
            for fut in done:
                tid = next((k for k, v in self._running.items() if v is fut), None)
                if tid is None:
                    continue  # reply session
                self._running.pop(tid, None)
                try:
                    _, ctx, outcome = fut.result()
                except asyncio.CancelledError:
                    outcome, ctx = SessionOutcome("cancelled", "cancelled"), None
                except Exception as e:  # runtime bug in a session must not silently lose the task
                    await rt.events.append(rt.run_id, "task.failed", {"reason": f"internal error: {type(e).__name__}: {rt.redactor.text(str(e))[:300]}"}, task_id=tid)
                    t = rt.tasks[tid]
                    t.blocked_reason = f"internal error: {e}"
                    await self._set(t, TaskStatus.failed)
                    continue
                if ctx is None:
                    await self._set(rt.tasks[tid], TaskStatus.cancelled, "task.cancelled", {"reason": "cancelled"})
                    continue
                await self._handle(tid, ctx, outcome)
                await self.checkpoint()
