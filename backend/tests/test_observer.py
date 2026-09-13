"""Actual network/SQLite/process lifecycle checks. No mocked transport or provider."""
import asyncio
import json
import os
import socket
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.operations.backup import backup, restore
from agentteam.operations.observer import Observer
from agentteam.security.accounts import issue_key
from .test_server_security import EVIDENCE, PROFILE, seed_actual_work


def listening_socket(port=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    return sock


@asynccontextmanager
async def running(svc, sock):
    server = uvicorn.Server(uvicorn.Config(create_app(svc), log_level='error', access_log=False))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError('verification server did not start')
                await asyncio.sleep(0.01)
        yield
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)
        sock.close()


def credentials(tmp_path, origin):
    access = tmp_path / 'access.json'
    for subject, role in [('maintainer', 'admin'), ('collector', 'auditor'), ('builder', 'operator')]:
        issue_key(access, subject, role, tmp_path / (subject + '.key'), organization='FORIFOR/Multibot', public_origin=origin)
    return access


async def test_auditor_reads_controls_but_never_workspace_or_mutations(tmp_path):
    sock = listening_socket(); origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    access = credentials(tmp_path, origin)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    async with running(svc, sock):
        run, _ = await seed_actual_work(svc)
        key = (tmp_path / 'collector.key').read_text().strip()
        async with httpx.AsyncClient(base_url=origin, headers={'Authorization': 'Bearer ' + key}, trust_env=False) as c:
            assert (await c.get('/api/auth/me')).json()['role'] == 'auditor'
            assert (await c.get('/api/admin/ready')).status_code == 503
            for path in ['/api/admin/metrics', '/api/admin/jobs', '/api/admin/audit?latest=true&limit=10']:
                assert (await c.get(path)).status_code == 200
            for path in ['/api/runs', '/api/config', '/api/config/yaml', '/api/approvals', f'/api/runs/{run.run_id}',
                         f'/api/runs/{run.run_id}/export', f'/api/artifacts/{run.run_id}/email.md/versions/1/raw']:
                assert (await c.get(path)).status_code == 403, path
            assert (await c.post(f'/api/runs/{run.run_id}/cancel')).status_code == 403
            assert (await c.put('/api/limits', json={})).status_code == 403
            # Even an accidental explicit write grant cannot extend this role.
            await svc.db.execute('INSERT INTO run_access(run_id,subject,permission) VALUES(?,?,?)', (run.run_id, 'collector', 'write'))
            assert (await c.get(f'/api/runs/{run.run_id}')).status_code == 403


async def test_external_collector_outage_restart_rotation_and_snapshot_cursor(tmp_path):
    sock = listening_socket(); port = sock.getsockname()[1]; origin = f'http://127.0.0.1:{port}'
    access = credentials(tmp_path, origin)
    actual = json.loads((EVIDENCE.parent / 'durable-execution-2026-09-14/cancelled-real-run.json').read_text())
    root = tmp_path / 'data'
    svc = AppService(root, config_yaml=actual['config_snapshot']['config_yaml'], access_file=access)
    observer = Observer(origin, tmp_path / 'collector.key', tmp_path / 'observer')
    results = []
    async with running(svc, sock):
        await seed_actual_work(svc)
        first = await asyncio.to_thread(observer.collect)
        assert first['state'] == 'healthy', first
        assert first['audit_records_retained'] > 0
        stream = svc.audit_stream_id
        second = await asyncio.to_thread(observer.collect)
        assert second['alerts_recorded'] == 0
        results += [first, second]
    down = await asyncio.to_thread(observer.collect)
    assert down['state'] == 'unreachable' and down['alerts_recorded'] == 1
    assert 'agentteam_runs' not in (tmp_path / 'observer/metrics.prom').read_text()
    results.append(down)
    async with running(AppService(root, access_file=access), listening_socket(port)):
        recovered = await asyncio.to_thread(Observer(origin, tmp_path / 'collector.key', tmp_path / 'observer').collect)
        assert recovered['state'] == 'healthy' and recovered['details']['audit_stream_id'] == stream
        assert recovered['audit_records_retained'] > second['audit_records_retained']
        issue_key(access, 'collector', 'auditor', tmp_path / 'rotated.key')
        rejected = await asyncio.to_thread(observer.collect)
        assert rejected['state'] == 'collection_failed'
        observer = Observer(origin, tmp_path / 'rotated.key', tmp_path / 'observer')
        rotated = await asyncio.to_thread(observer.collect)
        assert rotated['state'] == 'healthy'
        results += [recovered, rejected, rotated]
    backup(root, tmp_path / 'snapshot')
    restore(tmp_path / 'snapshot', tmp_path / 'restored')
    async with running(AppService(tmp_path / 'restored', access_file=access), listening_socket(port)):
        restored = await asyncio.to_thread(observer.collect)
        assert restored['state'] == 'healthy' and restored['details']['audit_stream_id'] != stream
        results.append(restored)
        with sqlite3.connect(tmp_path / 'observer/observer.sqlite') as db:
            assert db.execute('SELECT count(*) FROM cursors').fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM alerts WHERE kind='audit_source_changed'").fetchone()[0] == 1
            assert db.execute('SELECT count(*) FROM audit_records').fetchone()[0] == restored['audit_records_retained']
        # A privileged admin key is intentionally refused by the collector itself.
        privileged = Observer(origin, tmp_path / 'maintainer.key', tmp_path / 'admin-observer')
        assert (await asyncio.to_thread(privileged.collect))['state'] == 'collection_failed'
    evidence = os.environ.get('AGENTTEAM_OBSERVER_EVIDENCE')
    if evidence:
        Path(evidence).write_text(json.dumps({'checks': ['restricted role', 'actual HTTP outage', 'restart with persistent cursor',
            'credential rotation', 'snapshot stream separation'], 'observations': results, 'business_success_claimed': False}, indent=2) + '\n')


async def test_collector_can_use_private_loopback_preserving_https_public_host(tmp_path):
    sock = listening_socket(); backend = f'http://127.0.0.1:{sock.getsockname()[1]}'
    origin = 'https://localhost'
    access = credentials(tmp_path, origin)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    async with running(svc, sock):
        observer = Observer(origin, tmp_path / 'collector.key', tmp_path / 'observer', private_backend=backend)
        result = await asyncio.to_thread(observer.collect)
        assert result['state'] == 'not_ready' and result['audit_records_retained'] > 0
        assert 'capability_check' in result['details']['configuration_problems']
    with pytest.raises(ValueError, match='loopback'):
        Observer(origin, tmp_path / 'collector.key', tmp_path / 'observer', private_backend='https://github.com')
