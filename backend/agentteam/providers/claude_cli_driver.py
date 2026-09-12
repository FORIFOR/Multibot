"""claude_cli driver: runs agent sessions through the local Claude Code CLI (`claude -p`).

No API key is needed; the CLI uses the machine's own Claude login. Differences from the API drivers:
- Claude Code owns the agentic loop for a session. Our tools are exposed to it as MCP tools via a
  stdio proxy (claude_cli_mcp) that forwards every call to this process's ToolGateway, so policy,
  counting and event recording are unchanged. Built-in Claude Code tools are disabled (--tools "").
- Cost and usage come from the CLI's JSON result (list-price accounting, `total_cost_usd`); the
  model actually used comes from `modelUsage`, never from the model's own claims.
- Single-shot completions (planning, reports) use --json-schema structured output.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any

from .base import LLMRequest, LLMResponse, ProbeResult, ProviderError, ProviderUsage, ToolSpec


@dataclass
class CliResult:
    ok: bool
    text: str
    structured: Any
    usage: ProviderUsage
    cost_usd: float
    model_reported: str | None
    models: dict[str, Any]
    num_turns: int
    terminal_reason: str | None
    permission_denials: list[Any]
    session_id: str | None
    error: str | None = None
    stderr: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def parse_cli_result(stdout: str, stderr: str = "", returncode: int = 0) -> CliResult:
    """Parse `claude -p --output-format json` output (the last JSON object on stdout)."""
    data: dict[str, Any] | None = None
    for line in reversed([l for l in stdout.splitlines() if l.strip()]):
        try:
            cand = json.loads(line)
            if isinstance(cand, dict) and cand.get("type") == "result":
                data = cand
                break
        except json.JSONDecodeError:
            continue
    if data is None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return CliResult(ok=False, text="", structured=None, usage=ProviderUsage(), cost_usd=0.0, model_reported=None,
                             models={}, num_turns=0, terminal_reason=None, permission_denials=[], session_id=None,
                             error=f"unparseable CLI output (exit {returncode}): {stderr[-400:] or stdout[-400:]}", stderr=stderr)
    u = data.get("usage") or {}
    usage = ProviderUsage(input_tokens=int(u.get("input_tokens") or 0), output_tokens=int(u.get("output_tokens") or 0),
                          cache_read_tokens=int(u.get("cache_read_input_tokens") or 0),
                          cache_write_tokens=int(u.get("cache_creation_input_tokens") or 0))
    models = data.get("modelUsage") or {}
    main_model = None
    if models:
        main_model = max(models.items(), key=lambda kv: float(kv[1].get("costUSD") or 0))[0]
        # sum tokens across models so usage reflects the whole session, not only the last iteration
        usage = ProviderUsage(
            input_tokens=sum(int(m.get("inputTokens") or 0) for m in models.values()),
            output_tokens=sum(int(m.get("outputTokens") or 0) for m in models.values()),
            cache_read_tokens=sum(int(m.get("cacheReadInputTokens") or 0) for m in models.values()),
            cache_write_tokens=sum(int(m.get("cacheCreationInputTokens") or 0) for m in models.values()))
    is_error = bool(data.get("is_error")) or data.get("subtype") not in (None, "success")
    return CliResult(ok=not is_error, text=str(data.get("result") or ""), structured=data.get("structured_output"), usage=usage,
                     cost_usd=float(data.get("total_cost_usd") or 0.0), model_reported=main_model, models=models,
                     num_turns=int(data.get("num_turns") or 0), terminal_reason=data.get("terminal_reason"),
                     permission_denials=list(data.get("permission_denials") or []), session_id=data.get("session_id"),
                     error=(str(data.get("result") or data.get("subtype")) if is_error else None), stderr=stderr, raw=data)


class ClaudeCliDriver:
    driver = "claude_cli"
    kind = "real"
    supports_sessions = True

    def __init__(self, connection_id: str, binary: str | None = None):
        self.connection_id = connection_id
        self.binary = binary or os.environ.get("AGENTTEAM_CLAUDE_BIN") or "claude"
        if shutil.which(self.binary) is None:
            raise ProviderError("unsupported", f"claude CLI not found on PATH ({self.binary}); install Claude Code and run `claude` once to log in")

    async def aclose(self) -> None:
        return None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _flatten(messages: list[dict[str, Any]]) -> str:
        """Single-shot prompt from canonical messages (used for plan/report: 1–3 text turns)."""
        parts = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if not text:
                continue
            parts.append(text if role == "user" else f"[Your previous answer]\n{text}")
        return "\n\n".join(parts)

    async def _exec(self, argv: list[str], *, timeout: float, cancel_event: asyncio.Event | None = None,
                    cwd: str | None = None) -> CliResult:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_API_KEY", "OPENAI_API_KEY"))}
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        proc = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                    stdin=asyncio.subprocess.DEVNULL, env=env, cwd=cwd)

        async def waiter():
            return await proc.communicate()

        comm = asyncio.create_task(waiter())
        watchers = [comm]
        cancel_task = asyncio.create_task(cancel_event.wait()) if cancel_event else None
        if cancel_task:
            watchers.append(cancel_task)
        done, _ = await asyncio.wait(watchers, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if comm not in done:
            proc.kill()
            try:
                await asyncio.wait_for(comm, timeout=5)
            except Exception:
                pass
            if cancel_task:
                cancel_task.cancel()
            reason = "cancelled" if (cancel_task and cancel_task in done) else "timeout"
            return CliResult(ok=False, text="", structured=None, usage=ProviderUsage(), cost_usd=0.0, model_reported=None, models={},
                             num_turns=0, terminal_reason=reason, permission_denials=[], session_id=None, error=f"claude cli {reason}")
        if cancel_task:
            cancel_task.cancel()
        out, err = comm.result()
        return parse_cli_result(out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace"), proc.returncode or 0)

    def _base_argv(self, model: str, effort: str | None, max_budget_usd: float | None) -> list[str]:
        argv = [self.binary, "-p", "--output-format", "json", "--no-session-persistence", "--model", model]
        if effort:
            argv += ["--effort", effort]
        if max_budget_usd:
            argv += ["--max-budget-usd", f"{max_budget_usd:.4f}"]
        return argv

    # ------------------------------------------------------------------ single-shot completion (no tools)
    async def complete(self, req: LLMRequest) -> LLMResponse:
        if req.tools:
            raise ProviderError("unsupported", "claude_cli complete() is single-shot; tool loops use run_session()")
        argv = self._base_argv(req.model, req.effort, req.metadata.get("max_budget_usd")) + [
            "--system-prompt", req.system, "--tools", "", "--max-turns", "1", "--strict-mcp-config"]
        if req.json_schema:
            argv += ["--json-schema", json.dumps(req.json_schema)]
        argv.append(self._flatten(req.messages))
        res = await self._exec(argv, timeout=float(req.metadata.get("timeout") or 600))
        if not res.ok:
            raise ProviderError("server" if "timeout" in (res.error or "") else "bad_request", res.error or "claude cli failed",
                                retryable="timeout" in (res.error or ""))
        text = json.dumps(res.structured, ensure_ascii=False) if res.structured is not None else res.text
        return LLMResponse(text=text, tool_calls=[], stop_reason="end_turn", usage=res.usage, model_reported=res.model_reported,
                           request_id=res.session_id, raw_content=[{"type": "text", "text": text}],
                           refusal=None, )

    # ------------------------------------------------------------------ tool session (Claude Code owns the loop)
    async def run_session(self, *, system: str, prompt: str, gateway_url: str, tool_names: list[str], model: str,
                          effort: str | None, max_turns: int, max_budget_usd: float, timeout: float,
                          cancel_event: asyncio.Event | None = None, cwd: str | None = None) -> CliResult:
        mcp_cfg = json.dumps({"mcpServers": {"agentteam": {"command": sys.executable,
                                                            "args": ["-m", "agentteam.providers.claude_cli_mcp", "--url", gateway_url]}}})
        allowed = ",".join(f"mcp__agentteam__{n}" for n in tool_names)
        argv = self._base_argv(model, effort, max_budget_usd) + [
            "--system-prompt", system, "--tools", "", "--mcp-config", mcp_cfg, "--strict-mcp-config",
            "--allowedTools", allowed, "--max-turns", str(max_turns), "--permission-mode", "dontAsk", prompt]
        return await self._exec(argv, timeout=timeout, cancel_event=cancel_event, cwd=cwd)

    # ------------------------------------------------------------------ probe
    async def probe(self, model: str) -> ProbeResult:
        from ..runtime.session_broker import get_broker

        usage = ProviderUsage()
        called: dict[str, Any] = {}

        class _PingGateway:
            ctx = None

            def specs(self):
                return [ToolSpec("ping", "Connectivity probe.", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                                "required": ["ok"], "additionalProperties": False})]

            async def call(self, name, args, causation_id=None):
                called.update(args)
                return "pong"

        try:
            broker = await get_broker()
            token = broker.register(_PingGateway())
            try:
                r1 = await self.run_session(system="You are a connectivity probe. Call the tool `ping` with ok=true exactly once, then reply 'done'.",
                                            prompt="Call ping now.", gateway_url=broker.url(token), tool_names=["ping"], model=model,
                                            effort="low", max_turns=3, max_budget_usd=0.5, timeout=180)
            finally:
                broker.unregister(token)
            usage.input_tokens += r1.usage.input_tokens; usage.output_tokens += r1.usage.output_tokens
            tool_ok = called.get("ok") is True
            r2 = await self.complete(LLMRequest(model=model, system="Return the requested JSON.",
                                                messages=[{"role": "user", "content": [{"type": "text", "text": "Return {\"ok\": true}."}]}],
                                                json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                                                             "additionalProperties": False}, effort="low",
                                                metadata={"max_budget_usd": 0.3, "timeout": 120}))
            usage.input_tokens += r2.usage.input_tokens; usage.output_tokens += r2.usage.output_tokens
            try:
                json_ok = json.loads(r2.text).get("ok") is True
            except Exception:
                json_ok = False
            err = None if (tool_ok and json_ok) else f"tool_calling={tool_ok} json_schema={json_ok} {r1.error or ''}"
            return ProbeResult(ok=tool_ok and json_ok, driver=self.driver, model_requested=model, model_reported=r1.model_reported or r2.model_reported,
                               tool_calling=tool_ok, json_schema=json_ok, error=err, usage=usage, request_id=r1.session_id)
        except ProviderError as e:
            return ProbeResult(ok=False, driver=self.driver, model_requested=model, model_reported=None, tool_calling=False,
                               json_schema=False, error=f"{e.kind}: {e}", usage=usage)
