"""Provision real credentials and replay real saved work through the API and SQLite.

No model responses, remote identity providers, or stores are mocked.
"""
from pathlib import Path
import json
import sqlite3

import httpx
import pytest

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.contracts import Run
from agentteam.security.accounts import issue_key
from agentteam.operations.backup import backup, restore, verify

EVIDENCE = Path(__file__).resolve().parents[2] / 'docs/evidence/local-fixes-2026-09-14'
PROFILE = EVIDENCE.parents[1] / 'config/local-qwen35-9b-team.yaml'
ORIGIN = 'https://localhost'


def provision(root):
    access = root / 'access.json'
    tokens = {}
    for subject, role in [('maintainer', 'admin'), ('builder', 'operator'), ('reviewer', 'viewer')]:
        credential = root / (subject + '.key')
        issue_key(access, subject, role, credential, organization='FORIFOR/Multibot', public_origin=ORIGIN)
        tokens[subject] = credential.read_text().strip()
    return access, tokens


async def seed_actual_work(svc):
    run = Run.model_validate(json.loads((EVIDENCE / 'thinking-interruption.json').read_text()))
    await svc.runs.create_run(run)
    audit = json.loads((EVIDENCE.parent / 'local-qwen35-9b-2026-09-14/thinking-team-quality-audit.json').read_text())
    artifact = await svc.artifacts.publish(run.run_id, 'email.md', audit['artifact_text'].encode(), agent_id='builder', task_id='t1')
    assert artifact.sha256 == audit['sha256']
    return run, artifact


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


async def test_authenticated_roles_isolate_real_runs_events_artifacts_and_exports(tmp_path):
    access, tokens = provision(tmp_path)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        run, artifact = await seed_actual_work(svc)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            assert (await c.get('/api/runs')).status_code == 401
            operator = bearer(tokens['builder']); admin = bearer(tokens['maintainer']); viewer = bearer(tokens['reviewer'])
            assert (await c.get('/api/runs', headers=operator)).json() == []
            paths = [f'/api/runs/{run.run_id}{suffix}' for suffix in ['', '/events', '/chat', '/timeline', '/stream', '/export']]
            paths += [f'/api/artifacts/{run.run_id}/email.md/versions/1{suffix}' for suffix in ['', '/raw']]
            for path in paths:
                assert (await c.get(path, headers=operator)).status_code == 404, path
            assert (await c.post(f'/api/runs/{run.run_id}/cancel', headers=operator)).status_code == 404
            assert (await c.get('/api/config/yaml', headers=operator)).status_code == 403
            assert (await c.put('/api/limits', headers=operator, json={})).status_code == 403
            assert (await c.get('/api/admin/audit', headers=operator)).status_code == 403
            assert (await c.post('/api/runs', headers=viewer, json={})).status_code == 403
            assert (await c.get('/api/config', headers=operator)).json()['connections'] == []
            revision = svc.config_revision
            conn = svc.config.connections[0]
            rejected = await c.put('/api/connections/' + conn.id, headers=admin, json={
                'expected_revision': revision, 'driver': conn.driver, 'base_url': conn.base_url,
                'api_key_ref': tokens['maintainer']})
            assert rejected.status_code == 400 and tokens['maintainer'] not in rejected.text
            assert svc.config_revision == revision
            assert tokens['maintainer'] not in svc.config_path.read_text()
            from agentteam.config.models import AgentTeamConfig
            config = svc.config.model_dump()
            config['connections'][0]['api_key_ref'] = tokens['maintainer']
            with pytest.raises(ValueError) as invalid:
                AgentTeamConfig.model_validate(config)
            assert tokens['maintainer'] not in str(invalid.value)
            assert (await c.get(f'/api/runs/{run.run_id}', headers=admin)).status_code == 200
            for subject in ['builder', 'reviewer']:
                grant = await c.put(f'/api/runs/{run.run_id}/access', headers=admin, json={'subject': subject, 'permission': 'read'})
                assert grant.status_code == 200, grant.text
            for path in paths:
                assert (await c.get(path, headers=viewer)).status_code == 200, path
            assert (await c.post(f'/api/runs/{run.run_id}/cancel', headers=operator)).status_code == 404
            assert (await c.post(f'/api/runs/{run.run_id}/cancel', headers=viewer)).status_code == 403
            assert (await c.put(f'/api/runs/{run.run_id}/access', headers=operator, json={'subject': 'builder', 'permission': 'write'})).status_code == 403
            records = (await c.get('/api/admin/audit?limit=1000', headers=admin)).json()
            assert any(r['outcome'] == 'denied' and r['status'] == 404 for r in records)
            assert any(r['subject'] == 'maintainer' and r['route'] == '/api/runs/{run_id}/access' for r in records)
            serialized = json.dumps(records)
            assert all(token not in serialized for token in tokens.values())
            assert 'agentteam_runs' in (await c.get('/api/admin/metrics', headers=admin)).text
            readiness = await c.get('/api/admin/ready', headers=admin)
            assert readiness.status_code == 503
            assert 'capability_check' in readiness.json()['configuration_problems']
            assert readiness.json()['sandbox_backend'] != 'not_required'


async def test_cookie_login_origin_revocation_and_private_key_storage(tmp_path):
    access, tokens = provision(tmp_path)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            assert (await c.post('/api/auth/login', json={'token': tokens['builder']})).status_code == 403
            r = await c.post('/api/auth/login', headers={'Origin': ORIGIN}, json={'token': tokens['builder']})
            assert r.status_code == 200
            assert 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']
            assert 'SameSite=strict' in r.headers['set-cookie']
            assert (await c.get('/api/auth/me')).json()['subject'] == 'builder'
            assert (await c.post('/api/auth/logout')).status_code == 403
            assert (await c.get('/api/auth/me', headers=bearer(tokens['builder'] + 'x'))).status_code == 401
            stored = await svc.db.fetchall('SELECT * FROM auth_sessions')
            assert tokens['builder'] not in json.dumps([dict(r) for r in stored])
            issue_key(access, 'builder', 'operator', tmp_path / 'rotated.key')
            assert (await c.get('/api/auth/me')).status_code == 401
            assert (await c.get('/api/auth/me', headers=bearer(tokens['builder']))).status_code == 401
            r = await c.post('/api/auth/login', headers={'Origin': ORIGIN}, json={'token': (tmp_path / 'rotated.key').read_text().strip()})
            assert r.status_code == 200
            assert (await c.post('/api/auth/logout', headers={'Origin': ORIGIN})).status_code == 200
            assert (await c.get('/api/auth/me')).status_code == 401
            assert all(token not in access.read_text() for token in tokens.values())
            assert access.stat().st_mode & 0o077 == 0


async def test_real_request_ownership_limits_and_configuration_override_denial(tmp_path):
    access, tokens = provision(tmp_path)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    app = create_app(svc)
    record = json.loads((EVIDENCE / 'thinking-interruption.json').read_text())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            headers = bearer(tokens['builder'])
            body = {'goal': record['goal'], 'inputs': record['inputs'], 'start': False}
            # The real profile requires a capability probe. This must remain a visible blocked run.
            r = await c.post('/api/runs', headers=headers, json=body)
            assert r.status_code == 409, r.text
            run_id = r.json()['run_id']
            assert (await c.get(f'/api/runs/{run_id}', headers=headers)).status_code == 200
            assert (await c.get('/api/runs', headers=headers)).json()[0]['run_id'] == run_id
            assert (await c.get(f'/api/runs/{run_id}', headers=bearer(tokens['reviewer']))).status_code == 404
            body['budget_usd'] = svc.config.limits.budget_usd + 1
            assert (await c.post('/api/runs', headers=headers, json=body)).status_code == 403
            assert (await c.post(f'/api/runs/{run_id}/fork', headers=headers, json={'overrides': {'budget_usd': 100}})).status_code == 403
            assert (await c.get('/api/runs?limit=-1', headers=headers)).status_code == 422
            assert (await c.get('/api/auth/me', headers={**headers, 'Host': 'foreign.example'})).status_code == 400
            assert (await c.get('/api/auth/me', headers={**headers, 'Origin': 'https://foreign.example'})).status_code == 403


async def test_process_exclusion_crash_recovery_and_organization_binding(tmp_path):
    access, _ = provision(tmp_path)
    root = tmp_path / 'data'
    svc = await AppService(root, config_yaml=PROFILE.read_text(), access_file=access).start()
    run, _ = await seed_actual_work(svc)
    await svc.runs.update_run(run.run_id, status='running')
    other = AppService(root, access_file=access)
    with pytest.raises(RuntimeError, match='already in use'):
        await other.start()
    await svc.stop()
    restarted = await AppService(root, access_file=access).start()
    saved = await restarted.runs.get_run(run.run_id)
    assert saved.status == 'interrupted'
    assert saved.blocked_reason == 'server restarted while running'
    assert (await restarted.events.list(run.run_id))[-1].type == 'run.interrupted'
    await restarted.stop()
    with pytest.raises(ValueError, match='requires its organization access configuration'):
        await AppService(root).start()
    data = json.loads(access.read_text()); data['organization'] += '-separate'
    access.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='different organization'):
        await AppService(root, access_file=access).start()


async def test_offline_snapshot_restores_real_artifact_and_revokes_sessions(tmp_path):
    access, tokens = provision(tmp_path)
    root = tmp_path / 'data'
    svc = await AppService(root, config_yaml=PROFILE.read_text(), access_file=access).start()
    run, artifact = await seed_actual_work(svc)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(svc)), base_url=ORIGIN) as client:
        response = await client.post('/api/auth/login', headers={'Origin': ORIGIN}, json={'token': tokens['maintainer']})
        assert response.status_code == 200
    assert len(await svc.db.fetchall('SELECT * FROM auth_sessions')) == 1
    with pytest.raises(RuntimeError, match='stop the service'):
        backup(root, tmp_path / 'live-snapshot')
    await svc.stop()
    snapshot, restored = tmp_path / 'snapshot', tmp_path / 'restored'
    manifest = backup(root, snapshot)
    assert verify(snapshot) == manifest
    result = restore(snapshot, restored)
    assert result['sessions_revoked']
    restored_svc = await AppService(restored, access_file=access).start()
    saved = await restored_svc.artifacts.get(run.run_id, artifact.artifact_id)
    assert restored_svc.artifacts.read_bytes(saved) == svc.artifacts.read_bytes(artifact)
    assert await restored_svc.db.fetchall('SELECT * FROM auth_sessions') == []
    await restored_svc.stop()
    with pytest.raises(FileExistsError):
        restore(snapshot, restored)
    # Corrupt a copy of the actual artifact: integrity checking must reject it.
    path = snapshot / 'runs' / artifact.storage_path
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError, match='checksum mismatch'):
        verify(snapshot)


async def test_real_input_size_limit_and_access_file_failure_are_closed(tmp_path):
    access, tokens = provision(tmp_path)
    cfg = json.loads(access.read_text()); cfg['max_request_bytes'] = 1024
    access.write_text(json.dumps(cfg))
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            record = (EVIDENCE / 'thinking-interruption.json').read_bytes()
            assert len(record) > 1024
            response = await c.post('/api/runs', headers={**bearer(tokens['maintainer']), 'Content-Type': 'application/json'}, content=record)
            assert response.status_code == 413
            assert await svc.runs.list_runs() == []
            access.chmod(0o644)
            assert (await c.get('/api/runs', headers=bearer(tokens['maintainer']))).status_code == 503
            access.chmod(0o600)
            assert (await c.get('/api/runs', headers=bearer(tokens['maintainer']))).status_code == 200
