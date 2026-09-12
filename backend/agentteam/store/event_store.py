"""Append-only event store: the single source of truth for a run.

seq is allocated by the store under a lock (monotonic per run, records insertion order).
Timestamps are taken by the runtime at append time. Payloads are redacted before persistence.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..contracts import Event
from ..ids import now_iso
from .db import Database, dumps, loads

Redactor = Callable[[Any], Any]


class EventStore:
    def __init__(self, db: Database, redactor: Redactor | None = None):
        self.db = db
        self.redactor = redactor or (lambda x: x)
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    async def append(
        self,
        run_id: str,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        actor_id: str = "runtime",
        actor_kind: str = "runtime",
        task_id: str | None = None,
        causation_id: str | None = None,
    ) -> Event:
        payload = self.redactor(payload or {})
        async with self.db.write_lock:
            row = await self.db.fetchone("SELECT COALESCE(MAX(seq),0)+1 AS n FROM events WHERE run_id=?", (run_id,))
            seq = int(row["n"])
            ev = Event(
                event_id=f"{run_id}:{seq}", run_id=run_id, seq=seq, recorded_at=now_iso(),
                actor_id=actor_id, actor_kind=actor_kind, task_id=task_id, causation_id=causation_id,
                type=str(type), payload=payload,
            )
            await self.db.execute(
                "INSERT INTO events(run_id,seq,event_id,recorded_at,actor_id,actor_kind,task_id,causation_id,type,payload_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ev.run_id, ev.seq, ev.event_id, ev.recorded_at, ev.actor_id, ev.actor_kind, ev.task_id,
                 ev.causation_id, ev.type, dumps(ev.payload)),
            )
        for q in list(self._subscribers.get(run_id, ())):
            q.put_nowait(ev)
        return ev

    async def list(self, run_id: str, after_seq: int = 0, limit: int = 10000, types: list[str] | None = None) -> list[Event]:
        sql = "SELECT * FROM events WHERE run_id=? AND seq>?"
        params: list[Any] = [run_id, after_seq]
        if types:
            sql += " AND type IN (%s)" % ",".join("?" * len(types))
            params.extend(types)
        sql += " ORDER BY seq LIMIT ?"
        params.append(limit)
        rows = await self.db.fetchall(sql, params)
        return [self._row(r) for r in rows]

    async def last_seq(self, run_id: str) -> int:
        row = await self.db.fetchone("SELECT COALESCE(MAX(seq),0) AS n FROM events WHERE run_id=?", (run_id,))
        return int(row["n"]) if row else 0

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        self._subscribers.get(run_id, set()).discard(q)

    @staticmethod
    def _row(r) -> Event:
        return Event(
            event_id=r["event_id"], run_id=r["run_id"], seq=r["seq"], recorded_at=r["recorded_at"],
            actor_id=r["actor_id"], actor_kind=r["actor_kind"], task_id=r["task_id"],
            causation_id=r["causation_id"], type=r["type"], payload=loads(r["payload_json"], {}),
        )
