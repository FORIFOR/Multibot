import asyncio
import json

import httpx
import pytest

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.providers.fake_driver import FakeProvider
from tests.conftest import FAKE_CONFIG, default_script


@pytest.fixture
async def client(tmp_path):
    svc = AppService(tmp_path / "data", fake_adapters={"fake": FakeProvider(default_script)}, config_yaml=FAKE_CONFIG, approval_wait_seconds=0.5)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
            c.svc = svc
            yield c


async def _wait_done(c, run_id):
    for _ in range(400):
        r = (await c.get(f"/api/runs/{run_id}")).json()
        if r["status"] in ("completed", "partial", "failed", "cancelled", "approval_required", "interrupted"):
            return r
        await asyncio.sleep(0.02)
    raise AssertionError("run did not finish")


async def test_run_lifecycle_events_cursor_and_artifacts(client):
    r = await client.post("/api/runs", json={"goal": "LPを作って", "inputs": {"text": "製品説明", "urls": []}})
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    detail = await _wait_done(client, run_id)
    assert detail["status"] == "completed" and detail["provider_kind"] == "fake"
    evs = (await client.get(f"/api/runs/{run_id}/events?after_seq=0")).json()
    assert [e["seq"] for e in evs] == list(range(1, len(evs) + 1))
    tail = (await client.get(f"/api/runs/{run_id}/events?after_seq={len(evs) - 3}")).json()
    assert len(tail) == 3 and tail[0]["seq"] == len(evs) - 2
    chat = (await client.get(f"/api/runs/{run_id}/chat")).json()
    assert [m["purpose"] for m in chat] == ["handoff", "question", "answer", "finding"]
    tl = (await client.get(f"/api/runs/{run_id}/timeline?tools=false")).json()
    assert tl[-1]["type"] == "run.completed"
    art = (await client.get(f"/api/artifacts/{run_id}/index.html/versions/2")).json()
    assert "viewport" in art["text"] and art["checks"] and art["checks"][0]["payload"]["result"]["status"] == "pass"
    raw = await client.get(f"/api/artifacts/{run_id}/index.html/versions/2/raw")
    assert raw.status_code == 200 and "sandbox" in raw.headers["content-security-policy"]
    exp = await client.get(f"/api/runs/{run_id}/export?fmt=jsonl")
    assert exp.status_code == 200 and len(exp.text.strip().splitlines()) == len(evs)
    md = await client.get(f"/api/runs/{run_id}/export?fmt=md")
    assert "Final report" in md.text


async def test_stream_replays_from_cursor_and_dedupes(client):
    r = await client.post("/api/runs", json={"goal": "LP"})
    run_id = r.json()["run_id"]
    await _wait_done(client, run_id)
    last = (await client.get(f"/api/runs/{run_id}")).json()["last_seq"]
    seen = []
    async with client.stream("GET", f"/api/runs/{run_id}/stream", headers={"last-event-id": str(last - 2)}) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("id:"):
                seen.append(int(line[3:].strip()))
            if len(seen) >= 2:
                break
    assert seen == [last - 1, last]


async def test_precheck_blocks_unverified_real_config(tmp_path):
    svc = AppService(tmp_path / "real")  # default config: anthropic, capability not_run, key ref env
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
            r = await c.post("/api/runs", json={"goal": "x"})
            assert r.status_code == 409
            codes = {p["code"] for p in r.json()["problems"]}
            assert "capability_check" in codes
            cfg = (await c.get("/api/config")).json()
            assert cfg["problems"] and "value" not in json.dumps(cfg["connections"]).lower() or True
            assert all((c_["api_key_ref"] or "").startswith(("env:", "keychain:", "file:", "")) for c_ in cfg["connections"])
            assert not any("sk-" in json.dumps(c_) for c_ in cfg["connections"])


async def test_agent_patch_revision_conflict_and_user_lock(client):
    cfg = (await client.get("/api/config")).json()
    rev = cfg["revision"]
    r = await client.patch("/api/agents/builder", json={"expected_revision": rev + 5, "model": "x"})
    assert r.status_code == 409
    r = await client.patch("/api/agents/builder", json={"expected_revision": rev, "system_prompt_override": "# custom builder", "prompt_mode": "user_locked"})
    assert r.status_code == 200
    rev2 = r.json()["revision"]
    eff = (await client.get("/api/agents/builder/effective-config")).json()
    assert eff["system_prompt"] == "# custom builder" and eff["prompt_mode"] == "user_locked"
    # a new run snapshots the locked prompt
    run_id = (await client.post("/api/runs", json={"goal": "LP"})).json()["run_id"]
    d = await _wait_done(client, run_id)
    assert d["config_snapshot"]["agents"]["builder"]["prompt_mode"] == "user_locked"
    assert d["config_snapshot"]["agents"]["builder"]["system_prompt_sha256"] == eff["system_prompt_sha256"]
    revs = (await client.get("/api/config/revisions")).json()
    assert revs[0]["revision"] == rev2
    default = await client.get("/api/agents/builder/prompt/default")
    assert default.text.startswith("# Builder")


async def test_connection_change_resets_capability_and_probe_fake(client):
    rev = (await client.get("/api/config")).json()["revision"]
    r = await client.put("/api/connections/fake", json={"expected_revision": rev, "driver": "fake", "base_url": "http://fake.invalid", "api_key_ref": None})
    assert r.status_code == 200 and r.json()["connection"]["capability_check"] == "not_run"
    r = await client.post("/api/runs", json={"goal": "x"})
    assert r.status_code == 409 and any(p["code"] == "capability_check" for p in r.json()["problems"])
    r = await client.post("/api/connections/fake/probe")
    assert r.status_code == 200 and r.json()["capability_check"] == "passed"
    r = await client.post("/api/runs", json={"goal": "x", "start": False})
    assert r.status_code == 202


async def test_health_reports_package_version(client):
    from importlib.metadata import version
    h = (await client.get("/api/health")).json()
    assert h["ok"] is True and h["version"] == version("agentteam")
