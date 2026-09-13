"""OpenAI-compatible chat-completions driver (also used for Ollama's /v1 endpoint).

This is a *compat* driver: tool calling and JSON-schema output depend on the actual server/model.
The probe verifies both before a connection can be used.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .base import LLMRequest, LLMResponse, ProbeResult, ProviderError, ProviderUsage, ToolCall, ToolSpec


class OpenAICompatDriver:
    kind = "real"

    def __init__(self, connection_id: str, api_key: str | None, base_url: str, driver: str = "openai_compatible_chat",
                 timeout: float = 600.0):
        self.connection_id = connection_id
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def aclose(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _convert_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            content = m["content"]
            if isinstance(content, str):
                out.append({"role": m["role"], "content": content})
                continue
            if m["role"] == "user":
                texts, tool_results = [], []
                for b in content:
                    if b["type"] == "text":
                        texts.append(b["text"])
                    elif b["type"] == "tool_result":
                        c = b.get("content")
                        tool_results.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                             "content": c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)})
                out.extend(tool_results)
                if texts:
                    out.append({"role": "user", "content": "\n".join(texts)})
            else:
                text = "".join(b.get("text", "") for b in content if b["type"] == "text")
                calls = [{"id": b["id"], "type": "function",
                          "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)}}
                         for b in content if b["type"] == "tool_use"]
                msg: dict[str, Any] = {"role": "assistant", "content": text or None}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
        return out

    async def complete(self, req: LLMRequest) -> LLMResponse:
        body: dict[str, Any] = {
            "model": req.model,
            "messages": self._convert_messages(req.system, req.messages),
            "max_tokens": req.max_tokens,
        }
        # Role execution and capability checks depend on reproducible tool/JSON
        # output. Ollama's server default is suited to creative text, not this.
        if self.driver == 'ollama':
            body['temperature'] = 0
        if req.tools:
            body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                              "parameters": t.input_schema}} for t in req.tools]
        if req.json_schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "output", "schema": req.json_schema,
                                                                               "strict": False}}
        try:
            r = await self.client.post(f"{self.base_url}/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise ProviderError("timeout", "request timed out", retryable=True) from e
        except httpx.HTTPError as e:
            raise ProviderError("connection", f"connection error: {type(e).__name__}", retryable=True) from e
        if r.status_code == 401 or r.status_code == 403:
            raise ProviderError("auth", "authentication failed", status=r.status_code)
        if r.status_code == 429:
            ra = r.headers.get("retry-after")
            raise ProviderError("rate_limit", "rate limited", status=429, retryable=True,
                                retry_after=float(ra) if ra and ra.replace(".", "", 1).isdigit() else None)
        if r.status_code >= 500:
            raise ProviderError("server", f"server error {r.status_code}", status=r.status_code, retryable=True)
        if r.status_code >= 400:
            raise ProviderError("bad_request", f"bad request {r.status_code}: {r.text[:300]}", status=r.status_code)
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = msg.get("content") or ""
        calls: list[ToolCall] = []
        raw: list[dict[str, Any]] = []
        if text:
            raw.append({"type": "text", "text": text})
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments")}
            calls.append(ToolCall(id=tc.get("id") or f"call_{len(calls)}", name=fn.get("name", ""), arguments=args))
            raw.append({"type": "tool_use", "id": calls[-1].id, "name": calls[-1].name, "input": args})
        u = data.get("usage") or {}
        usage = ProviderUsage(input_tokens=int(u.get("prompt_tokens") or 0), output_tokens=int(u.get("completion_tokens") or 0))
        finish = choice.get("finish_reason") or "stop"
        stop = "tool_use" if calls else ("max_tokens" if finish == "length" else "end_turn")
        return LLMResponse(text=text, tool_calls=calls, stop_reason=stop, usage=usage,
                           model_reported=data.get("model"), request_id=r.headers.get("x-request-id"), raw_content=raw)

    async def probe(self, model: str) -> ProbeResult:
        usage = ProviderUsage()
        try:
            r1 = await self.complete(LLMRequest(
                model=model, system="You are a connectivity probe. Call the tool `ping` exactly once with ok=true.",
                messages=[{"role": "user", "content": [{"type": "text", "text": "Call ping now."}]}],
                tools=[ToolSpec("ping", "Connectivity probe.", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                               "required": ["ok"]})], max_tokens=256))
            usage.input_tokens += r1.usage.input_tokens; usage.output_tokens += r1.usage.output_tokens
            tool_ok = (len(r1.tool_calls) == 1 and r1.tool_calls[0].name == 'ping'
                       and r1.tool_calls[0].arguments.get('ok') is True)
            r2 = await self.complete(LLMRequest(
                model=model, system="Return the requested JSON only.",
                messages=[{"role": "user", "content": [{"type": "text", "text": "Return {\"ok\": true}."}]}],
                json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}, max_tokens=128))
            usage.input_tokens += r2.usage.input_tokens; usage.output_tokens += r2.usage.output_tokens
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
