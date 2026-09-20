"""Real API + SQLite contract checks using repository documents; no provider or store mocks.

No model is called: the checked-in profile has an unprobed connection, and creation
uses start=False. Published bytes are actual repository files, not generated fixtures.
"""
import asyncio
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx

from agentteam.api.app import create_app
from agentteam.api.service import AppService

ROOT = Path(__file__).resolve().parents[2]
PROFILE = (ROOT / 'docs/config/local-qwen35-9b-team.yaml').read_text()


def client_for(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1')


async def test_local_idempotency_concurrency_restart_and_conflict(tmp_path):
    body = {'goal': (ROOT / 'docs/design/brief.md').read_text(), 'start': False}
    headers = {'Idempotency-Key': 'product-contract-create'}
    svc = AppService(tmp_path, config_yaml=PROFILE)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with client_for(app) as client:
            first, second = await asyncio.gather(*(client.post('/api/runs', json=body, headers=headers) for _ in range(2)))
            # This is an actual failed connection precheck, never a fabricated completion.
            assert first.status_code == second.status_code == 409
            assert first.json() == second.json()
            assert len((await client.get('/api/runs')).json()) == 1
            changed = await client.post('/api/runs', json={**body, 'goal': (ROOT / 'README.md').read_text()}, headers=headers)
            assert changed.status_code == 409
            assert 'different input' in changed.text
            invalid = await client.post('/api/runs', json=body, headers={'Idempotency-Key': 'bad'})
            assert invalid.status_code == 400
    reopened = create_app(AppService(tmp_path))
    async with reopened.router.lifespan_context(reopened):
        async with client_for(reopened) as client:
            replay = await client.post('/api/runs', json=body, headers=headers)
            assert replay.json() == first.json()
            assert len((await client.get('/api/runs')).json()) == 1


async def test_adoption_compare_and_set_and_exact_selected_export(tmp_path):
    svc = AppService(tmp_path, config_yaml=PROFILE)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        run, _ = await svc.manager.create_run('Compare the existing and extended product acceptance documents')
        documents = [ROOT / 'docs/design/acceptance.md', ROOT / 'docs/quality/acceptance.md']
        versions = [await svc.artifacts.publish(run.run_id, 'acceptance.md', p.read_bytes(), agent_id='user', task_id=None) for p in documents]
        async with client_for(app) as client:
            url = f'/api/artifacts/{run.run_id}/acceptance.md/adopt'
            export = f'/api/runs/{run.run_id}/export?fmt=zip'
            assert (await client.get(export+'&selection=adopted')).status_code == 409
            responses = await asyncio.gather(*(client.post(url, json={'revision': v.revision, 'expected_selected_revision': 0}) for v in versions))
            assert sorted(r.status_code for r in responses) == [202, 409]
            chosen = next(r.json()['revision'] for r in responses if r.status_code == 202)
            # Select the first document explicitly, regardless of the race winner.
            response = await client.post(url, json={'revision': 1, 'expected_selected_revision': chosen})
            assert response.status_code == 202
            seq = response.json()['seq']
            repeated = await client.post(url, json={'revision': 1, 'expected_selected_revision': 1})
            assert repeated.json()['seq'] == seq  # same state does not append a duplicate effect
            assert (await client.get(f'/api/runs/{run.run_id}')).json()['artifact_selection']['acceptance.md']['revision'] == 1
            for selection, expected in [('adopted', versions[0]), ('latest', versions[1])]:
                response = await client.get(export+'&selection='+selection)
                assert response.status_code == 200
                with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
                    assert hashlib.sha256(bundle.read('artifacts/acceptance.md')).hexdigest() == expected.sha256
                    manifest = json.loads(bundle.read('manifest.json'))
                    assert manifest['selection'] == selection
                    assert manifest['artifacts'][0]['revision'] == expected.revision
            assert (await client.get(export+'&selection=unknown')).status_code == 422


async def test_preflight_discloses_real_config_without_credentials(tmp_path):
    app = create_app(AppService(tmp_path, config_yaml=PROFILE))
    async with app.router.lifespan_context(app):
        async with client_for(app) as client:
            config = (await client.get('/api/config')).json()
            summary = config['execution_summary']
            assert summary
            for item in summary:
                assert item['destination'] == 'http://127.0.0.1:11434'
                assert item['driver'] == 'ollama'
                assert set(item) == {'driver','model','destination','tools'}


async def test_paused_direction_persists_without_execution_and_reaches_task_prompt(tmp_path):
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.worker import build_task_message

    svc = AppService(tmp_path, config_yaml=PROFILE)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        record = json.loads((ROOT/'docs/evidence/real-readiness-v12-qwen35-2026-09-14/02-run_1a09e84a3449aa4c8f5/run.json').read_text())
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        for saved in record['tasks']:
            await svc.runs.upsert_task(TaskState.model_validate(saved))
        # The original actual request is a direction to retain its source constraints.
        body = {'text': run.goal, 'kind': 'change'}
        async with client_for(app) as c:
            url = f'/api/runs/{run.run_id}'
            before = (await c.get(url)).json()
            assert before['access']['can_instruct']
            response = await c.post(url+'/instructions', json=body)
            assert response.status_code == 202 and response.json()['state'] == 'received'
            after = (await c.get(url)).json()
            for field in ['status', 'usage', 'plan', 'artifacts']:
                assert after[field] == before[field]
            assert after['latest_instruction']['payload']['text'] == run.goal
            assert not svc.manager._tasks
            rt = svc.manager._build_runtime(run, svc.config)
            task = (await svc.runs.list_tasks(run.run_id))[0]
            prompt = await build_task_message(SessionContext(rt, rt.agents[task.spec.owner], 'task', task), task)
            assert f"[{body['kind']}] {body['text']}" in prompt
            # Actual unprobed creation is blocked and has no plan.
            new, _ = await svc.manager.create_run((ROOT/'docs/design/brief.md').read_text())
            assert not new.can_receive_instruction()  # real unprobed profile is blocked
            assert (await c.post(f'/api/runs/{new.run_id}/instructions', json=body)).status_code == 409
    reopened = create_app(AppService(tmp_path))
    async with reopened.router.lifespan_context(reopened):
        async with client_for(reopened) as c:
            saved = (await c.get(url)).json()
            assert saved['status'] == 'interrupted'
            assert saved['latest_instruction']['payload']['text'] == run.goal
            assert saved['usage'] == before['usage']


async def test_direction_permissions_and_completed_record_rejected(tmp_path):
    from agentteam.contracts import Run
    from .test_server_security import provision, seed_actual_work, ORIGIN
    access, keys = provision(tmp_path)
    svc = AppService(tmp_path/'data', config_yaml=PROFILE, access_file=access)
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        run, _ = await seed_actual_work(svc)
        completed = Run.model_validate_json((ROOT/'docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/01/run.json').read_text())
        assert completed.status == 'completed'
        await svc.runs.create_run(completed)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
            admin = {'Authorization': 'Bearer '+keys['maintainer']}
            assert (await c.put(f'/api/runs/{run.run_id}/access', headers=admin, json={'subject':'reviewer','permission':'read'})).status_code == 200
            viewer = {'Authorization': 'Bearer '+keys['reviewer']}
            assert not (await c.get(f'/api/runs/{run.run_id}', headers=viewer)).json()['access']['can_instruct']
            assert (await c.post(f'/api/runs/{run.run_id}/instructions', headers=viewer, json={'text':run.goal})).status_code == 403
            assert (await c.post(f'/api/runs/{completed.run_id}/instructions', headers=admin, json={'text':completed.goal})).status_code == 409


async def test_resumed_queue_clears_current_reason_but_retains_history(tmp_path):
    from agentteam.contracts import Run, TaskState
    from agentteam.store.db import dumps
    source = ROOT/'docs/evidence/real-readiness-v12-qwen35-2026-09-14/02-run_1a09e84a3449aa4c8f5'
    record = json.loads((source/'run.json').read_text())
    run = Run.model_validate(record)
    assert run.blocked_reason == 'wall-clock limit reached'
    svc = await AppService(tmp_path, config_yaml=PROFILE).start()
    try:
        await svc.runs.create_run(run)
        for saved in record['tasks']:
            await svc.runs.upsert_task(TaskState.model_validate(saved))
        original = (source/'events.jsonl').read_text().splitlines()
        for line in original:
            event = json.loads(line)
            fields = ['run_id','seq','event_id','recorded_at','actor_id','actor_kind','task_id','causation_id','type']
            await svc.db.execute('INSERT INTO events('+','.join(fields)+',payload_json) VALUES('+','.join('?' for _ in range(10))+')',
                                 tuple(event.get(k) for k in fields)+(dumps(event['payload']),))
        await svc.manager.jobs.enqueue(run.run_id, resume=True, max_pending=1)
        queued = await svc.runs.get_run(run.run_id)
        assert queued.status == 'queued' and queued.blocked_reason is None and queued.finished_at is None
        assert queued.usage == run.usage
        rt = svc.manager._build_runtime(queued, svc.config)
        await svc.manager._prepare_resume(rt)
        tasks = await svc.runs.list_tasks(run.run_id)
        assert all(t.status == 'queued' and t.blocked_reason is None for t in tasks)
        assert [e.model_dump() for e in await svc.events.list(run.run_id)] == [json.loads(line) for line in original]
        # Admission/preparation are tested without starting any model execution.
        assert not svc.manager._tasks
        await svc.manager.jobs.cancel_queued(run.run_id)
    finally:
        await svc.stop()


async def test_model_changes_require_matching_real_probe_evidence(tmp_path):
    from agentteam.config.loader import load_config_text
    svc = await AppService(tmp_path, config_yaml=PROFILE).start()
    try:
        cfg = svc.config.model_copy(deep=True)
        probe = json.loads((ROOT / 'docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/probe.json').read_text())
        conn = cfg.connection(cfg.defaults.connection_id)
        conn.capability_check = 'passed'
        conn.capability_detail = probe
        await svc.save_config(cfg, 'Use recorded real Ollama capability evidence')
        other = load_config_text((ROOT / 'docs/config/local-qwen25-7b-team.yaml').read_text()).defaults.model
        body = {'goal': (ROOT / 'docs/design/brief.md').read_text(), 'start': False}
        async with client_for(create_app(svc)) as client:
            assert (await client.post('/api/runs', json=body)).status_code == 202
            response = await client.put('/api/limits', json={'expected_revision': svc.config_revision, 'limits': {}, 'defaults': {'model': other}})
            assert response.status_code == 200
            blocked = await client.post('/api/runs', json=body)
            assert blocked.status_code == 409 and 'capability_model' in blocked.text
            response = await client.put('/api/limits', json={'expected_revision': svc.config_revision, 'limits': {}, 'defaults': {'model': probe['model_requested']}})
            assert response.status_code == 200
            assert (await client.post('/api/runs', json=body)).status_code == 202
            response = await client.patch('/api/agents/builder', json={'expected_revision': svc.config_revision, 'model': other})
            assert response.status_code == 200
            blocked = await client.post('/api/runs', json=body)
            assert blocked.status_code == 409 and 'capability_model' in blocked.text
            swapped = svc.config.model_copy(deep=True)
            swapped.agents.reverse()
            assert any(p.get('agent_id') == 'builder' and p['code'] == 'capability_model' for p in svc.manager.precheck(swapped))
            swapped.connection(swapped.defaults.connection_id).capability_detail = None
            assert any(p['code'] == 'capability_model' for p in svc.manager.precheck(swapped))
            for run in await svc.runs.list_runs():
                assert run.usage.model_calls == 0
    finally:
        await svc.stop()
