"""Delete isolated copies of actual saved work; original evidence is never changed."""
import os
import json
import sqlite3
from datetime import date, timedelta

import pytest
import httpx

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.contracts import Run
from agentteam.ids import new_id
from agentteam.operations.retention import plan, purge
from .test_server_security import EVIDENCE, ORIGIN, PROFILE, provision, seed_actual_work


async def test_offline_preview_purge_and_no_follow_of_workspace_links(tmp_path):
    access, _ = provision(tmp_path)
    root = tmp_path / 'data'
    svc = await AppService(root, config_yaml=PROFILE.read_text(), access_file=access).start()
    run, artifact = await seed_actual_work(svc)
    original = svc.artifacts.read_bytes(artifact)
    outside = tmp_path / 'preserved-original.md'; outside.write_bytes(original)
    workspace = root / 'runs' / run.run_id / 'workspaces'; workspace.mkdir()
    (workspace / 'original-link.md').symlink_to(outside)
    with pytest.raises(RuntimeError, match='stop the service'):
        purge(root, run_ids=[run.run_id])
    await svc.stop()
    preview = plan(root, run_ids=[run.run_id])
    assert preview['file_count'] == 2 and (root / 'runs' / run.run_id).exists()
    result = purge(root, run_ids=[run.run_id])
    assert result['completed'] and not result['backups_and_provider_copies_deleted']
    assert not (root / 'runs' / run.run_id).exists()
    assert outside.read_bytes() == original
    with sqlite3.connect(root / 'agentteam.sqlite') as conn:
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
        assert conn.execute('SELECT state FROM purge_journal').fetchone()[0] == 'completed'
    assert run.goal.encode() not in (root / 'agentteam.sqlite').read_bytes()
    restored = await AppService(root, access_file=access).start()
    assert await restored.runs.list_runs() == []
    await restored.stop()


async def test_real_permission_failure_stays_pending_and_can_resume(tmp_path):
    assert os.geteuid() != 0, 'run this real permissions drill as an unprivileged account'
    access, _ = provision(tmp_path)
    root = tmp_path / 'data'
    svc = await AppService(root, config_yaml=PROFILE.read_text(), access_file=access).start()
    run, artifact = await seed_actual_work(svc)
    await svc.stop()
    revision = (root / 'runs' / artifact.storage_path).parent
    revision.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            purge(root, run_ids=[run.run_id])
        with pytest.raises(RuntimeError, match='unfinished data deletion'):
            await AppService(root, access_file=access).start()
        with sqlite3.connect(root / 'agentteam.sqlite') as conn:
            assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 0
            assert conn.execute('SELECT state FROM purge_journal').fetchone()[0] == 'pending'
    finally:
        revision.chmod(0o700)
    result = purge(root, resume=True)
    assert result['completed'] and result['resumed']
    assert not (root / 'runs' / run.run_id).exists()
    svc = await AppService(root, access_file=access).start()
    await svc.stop()


async def test_utc_retention_cutoff_uses_actual_completion_and_rejects_active_run(tmp_path):
    access, _ = provision(tmp_path)
    root = tmp_path / 'data'
    svc = await AppService(root, config_yaml=PROFILE.read_text(), access_file=access).start()
    completed = Run.model_validate_json((EVIDENCE.parent / 'durable-execution-2026-09-14/cancelled-real-run.json').read_text())
    await svc.runs.create_run(completed)
    interrupted, _ = await seed_actual_work(svc)
    await svc.stop()
    finished = date.fromisoformat(completed.finished_at[:10])
    assert plan(root, before=finished.isoformat())['run_ids'] == []
    selected = plan(root, before=(finished + timedelta(days=1)).isoformat())
    assert selected['run_ids'] == [completed.run_id]
    assert interrupted.run_id not in selected['run_ids']
    with pytest.raises(ValueError, match='unsafe run'):
        plan(root, run_ids=['../' + completed.run_id])
    # Reproduce the persisted state of an in-flight request; deletion must refuse it.
    with sqlite3.connect(root / 'agentteam.sqlite') as conn:
        conn.execute("UPDATE runs SET status='running' WHERE run_id=?", (interrupted.run_id,))
    with pytest.raises(ValueError, match='interrupt or cancel'):
        plan(root, run_ids=[interrupted.run_id])


async def test_old_http_retry_cannot_recreate_deleted_work(tmp_path):
    access, keys = provision(tmp_path)
    root = tmp_path / 'data'
    record = json.loads((EVIDENCE / 'thinking-interruption.json').read_text())
    body = {'goal': record['goal'], 'inputs': record['inputs'], 'start': False}
    headers = {'Authorization': 'Bearer ' + keys['builder'], 'Idempotency-Key': new_id('request')}
    svc = AppService(root, config_yaml=PROFILE.read_text(), access_file=access)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            response = await c.post('/api/runs', headers=headers, json=body)
            assert response.status_code == 409  # Real unprobed local profile is blocked.
            run_id = response.json()['run_id']
    purge(root, run_ids=[run_id])
    app = create_app(AppService(root, access_file=access))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            response = await c.post('/api/runs', headers=headers, json=body)
            assert response.status_code == 410
            assert (await c.get('/api/runs', headers=headers)).json() == []
