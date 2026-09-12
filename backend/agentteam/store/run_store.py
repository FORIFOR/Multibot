"""Runs, tasks, messages, approvals, config revisions and checkpoints."""
from __future__ import annotations

from typing import Any

from ..contracts import Approval, Message, Run, RunInputs, RunStatus, TaskState, TaskStatus, TeamPlan, Usage
from ..ids import now_iso
from .db import Database, dumps, loads


class RunStore:
    def __init__(self, db: Database):
        self.db = db

    # ---- runs
    async def create_run(self, run: Run) -> None:
        await self.db.execute(
            "INSERT INTO runs(run_id,status,goal,inputs_json,created_at,started_at,finished_at,config_snapshot_json,"
            "plan_json,usage_json,parent_run_id,fork_from_seq,final_report_json,blocked_reason,provider_kind)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run.run_id, run.status, run.goal, dumps(run.inputs.model_dump()), run.created_at, run.started_at,
             run.finished_at, dumps(run.config_snapshot) if run.config_snapshot else None,
             dumps(run.plan.model_dump()) if run.plan else None, dumps(run.usage.model_dump()), run.parent_run_id,
             run.fork_from_seq, dumps(run.final_report) if run.final_report else None, run.blocked_reason,
             run.provider_kind),
        )

    async def get_run(self, run_id: str) -> Run | None:
        r = await self.db.fetchone("SELECT * FROM runs WHERE run_id=?", (run_id,))
        return self._run(r) if r else None

    async def list_runs(self, limit: int = 100) -> list[Run]:
        rows = await self.db.fetchall("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [self._run(r) for r in rows]

    async def update_run(self, run_id: str, **fields: Any) -> None:
        mapping = {
            "status": ("status", lambda v: str(v)),
            "started_at": ("started_at", lambda v: v),
            "finished_at": ("finished_at", lambda v: v),
            "config_snapshot": ("config_snapshot_json", dumps),
            "plan": ("plan_json", lambda v: dumps(v.model_dump() if hasattr(v, "model_dump") else v)),
            "usage": ("usage_json", lambda v: dumps(v.model_dump() if hasattr(v, "model_dump") else v)),
            "final_report": ("final_report_json", dumps),
            "blocked_reason": ("blocked_reason", lambda v: v),
            "cancel_requested": ("cancel_requested", lambda v: 1 if v else 0),
        }
        sets, params = [], []
        for k, v in fields.items():
            col, fn = mapping[k]
            sets.append(f"{col}=?")
            params.append(fn(v) if v is not None else None)
        params.append(run_id)
        await self.db.execute(f"UPDATE runs SET {', '.join(sets)} WHERE run_id=?", params)

    async def cancel_requested(self, run_id: str) -> bool:
        r = await self.db.fetchone("SELECT cancel_requested FROM runs WHERE run_id=?", (run_id,))
        return bool(r and r["cancel_requested"])

    @staticmethod
    def _run(r) -> Run:
        return Run(
            run_id=r["run_id"], status=RunStatus(r["status"]), goal=r["goal"],
            inputs=RunInputs.model_validate(loads(r["inputs_json"], {})), created_at=r["created_at"],
            started_at=r["started_at"], finished_at=r["finished_at"], config_snapshot=loads(r["config_snapshot_json"]),
            plan=TeamPlan.model_validate(loads(r["plan_json"])) if r["plan_json"] else None,
            usage=Usage.model_validate(loads(r["usage_json"], {})), parent_run_id=r["parent_run_id"],
            fork_from_seq=r["fork_from_seq"], final_report=loads(r["final_report_json"]),
            blocked_reason=r["blocked_reason"], provider_kind=r["provider_kind"],
        )

    # ---- tasks
    async def upsert_task(self, t: TaskState) -> None:
        t.updated_at = now_iso()
        await self.db.execute(
            "INSERT INTO tasks(run_id,task_id,state_json,status,owner,updated_at) VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(run_id,task_id) DO UPDATE SET state_json=excluded.state_json,status=excluded.status,"
            "owner=excluded.owner,updated_at=excluded.updated_at",
            (t.run_id, t.spec.id, dumps(t.model_dump()), str(t.status), t.spec.owner, t.updated_at),
        )

    async def get_task(self, run_id: str, task_id: str) -> TaskState | None:
        r = await self.db.fetchone("SELECT state_json FROM tasks WHERE run_id=? AND task_id=?", (run_id, task_id))
        return TaskState.model_validate(loads(r["state_json"])) if r else None

    async def list_tasks(self, run_id: str) -> list[TaskState]:
        rows = await self.db.fetchall("SELECT state_json FROM tasks WHERE run_id=? ORDER BY rowid", (run_id,))
        return [TaskState.model_validate(loads(r["state_json"])) for r in rows]

    # ---- messages
    async def insert_message(self, m: Message) -> None:
        await self.db.execute(
            "INSERT INTO messages(message_id,run_id,seq,from_agent_id,to_agent_id,task_id,purpose,text,artifact_refs_json,"
            "reply_to,recorded_at,read_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (m.message_id, m.run_id, m.seq, m.from_agent_id, m.to_agent_id, m.task_id, m.purpose, m.text,
             dumps([a.model_dump() for a in m.artifact_refs]), m.reply_to, m.recorded_at, m.read_at),
        )

    async def list_messages(self, run_id: str, *, to_agent_id: str | None = None, task_ids: list[str] | None = None,
                            after_seq: int = 0, unread_only: bool = False) -> list[Message]:
        sql = "SELECT * FROM messages WHERE run_id=? AND seq>?"
        params: list[Any] = [run_id, after_seq]
        if to_agent_id:
            sql += " AND to_agent_id=?"
            params.append(to_agent_id)
        if task_ids is not None:
            if not task_ids:
                return []
            sql += " AND task_id IN (%s)" % ",".join("?" * len(task_ids))
            params.extend(task_ids)
        if unread_only:
            sql += " AND read_at IS NULL"
        sql += " ORDER BY seq"
        rows = await self.db.fetchall(sql, params)
        return [self._msg(r) for r in rows]

    async def count_messages_for_task(self, run_id: str, task_id: str) -> int:
        r = await self.db.fetchone("SELECT COUNT(*) AS n FROM messages WHERE run_id=? AND task_id=?", (run_id, task_id))
        return int(r["n"]) if r else 0

    async def mark_read(self, message_ids: list[str]) -> None:
        if not message_ids:
            return
        ts = now_iso()
        await self.db.execute(
            "UPDATE messages SET read_at=? WHERE message_id IN (%s) AND read_at IS NULL" % ",".join("?" * len(message_ids)),
            [ts, *message_ids])

    @staticmethod
    def _msg(r) -> Message:
        return Message(
            message_id=r["message_id"], run_id=r["run_id"], seq=r["seq"], from_agent_id=r["from_agent_id"],
            to_agent_id=r["to_agent_id"], task_id=r["task_id"], purpose=r["purpose"], text=r["text"],
            artifact_refs=loads(r["artifact_refs_json"], []), reply_to=r["reply_to"], recorded_at=r["recorded_at"],
            read_at=r["read_at"],
        )

    # ---- approvals
    async def insert_approval(self, a: Approval) -> None:
        await self.db.execute(
            "INSERT INTO approvals(approval_id,run_id,task_id,agent_id,action,payload_json,payload_hash,nonce,status,"
            "created_at,expires_at,resolved_at,resolution_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.approval_id, a.run_id, a.task_id, a.agent_id, a.action, dumps(a.payload), a.payload_hash, a.nonce,
             str(a.status), a.created_at, a.expires_at, a.resolved_at, dumps(a.resolution) if a.resolution else None),
        )

    async def update_approval(self, a: Approval) -> None:
        await self.db.execute(
            "UPDATE approvals SET status=?, resolved_at=?, resolution_json=?, payload_json=?, payload_hash=? WHERE approval_id=?",
            (str(a.status), a.resolved_at, dumps(a.resolution) if a.resolution else None, dumps(a.payload), a.payload_hash,
             a.approval_id),
        )

    async def get_approval(self, approval_id: str) -> Approval | None:
        r = await self.db.fetchone("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
        return self._approval(r) if r else None

    async def list_approvals(self, run_id: str | None = None, status: str | None = None) -> list[Approval]:
        sql, params = "SELECT * FROM approvals WHERE 1=1", []
        if run_id:
            sql += " AND run_id=?"; params.append(run_id)
        if status:
            sql += " AND status=?"; params.append(status)
        sql += " ORDER BY created_at"
        return [self._approval(r) for r in await self.db.fetchall(sql, params)]

    @staticmethod
    def _approval(r) -> Approval:
        return Approval(
            approval_id=r["approval_id"], run_id=r["run_id"], task_id=r["task_id"], agent_id=r["agent_id"],
            action=r["action"], payload=loads(r["payload_json"], {}), payload_hash=r["payload_hash"], nonce=r["nonce"],
            status=r["status"], created_at=r["created_at"], expires_at=r["expires_at"], resolved_at=r["resolved_at"],
            resolution=loads(r["resolution_json"]),
        )

    # ---- config revisions
    async def add_config_revision(self, config_yaml: str, note: str = "") -> int:
        async with self.db.write_lock:
            await self.db.execute("INSERT INTO config_revisions(created_at,config_yaml,note) VALUES(?,?,?)",
                                  (now_iso(), config_yaml, note))
            r = await self.db.fetchone("SELECT MAX(revision) AS n FROM config_revisions")
            return int(r["n"])

    async def latest_config_revision(self) -> tuple[int, str] | None:
        r = await self.db.fetchone("SELECT revision, config_yaml FROM config_revisions ORDER BY revision DESC LIMIT 1")
        return (int(r["revision"]), r["config_yaml"]) if r else None

    async def list_config_revisions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self.db.fetchall("SELECT revision, created_at, note FROM config_revisions ORDER BY revision DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    async def get_config_revision(self, revision: int) -> str | None:
        r = await self.db.fetchone("SELECT config_yaml FROM config_revisions WHERE revision=?", (revision,))
        return r["config_yaml"] if r else None

    # ---- checkpoints
    async def save_checkpoint(self, run_id: str, seq: int, snapshot: dict[str, Any]) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO checkpoints(run_id,seq,created_at,snapshot_json) VALUES(?,?,?,?)",
            (run_id, seq, now_iso(), dumps(snapshot)))

    async def list_checkpoints(self, run_id: str) -> list[dict[str, Any]]:
        rows = await self.db.fetchall("SELECT seq, created_at, snapshot_json FROM checkpoints WHERE run_id=? ORDER BY seq", (run_id,))
        return [{"seq": r["seq"], "created_at": r["created_at"], "snapshot": loads(r["snapshot_json"])} for r in rows]
