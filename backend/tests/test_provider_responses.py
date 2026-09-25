"""Malformed provider responses become ProviderErrors the worker can retry, not internal errors.

These use an in-memory HTTP transport to shape the server's bytes; they say nothing about real model behaviour."""
import json
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from agentteam.providers.base import LLMRequest, ProviderError, parse_retry_after
from agentteam.providers.openai_compat_driver import OpenAICompatDriver


def _driver(handler):
    d = OpenAICompatDriver("c", None, "http://provider.invalid/v1")
    d.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return d


def _req():
    return LLMRequest(model="m", system="s", messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}])


@pytest.mark.parametrize("body,ctype", [("<html>502 Bad Gateway</html>", "text/html"), ('{"choices": [', "application/json"),
                                        ("[1, 2]", "application/json")])
async def test_non_json_or_non_object_body_is_a_retryable_provider_error(body, ctype):
    d = _driver(lambda request: httpx.Response(200, content=body.encode(), headers={"content-type": ctype}))
    try:
        with pytest.raises(ProviderError) as ei:
            await d.complete(_req())
        assert ei.value.kind == "server" and ei.value.retryable
    finally:
        await d.aclose()


async def test_odd_but_valid_shapes_do_not_crash():
    body = {"choices": [{"message": {"content": None, "tool_calls": [
        "garbage", {"id": "a", "function": {"name": "ping", "arguments": {"ok": True}}},
        {"id": "b", "function": {"name": "ping", "arguments": "[1]"}}]}, "finish_reason": "tool_calls"}], "usage": "n/a"}
    d = _driver(lambda request: httpx.Response(200, json=body))
    try:
        resp = await d.complete(_req())
        assert [(c.id, c.arguments) for c in resp.tool_calls] == [("a", {"ok": True}), ("b", {"_raw": "[1]"})]
        assert resp.text == "" and resp.usage.input_tokens == 0
    finally:
        await d.aclose()


async def test_rate_limit_with_http_date_retry_after():
    later = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=40), usegmt=True)
    d = _driver(lambda request: httpx.Response(429, headers={"retry-after": later}))
    try:
        with pytest.raises(ProviderError) as ei:
            await d.complete(_req())
        assert ei.value.kind == "rate_limit" and 30 <= ei.value.retry_after <= 41
    finally:
        await d.aclose()


def test_parse_retry_after_forms():
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("1.5") == 1.5
    assert parse_retry_after("Fri, 25 Sep 2026 12:00:30 GMT", now=now.timestamp()) == 30.0
    assert parse_retry_after("Fri, 25 Sep 2026 11:59:00 GMT", now=now.timestamp()) == 0.0
    for bad in (None, "", "soon", "nan", "inf", "-5x"):
        assert parse_retry_after(bad) is None
    assert parse_retry_after("-5") == 0.0
