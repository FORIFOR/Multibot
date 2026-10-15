"""Real HTTP/SQLite admission regression using repository documents; no inference.

The config must be an existing, genuinely probed local-provider profile. Requests
are saved with start=false. Queue checks operate the real store while the server
is stopped, then cancel the queued work before restart (no fake dispatcher).
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import httpx
import uvicorn

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.security.accounts import issue_key
from agentteam.store.db import Database
from agentteam.store.job_store import JobStore
from agentteam.store.usage_store import AdmissionLimit, UsageStore


@asynccontextmanager
async def running(data, access, port):
    service = AppService(data_dir=data, access_file=access)
    server = uvicorn.Server(uvicorn.Config(create_app(service), host='127.0.0.1', port=port,
                                         log_level='error', access_log=False))
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError('server stopped before startup')
            await asyncio.sleep(.05)
        if not server.started:
            raise RuntimeError('server did not start')
        yield
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 15)


async def verify(root: Path, config: Path):
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    data = root / 'data'
    data.mkdir(mode=0o700)
    shutil.copyfile(config, data / 'agents.yaml')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    access = root / 'access.json'
    for subject, role in [('admission-admin', 'admin'), ('admission-operator', 'operator'), ('admission-other', 'operator')]:
        issue_key(access, subject, role, root / f'{subject}.key', organization='Multibot admission verification', public_origin=base)
    cfg = json.loads(access.read_text())
    cfg.update(max_subject_requests_per_day=2, max_subject_pending_runs=1)
    access.write_text(json.dumps(cfg))
    source = BACKEND.parent / 'docs/PRODUCTION_PLAN.md'
    payload = {'goal': '添付したMultibot本番計画から、実装済みと残る受入条件を整理してください。',
               'inputs': {'files': [{'name': source.name, 'content': source.read_text()}]}, 'start': False}
    def auth(subject, key=None):
        result = {'Authorization': 'Bearer ' + (root / f'{subject}.key').read_text().strip()}
        if key:
            result['Idempotency-Key'] = key
        return result
    checks = {}
    operator = auth('admission-operator')
    other = auth('admission-other')
    async with running(data, access, port):
        async with httpx.AsyncClient(base_url=base, timeout=20, trust_env=False) as client:
            responses = await asyncio.gather(*[
                client.post('/api/runs', json=payload, headers=auth('admission-operator', f'admission-actual-{i}')) for i in range(3)])
            assert sorted(r.status_code for r in responses) == [202, 202, 429], [r.status_code for r in responses]
            accepted = [(i, r.json()['run_id']) for i, r in enumerate(responses) if r.status_code == 202]
            rejected = next(r for r in responses if r.status_code == 429)
            assert rejected.json()['detail']['code'] == 'subject_daily_limit'
            assert 1 <= int(rejected.headers['retry-after']) <= 86400
            checks['concurrent_http_admissions'] = '2 accepted, 1 refused; rolling 24h limit=2'
            index, run_id = accepted[0]
            replay = await client.post('/api/runs', json=payload, headers=auth('admission-operator', f'admission-actual-{index}'))
            assert replay.status_code == 202 and replay.json()['run_id'] == run_id
            usage = (await client.get('/api/usage', headers=operator)).json()
            assert usage['requests_last_24h'] == 2 and usage['requests_remaining'] == 0 and usage['next_request_at']
            checks['replay_does_not_charge_again'] = True
            fork = await client.post(f'/api/runs/{run_id}/fork', headers=operator, json={'start': False})
            assert fork.status_code == 429
            checks['fork_cannot_bypass_limit'] = True
            independent = await client.post('/api/runs', json=payload, headers=other)
            assert independent.status_code == 202
            assert (await client.get(f'/api/runs/{run_id}', headers=other)).status_code == 404
            checks['other_principal_has_separate_allowance_and_no_access'] = True
            before_switch = (await client.get('/api/usage', headers=other)).json()['requests_last_24h']
            switched = await client.post('/api/runs', json=payload, headers={**other, 'X-AgentTeam-Subject': 'admission-operator'})
            assert switched.status_code == 401
            assert (await client.get('/api/usage', headers=other)).json()['requests_last_24h'] == before_switch
            checks['stale_browser_subject_cannot_submit_as_new_account'] = True
            assert (await client.get('/api/usage')).status_code == 401
            assert (await client.get('/api/usage', headers=auth('admission-admin'))).json() == {'limited': False}
            checks['usage_is_authenticated_and_subject_scoped'] = True
    db = await Database(data / 'agentteam.sqlite').connect()
    try:
        jobs, usage = JobStore(db), UsageStore(db)
        await jobs.enqueue(run_id, resume=False, max_pending=20)
        try:
            await usage.reserve('admission-operator', 20, 1)
        except AdmissionLimit as exc:
            assert exc.code == 'subject_pending_limit'
        else:
            raise AssertionError('pending queue allowance was bypassed')
        assert (await usage.summary('admission-other', 20, 1))['pending_runs'] == 0
        assert await jobs.cancel_queued(run_id)
        assert (await usage.summary('admission-operator', 20, 1))['pending_runs'] == 0
        checks['actual_queue_pending_limit_and_cancellation'] = True
    finally:
        await db.close()
    async with running(data, access, port):
        async with httpx.AsyncClient(base_url=base, timeout=20, trust_env=False) as client:
            usage = (await client.get('/api/usage', headers=operator)).json()
            assert usage['requests_last_24h'] == 2
            denied = await client.post('/api/runs', json=payload, headers=operator)
            assert denied.status_code == 429
            checks['restart_preserves_allowance'] = True
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'source': str(source.relative_to(BACKEND.parent)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BACKEND.parent, text=True).strip(),
              'tracked_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff'], cwd=BACKEND.parent)).hexdigest(),
              'transport': 'real loopback HTTP and actual SQLite; server stopped during direct queue checks',
              'inference': 'not requested; no model replacement, no generated artifact or business-quality claim'}
    (root / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(verify(args.root.resolve(), args.config.resolve()))
