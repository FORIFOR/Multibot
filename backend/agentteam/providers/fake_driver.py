"""Scripted provider for deterministic tests ONLY.

It is never selectable from a config file (see config.loader). Runs that use it are marked
provider_kind="fake" and the UI labels them. It must not be used to claim a real-LLM result.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable

from .base import LLMRequest, LLMResponse, ProbeResult, ProviderUsage, ToolCall

Script = Callable[[LLMRequest], LLMResponse | Awaitable[LLMResponse]]


def tool_response(name: str, arguments: dict[str, Any], *, text: str = "", call_id: str | None = None,
                  in_tokens: int = 500, out_tokens: int = 100) -> LLMResponse:
    cid = call_id or f"call_{name}_{abs(hash(repr(sorted(arguments.items()))))%100000}"
    raw: list[dict[str, Any]] = []
    if text:
        raw.append({"type": "text", "text": text})
    raw.append({"type": "tool_use", "id": cid, "name": name, "input": arguments})
    return LLMResponse(text=text, tool_calls=[ToolCall(cid, name, arguments)], stop_reason="tool_use",
                       usage=ProviderUsage(in_tokens, out_tokens), model_reported="fake-model", raw_content=raw)


def text_response(text: str, *, in_tokens: int = 500, out_tokens: int = 100) -> LLMResponse:
    return LLMResponse(text=text, tool_calls=[], stop_reason="end_turn", usage=ProviderUsage(in_tokens, out_tokens),
                       model_reported="fake-model", raw_content=[{"type": "text", "text": text}])


class FakeProvider:
    driver = "fake"
    kind = "fake"

    def __init__(self, script: Script, connection_id: str = "fake"):
        self.script = script
        self.connection_id = connection_id
        self.calls: list[LLMRequest] = []

    async def complete(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        delay_ms = int(os.environ.get("AGENTTEAM_FAKE_DELAY_MS", "0") or 0)  # demo pacing only
        if delay_ms:
            await asyncio.sleep(delay_ms / 1000)
        out = self.script(req)
        if hasattr(out, "__await__"):
            out = await out  # type: ignore[assignment]
        return out  # type: ignore[return-value]

    async def probe(self, model: str) -> ProbeResult:
        return ProbeResult(ok=True, driver="fake", model_requested=model, model_reported="fake-model", tool_calling=True,
                           json_schema=True, error=None, usage=ProviderUsage())

    async def aclose(self) -> None:
        return None
