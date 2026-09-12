"""Anthropic Messages API driver (official SDK)."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from .base import LLMRequest, LLMResponse, ProbeResult, ProviderError, ProviderUsage, ToolCall, ToolSpec

# Models that take adaptive thinking (everything current except Haiku 4.5 and pre-4.6 models).
def _supports_adaptive(model: str) -> bool:
    m = model.lower()
    if "haiku" in m:
        return False
    for old in ("-3-", "-4-0", "-4-1", "-4-5", "claude-3"):
        if old in m:
            return False
    return True


def _supports_effort(model: str) -> bool:
    return _supports_adaptive(model)


class AnthropicDriver:
    driver = "anthropic_messages"
    kind = "real"

    def __init__(self, connection_id: str, api_key: str | None, base_url: str | None = None,
                 timeout: float = 600.0, refusal_fallback: bool = False):
        self.connection_id = connection_id
        kwargs: dict[str, Any] = {"timeout": timeout, "max_retries": 2}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url and base_url.rstrip("/") != "https://api.anthropic.com":
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)
        self.refusal_fallback = refusal_fallback

    async def aclose(self) -> None:
        await self.client.close()

    @staticmethod
    def _tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        out = []
        for i, t in enumerate(tools):
            d: dict[str, Any] = {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            if i == len(tools) - 1:
                d["cache_control"] = {"type": "ephemeral"}
            out.append(d)
        return out

    async def complete(self, req: LLMRequest) -> LLMResponse:
        params: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "system": [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}],
            "messages": req.messages,
        }
        if req.tools:
            params["tools"] = self._tools(req.tools)
        if _supports_adaptive(req.model):
            params["thinking"] = {"type": "adaptive"}
        output_config: dict[str, Any] = {}
        if req.effort and _supports_effort(req.model):
            output_config["effort"] = req.effort
        if req.json_schema:
            output_config["format"] = {"type": "json_schema", "schema": req.json_schema}
        if output_config:
            params["output_config"] = output_config
        try:
            if self.refusal_fallback:
                resp = await self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
            else:
                resp = await self.client.messages.create(**params)
        except anthropic.AuthenticationError as e:
            raise ProviderError("auth", "authentication failed", status=401) from e
        except anthropic.PermissionDeniedError as e:
            raise ProviderError("auth", "permission denied", status=403) from e
        except anthropic.NotFoundError as e:
            raise ProviderError("bad_request", f"model or endpoint not found: {req.model}", status=404) from e
        except anthropic.RateLimitError as e:
            ra = e.response.headers.get("retry-after") if getattr(e, "response", None) is not None else None
            raise ProviderError("rate_limit", "rate limited", status=429, retryable=True,
                                retry_after=float(ra) if ra else None) from e
        except anthropic.BadRequestError as e:
            raise ProviderError("bad_request", _safe_msg(e), status=400) from e
        except anthropic.APIStatusError as e:
            raise ProviderError("server" if e.status_code >= 500 else "bad_request", _safe_msg(e),
                                status=e.status_code, retryable=e.status_code >= 500) from e
        except anthropic.APITimeoutError as e:
            raise ProviderError("timeout", "request timed out", retryable=True) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("connection", "connection error", retryable=True) from e

        content = [b.model_dump(exclude_none=True) for b in resp.content]
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input or {})) for b in resp.content if b.type == "tool_use"]
        u = resp.usage
        usage = ProviderUsage(
            input_tokens=u.input_tokens or 0, output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
        refusal = None
        if resp.stop_reason == "refusal":
            sd = getattr(resp, "stop_details", None)
            refusal = {"category": getattr(sd, "category", None), "explanation": getattr(sd, "explanation", None)}
        return LLMResponse(
            text=text, tool_calls=calls, stop_reason=resp.stop_reason or "end_turn", usage=usage,
            model_reported=getattr(resp, "model", None), request_id=getattr(resp, "_request_id", None),
            raw_content=content, refusal=refusal,
        )

    async def probe(self, model: str) -> ProbeResult:
        """Small real call that checks tool calling and JSON-schema output. Costs a few hundred tokens."""
        usage = ProviderUsage()
        try:
            r1 = await self.complete(LLMRequest(
                model=model, system="You are a connectivity probe. Call the tool `ping` exactly once with ok=true.",
                messages=[{"role": "user", "content": [{"type": "text", "text": "Call ping now."}]}],
                tools=[ToolSpec("ping", "Connectivity probe.", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                               "required": ["ok"], "additionalProperties": False})],
                max_tokens=512, effort="low",
            ))
            usage.input_tokens += r1.usage.input_tokens; usage.output_tokens += r1.usage.output_tokens
            tool_ok = any(c.name == "ping" for c in r1.tool_calls)
            r2 = await self.complete(LLMRequest(
                model=model, system="Return the requested JSON.",
                messages=[{"role": "user", "content": [{"type": "text", "text": "Return {\"ok\": true}."}]}],
                json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                             "additionalProperties": False},
                max_tokens=256, effort="low",
            ))
            usage.input_tokens += r2.usage.input_tokens; usage.output_tokens += r2.usage.output_tokens
            json_ok = False
            try:
                json_ok = json.loads(r2.text).get("ok") is True
            except Exception:
                json_ok = False
            return ProbeResult(ok=tool_ok and json_ok, driver=self.driver, model_requested=model,
                               model_reported=r1.model_reported, tool_calling=tool_ok, json_schema=json_ok,
                               error=None if (tool_ok and json_ok) else "tool calling or json schema output not confirmed",
                               usage=usage, request_id=r1.request_id)
        except ProviderError as e:
            return ProbeResult(ok=False, driver=self.driver, model_requested=model, model_reported=None,
                               tool_calling=False, json_schema=False, error=f"{e.kind}: {e}", usage=usage)


def _safe_msg(e: Exception) -> str:
    msg = getattr(e, "message", None) or str(e)
    return msg[:500]
