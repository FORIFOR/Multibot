"""PolicyEngine: enforces budgets, counters, scopes and cancellation. Prompt wording never changes these."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from ..config.models import Limits, ModelPrice
from ..contracts import Usage
from ..providers.base import ProviderUsage
from ..providers.pricing import cost_of, estimate_max_cost


class PolicyViolation(Exception):
    def __init__(self, code: str, message: str, *, fatal: bool = False):
        super().__init__(message)
        self.code = code
        self.fatal = fatal


class Cancelled(Exception):
    pass


@dataclass
class Reservation:
    amount: float


@dataclass
class PolicyEngine:
    limits: Limits
    usage: Usage = field(default_factory=Usage)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    peer_messages: dict[str, int] = field(default_factory=dict)
    revision_rounds: dict[str, int] = field(default_factory=dict)
    denials: int = 0

    # ---- cancellation
    def cancel(self) -> None:
        self.cancel_event.set()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def check_cancel(self) -> None:
        if self.cancelled:
            raise Cancelled()

    # ---- model call budget with reservation
    def reserve_model_call(self, price: ModelPrice | None, est_input_tokens: int, max_output_tokens: int) -> Reservation:
        self.check_cancel()
        if self.usage.model_calls >= self.limits.max_model_calls:
            raise PolicyViolation("max_model_calls", f"model call limit {self.limits.max_model_calls} reached", fatal=True)
        if price is None:
            raise PolicyViolation("unknown_pricing", "model price unknown; cannot reserve budget", fatal=True)
        amount = estimate_max_cost(price, est_input_tokens, max_output_tokens)
        if self.usage.cost_usd + self.usage.reserved_usd + amount > self.limits.budget_usd:
            raise PolicyViolation(
                "budget", f"budget {self.limits.budget_usd:.2f} USD would be exceeded "
                          f"(spent {self.usage.cost_usd:.4f} + reserved {self.usage.reserved_usd:.4f} + est {amount:.4f})",
                fatal=True)
        self.usage.reserved_usd += amount
        self.usage.model_calls += 1
        return Reservation(amount)

    def settle_model_call(self, res: Reservation, price: ModelPrice | None, usage: ProviderUsage) -> float:
        self.usage.reserved_usd = max(0.0, self.usage.reserved_usd - res.amount)
        cost = cost_of(usage, price) if price else 0.0
        self.usage.cost_usd += cost
        self.usage.input_tokens += usage.input_tokens
        self.usage.output_tokens += usage.output_tokens
        self.usage.cache_read_tokens += usage.cache_read_tokens
        self.usage.cache_write_tokens += usage.cache_write_tokens
        return cost

    def release(self, res: Reservation) -> None:
        self.usage.reserved_usd = max(0.0, self.usage.reserved_usd - res.amount)

    # ---- tool calls
    def count_tool_call(self) -> None:
        self.check_cancel()
        if self.usage.tool_calls >= self.limits.max_tool_calls:
            raise PolicyViolation("max_tool_calls", f"tool call limit {self.limits.max_tool_calls} reached", fatal=True)
        self.usage.tool_calls += 1

    def check_tool_allowed(self, agent_tools: list[str], tool_name: str) -> None:
        if tool_name not in agent_tools:
            self.denials += 1
            raise PolicyViolation("tool_scope", f"tool {tool_name} is not authorized for this agent")

    def count_peer_message(self, task_id: str) -> None:
        n = self.peer_messages.get(task_id, 0)
        if n >= self.limits.max_peer_messages_per_task:
            raise PolicyViolation("max_peer_messages", f"peer message limit {self.limits.max_peer_messages_per_task} for task {task_id} reached")
        self.peer_messages[task_id] = n + 1

    def next_revision_round(self, task_id: str) -> int | None:
        n = self.revision_rounds.get(task_id, 0)
        if n >= self.limits.max_revision_rounds:
            return None
        self.revision_rounds[task_id] = n + 1
        return n + 1

    # ---- path scopes
    @staticmethod
    def check_write_path(relative_path: str) -> str:
        p = PurePosixPath(relative_path.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or any(part.startswith("~") for part in p.parts) or str(p) in ("", "."):
            raise PolicyViolation("path_scope", f"path {relative_path!r} escapes the task workspace")
        return str(p)

    def snapshot(self) -> dict[str, Any]:
        return {"usage": self.usage.model_dump(), "peer_messages": dict(self.peer_messages),
                "revision_rounds": dict(self.revision_rounds)}
