"""MessageBus: real delivery to per-agent mailboxes, recorded as message.sent events."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ..contracts import ArtifactRef, Message
from ..ids import new_id
from ..store.event_store import EventStore
from ..store.run_store import RunStore

Listener = Callable[[Message], Awaitable[None]]


class MessageBus:
    def __init__(self, run_id: str, runs: RunStore, events: EventStore):
        self.run_id = run_id
        self.runs = runs
        self.events = events
        self._conds: dict[str, asyncio.Condition] = {}
        self._listeners: list[Listener] = []

    def on_deliver(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def _cond(self, agent_id: str) -> asyncio.Condition:
        if agent_id not in self._conds:
            self._conds[agent_id] = asyncio.Condition()
        return self._conds[agent_id]

    async def send(self, *, from_agent_id: str, to_agent_id: str, task_id: str, purpose: str, text: str,
                   artifact_refs: list[ArtifactRef] | None = None, reply_to: str | None = None,
                   causation_id: str | None = None) -> Message:
        ev = await self.events.append(
            self.run_id, "message.sent",
            {"from_agent_id": from_agent_id, "to_agent_id": to_agent_id, "task_id": task_id, "purpose": purpose,
             "text": text, "artifact_refs": [a.model_dump() for a in (artifact_refs or [])], "reply_to": reply_to},
            actor_id=from_agent_id, actor_kind="agent", task_id=task_id, causation_id=causation_id,
        )
        m = Message(message_id=new_id("msg"), run_id=self.run_id, seq=ev.seq, from_agent_id=from_agent_id,
                    to_agent_id=to_agent_id, task_id=task_id, purpose=purpose, text=text,
                    artifact_refs=artifact_refs or [], reply_to=reply_to, recorded_at=ev.recorded_at)
        await self.runs.insert_message(m)
        cond = self._cond(to_agent_id)
        async with cond:
            cond.notify_all()
        for fn in self._listeners:
            await fn(m)
        return m

    async def read(self, agent_id: str, task_ids: list[str] | None, *, unread_only: bool = True,
                   wait_seconds: float = 0) -> list[Message]:
        msgs = await self.runs.list_messages(self.run_id, to_agent_id=agent_id, task_ids=task_ids, unread_only=unread_only)
        if msgs or wait_seconds <= 0:
            return msgs
        cond = self._cond(agent_id)
        deadline = asyncio.get_event_loop().time() + wait_seconds
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return []
            async with cond:
                try:
                    await asyncio.wait_for(cond.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    return []
            msgs = await self.runs.list_messages(self.run_id, to_agent_id=agent_id, task_ids=task_ids, unread_only=unread_only)
            if msgs:
                return msgs

    async def mark_read(self, msgs: list[Message], reader_id: str) -> None:
        if not msgs:
            return
        await self.runs.mark_read([m.message_id for m in msgs])
        await self.events.append(self.run_id, "message.read",
                                 {"message_ids": [m.message_id for m in msgs], "count": len(msgs)},
                                 actor_id=reader_id, actor_kind="agent", task_id=msgs[0].task_id)

    async def unread_count(self, agent_id: str) -> int:
        return len(await self.runs.list_messages(self.run_id, to_agent_id=agent_id, unread_only=True))

    def to_dict(self, m: Message) -> dict[str, Any]:
        return m.model_dump()
