"""SessionBroker: a loopback HTTP endpoint that exposes one ToolGateway per session to the MCP proxy.

Started lazily in-process (uvicorn on 127.0.0.1, random port). Each session gets a random token;
unknown tokens get 404. Nothing here bypasses the gateway: authorization, counting, redaction and
event recording all happen inside ToolGateway.call().
"""
from __future__ import annotations

import asyncio
import secrets
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class SessionBroker:
    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None
        self.port: int | None = None
        self._lock = asyncio.Lock()

    async def _tools(self, request: Request) -> JSONResponse:
        gw = self._sessions.get(request.path_params["token"])
        if gw is None:
            return JSONResponse({"error": "unknown session"}, status_code=404)
        return JSONResponse({"tools": [{"name": s.name, "description": s.description, "input_schema": s.input_schema} for s in gw.specs()]})

    async def _call(self, request: Request) -> JSONResponse:
        gw = self._sessions.get(request.path_params["token"])
        if gw is None:
            return JSONResponse({"error": "unknown session"}, status_code=404)
        body = await request.json()
        args = body.get("arguments") or {}
        try:
            out = await gw.call(request.path_params["name"], args, causation_id=getattr(gw.ctx, "causation_id", None))
        except Exception as e:  # fatal policy violation etc.: report to the model, session ends on next check
            out = f"DENIED (fatal): {e}"
        return JSONResponse({"result": out, "is_error": out.startswith(("ERROR", "DENIED", "REJECTED", "NOT FOUND"))})

    async def start(self) -> None:
        async with self._lock:
            if self._server is not None:
                return
            app = Starlette(routes=[Route("/s/{token}/tools", self._tools, methods=["GET"]),
                                    Route("/s/{token}/tools/{name}", self._call, methods=["POST"])])
            config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
            self._server = uvicorn.Server(config)
            self._task = asyncio.create_task(self._server.serve())
            for _ in range(200):
                await asyncio.sleep(0.02)
                servers = getattr(self._server, "servers", None)
                if servers:
                    sock = servers[0].sockets[0]
                    self.port = sock.getsockname()[1]
                    return
            raise RuntimeError("session broker failed to start")

    def register(self, gateway: Any) -> str:
        token = secrets.token_urlsafe(24)
        self._sessions[token] = gateway
        return token

    def unregister(self, token: str) -> None:
        self._sessions.pop(token, None)

    def url(self, token: str) -> str:
        return f"http://127.0.0.1:{self.port}/s/{token}"

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            if self._task:
                try:
                    await asyncio.wait_for(self._task, timeout=5)
                except Exception:
                    pass
            self._server = None
            self._task = None


_broker: SessionBroker | None = None


async def get_broker() -> SessionBroker:
    global _broker
    if _broker is None:
        _broker = SessionBroker()
    await _broker.start()
    return _broker
