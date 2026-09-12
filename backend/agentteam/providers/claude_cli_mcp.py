"""stdio MCP server that proxies tool calls from a `claude -p` subprocess to the run's ToolGateway.

Spawned by ClaudeCliDriver via --mcp-config. It knows nothing about the run: it fetches the tool
list from the session URL (localhost, per-session random token) and forwards each call over HTTP.
Every call therefore still passes through PolicyEngine and is recorded as a tool.called event.

    python -m agentteam.providers.claude_cli_mcp --url http://127.0.0.1:PORT/s/TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server


async def main(url: str) -> None:
    client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))
    r = await client.get(f"{url}/tools")
    r.raise_for_status()
    specs = r.json()["tools"]

    async def on_list_tools(ctx, params):
        return types.ListToolsResult(tools=[
            types.Tool(name=s["name"], description=s["description"], inputSchema=s["input_schema"]) for s in specs])

    async def on_call_tool(ctx, params):
        try:
            resp = await client.post(f"{url}/tools/{params.name}", json={"arguments": params.arguments or {}})
            data = resp.json()
            text = data.get("result", "")
            is_error = bool(data.get("is_error"))
        except Exception as e:  # keep the CLI alive; surface the failure to the model
            text, is_error = f"ERROR (proxy): {type(e).__name__}: {e}", True
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], isError=is_error)

    server = Server("agentteam", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
    await client.aclose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    args = ap.parse_args()
    try:
        asyncio.run(main(args.url))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(json.dumps({"proxy_error": str(e)}), file=sys.stderr)
        sys.exit(1)
