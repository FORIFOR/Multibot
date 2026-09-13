"""claude_cli driver: result parsing and the session broker round trip (no CLI spawned here)."""
import json

import httpx
import pytest

from agentteam.providers.base import ToolSpec
from agentteam.providers.claude_cli_driver import parse_cli_result
from agentteam.runtime.session_broker import SessionBroker

SAMPLE = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "total_cost_usd": 0.0561,
          "usage": {"input_tokens": 2, "output_tokens": 129, "cache_read_input_tokens": 12361, "cache_creation_input_tokens": 0},
          "modelUsage": {"claude-haiku-4-5-20251001": {"inputTokens": 911, "outputTokens": 12, "costUSD": 0.00097},
                         "claude-sonnet-5": {"inputTokens": 2, "outputTokens": 129, "cacheReadInputTokens": 12361, "costUSD": 0.0037}},
          "permission_denials": [], "terminal_reason": "completed", "result": "done", "session_id": "abc"}


def test_parse_cli_result_attributes_model_and_cost():
    r = parse_cli_result("noise line\n" + json.dumps(SAMPLE))
    assert r.ok and r.text == "done" and r.num_turns == 3 and r.cost_usd == 0.0561
    assert r.model_reported == "claude-sonnet-5"  # the model that did the work, not the small helper
    assert r.usage.output_tokens == 141 and r.usage.cache_read_tokens == 12361


def test_parse_cli_result_error_and_garbage():
    bad = dict(SAMPLE, is_error=True, subtype="error_max_turns", result="Reached max turns")
    r = parse_cli_result(json.dumps(bad))
    assert not r.ok and "max turns" in (r.error or "").lower()
    g = parse_cli_result("", "boom", 1)
    assert not g.ok and "unparseable" in g.error


class _Gateway:
    ctx = None
    calls = []

    def specs(self):
        return [ToolSpec("echo", "Echo", {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]})]

    async def call(self, name, args, causation_id=None):
        self.calls.append((name, args))
        return "DENIED (tool_scope): nope" if name != "echo" else f"echo:{args['x']}"


async def test_session_broker_roundtrip():
    b = SessionBroker()
    await b.start()
    try:
        gw = _Gateway()
        token = b.register(gw)
        async with httpx.AsyncClient() as c:
            r = await c.get(b.url(token) + "/tools")
            assert r.status_code == 200 and r.json()["tools"][0]["name"] == "echo"
            r = await c.post(b.url(token) + "/tools/echo", json={"arguments": {"x": "hi"}})
            assert r.json() == {"result": "echo:hi", "is_error": False}
            r = await c.post(b.url(token) + "/tools/other", json={"arguments": {}})
            assert r.json()["is_error"] is True
            r = await c.get(b.url("wrong") + "/tools")
            assert r.status_code == 404
        b.unregister(token)
        async with httpx.AsyncClient() as c:
            assert (await c.get(b.url(token) + "/tools")).status_code == 404
    finally:
        await b.stop()


def test_probe_cli_reports_missing_binary_as_structured_json(tmp_path, monkeypatch, capsys):
    """`agentteam probe` with the claude binary absent prints a JSON reason and exits 2 (no traceback)."""
    from agentteam.cli import main
    monkeypatch.setenv("AGENTTEAM_CLAUDE_BIN", "claude-binary-that-does-not-exist")
    monkeypatch.setenv("AGENTTEAM_NO_SEATBELT", "1")
    rc = main(["probe", "--data-dir", str(tmp_path / "data")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and out["ok"] is False and "not found on PATH" in out["error"] and "Install Claude Code" in out["hint"]


def test_probe_hint_for_not_logged_in():
    from agentteam.cli import _probe_hint
    assert "log in" in _probe_hint("bad_request: Not logged in · Please run /login")
    assert _probe_hint("something else") is None
