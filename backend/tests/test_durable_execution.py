"""Actual SQLite/process/HTTP failure drills using original recorded local-model work.

No mocked provider, fabricated response, fake store or synthetic business input.
Queue-store checks inspect delivery state and do not claim a business task passed.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.contracts import Run
from agentteam.ids import new_id
from agentteam.operations.backup import backup, restore
from agentteam.security.accounts import digest
from agentteam.store.db import Database
from agentteam.store.job_store import JobConflict, JobStore
from agentteam.store.run_store import RunStore
from .test_server_security import EVIDENCE, ORIGIN, PROFILE, provision, seed_actual_work


async def stored_request(root):
    root.mkdir()
    db = await Database(root / 'agentteam.sqlite').connect()
    run = Run.model_validate_json((EVIDENCE / 'thinking-interruption.json').read_text())
    await RunStore(db).create_run(run)
    return db, run


async def test_actual_sqlite_competing_claims_and_owner_fencing(tmp_path):
    db, run = await stored_request(tmp_path / 'queue')
    peer = await Database(db.path).connect()
    try:
        jobs, other = JobStore(db), JobStore(peer)
        job = await jobs.enqueue(run.run_id, resume=True, max_pending=2)
        owners = [new_id('worker'), new_id('worker')]
        claims = await asyncio.gather(jobs.claim(job['job_id'], owners[0]), other.claim(job['job_id'], owners[1]))
        assert sum(c is not None for c in claims) == 1
        winner = 0 if claims[0] else 1
        assert not await jobs.renew(job['job_id'], owners[1 - winner])
        assert not await jobs.finish(job['job_id'], owners[1 - winner], 'finished')
        assert await jobs.renew(job['job_id'], owners[winner])
        assert await jobs.finish(job['job_id'], owners[winner], 'interrupted')
        assert not await jobs.claim(job['job_id'], new_id('worker'))
        assert (await RunStore(db).get_run(run.run_id)).usage == run.usage
    finally:
        await peer.close(); await db.close()


async def test_queue_cancellation_and_receipt_are_persistent(tmp_path):
    db, run = await stored_request(tmp_path / 'queue')
    try:
        jobs = JobStore(db)
        receipt = {'scope_key': digest(new_id('request')), 'request_hash': digest(run.model_dump_json()),
                   'status': 202, 'response_json': run.model_dump_json()}
        job = await jobs.enqueue(run.run_id, resume=True, max_pending=1, receipt=receipt)
        assert (await jobs.receipt(receipt['scope_key']))['run_id'] == run.run_id
        with pytest.raises(JobConflict):
            await jobs.enqueue(run.run_id, resume=True, max_pending=1)
        assert await jobs.cancel_queued(run.run_id)
        assert not await jobs.claim(job['job_id'], new_id('worker'))
        assert (await RunStore(db).get_run(run.run_id)).status == 'cancelled'
        assert (await jobs.get(job['job_id']))['state'] == 'cancelled'
    finally:
        await db.close()
    db = await Database(db.path).connect()
    try:
        assert (await JobStore(db).receipt(receipt['scope_key']))['response_json'] == run.model_dump_json()
        assert (await JobStore(db).get(job['job_id']))['state'] == 'cancelled'
    finally:
        await db.close()


async def test_process_death_after_claim_does_not_replay_work(tmp_path):
    access, _ = provision(tmp_path)
    svc = await AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access).start()
    run, _ = await seed_actual_work(svc)
    await svc.stop()
    # A real child process claims the recorded request, then dies without cleanup.
    script = '''
import asyncio, os, sys
from agentteam.store.db import Database
from agentteam.store.job_store import JobStore
from agentteam.ids import new_id
async def main():
    db = await Database(sys.argv[1]).connect()
    jobs = JobStore(db)
    job = await jobs.enqueue(sys.argv[2], resume=True, max_pending=1)
    assert await jobs.claim(job['job_id'], new_id('worker'))
    os._exit(17)
asyncio.run(main())
'''
    child = await asyncio.create_subprocess_exec(sys.executable, '-c', script, str(svc.data_dir / 'agentteam.sqlite'), run.run_id,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = await child.communicate()
    assert child.returncode == 17, stderr.decode()
    restarted = await AppService(svc.data_dir, access_file=access).start()
    try:
        saved = await restarted.runs.get_run(run.run_id)
        assert saved.status == 'interrupted' and saved.usage == run.usage
        assert not restarted.manager._tasks
        assert await restarted.manager.jobs.pending() == []
        row = await restarted.db.fetchone('SELECT state,reason FROM execution_jobs WHERE run_id=?', (run.run_id,))
        assert row['state'] == 'interrupted' and 'no automatic replay' in row['reason']
        assert any(e.type == 'execution.recovered' for e in await restarted.events.list(run.run_id))
    finally:
        await restarted.stop()


async def test_actual_request_idempotency_survives_restart_and_is_actor_scoped(tmp_path):
    access, keys = provision(tmp_path)
    record = json.loads((EVIDENCE / 'thinking-interruption.json').read_text())
    body = {'goal': record['goal'], 'inputs': record['inputs'], 'start': False}
    request_key = new_id('request')
    builder = {'Authorization': 'Bearer ' + keys['builder'], 'Idempotency-Key': request_key}
    root = tmp_path / 'data'
    replies = []
    for _ in range(2):
        svc = AppService(root, config_yaml=PROFILE.read_text(), access_file=access)
        app = create_app(svc)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
                response = await client.post('/api/runs', headers=builder, json=body)
                assert response.status_code == 409  # real unprobed profile; never fabricate a passing capability
                replies.append(response.json())
                assert len(await svc.runs.list_runs()) == 1
                changed = await client.post('/api/runs', headers=builder, json={**body, 'budget_usd': 1})
                assert changed.status_code == 409 and changed.json()['detail'].startswith('Idempotency-Key')
    assert replies[0] == replies[1]
    app = create_app(AppService(root, access_file=access))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
            other = await client.post('/api/runs', headers={'Authorization': 'Bearer ' + keys['maintainer'], 'Idempotency-Key': request_key}, json=body)
            assert other.status_code == 409 and other.json()['run_id'] != replies[0]['run_id']


async def test_snapshot_restored_queue_cannot_replay_original_host_effects(tmp_path):
    access, _ = provision(tmp_path)
    svc = await AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access).start()
    run, _ = await seed_actual_work(svc)
    await svc.stop()
    db = await Database(svc.data_dir / 'agentteam.sqlite').connect()
    await JobStore(db).enqueue(run.run_id, resume=True, max_pending=1)
    await db.close()
    backup(svc.data_dir, tmp_path / 'snapshot')
    restore(tmp_path / 'snapshot', tmp_path / 'restored')
    recovered = await AppService(tmp_path / 'restored', access_file=access).start()
    try:
        assert not recovered.manager._tasks
        assert await recovered.manager.jobs.pending() == []
        assert (await recovered.runs.get_run(run.run_id)).status == 'interrupted'
        assert (await recovered.db.fetchone('SELECT state FROM execution_jobs'))['state'] == 'interrupted'
    finally:
        await recovered.stop()
