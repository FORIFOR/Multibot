"""Shared per-run runtime state handed to tools, workers, planner and scheduler."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import AgentTeamConfig, EffectiveAgentConfig
from ..contracts import Approval, Review, Run, TaskResult, TaskState
from ..providers.registry import ProviderRegistry
from ..store.artifact_store import ArtifactStore
from ..store.event_store import EventStore
from ..store.run_store import RunStore
from .mailbox import MessageBus
from .policy import PolicyEngine
from .redaction import Redactor


@dataclass
class RunRuntime:
    run: Run
    config: AgentTeamConfig
    agents: dict[str, EffectiveAgentConfig]
    policy: PolicyEngine
    events: EventStore
    artifacts: ArtifactStore
    runs: RunStore
    bus: MessageBus
    providers: ProviderRegistry
    redactor: Redactor
    data_dir: Path
    require_container: bool = False
    started_monotonic: float = field(default_factory=time.monotonic)
    tasks: dict[str, TaskState] = field(default_factory=dict)
    active_sessions: dict[str, int] = field(default_factory=dict)
    approval_waiters: dict[str, asyncio.Event] = field(default_factory=dict)
    approval_wait_seconds: float = 120.0
    scheduler: Any = None  # set by Scheduler; used by master tools create_task/update_task

    @property
    def run_id(self) -> str:
        return self.run.run_id

    def workspace(self, task_id: str) -> Path:
        p = self.data_dir / self.run_id / "workspaces" / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def remaining_seconds(self) -> float:
        return self.config.limits.timeout_seconds - (time.monotonic() - self.started_monotonic)

    def enabled_agents(self) -> list[EffectiveAgentConfig]:
        return [a for a in self.agents.values() if a.enabled]

    def owned_tasks(self, agent_id: str) -> list[TaskState]:
        return [t for t in self.tasks.values() if t.spec.owner == agent_id]

    async def save_task(self, t: TaskState) -> None:
        self.tasks[t.spec.id] = t
        await self.runs.upsert_task(t)

    async def persist_usage(self) -> None:
        self.run.usage = self.policy.usage
        self.run.usage.wall_seconds = time.monotonic() - self.started_monotonic
        await self.runs.update_run(self.run_id, usage=self.run.usage)


@dataclass
class SessionContext:
    """One agent session: a task attempt, a peer reply, or a master exception session."""
    rt: RunRuntime
    agent: EffectiveAgentConfig
    mode: str  # task | reply | exception | report
    task: TaskState | None = None
    attempt: int = 1
    causation_id: str | None = None
    tools: list[str] = field(default_factory=list)
    # outcomes set by tools
    finished: TaskResult | None = None
    blocked: dict[str, Any] | None = None
    reviews: list[Review] = field(default_factory=list)
    approval_pending: Approval | None = None
    replied: bool = False
    published: list[Any] = field(default_factory=list)

    @property
    def task_id(self) -> str | None:
        return self.task.spec.id if self.task else None

    @property
    def workspace(self) -> Path | None:
        return self.rt.workspace(self.task.spec.id) if self.task else None

    def owned_task_ids(self) -> list[str]:
        ids = [t.spec.id for t in self.rt.owned_tasks(self.agent.agent_id)]
        if self.task and self.task.spec.id not in ids:
            ids.append(self.task.spec.id)
        return ids

    @property
    def review(self) -> Review | None:
        return self.reviews[-1] if self.reviews else None
