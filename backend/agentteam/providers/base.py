"""ProviderAdapter contract. Canonical message format is Anthropic-shaped content blocks:

  {"role": "user"|"assistant", "content": [
      {"type": "text", "text": "..."},
      {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
      {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": false},
      {"type": "thinking", ...}   # passed through unchanged for the producing model only
  ]}
Drivers translate to/from their wire format. Nothing here decides ids or timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class LLMRequest:
    model: str
    system: str
    messages: list[dict[str, Any]]
    tools: list[ToolSpec] = field(default_factory=list)
    max_tokens: int = 8000
    json_schema: dict[str, Any] | None = None  # structured output request
    effort: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)  # agent_id, task_id, purpose (for fakes/logging)


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: ProviderUsage
    model_reported: str | None  # from the provider response, never from the model's self-description
    request_id: str | None = None
    raw_content: list[dict[str, Any]] = field(default_factory=list)  # canonical assistant content to append
    refusal: dict[str, Any] | None = None


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """Retry-After is either delay-seconds or an HTTP-date (RFC 9110 §10.2.3). Unparseable values mean 'no hint'."""
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        from email.utils import parsedate_to_datetime
        import time
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when is None or when.tzinfo is None:
            return None
        seconds = when.timestamp() - (time.time() if now is None else now)
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return None
    return max(0.0, seconds)


class ProviderError(Exception):
    def __init__(self, kind: str, message: str, *, status: int | None = None, retryable: bool = False,
                 retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind  # auth | rate_limit | server | bad_request | connection | timeout | unsupported | refusal
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass
class ProbeResult:
    ok: bool
    driver: str
    model_requested: str
    model_reported: str | None
    tool_calling: bool
    json_schema: bool
    error: str | None
    usage: ProviderUsage
    request_id: str | None = None


class ProviderAdapter(Protocol):
    driver: str
    connection_id: str
    kind: str  # "real" | "fake"

    async def complete(self, req: LLMRequest) -> LLMResponse: ...
    async def probe(self, model: str) -> ProbeResult: ...
    async def aclose(self) -> None: ...


def text_of(content: list[dict[str, Any]]) -> str:
    return "".join(b.get("text", "") for b in content if b.get("type") == "text")
