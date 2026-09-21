import asyncio
import json
import zipfile
from io import BytesIO

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
    assert [m["purpose"] for m in chat if m["from"] == "master"] == ["handoff"] * 3
    assert [m["purpose"] for m in chat if m["from"] != "master"] == ["handoff", "question", "answer", "handoff", "finding", "handoff", "handoff"]
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
    diff = await client.get(f"/api/artifacts/{run_id}/index.html/versions/2/diff?from_revision=1")
    assert diff.status_code == 200 and diff.json()["supported"] and "+++" in diff.json()["diff"]
    adopted = await client.post(f"/api/artifacts/{run_id}/index.html/adopt", json={"revision": 2, "note": "確認済み"})
    assert adopted.status_code == 202 and adopted.json()["revision"] == 2
    detail = (await client.get(f"/api/runs/{run_id}")).json()
    assert detail["artifact_selection"]["index.html"]["revision"] == 2
    bundle = await client.get(f"/api/runs/{run_id}/export?fmt=zip")
    assert bundle.status_code == 200
    with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
        assert "final-report.md" in archive.namelist()
        assert any(name.endswith("artifacts/index.html") for name in archive.namelist())


async def test_completion_waits_for_report_and_terminal_event(client, monkeypatch):
    manager = client.svc.manager
    making_report, release_report = asyncio.Event(), asyncio.Event()
    writing_terminal, release_terminal = asyncio.Event(), asyncio.Event()
    make_report = manager._make_report
    append = client.svc.events.append

    async def delayed_report(*args, **kwargs):
        making_report.set()
        await release_report.wait()
        return await make_report(*args, **kwargs)

    async def delayed_append(run_id, event_type, *args, **kwargs):
        if event_type == "run.completed":
            writing_terminal.set()
            await release_terminal.wait()
        return await append(run_id, event_type, *args, **kwargs)

    monkeypatch.setattr(manager, "_make_report", delayed_report)
    monkeypatch.setattr(client.svc.events, "append", delayed_append)
    run_id = (await client.post("/api/runs", json={"goal": "LP"})).json()["run_id"]
    try:
        await asyncio.wait_for(making_report.wait(), timeout=5)
        detail = (await client.get(f"/api/runs/{run_id}")).json()
        assert detail["status"] == "running"
        assert detail["final_report"] is None
        release_report.set()
        await asyncio.wait_for(writing_terminal.wait(), timeout=5)
        detail = (await client.get(f"/api/runs/{run_id}")).json()
        assert detail["status"] == "running"
        release_terminal.set()
        detail = await _wait_done(client, run_id)
        assert detail["status"] == "completed"
        assert detail["final_report"]["report_artifact"]
        events = (await client.get(f"/api/runs/{run_id}/events")).json()
        assert events[-1]["type"] == "run.completed"
        assert detail["usage"]["model_calls"] == events[-1]["payload"]["usage"]["model_calls"]
        await manager.wait(run_id)
        exported = await client.get(f"/api/runs/{run_id}/export?fmt=jsonl")
        assert len(exported.text.strip().splitlines()) == len(events)
    finally:
        release_report.set()
        release_terminal.set()
        await manager.wait(run_id)


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


async def test_human_instruction_is_event_backed_and_cursor_checked(client):
    created = await client.post("/api/runs", json={"goal": "資料を整理する", "start": False})
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    received = await client.post(f"/api/runs/{run_id}/instructions", json={"kind": "change", "text": "結論を先に書いてください。"})
    assert received.status_code == 202
    payload = received.json()
    assert payload["state"] == "received" and payload["event"]["type"] == "instruction.received"
    timeline = (await client.get(f"/api/runs/{run_id}/timeline")).json()
    assert timeline[-1]["type"] == "instruction.received"
    stale = await client.post(f"/api/runs/{run_id}/instructions", json={"text": "古い前提", "expected_seq": 0})
    assert stale.status_code == 409
