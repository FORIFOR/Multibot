"""Check public response boundaries over real HTTP, SQLite and issued keys.

Uses unchanged recorded local-model runs/events and actual repository documents.
New requests and forks use start=False; no provider, IdP or LLM is invoked.
The supplied root must not exist. Credentials and the database stay private there.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import socket
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import uvicorn

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from agentteam.api.app import create_app
from agentteam.api.responses import event_response
from agentteam.api.service import AppService
from agentteam.contracts import Event, Run
from agentteam.security.accounts import issue_key


PRIVATE_AGENT_FIELDS = {'config_yaml', 'system_prompt', 'api_key_ref', 'base_url', 'connection_id', 'skills', 'prompt_mode'}


def keys_in(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(keys_in(v) for v in value.values()), set())
    if isinstance(value, list):
        return set().union(*(keys_in(v) for v in value), set())
    return set()


def check_run(value):
    assert 'config_snapshot' in value
    assert not PRIVATE_AGENT_FIELDS & keys_in(value['config_snapshot'])


def check_events(events):
    for event in events:
        if event.get('type') == 'config.resolved':
            assert not PRIVATE_AGENT_FIELDS & keys_in(event['payload'])
        if event.get('type') == 'tool.called':
            assert event['payload']['details_restricted'] is True
            assert 'args' not in event['payload'] and 'result_preview' not in event['payload']
        if event.get('type') == 'run.forked':
            assert 'overrides' not in event['payload']
            assert isinstance(event['payload']['configuration_changed'], bool)


async def check(root: Path):
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    (root / 'security').mkdir(mode=0o700)
    source = REPO / 'docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/01/run.json'
    source_events = source.with_name('events.jsonl')
    profile = REPO / 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-run.json'
    source_data = json.loads(source.read_text())
    recorded = Run.model_validate(source_data)
    recorded_events = [Event.model_validate_json(line) for line in source_events.read_text().splitlines() if line]
    config_yaml = json.loads(profile.read_text())['config_snapshot']['config_yaml']
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    access = root / 'security/access.json'
    for subject, role in [('forifor', 'admin'), ('public-response-reviewer', 'operator')]:
        issue_key(access, subject, role, root / f'{subject}.key',
                  organization='FORIFOR/Multibot', public_origin=origin)
    admin = {'Authorization': 'Bearer ' + (root / 'forifor.key').read_text().strip()}
    operator = {'Authorization': 'Bearer ' + (root / 'public-response-reviewer.key').read_text().strip()}
    svc = AppService(root / 'data', config_yaml=config_yaml, access_file=access)
    server = uvicorn.Server(uvicorn.Config(create_app(svc), log_level='warning', access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    results = []
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if serving.done():
                await serving
                raise RuntimeError('HTTP server did not start')
            if time.monotonic() > deadline:
                raise TimeoutError('HTTP server startup timed out')
            await asyncio.sleep(0.05)
        await svc.runs.create_run(recorded)
        # Preserve source event IDs, timestamps and payloads when importing.
        for event in recorded_events:
            assert event.run_id == recorded.run_id
            await svc.db.execute(
                'INSERT INTO events(run_id,seq,event_id,recorded_at,actor_id,actor_kind,task_id,causation_id,type,payload_json) '
                'VALUES(?,?,?,?,?,?,?,?,?,?)',
                (event.run_id, event.seq, event.event_id, event.recorded_at, event.actor_id, event.actor_kind,
                 event.task_id, event.causation_id, event.type, json.dumps(event.payload, ensure_ascii=False)))
        async with httpx.AsyncClient(base_url=origin, timeout=15, trust_env=False) as client:
            private = await client.get(f'/api/runs/{recorded.run_id}', headers=admin)
            assert private.status_code == 200
            assert private.json()['config_snapshot'] == recorded.config_snapshot
            assert (await client.get(f'/api/runs/{recorded.run_id}', headers=operator)).status_code == 404
            grant = await client.put(f'/api/runs/{recorded.run_id}/access', headers=admin,
                                     json={'subject': 'public-response-reviewer', 'permission': 'write'})
            assert grant.status_code == 200
            public = await client.get(f'/api/runs/{recorded.run_id}', headers=operator)
            assert public.status_code == 200
            check_run(public.json())
            assert public.json()['config_snapshot']['agents']
            results.append('recorded run detail projected; administrator snapshot and run authorization retained')

            # Native SSE/download URLs remain bound to their original browser
            # principal even when a shared cookie switches to an administrator.
            for suffix, extra in (('stream', {}), ('export', {}), ('export', {'fmt': 'zip'})):
                url = f'/api/runs/{recorded.run_id}/{suffix}'
                subject_context = {'browser_subject': 'public-response-reviewer', **extra}
                changed = await client.get(url, headers=admin, params=subject_context)
                assert changed.status_code == 401
                matched = await client.get(url, headers=operator, params=subject_context)
                assert matched.status_code == 200
            results.append('SSE and native downloads reject changed browser principal before administrator projection')

            cfg = (await client.get('/api/config', headers=operator)).json()
            assert not PRIVATE_AGENT_FIELDS & keys_in(cfg)
            assert cfg['connections'] == [] and cfg['effective_agents'] == {}
            assert cfg['agents'] and all(set(a) <= {'id', 'role', 'enabled', 'display_name', 'emoji'} for a in cfg['agents'])
            assert cfg['execution_summary'] and 'budget_usd' in cfg['limits']
            assert 'pricing' not in cfg and 'profile_name' not in cfg and 'skills' not in cfg
            assert (await client.get('/api/config/yaml', headers=operator)).status_code == 403
            assert (await client.get('/api/admin/audit', headers=operator)).status_code == 403
            assert (await client.get('/api/config', headers=admin)).json()['effective_agents']
            results.append('non-admin configuration allowlist keeps roster, model destination and request budget')

            document = (REPO / 'docs/PRODUCTION_PLAN.md').read_text()
            body = {'goal': '添付した実資料の本番受入条件を確認する依頼を保存してください。今回は実行しません。',
                    'inputs': {'text': document}, 'start': False}
            headers = {**operator, 'Idempotency-Key': 'public-response-recorded-input'}
            created = await client.post('/api/runs', headers=headers, json=body)
            assert created.status_code == 202, created.status_code
            check_run(created.json())
            created_id = created.json()['run_id']
            replay = await client.post('/api/runs', headers=headers, json=body)
            assert replay.status_code == 202 and replay.json() == created.json()
            check_run(replay.json())
            # Receipts intentionally retain internal state, but replay is viewed
            # under the current role, never returned as a trusted serialized body.
            receipt = await svc.db.fetchone('SELECT response_json FROM request_receipts WHERE run_id=?', (created_id,))
            assert receipt and 'config_yaml' in json.loads(receipt['response_json'])['config_snapshot']
            results.append('real-document start=False creation and persisted receipt replay projected without inference')

            fork = await client.post(f'/api/runs/{recorded.run_id}/fork', headers=operator, json={'start': False})
            assert fork.status_code == 202, fork.status_code
            check_run(fork.json())
            # Reapply the actual configured model explicitly through an admin
            # fork, so the event contains real administrator override data.
            admin_fork = await client.post(f'/api/runs/{recorded.run_id}/fork', headers=admin,
                                          json={'start': False, 'overrides': {'agents': {
                                              'builder': {'model': svc.config.defaults.model}}}})
            assert admin_fork.status_code == 202, admin_fork.status_code
            listing = await client.get('/api/runs', headers=operator)
            assert listing.status_code == 200
            for run in listing.json():
                check_run(run)
            assert admin_fork.json()['run_id'] not in {run['run_id'] for run in listing.json()}
            results.append('start=False fork and run list projected')

            events = await client.get(f'/api/runs/{recorded.run_id}/events', headers=operator)
            assert events.status_code == 200
            check_events(events.json())
            assert any(e['type'] == 'config.resolved' for e in events.json())
            assert any(e['type'] == 'tool.called' for e in events.json())
            streamed = await client.get(f'/api/runs/{recorded.run_id}/stream', headers=operator)
            assert streamed.status_code == 200
            stream_events = [json.loads(line[6:]) for line in streamed.text.splitlines()
                             if line.startswith('data: ') and '"payload"' in line]
            assert stream_events
            check_events(stream_events)
            exported = await client.get(f'/api/runs/{recorded.run_id}/export', headers=operator)
            assert exported.status_code == 200
            check_events([json.loads(line) for line in exported.text.splitlines() if line])
            zipped = await client.get(f'/api/runs/{recorded.run_id}/export?fmt=zip', headers=operator)
            assert zipped.status_code == 200
            with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
                check_events([json.loads(line) for line in archive.read('events.jsonl').splitlines() if line])
            admin_events = (await client.get(f'/api/runs/{recorded.run_id}/events', headers=admin)).json()
            assert admin_events[:len(recorded_events)] == [event.model_dump(mode='json') for event in recorded_events]
            # The real fork above appends its own source-run audit event.
            assert [event['type'] for event in admin_events[len(recorded_events):]] == ['run.forked', 'run.forked']
            results.append('recorded event API, SSE, JSONL and ZIP logs projected; administrator events unchanged')

            # Saving the actual existing connection through its real API resets
            # its capability record. The resulting genuine fork refusal must
            # disclose no configuration diagnostics to the operator.
            connection = svc.config.connections[0]
            updated = await client.put(f'/api/connections/{connection.id}', headers=admin, json={
                'expected_revision': svc.config_revision, 'driver': connection.driver,
                'base_url': connection.base_url, 'api_key_ref': connection.api_key_ref})
            assert updated.status_code == 200
            refused = await client.post(f'/api/runs/{created_id}/fork', headers=operator, json={'start': False})
            assert refused.status_code == 409
            assert refused.json() == {'detail': 'execution could not be started; contact the administrator'}
            private_refusal = await client.post(f'/api/runs/{created_id}/fork', headers=admin, json={'start': False})
            assert private_refusal.status_code == 409 and private_refusal.json() != refused.json()
            results.append('real preflight refusal keeps 409 with private administrator diagnostics')

            original = await svc.runs.get_run(recorded.run_id)
            assert original.config_snapshot == recorded.config_snapshot
            assert not await svc.db.fetchone('SELECT job_id FROM execution_jobs LIMIT 1')
            assert not await svc.db.fetchone("SELECT seq FROM events WHERE run_id=? AND type='model.called'", (created_id,))
            results.append('runtime snapshot preserved; no execution jobs or new model calls')

        # Only actual-source workflow evidence is eligible here. Its tool event
        # exercises the projection boundary; it contains no host absolute path,
        # so it cannot prove that concrete path case. Do not fabricate one.
        original = next(event.model_dump(mode='json') for event in recorded_events
                        if event.type == 'tool.called' and 'args' in event.payload)
        original_bytes = json.dumps(original, ensure_ascii=False, sort_keys=True)
        projected = event_response(original, administrator=False)
        assert 'args' not in projected['payload'] and 'result_preview' not in projected['payload']
        assert projected['payload']['details_restricted'] is True
        assert projected['payload']['ok'] == original['payload']['ok']
        assert json.dumps(original, ensure_ascii=False, sort_keys=True) == original_bytes
        results.append('actual-source v18 tool details withheld without rewriting source evidence')
        result = {
            'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': results,
            'transport': 'real loopback HTTP with actual issued keys and SQLite',
            'source_sha256': {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (source, source_events, profile)},
            'model_inference': 'none; saved actual records and start=False requests only',
            'previous_evidence': 'r3 is retained but excluded from acceptance evidence because it also used a legacy synthetic LP scenario.',
            'limitations': ['No successful resume was initiated because that starts model execution.',
                            'No concrete host-absolute-path case is verified by the selected actual-source tool events.',
                            'No hosted IdP, public TLS, business-quality or production acceptance is claimed.'],
        }
        (root / 'response-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=15)
        sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='new private verification directory')
    asyncio.run(check(parser.parse_args().root.resolve()))
