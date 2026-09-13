"""FastAPI application: runs, events (cursor + SSE), approvals, agents/config, connections, artifacts."""
from __future__ import annotations

import asyncio
import json
import secrets
import ipaddress
import shutil
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sse_starlette.sse import EventSourceResponse

from .. import __version__
from ..config.loader import ConfigError, PKG_ROOT, REPO_ROOT, config_to_yaml, effective_agent, list_skills, load_config_text
from ..config.models import Connection
from ..contracts import RunInputs, RunStatus
from ..projections.views import chat_view, timeline_view
from ..providers.registry import ProviderRegistry
from .service import AppService
from ..security.accounts import digest
from ..security.server import COOKIE

FRONTEND_DIST = PKG_ROOT / "ui"  # built UI bundled inside the package
if not FRONTEND_DIST.is_dir():  # dev checkout without a bundled build
    FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


class CreateRunBody(BaseModel):
    goal: str = Field(min_length=1)
    inputs: RunInputs = Field(default_factory=RunInputs)
    budget_usd: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    start: bool = True


class PatchAgentBody(BaseModel):
    expected_revision: int
    model: str | None = None
    connection_id: str | None = None
    system_prompt_override: str | None = None
    reset_prompt: bool = False
    prompt_mode: str | None = None
    enabled: bool | None = None
    effort: str | None = None
    skill_ids: list[str] | None = None
    tools: list[str] | None = None


class PutConnectionBody(BaseModel):
    expected_revision: int
    driver: str
    base_url: str
    api_key_ref: str | None = None
    refusal_fallback: bool = False
    ollama_thinking: bool | None = None


class PutLimitsBody(BaseModel):
    expected_revision: int
    limits: dict[str, Any]
    defaults: dict[str, Any] | None = None
    pricing: dict[str, Any] | None = None


class ResolveApprovalBody(BaseModel):
    decision: str  # approve | reject | edit
    note: str = ""
    expected_hash: str | None = None
    nonce: str | None = None
    edited_payload: dict[str, Any] | None = None


class ForkBody(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)
    from_seq: int | None = None
    start: bool = True


class LoginBody(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class GrantBody(BaseModel):
    subject: str
    permission: str


def create_app(service: AppService | None = None) -> FastAPI:
    svc = service or AppService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await svc.start()
        app.state.svc = svc
        try:
            yield
        finally:
            await svc.stop()

    app = FastAPI(title="Agent Team", version=__version__, lifespan=lifespan,
                  dependencies=[Depends(svc.access.authorize)],
                  docs_url=None if svc.access.enabled else '/docs',
                  redoc_url=None if svc.access.enabled else '/redoc',
                  openapi_url=None if svc.access.enabled else '/openapi.json')

    @app.middleware('http')
    async def server_boundary(request: Request, call_next):
        request.state.request_id = secrets.token_hex(16)
        host = request.url.hostname
        origin = svc.access.config.public_origin if svc.access.enabled else str(request.base_url).rstrip('/')
        if svc.access.enabled:
            if request.headers.get('host', '').lower() != urlsplit(origin).netloc.lower():
                return JSONResponse({'detail': 'invalid host'}, status_code=400)
        elif host not in ('127.0.0.1', 'localhost', '::1'):
            return JSONResponse({'detail': 'local mode accepts only loopback hosts'}, status_code=400)
        elif request.client:
            try:
                if not ipaddress.ip_address(request.client.host).is_loopback:
                    return JSONResponse({'detail': 'local mode accepts only loopback clients'}, status_code=403)
            except ValueError:
                return JSONResponse({'detail': 'invalid client address'}, status_code=403)
        if request.headers.get('origin') and request.headers['origin'] != origin:
            return JSONResponse({'detail': 'cross-origin access is not allowed'}, status_code=403)
        if request.url.path.startswith('/api/') and request.method not in ('GET', 'HEAD'):
            limit = svc.access.config.max_request_bytes if svc.access.enabled else 2_000_000
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    return JSONResponse({'detail': 'request too large'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        if svc.access.enabled and request.url.path.startswith('/api/') and request.url.path != '/api/health/live':
            await svc.access.audit(request, 'response', response.status_code)
        response.headers['x-request-id'] = request.state.request_id
        response.headers['x-content-type-options'] = 'nosniff'
        response.headers['referrer-policy'] = 'no-referrer'
        response.headers['cache-control'] = 'no-store'
        response.headers.setdefault('content-security-policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if origin.startswith('https://'):
            response.headers['strict-transport-security'] = 'max-age=31536000'
        return response

    @app.get('/api/health/live')
    async def liveness():
        return {'ok': True}

    @app.get('/api/admin/ready')
    async def readiness():
        from ..runtime.sandbox import backend_name
        await svc.db.fetchone('SELECT 1')
        free = shutil.disk_usage(svc.data_dir).free
        problems = svc.manager.precheck(svc.config)
        needs_sandbox = any(a.enabled and set(a.tools) & {'sandbox_run', 'run_check'} for a in svc.config.agents)
        sandbox = await backend_name() if needs_sandbox else 'not_required'
        ready = not svc.stopping and free >= 500 * 1024 * 1024 and not problems and sandbox not in ('none', 'subprocess')
        return JSONResponse({'ready': ready, 'disk_free_bytes': free, 'sandbox_backend': sandbox,
                             'configuration_problems': [p['code'] for p in problems]}, status_code=200 if ready else 503)

    @app.get('/api/admin/metrics', response_class=PlainTextResponse)
    async def metrics():
        counts = await svc.db.fetchall('SELECT status,COUNT(*) AS n FROM runs GROUP BY status')
        body = '# TYPE agentteam_runs gauge\n'
        body += ''.join(f'agentteam_runs{{status="{RunStatus(r["status"]).value}"}} {r["n"]}\n' for r in counts)
        body += '# TYPE agentteam_active_runs gauge\n'
        body += f'agentteam_active_runs {sum(not t.done() for t in svc.manager._tasks.values())}\n'
        body += '# TYPE agentteam_disk_free_bytes gauge\n'
        body += f'agentteam_disk_free_bytes {shutil.disk_usage(svc.data_dir).free}\n'
        return PlainTextResponse(body, media_type='text/plain; version=0.0.4')

    @app.get('/api/auth/status')
    async def auth_status():
        svc.access.reload()
        return {'enabled': svc.access.enabled, 'sso_login_url': '/oauth2/start?rd=/' if svc.access.oidc else None}

    @app.post('/api/auth/login')
    async def login(body: LoginBody, request: Request, response: Response):
        account, token = await svc.access.login(request, body.token)
        response.set_cookie(COOKIE, token, max_age=svc.access.config.session_seconds, httponly=True,
                            secure=svc.access.config.public_origin.startswith('https://'), samesite='strict', path='/')
        return {'subject': account.subject, 'role': account.role, 'organization': svc.access.config.organization}

    @app.get('/api/auth/me')
    async def me(request: Request):
        p = svc.access.principal(request)
        return {'subject': p.subject if p else 'local', 'role': p.role if p else 'admin',
                'display_name': p.display_name if p else '', 'source': p.source if p else 'local',
                'organization': svc.access.config.organization if svc.access.enabled else None}

    @app.post('/api/auth/logout')
    async def logout(request: Request, response: Response):
        await svc.access.logout_oidc(request)
        await svc.db.execute('DELETE FROM auth_sessions WHERE session_digest=?', (digest(request.cookies.get(COOKIE, '')),))
        response.delete_cookie(COOKIE, path='/')
        p = svc.access.principal(request)
        return {'ok': True, 'redirect': '/oauth2/sign_out' if p and p.source == 'oidc' else '/'}

    @app.get('/api/admin/audit')
    async def audit_log(after_id: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000)):
        return [dict(r) for r in await svc.db.fetchall('SELECT * FROM audit_log WHERE id>? ORDER BY id LIMIT ?', (after_id, limit))]

    @app.put('/api/runs/{run_id}/access')
    async def grant_access(run_id: str, body: GrantBody, request: Request):
        if not svc.access.enabled or body.permission not in ('read', 'write', 'revoke'):
            raise HTTPException(400, 'invalid access grant')
        known_oidc = svc.access.config.oidc and body.subject not in svc.access.config.oidc.disabled_subjects and await svc.db.fetchone(
            'SELECT subject FROM oidc_identities WHERE subject=? AND issuer=?', (body.subject, svc.access.config.oidc.issuer))
        if not known_oidc and not any(a.subject == body.subject and not a.disabled for a in svc.access.config.users):
            raise HTTPException(400, 'unknown subject')
        if await svc.runs.get_run(run_id) is None:
            raise HTTPException(404, 'run not found')
        if body.permission == 'revoke':
            await svc.db.execute('DELETE FROM run_access WHERE run_id=? AND subject=?', (run_id, body.subject))
        else:
            await svc.db.execute('INSERT INTO run_access(run_id,subject,permission) VALUES(?,?,?) '
                                 'ON CONFLICT(run_id,subject) DO UPDATE SET permission=excluded.permission',
                                 (run_id, body.subject, body.permission))
        await svc.access.audit(request, 'access_grant', 200, {'subject': body.subject, 'permission': body.permission})
        return {'run_id': run_id, 'subject': body.subject, 'permission': body.permission}

    # ------------------------------------------------------------------ meta / config
    @app.get("/api/health")
    async def health(request: Request):
        await svc.db.fetchone('SELECT 1')
        return {"ok": not svc.stopping, "version": __version__, "config_revision": svc.config_revision,
                "live_runs": [rid for rid in svc.manager.live if await svc.access.can_access(request, rid)]}

    @app.get("/api/config")
    async def get_config(request: Request):
        cfg = svc.public_config()
        if not svc.access.admin(request):
            cfg['connections'] = []
            cfg['effective_agents'] = {}
            cfg['agents'] = []
            cfg['problems'] = [{'code': p['code'], 'message': 'Administrator setup required'} for p in cfg['problems']]
        return cfg

    @app.get("/api/config/yaml", response_class=PlainTextResponse)
    async def get_config_yaml():
        return config_to_yaml(svc.config)

    @app.get("/api/config/revisions")
    async def config_revisions():
        return await svc.runs.list_config_revisions()

    @app.get("/api/skills")
    async def skills():
        return list_skills()

    @app.get("/api/agents")
    async def agents():
        return [a.model_dump() for a in svc.config.agents]

    @app.get("/api/agents/{agent_id}/effective-config")
    async def agent_effective(agent_id: str):
        a = svc.config.agent(agent_id)
        if a is None:
            raise HTTPException(404, "agent not found")
        return effective_agent(svc.config, a).model_dump()

    @app.get("/api/agents/{agent_id}/prompt/default", response_class=PlainTextResponse)
    async def agent_prompt_default(agent_id: str):
        a = svc.config.agent(agent_id)
        if a is None:
            raise HTTPException(404, "agent not found")
        return (PKG_ROOT / a.system_prompt_file).read_text(encoding="utf-8")

    @app.patch("/api/agents/{agent_id}")
    async def patch_agent(agent_id: str, body: PatchAgentBody):
        if body.expected_revision != svc.config_revision:
            raise HTTPException(409, {"code": "revision_conflict", "current": svc.config_revision})
        cfg = svc.config.model_copy(deep=True)
        a = cfg.agent(agent_id)
        if a is None:
            raise HTTPException(404, "agent not found")
        if body.model is not None:
            a.model = body.model
        if body.connection_id is not None:
            if body.connection_id != "inherit" and cfg.connection(body.connection_id) is None:
                raise HTTPException(400, "unknown connection")
            a.connection_id = body.connection_id
        if body.reset_prompt:
            a.system_prompt_override = None
        elif body.system_prompt_override is not None:
            a.system_prompt_override = body.system_prompt_override
        if body.prompt_mode is not None:
            if body.prompt_mode not in ("auto_seed", "user_locked"):
                raise HTTPException(400, "prompt_mode must be auto_seed or user_locked")
            a.prompt_mode = body.prompt_mode  # type: ignore[assignment]
        if body.enabled is not None:
            a.enabled = body.enabled
        if body.effort is not None:
            a.effort = body.effort or None  # type: ignore[assignment]
        if body.skill_ids is not None:
            a.skill_ids = body.skill_ids
        if body.tools is not None:
            a.tools = body.tools
        try:
            rev = await svc.save_config(cfg, f"patch agent {agent_id}")
        except (ConfigError, ValueError) as e:
            raise HTTPException(400, str(e))
        return {"revision": rev, "agent": a.model_dump(), "note": "applies to runs started after this revision"}

    @app.get("/api/connections")
    async def connections():
        return [c.model_dump() for c in svc.config.connections]

    @app.put("/api/connections/{connection_id}")
    async def put_connection(connection_id: str, body: PutConnectionBody):
        if body.expected_revision != svc.config_revision:
            raise HTTPException(409, {"code": "revision_conflict", "current": svc.config_revision})
        cfg = svc.config.model_copy(deep=True)
        existing = cfg.connection(connection_id)
        try:
            new = Connection(id=connection_id, driver=body.driver, base_url=body.base_url, api_key_ref=body.api_key_ref,
                             capability_check="not_run", refusal_fallback=body.refusal_fallback,
                             ollama_thinking=(body.ollama_thinking if "ollama_thinking" in body.model_fields_set
                                              else existing.ollama_thinking if existing else None)
                             if body.driver == "ollama" else None)  # any change re-requires the probe
        except ValidationError as exc:
            raise HTTPException(400, str(exc))  # Connection excludes secret input values from this message
        if existing:
            cfg.connections[cfg.connections.index(existing)] = new
        else:
            cfg.connections.append(new)
        try:
            rev = await svc.save_config(cfg, f"connection {connection_id}")
        except (ConfigError, ValueError) as e:
            raise HTTPException(400, str(e))
        return {"revision": rev, "connection": new.model_dump()}

    @app.put("/api/limits")
    async def put_limits(body: PutLimitsBody):
        if body.expected_revision != svc.config_revision:
            raise HTTPException(409, {"code": "revision_conflict", "current": svc.config_revision})
        cfg = svc.config.model_copy(deep=True)
        try:
            cfg.limits = cfg.limits.model_copy(update=body.limits)
            if body.defaults:
                cfg.defaults = cfg.defaults.model_copy(update=body.defaults)
            if body.pricing is not None:
                from ..config.models import ModelPrice
                cfg.pricing = {k: ModelPrice.model_validate(v) for k, v in body.pricing.items()}
            rev = await svc.save_config(cfg, "limits/defaults")
        except (ConfigError, ValueError) as e:
            raise HTTPException(400, str(e))
        return {"revision": rev, "limits": cfg.limits.model_dump(), "defaults": cfg.defaults.model_dump()}

    @app.post("/api/connections/{connection_id}/probe")
    async def probe_connection(connection_id: str, model: str | None = None):
        conn = svc.config.connection(connection_id)
        if conn is None:
            raise HTTPException(404, "connection not found")
        target_model = model or svc.config.defaults.model
        registry = ProviderRegistry(svc.config, fake_adapters=svc.fake_adapters)
        try:
            adapter = registry.adapter(connection_id)
            for s in registry.secret_values:
                svc.redactor.add(s)
            result = await adapter.probe(target_model)
        except Exception as e:
            raise HTTPException(400, svc.redactor.text(str(e)))
        finally:
            await registry.aclose()
        cfg = svc.config.model_copy(deep=True)
        c = cfg.connection(connection_id)
        assert c is not None
        c.capability_check = "passed" if result.ok else "failed"
        c.capability_detail = {"model_requested": result.model_requested, "model_reported": result.model_reported,
                               "tool_calling": result.tool_calling, "json_schema": result.json_schema, "error": result.error,
                               "usage": {"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens},
                               "request_id": result.request_id}
        rev = await svc.save_config(cfg, f"probe {connection_id}:{target_model} → {c.capability_check}")
        return {"revision": rev, "result": c.capability_detail, "capability_check": c.capability_check}

    # ------------------------------------------------------------------ runs
    @app.post("/api/runs", status_code=202)
    async def create_run(body: CreateRunBody, request: Request):
        async with svc.admission_lock:
            await _check_admission(require_execution=body.start)
            if not svc.access.admin(request) and body.budget_usd and body.budget_usd > svc.config.limits.budget_usd:
                raise HTTPException(403, 'budget exceeds organization limit')
            run, problems = await svc.manager.create_run(body.goal, body.inputs, budget_usd=body.budget_usd)
            await svc.access.grant_creator(request, run.run_id)
            if problems:
                return JSONResponse(status_code=409, content={"run_id": run.run_id, "status": run.status, "problems": problems})
            if body.start:
                svc.manager.start(run.run_id)
            return run.model_dump()

    async def _check_admission(*, require_execution: bool = True):
        if svc.stopping:
            raise HTTPException(503, 'server shutting down')
        if svc.access.enabled and sum(not t.done() for t in svc.manager._tasks.values()) >= svc.access.config.max_active_runs:
            raise HTTPException(429, 'active run limit reached', headers={'Retry-After': '30'})
        if shutil.disk_usage(svc.data_dir).free < 500 * 1024 * 1024:
            raise HTTPException(503, 'insufficient storage space')
        if require_execution and svc.access.enabled and any(a.enabled and set(a.tools) & {'sandbox_run', 'run_check'} for a in svc.config.agents):
            from ..runtime.sandbox import backend_name
            if await backend_name() in ('none', 'subprocess'):
                raise HTTPException(503, 'configured tools require an isolated command sandbox')

    @app.get("/api/runs")
    async def list_runs(request: Request, limit: int = Query(default=50, ge=1, le=500)):
        if svc.access.admin(request):
            return [r.model_dump() for r in await svc.runs.list_runs(limit)]
        rows = await svc.db.fetchall('SELECT r.* FROM runs r JOIN run_access a ON a.run_id=r.run_id '
                                     'WHERE a.subject=? ORDER BY r.created_at DESC LIMIT ?',
                                     (svc.access.principal(request).subject, limit))
        return [svc.runs._run(r).model_dump() for r in rows]

    async def _run_detail(run_id: str, request: Request) -> dict[str, Any]:
        run = await svc.runs.get_run(run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        d = run.model_dump()
        d["tasks"] = [t.model_dump() for t in await svc.runs.list_tasks(run_id)]
        d["artifacts"] = [m.model_dump() for m in await svc.artifacts.list(run_id)]
        d["approvals"] = [a.model_dump() for a in await svc.runs.list_approvals(run_id)]
        d["last_seq"] = await svc.events.last_seq(run_id)
        d["live"] = run_id in svc.manager.live
        d['access'] = {'can_write': await svc.access.can_access(request, run_id, write=True),
                       'can_override': svc.access.admin(request)}
        return d

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, request: Request):
        return await _run_detail(run_id, request)

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, after_seq: int = Query(default=0, ge=0), limit: int = Query(default=2000, ge=1, le=10000), types: str | None = None):
        evs = await svc.events.list(run_id, after_seq=after_seq, limit=limit, types=types.split(",") if types else None)
        return [e.model_dump() for e in evs]

    @app.get("/api/runs/{run_id}/chat")
    async def run_chat(run_id: str):
        return chat_view(await svc.events.list(run_id))

    @app.get("/api/runs/{run_id}/timeline")
    async def run_timeline(run_id: str, tools: bool = True):
        return timeline_view(await svc.events.list(run_id), include_tool_calls=tools)

    @app.get("/api/runs/{run_id}/stream")
    async def run_stream(run_id: str, request: Request, after_seq: int = 0):
        if await svc.runs.get_run(run_id) is None:
            raise HTTPException(404, "run not found")
        last_id = request.headers.get("last-event-id")
        if last_id and last_id.isdigit():
            after_seq = max(after_seq, int(last_id))

        async def gen():
            cursor = after_seq
            q = svc.events.subscribe(run_id)
            try:
                for e in await svc.events.list(run_id, after_seq=cursor):  # durable replay first
                    cursor = e.seq
                    yield {"id": str(e.seq), "event": e.type, "data": json.dumps(e.model_dump(), ensure_ascii=False)}
                while True:
                    if svc.access.enabled:
                        account = await svc.access.authenticate(request)
                        if account is None:
                            break
                        request.state.principal = account
                        if not await svc.access.can_access(request, run_id):
                            break
                    if await request.is_disconnected():
                        break
                    if run_id not in svc.manager.live:
                        # nothing more will be appended until the run is resumed/forked: flush and close
                        for e in await svc.events.list(run_id, after_seq=cursor):
                            cursor = e.seq
                            yield {"id": str(e.seq), "event": e.type, "data": json.dumps(e.model_dump(), ensure_ascii=False)}
                        run = await svc.runs.get_run(run_id)
                        yield {"event": "end", "data": json.dumps({"last_seq": cursor, "status": str(run.status) if run else None})}
                        break
                    try:
                        e = await asyncio.wait_for(q.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": json.dumps({"last_seq": cursor})}
                        continue
                    if e.seq <= cursor:
                        continue  # dedupe by seq/id
                    cursor = e.seq
                    yield {"id": str(e.seq), "event": e.type, "data": json.dumps(e.model_dump(), ensure_ascii=False)}
            finally:
                svc.events.unsubscribe(run_id, q)

        return EventSourceResponse(gen())

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str):
        if await svc.runs.get_run(run_id) is None:
            raise HTTPException(404, "run not found")
        ok = await svc.manager.cancel(run_id)
        return {"cancel_requested": ok}

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str):
        try:
            async with svc.admission_lock:
                await _check_admission()
                run = await svc.manager.resume(run_id)
        except KeyError:
            raise HTTPException(404, "run not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(409, str(e))
        return run.model_dump()

    @app.post("/api/runs/{run_id}/fork", status_code=202)
    async def fork_run(run_id: str, body: ForkBody, request: Request):
        if not svc.access.admin(request) and body.overrides:
            raise HTTPException(403, 'only administrators may override the execution configuration')
        try:
            async with svc.admission_lock:
                await _check_admission(require_execution=body.start)
                new = await svc.manager.fork(run_id, overrides=body.overrides, from_seq=body.from_seq)
                await svc.access.grant_creator(request, new.run_id)
                if body.start:
                    await svc.manager.start_fork(new.run_id)
        except KeyError:
            raise HTTPException(404, "run not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        return new.model_dump()

    @app.get("/api/runs/{run_id}/export")
    async def export_run(run_id: str, fmt: str = "jsonl"):
        run = await svc.runs.get_run(run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        evs = await svc.events.list(run_id)
        if fmt == "jsonl":
            body = "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in evs) + "\n"
            return PlainTextResponse(body, media_type="application/x-ndjson",
                                     headers={"content-disposition": f'attachment; filename="{run_id}.events.jsonl"'})
        final = await svc.artifacts.get(run_id, "final-report.md")
        md = svc.artifacts.read_text(final) if final else f"# {run.goal}\n\n(no report yet)\n"
        return PlainTextResponse(md, media_type="text/markdown")

    # ------------------------------------------------------------------ approvals
    @app.get("/api/approvals")
    async def approvals(request: Request, run_id: str | None = None, status: str | None = None):
        return [a.model_dump() for a in await svc.runs.list_approvals(run_id, status)
                if await svc.access.can_access(request, a.run_id)]

    @app.post("/api/approvals/{approval_id}/resolve")
    async def resolve_approval(approval_id: str, body: ResolveApprovalBody):
        if body.decision not in ("approve", "reject", "edit"):
            raise HTTPException(400, "decision must be approve, reject or edit")
        try:
            ap = await svc.manager.resolve_approval(approval_id, body.decision, note=body.note, edited_payload=body.edited_payload,
                                                    expected_hash=body.expected_hash, nonce=body.nonce)
        except KeyError:
            raise HTTPException(404, "approval not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        return ap.model_dump()

    # ------------------------------------------------------------------ artifacts
    @app.get("/api/artifacts/{run_id}/{artifact_id}/versions/{revision}")
    async def artifact_version(run_id: str, artifact_id: str, revision: int):
        m = await svc.artifacts.get(run_id, artifact_id, revision)
        if m is None:
            raise HTTPException(404, "artifact revision not found")
        d = m.model_dump()
        evs = await svc.events.list(run_id, types=["check.completed", "review.submitted"])
        d["checks"] = [e.model_dump() for e in evs if e.type == "check.completed" and (e.payload.get("target") or {}).get("artifact_id") == artifact_id
                       and (e.payload.get("target") or {}).get("revision") == revision]
        d["reviews"] = [e.model_dump() for e in evs if e.type == "review.submitted" and any(
            a.get("artifact_id") == artifact_id and a.get("revision") == revision for a in e.payload.get("target_artifacts", []))]
        if m.media_type.startswith("text/") or m.media_type in ("application/json", "image/svg+xml"):
            d["text"] = svc.artifacts.read_text(m)
        return d

    @app.get("/api/artifacts/{run_id}/{artifact_id}/versions/{revision}/raw")
    async def artifact_raw(run_id: str, artifact_id: str, revision: int):
        m = await svc.artifacts.get(run_id, artifact_id, revision)
        if m is None:
            raise HTTPException(404, "artifact revision not found")
        data = svc.artifacts.read_bytes(m)
        # generated content is untrusted: no scripts, no network, sandboxed when framed
        headers = {"content-security-policy": "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:",
                   "x-content-type-options": "nosniff", "cache-control": "no-store"}
        return Response(content=data, media_type=m.media_type, headers=headers)

    # ------------------------------------------------------------------ frontend
    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (FRONTEND_DIST / path).resolve()
            if not f.is_relative_to(FRONTEND_DIST.resolve()):
                raise HTTPException(404)
            if path and f.is_file():
                return FileResponse(f)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
