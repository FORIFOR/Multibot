"""RunManager: run lifecycle (create → precheck → plan → schedule → report), cancel, resume, fork."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable

import yaml

from ..config.loader import config_to_yaml, effective_all, load_config_text
from ..config.models import AgentTeamConfig, IMPLEMENTED_DRIVERS
from ..config.secrets import SecretResolutionError, resolve_secret
from ..contracts import Run, RunInputs, RunStatus, TaskState, TaskStatus, Usage
from ..ids import new_id, now_iso
from ..projections.views import evidence_view
from ..providers.base import ProviderAdapter
from ..providers.pricing import price_for
from ..providers.registry import ProviderRegistry
from ..store.artifact_store import ArtifactStore
from ..store.event_store import EventStore
from ..store.run_store import RunStore
from ..store.job_store import JobStore
from .context import RunRuntime
from .mailbox import MessageBus
from .planner import PlanError, final_report, plan_team, single_agent_plan
from .policy import PolicyEngine
from .redaction import Redactor
from .scheduler import Scheduler


class RunManager:
    def __init__(self, *, runs: RunStore, events: EventStore, artifacts: ArtifactStore, data_dir: Path,
                 config_getter: Callable[[], AgentTeamConfig], redactor: Redactor,
                 fake_adapters: dict[str, ProviderAdapter] | None = None, approval_wait_seconds: float = 120.0,
                 durable: bool = False, run_concurrency: int = 2, max_pending: int = 20):
        self.runs, self.events, self.artifacts = runs, events, artifacts
        self.data_dir = Path(data_dir)
        self.config_getter = config_getter
        self.redactor = redactor
        self.fake_adapters = fake_adapters or {}
        self.approval_wait_seconds = approval_wait_seconds
        self.live: dict[str, RunRuntime] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self.stopping = False
        self.durable = durable
        self.jobs = JobStore(runs.db)
        self._run_slots = asyncio.Semaphore(run_concurrency)
        self.max_pending = max_pending
        self._dispatcher = None

    async def submit(self, run_id: str, *, resume: bool = False, receipt=None):
        """Commit execution intent before acknowledging a secured API request."""
        if self.stopping:
            raise RuntimeError('server is shutting down')
        if not self.durable:
            self.start(run_id, resume=resume)
            return
        job = await self.jobs.enqueue(run_id, resume=resume, max_pending=self.max_pending, receipt=receipt)
        self._schedule_job(job)
        await self.events.append(run_id, 'run.queued', {'job_id': job['job_id'], 'resume': resume})

    def _schedule_job(self, job):
        run_id = job['run_id']
        existing = self._tasks.get(run_id)
        if existing and not existing.done():
            return  # the dispatcher may observe a committed job before submit returns
        task = self._tasks[run_id] = asyncio.create_task(self._run_job(job))
        def done(t):
            if self._tasks.get(run_id) is t:
                self._tasks.pop(run_id, None)
            if not t.cancelled():
                t.exception()  # state/reason is persisted by _run_job; consume background exceptions
        task.add_done_callback(done)

    async def recover_jobs(self):
        if not self.durable:
            return
        for job in await self.jobs.recover():
            await self.events.append(job['run_id'], 'execution.recovered', {'job_id': job['job_id'], 'automatic_replay': False})
        for job in await self.jobs.pending():
            self._schedule_job(job)
        async def dispatch():
            while not self.stopping:
                await asyncio.sleep(1)
                for job in await self.jobs.pending():
                    task = self._tasks.get(job['run_id'])
                    if task is None or task.done():
                        self._schedule_job(job)
        self._dispatcher = asyncio.create_task(dispatch())

    async def pending_run(self, run_id):
        if self.durable:
            return bool(await self.runs.db.fetchone("SELECT job_id FROM execution_jobs WHERE run_id=? AND state IN ('queued','leased')", (run_id,)))
        return run_id in self.live or (run_id in self._tasks and not self._tasks[run_id].done())

    async def _run_job(self, queued):
        async with self._run_slots:
            await self._deliver_job(queued)

    async def _deliver_job(self, queued):
        owner = new_id('worker')
        job = None
        execution = heartbeat = None
        reason = None
        try:
            job = await self.jobs.claim(queued['job_id'], owner)
            if job is None:
                return

            async def renew():
                while True:
                    await asyncio.sleep(10)
                    if not await self.jobs.renew(job['job_id'], owner):
                        raise RuntimeError('execution lease lost')

            execution = asyncio.create_task(self._execute(job['run_id'], resume=bool(job['resume'])))
            heartbeat = asyncio.create_task(renew())
            done, _ = await asyncio.wait({execution, heartbeat}, return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                await heartbeat
            await execution
        except asyncio.CancelledError:
            reason = 'server shutting down' if self.stopping else 'execution delivery interrupted'
            raise
        except Exception as exc:
            reason = self.redactor.text(str(exc))[:300]
            raise
        finally:
            for task in (execution, heartbeat):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (execution, heartbeat) if t), return_exceptions=True)
            if job:
                run = await self.runs.get_run(job['run_id'])
                terminal = run and run.status in (RunStatus.completed, RunStatus.partial, RunStatus.failed, RunStatus.cancelled)
                await self.jobs.finish(job['job_id'], owner, 'finished' if terminal else 'interrupted', reason)
                if reason and not terminal:
                    await self.runs.update_run(job['run_id'], status=RunStatus.interrupted, blocked_reason=reason)

    # ------------------------------------------------------------ precheck
    def precheck(self, cfg: AgentTeamConfig) -> list[dict[str, Any]]:
        problems: list[dict[str, Any]] = []
        agents = {a.id: a for a in cfg.agents}
        master = agents.get("master")
        if cfg.defaults.team_mode == "single":
            solos = [a for a in cfg.agents if a.enabled and a.role == "builder"]
            others = [a.id for a in cfg.agents if a.enabled and a.role not in ("builder", "reporter")]
            if len(solos) != 1 or others:
                problems.append({"code": "single_agent_shape", "message": "team_mode=single needs exactly one enabled builder-role agent "
                                                                          "and no other enabled agents (reporter may stay)"})
        elif master is None or not master.enabled:
            problems.append({"code": "no_master", "message": "an enabled 'master' agent is required"})
        if cfg.limits.budget_usd <= 0:
            problems.append({"code": "budget", "message": "limits.budget_usd must be > 0"})
        seen_conn: set[str] = set()
        for a in cfg.agents:
            if not a.enabled:
                continue
            cid = cfg.defaults.connection_id if a.connection_id == "inherit" else a.connection_id
            model = cfg.defaults.model if a.model == "inherit" else a.model
            conn = cfg.connection(cid)
            if conn is None:
                problems.append({"code": "unknown_connection", "agent_id": a.id, "message": f"connection {cid} not found"})
                continue
            if not model or "SELECT" in model.upper() or "PLACEHOLDER" in model.upper():
                problems.append({"code": "placeholder_model", "agent_id": a.id, "connection_id": cid,
                                 "message": f"agent {a.id}: model {model!r} is a placeholder; pick a real model", "fix": "settings"})
            if conn.driver not in IMPLEMENTED_DRIVERS:
                problems.append({"code": "driver_unsupported", "connection_id": cid, "message": f"driver {conn.driver} is not implemented"})
            if conn.driver == "fake" and cid not in self.fake_adapters:
                problems.append({"code": "fake_not_injected", "connection_id": cid, "message": "fake provider is test-only"})
            if price_for(model, cfg.pricing, driver=conn.driver) is None:
                problems.append({"code": "unknown_pricing", "agent_id": a.id, "message": f"no price for model {model}; add it under pricing: in the config",
                                 "fix": "settings"})
            if cid in seen_conn:
                continue
            seen_conn.add(cid)
            if conn.driver == "claude_cli":
                import shutil
                if shutil.which(os.environ.get("AGENTTEAM_CLAUDE_BIN") or "claude") is None:
                    problems.append({"code": "claude_cli_missing", "connection_id": cid,
                                     "message": "claude CLI not found on PATH; install Claude Code and log in once", "fix": "settings"})
            if conn.driver in ("anthropic_messages", "openai_compatible_chat") and cid not in self.fake_adapters:
                try:
                    resolve_secret(conn.api_key_ref)
                except SecretResolutionError as e:
                    problems.append({"code": "secret", "connection_id": cid, "message": f"connection {cid}: {e}", "fix": "settings"})
            if conn.capability_check != "passed":
                problems.append({"code": "capability_check", "connection_id": cid,
                                 "message": f"connection {cid}: capability check is {conn.capability_check}; run the probe first", "fix": "probe"})
        return problems

    # ------------------------------------------------------------ create/start
    async def create_run(self, goal: str, inputs: RunInputs | None = None, *, budget_usd: float | None = None,
                         config: AgentTeamConfig | None = None) -> tuple[Run, list[dict[str, Any]]]:
        cfg = config or self.config_getter()
        if budget_usd is not None:
            cfg = cfg.model_copy(deep=True)
            cfg.limits.budget_usd = float(budget_usd)
        problems = self.precheck(cfg)
        run = Run(run_id=new_id("run"), status=RunStatus.created, goal=goal.strip(), inputs=inputs or RunInputs(), created_at=now_iso(),
                  config_snapshot={"config_yaml": config_to_yaml(cfg)}, usage=Usage())
        if problems:
            run.status = RunStatus.blocked
            run.blocked_reason = "; ".join(p["message"] for p in problems)
            await self.runs.create_run(run)
            await self.events.append(run.run_id, "run.blocked", {"problems": problems})
            return run, problems
        await self.runs.create_run(run)
        await self.events.append(run.run_id, "run.created", {"goal": run.goal, "urls": run.inputs.urls,
                                                             "has_text": bool(run.inputs.text), "files": [f.get("name") for f in run.inputs.files]},
                                 actor_id="user", actor_kind="human")
        return run, []

    def _build_runtime(self, run: Run, cfg: AgentTeamConfig) -> RunRuntime:
        registry = ProviderRegistry(cfg, fake_adapters=self.fake_adapters)
        agents = effective_all(cfg)
        policy = PolicyEngine(limits=cfg.limits, usage=run.usage.model_copy())
        bus = MessageBus(run.run_id, self.runs, self.events)
        rt = RunRuntime(run=run, config=cfg, agents=agents, policy=policy, events=self.events, artifacts=self.artifacts,
                        runs=self.runs, bus=bus, providers=registry, redactor=self.redactor, data_dir=self.data_dir,
                        approval_wait_seconds=self.approval_wait_seconds)
        return rt

    def start(self, run_id: str, *, resume: bool = False) -> asyncio.Task:
        if self.stopping:
            raise RuntimeError('server is shutting down')
        if run_id in self._tasks and not self._tasks[run_id].done():
            raise RuntimeError("run already executing")
        t = asyncio.create_task(self._execute(run_id, resume=resume))
        self._tasks[run_id] = t
        return t

    async def shutdown(self) -> None:
        """Stop live provider/worker calls before closing SQLite; preserve resumable work."""
        self.stopping = True
        if self._dispatcher:
            self._dispatcher.cancel()
            await asyncio.gather(self._dispatcher, return_exceptions=True)
        pending = [t for t in self._tasks.values() if not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def wait(self, run_id: str) -> Run:
        t = self._tasks.get(run_id)
        if t:
            await t
        return await self.runs.get_run(run_id)  # type: ignore[return-value]

    async def _execute(self, run_id: str, *, resume: bool) -> None:
        run = await self.runs.get_run(run_id)
        assert run is not None
        cfg = load_config_text(run.config_snapshot["config_yaml"], allow_fake=bool(self.fake_adapters))
        rt = self._build_runtime(run, cfg)
        self.live[run_id] = rt
        try:
            for secret_ref in {c.api_key_ref for c in cfg.connections if c.api_key_ref}:
                try:
                    self.redactor.add(resolve_secret(secret_ref))
                except SecretResolutionError:
                    pass
            snapshot = {"config_yaml": run.config_snapshot["config_yaml"],
                        "agents": {aid: a.model_dump() for aid, a in rt.agents.items() if a.enabled},
                        "provider_kind": "fake" if any(getattr(rt.providers.adapter(a.connection_id), "kind", "real") == "fake"
                                                       for a in rt.enabled_agents()) else "real"}
            run.config_snapshot = snapshot
            run.provider_kind = snapshot["provider_kind"]
            await self.runs.update_run(run_id, config_snapshot=snapshot)
            await self.runs.db.execute("UPDATE runs SET provider_kind=? WHERE run_id=?", (run.provider_kind, run_id))
            if resume:
                await self._prepare_resume(rt)
                await self.events.append(run_id, "run.resumed", {"tasks": {t.spec.id: str(t.status) for t in rt.tasks.values()}})
            else:
                run.started_at = now_iso()
                await self.runs.update_run(run_id, status=RunStatus.planning, started_at=run.started_at)
                await self.events.append(run_id, "run.started", {"goal": run.goal, "limits": cfg.limits.model_dump(),
                                                                 "provider_kind": run.provider_kind})
            await self.events.append(run_id, "config.resolved", {
                "agents": {aid: {"connection_id": a.connection_id, "driver": a.driver, "model": a.model, "prompt_mode": a.prompt_mode,
                                 "system_prompt_sha256": a.system_prompt_sha256, "skills": [{"name": s["name"], "sha256": s["sha256"]} for s in a.skills],
                                 "tools": a.tools, "effort": a.effort} for aid, a in rt.agents.items() if a.enabled},
                "limits": cfg.limits.model_dump(), "provider_kind": run.provider_kind})
            scheduler = Scheduler(rt)
            if not resume:
                if run.plan is None:
                    try:
                        plan = await (single_agent_plan(rt) if cfg.defaults.team_mode == "single" else plan_team(rt))
                    except PlanError as e:
                        await self._finish(rt, RunStatus.failed, reason=str(e))
                        return
                    run.plan = plan
                    await self.runs.update_run(run_id, plan=plan)
                await scheduler.init_from_plan()
            await self.runs.update_run(run_id, status=RunStatus.running)
            run.status = RunStatus.running
            status = await scheduler.run()
            await scheduler.checkpoint()
            await self._finish(rt, status, reason=await self._status_reason(rt, status))
        except asyncio.CancelledError:
            if rt.scheduler:
                await rt.scheduler._cancel_all()
                await rt.scheduler.checkpoint()
            await self._finish(rt, RunStatus.interrupted, reason="server shutting down")
            raise
        except Exception as e:  # never leave a run in 'running'
            await self.events.append(run_id, "run.failed", {"reason": f"internal error: {type(e).__name__}: {self.redactor.text(str(e))[:500]}"})
            await self.runs.update_run(run_id, status=RunStatus.failed, finished_at=now_iso(), blocked_reason=self.redactor.text(str(e))[:500])
            raise
        finally:
            await rt.persist_usage()
            await rt.providers.aclose()
            self.live.pop(run_id, None)

    async def _status_reason(self, rt: RunRuntime, status: RunStatus) -> str | None:
        """One line naming the tasks that kept the run from 'completed' (their own blocked_reason when they have one)."""
        if status == RunStatus.interrupted:
            return rt.run.blocked_reason or "interrupted"
        if status not in (RunStatus.partial, RunStatus.failed):
            return None
        # tasks the Master added later (exception / milestone) carry created_by=master on their task.created event;
        # run.plan.tasks grows with them, so the original plan is "everything else"
        added = {e.task_id for e in await self.events.list(rt.run_id) if e.type == "task.created" and e.payload.get("created_by")}
        planned = {t.spec.id for t in rt.tasks.values() if t.spec.id not in added}
        parts = []
        if rt.scheduler:
            parts.extend(f"{tid}: required independent review was not submitted" for tid in rt.scheduler.unreviewed_final_tasks())
        for t in rt.tasks.values():
            if t.status == TaskStatus.accepted:
                continue
            why = (t.blocked_reason or "").strip()
            parts.append(f"{t.spec.id} {t.status}" + (f": {why[:160]}" if why else ""))
        if not parts:
            return None
        if planned and all(t.status == TaskStatus.accepted for t in rt.tasks.values() if t.spec.id in planned):
            parts.insert(0, "every task of the original plan was accepted; only tasks added at a milestone are unfinished")
        return "; ".join(parts)[:500]

    async def _finish(self, rt: RunRuntime, status: RunStatus, *, reason: str | None = None) -> None:
        run = rt.run
        if status in (RunStatus.approval_required, RunStatus.interrupted):
            ev = await self.events.append(run.run_id, "run.interrupted" if status == RunStatus.interrupted else "task.blocked",
                                          {"reason": reason or str(status)}, notify=False)
            await self.runs.update_run(run.run_id, status=status, blocked_reason=reason)
            self.events.notify(ev)
            return
        run.status = status  # report context; keep the stored run active until all output is ready
        report = await self._make_report(rt, status, reason)
        if rt.policy.cancelled and status != RunStatus.cancelled:
            status = run.status = RunStatus.cancelled
            reason = "cancelled while preparing the final report"
            report = await self._make_report(rt, status, reason)  # deterministic; no further model call
        run.finished_at = now_iso()
        ev = await self.events.append(run.run_id, {"completed": "run.completed", "partial": "run.partial", "failed": "run.failed",
                                                 "cancelled": "run.cancelled"}[str(status)],
                                      {"reason": reason, "usage": rt.policy.usage.model_dump(),
                                       "deliverables": report.get("deliverables") if report else []}, notify=False)
        await self.runs.update_run(run.run_id, status=status, finished_at=run.finished_at, blocked_reason=reason,
                                   final_report=report)
        self.events.notify(ev)  # SSE consumers now see the same complete state as polling/export clients

    async def _make_report(self, rt: RunRuntime, status: RunStatus, reason: str | None) -> dict[str, Any]:
        run = rt.run
        tasks = list(rt.tasks.values())
        artifacts = await self.artifacts.list(run.run_id, latest_only=True)
        events = await self.events.list(run.run_id)
        evidence = evidence_view(run, tasks, artifacts, events)
        evidence["run"]["final_status"] = str(status)
        evidence["run"]["reason"] = reason
        narrative = None
        if status != RunStatus.cancelled and not rt.policy.cancelled:
            narrative = await final_report(rt, evidence)
        report = {"status": str(status), "reason": reason, "generated_at": now_iso(), "evidence": evidence, "narrative": narrative,
                  "deliverables": [{"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256, "logical_path": m.logical_path,
                                    "by": m.agent_id, "task_id": m.task_id} for m in artifacts if m.artifact_id != "final-report.md"],
                  "usage": rt.policy.usage.model_dump()}
        md = render_report_markdown(report, run)
        m = await self.artifacts.publish(run.run_id, "final-report.md", md.encode("utf-8"), agent_id=(narrative or {}).get("author", "runtime"),
                                         task_id=None, media_type="text/markdown")
        ev = await self.events.append(run.run_id, "report.generated", {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256,
                                                                      "narrative_by": (narrative or {}).get("author")})
        await self.artifacts.set_event(run.run_id, m.artifact_id, m.revision, ev.event_id)
        report["report_artifact"] = {"artifact_id": m.artifact_id, "revision": m.revision}
        return report

    # ------------------------------------------------------------ cancel/resume/fork
    async def cancel(self, run_id: str) -> bool:
        if self.durable and await self.jobs.cancel_queued(run_id):
            task = self._tasks.get(run_id)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await self.runs.update_run(run_id, status=RunStatus.cancelled, cancel_requested=True, finished_at=now_iso())
            await self.events.append(run_id, 'run.cancelled', {'reason': 'cancelled before execution'}, actor_id='user', actor_kind='human')
            return True
        rt = self.live.get(run_id)
        task = self._tasks.get(run_id)
        if self.durable and rt is None and task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await self.runs.update_run(run_id, status=RunStatus.cancelled, cancel_requested=True, finished_at=now_iso())
            await self.events.append(run_id, 'run.cancelled', {'reason': 'cancelled before runtime initialization'}, actor_id='user', actor_kind='human')
            return True
        await self.runs.update_run(run_id, cancel_requested=True)
        if rt is None:
            run = await self.runs.get_run(run_id)
            if run and run.status in (RunStatus.approval_required, RunStatus.interrupted, RunStatus.created):
                await self.runs.update_run(run_id, status=RunStatus.cancelled, finished_at=now_iso())
                await self.events.append(run_id, "run.cancelled", {"reason": "cancelled by user while paused"}, actor_id="user", actor_kind="human")
                return True
            return False
        await self.events.append(run_id, "run.cancelled", {"reason": "cancellation requested by user", "note": "external side effects, if any, are recorded separately"},
                                 actor_id="user", actor_kind="human")
        rt.policy.cancel()
        return True

    async def _prepare_resume(self, rt: RunRuntime) -> None:
        tasks = await self.runs.list_tasks(rt.run_id)
        pending = await self.runs.list_approvals(rt.run_id, status="pending")
        for t in tasks:
            if t.status in (TaskStatus.running, TaskStatus.waiting, TaskStatus.interrupted, TaskStatus.ready, TaskStatus.cancelled):
                t.status = TaskStatus.queued
            elif t.status == TaskStatus.approval_required:
                if any(a.task_id == t.spec.id for a in pending):
                    raise PlanError(f"approval for task {t.spec.id} is still pending")
                t.status = TaskStatus.queued
            await rt.save_task(t)
        for t in tasks:
            rt.policy.peer_messages[t.spec.id] = await self.runs.count_messages_for_task(rt.run_id, t.spec.id)
        cps = await self.runs.list_checkpoints(rt.run_id)
        if cps:
            rt.policy.revision_rounds = dict(cps[-1]["snapshot"].get("policy", {}).get("revision_rounds", {}))
        rt.policy.usage = rt.run.usage.model_copy()
        rt.policy.usage.reserved_usd = 0.0

    async def resume(self, run_id: str, *, receipt=None) -> Run:
        run = await self.runs.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status not in (RunStatus.interrupted, RunStatus.approval_required, RunStatus.failed, RunStatus.partial, RunStatus.cancelled):
            raise ValueError(f"run in status {run.status} cannot be resumed")
        if run.plan is None:
            raise ValueError("run has no plan to resume")
        if not self.durable:
            await self.runs.update_run(run_id, status=RunStatus.running, cancel_requested=False, finished_at=None)
        await self.submit(run_id, resume=True, receipt=receipt)
        return (await self.runs.get_run(run_id))  # type: ignore[return-value]

    async def fork(self, run_id: str, *, overrides: dict[str, Any] | None = None, from_seq: int | None = None,
                   keep_accepted: bool = True) -> Run:
        src = await self.runs.get_run(run_id)
        if src is None:
            raise KeyError(run_id)
        cfg = self.config_getter().model_copy(deep=True)
        for aid, o in (overrides or {}).get("agents", {}).items():
            a = cfg.agent(aid)
            if a is None:
                continue
            if "model" in o:
                a.model = o["model"]
            if "connection_id" in o:
                a.connection_id = o["connection_id"]
            if "system_prompt_override" in o and a.prompt_mode != "user_locked":
                a.system_prompt_override = o["system_prompt_override"]
        if (overrides or {}).get("budget_usd"):
            cfg.limits.budget_usd = float(overrides["budget_usd"])
        problems = self.precheck(cfg)
        if problems:
            raise ValueError("; ".join(p["message"] for p in problems))
        seq = from_seq if from_seq is not None else await self.events.last_seq(run_id)
        new = Run(run_id=new_id("run"), status=RunStatus.created, goal=src.goal, inputs=src.inputs, created_at=now_iso(),
                  config_snapshot={"config_yaml": config_to_yaml(cfg)}, plan=src.plan, parent_run_id=run_id, fork_from_seq=seq)
        await self.runs.create_run(new)
        copied: list[str] = []
        if keep_accepted and src.plan is not None:
            src_tasks = {t.spec.id: t for t in await self.runs.list_tasks(run_id)}
            rerun: set[str] = set((overrides or {}).get("rerun_tasks", []))
            changed = True
            while changed:  # anything downstream of a re-run task must also re-run (no stale reviews/inputs)
                changed = False
                for spec in src.plan.tasks:
                    if spec.id not in rerun and any(d in rerun for d in spec.depends_on):
                        rerun.add(spec.id)
                        changed = True
            for spec in src.plan.tasks:
                st = src_tasks.get(spec.id)
                keep = st is not None and st.status == TaskStatus.accepted and spec.id not in rerun
                t = TaskState(run_id=new.run_id, spec=spec, status=TaskStatus.accepted if keep else TaskStatus.queued,
                              attempt=st.attempt if (keep and st) else 0, result=st.result if (keep and st) else None, updated_at=now_iso())
                await self.runs.upsert_task(t)
                if keep:
                    copied.append(spec.id)
            for m in await self.artifacts.list(run_id):
                if m.task_id in copied:
                    await self.artifacts.publish(new.run_id, m.logical_path, self.artifacts.read_bytes(m), agent_id=m.agent_id,
                                                 task_id=m.task_id, media_type=m.media_type, sources=m.sources)
        await self.events.append(run_id, "run.forked", {"child_run_id": new.run_id, "from_seq": seq, "overrides": overrides or {}},
                                 actor_id="user", actor_kind="human")
        await self.events.append(new.run_id, "run.forked", {"parent_run_id": run_id, "from_seq": seq, "overrides": overrides or {},
                                                            "kept_tasks": copied}, actor_id="user", actor_kind="human")
        await self.events.append(new.run_id, "run.created", {"goal": new.goal, "forked": True}, actor_id="user", actor_kind="human")
        return new

    async def start_fork(self, new_run_id: str, *, receipt=None) -> None:
        """Forked runs already have their tasks; start in resume mode so accepted tasks are kept."""
        run = await self.runs.get_run(new_run_id)
        assert run is not None
        run.started_at = now_iso()
        await self.runs.update_run(new_run_id, started_at=run.started_at, status=RunStatus.created if self.durable else RunStatus.running)
        await self.events.append(new_run_id, "run.started", {"goal": run.goal, "forked_from": run.parent_run_id})
        await self.submit(new_run_id, resume=run.plan is not None, receipt=receipt)

    async def resolve_approval(self, approval_id: str, decision: str, *, note: str = "", edited_payload: dict[str, Any] | None = None,
                               expected_hash: str | None = None, nonce: str | None = None) -> Any:
        from ..contracts import ApprovalStatus
        import hashlib
        ap = await self.runs.get_approval(approval_id)
        if ap is None:
            raise KeyError(approval_id)
        if ap.status != ApprovalStatus.pending:
            raise ValueError(f"approval already {ap.status}")
        if expected_hash and expected_hash != ap.payload_hash:
            raise ValueError("payload hash mismatch: the requested action changed since it was displayed")
        if nonce and nonce != ap.nonce:
            raise ValueError("nonce mismatch")
        if ap.expires_at < now_iso():
            ap.status = ApprovalStatus.expired
            await self.runs.update_approval(ap)
            raise ValueError("approval expired")
        ap.resolved_at = now_iso()
        ap.resolution = {"decision": decision, "note": note}
        if decision == "approve":
            ap.status = ApprovalStatus.approved
        elif decision == "edit":
            ap.status = ApprovalStatus.edited
            ap.payload = edited_payload or ap.payload
            ap.payload_hash = hashlib.sha256(json.dumps(ap.payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        else:
            ap.status = ApprovalStatus.rejected
        await self.runs.update_approval(ap)
        await self.events.append(ap.run_id, "approval.resolved", {"approval_id": ap.approval_id, "decision": decision, "note": note,
                                                                  "payload_hash": ap.payload_hash}, actor_id="user", actor_kind="human", task_id=ap.task_id)
        rt = self.live.get(ap.run_id)
        if rt and approval_id in rt.approval_waiters:
            rt.approval_waiters[approval_id].set()
        else:
            run = await self.runs.get_run(ap.run_id)
            if run and run.status == RunStatus.approval_required:
                await self.resume(ap.run_id)
        return ap


def render_report_markdown(report: dict[str, Any], run: Run) -> str:
    ev = report["evidence"]
    n = report.get("narrative") or {}
    lines = [f"# Final report — {run.goal}", "",
             f"- Status: **{report['status']}**" + (f" ({report['reason']})" if report.get("reason") else ""),
             f"- Provider kind: {ev['run'].get('provider_kind')}",
             f"- Usage: {ev['run']['usage']['model_calls']} model calls, {ev['run']['usage']['tool_calls']} tool calls, "
             f"${ev['run']['usage']['cost_usd']:.4f}, {ev['run']['usage']['wall_seconds']:.0f}s", ""]
    if n.get("summary"):
        lines += ["## Summary", n["summary"], ""]
    lines.append("## Deliverables")
    for d in report["deliverables"]:
        lines.append(f"- `{d['logical_path']}` — {d['artifact_id']} r{d['revision']} (sha256 {d['sha256'][:12]}…) by {d['by']} / task {d['task_id']}")
    if not report["deliverables"]:
        lines.append("- (none)")
    lines += ["", "## Tasks"]
    for t in ev["tasks"]:
        lines.append(f"- {t['id']} [{t['status']}] {t['owner']}: {t['objective']} (attempts {t['attempts']})" + (f" — {t['blocked_reason']}" if t.get("blocked_reason") else ""))
    lines += ["", "## Verified (from checks and reviews)"]
    for c in ev["checks"]:
        lines.append(f"- check {c['kind']} on {c.get('target')} → {c['status']} (seq {c['seq']})")
    for r in ev["reviews"]:
        lines.append(f"- review of {r['target_task_id']} by {r['by']}: " + ", ".join(f"{x['acceptance_id']}={x['status']}" for x in (r.get("results") or [])) + f" (seq {r['seq']})")
    if n.get("verified"):
        lines += [f"- {v}" for v in n["verified"]]
    lines += ["", "## Unresolved / pending"]
    for f in ev["failures"]:
        lines.append(f"- {f['type']} task={f.get('task_id')}: {f.get('reason')} (seq {f['seq']})")
    for b in ev["blockers"]:
        lines.append(f"- blocker by {b['actor']}: {b.get('reason')} — needed: {b.get('needed')}")
    for a in ev["approvals"]:
        lines.append(f"- approval {a.get('approval_id')}: {a.get('action') or a.get('decision')}")
    if n.get("unresolved"):
        lines += [f"- {u}" for u in n["unresolved"]]
    if not (ev["failures"] or ev["blockers"] or ev["approvals"] or n.get("unresolved")):
        lines.append("- (none recorded)")
    if n.get("next_steps"):
        lines += ["", "## Next steps"] + [f"- {s}" for s in n["next_steps"]]
    lines += ["", "## Trace", f"- Messages delivered: {ev['messages']['count']} ({ev['messages']['by_purpose']})",
              "- Model usage by agent: " + ", ".join(f"{k}: {v['calls']} calls / ${v['cost_usd']:.4f} (reported {', '.join(v['models_reported']) or 'unknown'})"
                                                     for k, v in ev["model_usage_by_agent"].items())]
    return "\n".join(lines) + "\n"
