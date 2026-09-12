"""FastAPI application: runs, events (cursor + SSE), approvals, agents/config, connections, artifacts."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..config.loader import ConfigError, PKG_ROOT, config_to_yaml, effective_agent, list_skills, load_config_text
from ..config.models import Connection
from ..contracts import RunInputs, RunStatus
from ..projections.views import chat_view, timeline_view
from ..providers.registry import ProviderRegistry
from .service import AppService

FRONTEND_DIST = PKG_ROOT.parent / "frontend" / "dist"


class CreateRunBody(BaseModel):
    goal: str = Field(min_length=1)
    inputs: RunInputs = Field(default_factory=RunInputs)
    budget_usd: float | None = None
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

    app = FastAPI(title="Agent Team", version="0.1.0", lifespan=lifespan)

    # ------------------------------------------------------------------ meta / config
    @app.get("/api/health")
    async def health():
        return {"ok": True, "config_revision": svc.config_revision, "live_runs": list(svc.manager.live)}

    @app.get("/api/config")
    async def get_config():
        return svc.public_config()

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
        new = Connection(id=connection_id, driver=body.driver, base_url=body.base_url, api_key_ref=body.api_key_ref,
                         capability_check="not_run", refusal_fallback=body.refusal_fallback)  # any change re-requires the probe
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
    async def create_run(body: CreateRunBody):
        run, problems = await svc.manager.create_run(body.goal, body.inputs, budget_usd=body.budget_usd)
        if problems:
            return JSONResponse(status_code=409, content={"run_id": run.run_id, "status": run.status, "problems": problems})
        if body.start:
            svc.manager.start(run.run_id)
        return run.model_dump()

    @app.get("/api/runs")
    async def list_runs(limit: int = 50):
        return [r.model_dump() for r in await svc.runs.list_runs(limit)]

    async def _run_detail(run_id: str) -> dict[str, Any]:
        run = await svc.runs.get_run(run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        d = run.model_dump()
        d["tasks"] = [t.model_dump() for t in await svc.runs.list_tasks(run_id)]
        d["artifacts"] = [m.model_dump() for m in await svc.artifacts.list(run_id)]
        d["approvals"] = [a.model_dump() for a in await svc.runs.list_approvals(run_id)]
        d["last_seq"] = await svc.events.last_seq(run_id)
        d["live"] = run_id in svc.manager.live
        return d

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        return await _run_detail(run_id)

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, after_seq: int = 0, limit: int = 2000, types: str | None = None):
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
            run = await svc.manager.resume(run_id)
        except KeyError:
            raise HTTPException(404, "run not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        except Exception as e:
            raise HTTPException(409, str(e))
        return run.model_dump()

    @app.post("/api/runs/{run_id}/fork", status_code=202)
    async def fork_run(run_id: str, body: ForkBody):
        try:
            new = await svc.manager.fork(run_id, overrides=body.overrides, from_seq=body.from_seq)
        except KeyError:
            raise HTTPException(404, "run not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        if body.start:
            await svc.manager.start_fork(new.run_id)
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
    async def approvals(run_id: str | None = None, status: str | None = None):
        return [a.model_dump() for a in await svc.runs.list_approvals(run_id, status)]

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
            f = FRONTEND_DIST / path
            if path and f.is_file():
                return FileResponse(f)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
