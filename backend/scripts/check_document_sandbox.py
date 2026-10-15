#!/usr/bin/env python3
"""Real HTTP/Gateway/SQLite regression for file-only document review.

Uses preserved v62 business inputs and bytes; technical configuration variants
exercise authorization boundaries, not new business examples. All actual run
slots are held before any execution request, queued jobs are cancelled before
release, and no model/probe/VM is started. Private logs are not CI artifacts;
only safe-report.json is intended for publication.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import redirect_stderr
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import traceback

import httpx
import uvicorn

from check_database_concurrency import import_records, now
from check_message_handoff import REPO, Replay, require, sha, tool, write_json
from public_service_workflow import restricted_profile
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.config.loader import config_to_yaml, load_config_text
from agentteam.runtime.context import SessionContext
from agentteam.runtime.sandbox import backend_name
from agentteam.runtime.tool_capabilities import requires_command_sandbox
from agentteam.runtime.tools import ToolGateway
from agentteam.runtime.worker import AgentRunner
from agentteam.security.accounts import issue_key

FILES = ['backend/agentteam/api/app.py', 'backend/agentteam/api/service.py',
         'backend/agentteam/runtime/tool_capabilities.py', 'backend/agentteam/runtime/tools.py',
         'backend/agentteam/runtime/orchestrator.py', 'backend/agentteam/runtime/checks.py',
         'backend/agentteam/runtime/check_worker.py', 'backend/agentteam/runtime/sandbox.py',
         'backend/agentteam/runtime/worker.py', 'backend/scripts/check_document_sandbox.py',
         'backend/scripts/check_message_handoff.py', 'backend/scripts/check_database_concurrency.py',
         'backend/scripts/public_service_workflow.py']
LIMITS = [
    'Actual v62 inputs/artifacts are reused; technical tool/role/workflow/selection/override variants are labelled boundary tests.',
    'All real execution slots are held before requests; queued jobs are cancelled before release. No model, probe, CLI agent or VM execution.',
    'Explicit seatbelt backend selection resolves to sandbox-exec on macOS or none elsewhere; require_container refuses both before shell creation.',
    'JSON schema replay launches the fixed bounded check_worker on real recorded bytes; this is not shell/model execution.',
    'TOCTOU checks use real config replacement between resolution and SQLite persistence; HTTP race timing is not claimed.',
    'This verifies implementation boundaries, not completed inference, document semantic quality or human acceptance.',
]


def db_state(path):
    path = Path(path).resolve()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        return {'model_events': conn.execute("SELECT count(*) FROM events WHERE type LIKE 'model.%'").fetchone()[0],
                'jobs': dict(conn.execute('SELECT state,count(*) FROM execution_jobs GROUP BY state'))}


def check(report, name, condition, **measurements):
    report['checks'].append({'id': name, 'passed': bool(condition), **measurements})
    require(condition, name)


async def gateway_checks(records, root, report):
    async with Replay(records, 1, root / 'gateway') as replay:
        replay.rt.require_container = True  # Same secured mode as RunManager._build_runtime.
        initial = replay.rt.policy.usage.model_calls
        call = tool(replay.original, 'run_check', predicate=lambda e: e.payload.get('ok'))
        actual = json.loads(await replay.call(call))
        events = await replay.rt.events.list(replay.run.run_id, replay.cutoff)
        completed = [e for e in events if e.type == 'check.completed']
        check(report, 'gateway_real_schema_worker', actual['result']['status'] == 'pass' and len(completed) == 1)
        target = completed[0].payload['target']
        artifact = await replay.rt.artifacts.get(replay.run.run_id, target['artifact_id'], target['revision'])
        check(report, 'gateway_recorded_revision_sha', target['sha256'] == artifact.sha256,
              artifact_sha256=artifact.sha256, revision=artifact.revision)
        runner = AgentRunner(replay.ctx)
        check(report, 'gateway_worker_same_tools', runner.gateway.allowed_tools() == replay.gateway.allowed_tools()
              and 'sandbox_run' not in [s.name for s in runner.gateway.specs()])
        # These are authorization probes with no payload execution, not business data.
        denied = await replay.gateway.call('run_check', {'kind': 'command'})
        check(report, 'document_reviewer_command_denied', denied.startswith('DENIED: document reviewers'))
        denied = await replay.gateway.call('sandbox_run', {'command': 'true'})
        check(report, 'document_reviewer_sandbox_denied', denied.startswith('DENIED'))
        for name, workflow, agent_id in [('team_reviewer', 'team', replay.ctx.agent.agent_id),
                                          ('document_builder', 'document', replay.owner)]:
            replay.rt.run.inputs.workflow = workflow
            agent = replay.rt.agents[agent_id]
            task = next(t for t in replay.rt.tasks.values() if t.spec.owner == agent_id)
            ctx = SessionContext(replay.rt, agent, 'task', task=task, tools=agent.tools)
            gateway = ToolGateway(ctx)
            result = json.loads(await gateway.call('run_check', {'kind': 'command'}))
            check(report, name + '_container_guard', result['result']['status'] == 'blocked'
                  and result['result']['exit_code'] is None and result['result']['backend'] != 'docker')
            result = await gateway.call('sandbox_run', {'command': 'true'})
            check(report, name + '_sandbox_container_guard', result.startswith('DENIED: secured work requires Docker isolation'))
        check(report, 'gateway_no_model', replay.rt.policy.usage.model_calls == initial)
        write_json(root / 'gateway-results.json', {'schema_response': actual,
                   'replay_calls': replay.calls,
                   'events': [e.model_dump(mode='json') for e in await replay.rt.events.list(replay.run.run_id, replay.cutoff)]})


async def verify(args):
    os.umask(0o077)
    require(not args.root.is_relative_to(args.source) and not args.root.is_relative_to(REPO), 'use a fresh private root')
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    # Actual backend selection, never a patched function or fake daemon response.
    os.environ['AGENTTEAM_SANDBOX'] = 'seatbelt'
    report = {'status': 'RUNNING', 'started_at': now(), 'checks': [], 'http': [], 'queues': [],
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'implementation_sha256': {name: sha((REPO / name).read_bytes()) for name in FILES},
              'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'limits': LIMITS,
              'model_execution': False, 'human_acceptance': 'not_performed', 'business_quality_accepted': False,
              'cleanup': {'service_stopped': False, 'port_closed': False, 'pending_jobs': None},
              'source_unchanged': None, 'model_event_delta': None}
    shutil.copyfile(__file__, args.root / 'runner-source.py')
    records = service = server = server_task = None
    port = None
    held = 0
    initial = None
    try:
        records = await import_records(args.source, args.root / 'data')
        _, original, _, _ = records.record(1)
        _, failed, _, _ = records.record(2)
        bounded = restricted_profile(args.root / 'data/agents.yaml')
        unrestricted = load_config_text(original.config_snapshot['config_yaml'])
        (args.root / 'data/agents.yaml').write_text(config_to_yaml(bounded))
        report['config_sha256'] = {key: sha(config_to_yaml(cfg).encode()) for key, cfg in
                                   [('file_only', bounded), ('preserved_full', unrestricted)]}
        initial = db_state(args.root / 'data/agentteam.sqlite')
        require(not initial['jobs'], 'no original jobs may be imported')
        actual_backend = await backend_name()
        check(report, 'actual_non_docker_backend', actual_backend in ('sandbox-exec', 'none'), backend=actual_backend)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        access = args.root / 'access.json'
        for subject, role in [('boundary-admin', 'admin'), ('boundary-operator', 'operator')]:
            issue_key(access, subject, role, args.root / f'{role}.key',
                      organization='Document sandbox boundary verification', public_origin=origin)
        service = AppService(args.root / 'data', access_file=access)
        log_config = {'version': 1, 'disable_existing_loggers': False,
                      'formatters': {'timed': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
                      'handlers': {'private': {'class': 'logging.FileHandler', 'filename': str(args.root / 'service.log'),
                                              'formatter': 'timed', 'encoding': 'utf-8'}},
                      'loggers': {'uvicorn': {'handlers': ['private'], 'level': 'INFO', 'propagate': False},
                                  'uvicorn.error': {'level': 'INFO'},
                                  'uvicorn.access': {'handlers': ['private'], 'level': 'INFO', 'propagate': False}}}
        logging.Formatter.converter = time.gmtime
        server = uvicorn.Server(uvicorn.Config(create_app(service), host='127.0.0.1', port=port,
                                             log_config=log_config, access_log=True))
        with (args.root / 'stderr.log').open('w') as stderr, redirect_stderr(stderr):
            server_task = asyncio.create_task(server.serve())
            for _ in range(100):
                if server.started:
                    break
                require(not server_task.done(), 'startup failed')
                await asyncio.sleep(.05)
            require(server.started, 'startup timed out')
            # Dispatcher has no imported jobs. Hold every real execution slot
            # before exposing any request that could enqueue work.
            for _ in range(service.access.config.max_active_runs):
                await service.manager._run_slots.acquire(); held += 1
            check(report, 'all_execution_slots_held', held == service.access.config.max_active_runs
                  and not service.manager.live and not await service.db.fetchall('SELECT * FROM execution_jobs'))
            async with httpx.AsyncClient(base_url=origin, timeout=20, trust_env=False) as admin, \
                    httpx.AsyncClient(base_url=origin, timeout=20, trust_env=False) as operator:
                for role, client in [('admin', admin), ('operator', operator)]:
                    login = await client.post('/api/auth/login', headers={'Origin': origin},
                                              json={'token': (args.root / f'{role}.key').read_text().strip()})
                    check(report, role + '_real_login', login.status_code == 200)

                async def request(name, method, path, expected, body=None, client=admin, key=None):
                    headers = {'Origin': origin}
                    if key:
                        headers['Idempotency-Key'] = key
                    response = await client.request(method, path, json=body, headers=headers)
                    report['http'].append({'id': name, 'method': method, 'path': path, 'status': response.status_code,
                                           'body': response.json(), 'request_id': response.headers.get('x-request-id')})
                    check(report, name, response.status_code == expected, http_status=response.status_code)
                    return response.json()

                async def cancel_queued(name, run_id):
                    jobs = await service.db.fetchall('SELECT state FROM execution_jobs WHERE run_id=?', (run_id,))
                    check(report, name + '_queued_only', bool(jobs) and jobs[-1]['state'] == 'queued'
                          and not any(j['state'] == 'leased' for j in jobs) and not service.manager.live)
                    check(report, name + '_model_before_cancel', db_state(service.db.path)['model_events'] == initial['model_events'])
                    result = await request(name + '_cancel', 'POST', f'/api/runs/{run_id}/cancel', 200)
                    states = [r['state'] for r in await service.db.fetchall('SELECT state FROM execution_jobs WHERE run_id=?', (run_id,))]
                    check(report, name + '_cancelled', result['cancel_requested'] and all(s == 'cancelled' for s in states))
                    report['queues'].append({'id': name, 'before': [j['state'] for j in jobs], 'after': states,
                                             'model_event_delta': db_state(service.db.path)['model_events'] - initial['model_events']})

                def create_body(inputs=None, start=True):
                    return {'goal': original.goal, 'inputs': (inputs or original.inputs).model_dump(mode='json'), 'start': start}

                await request('ready_default_conservative', 'GET', '/api/admin/ready', 503)
                ready = await request('ready_document_file_only', 'GET', '/api/admin/ready?workflow=document', 200)
                check(report, 'ready_not_required', ready['sandbox_backend'] == 'not_required' and ready['workflow'] == 'document')
                await request('ready_unknown_workflow', 'GET', '/api/admin/ready?workflow=unknown', 422)
                created = await request('create_document', 'POST', '/api/runs', 202, create_body(), operator, 'document-boundary-create')
                await cancel_queued('create_document', created['run_id'])
                replay = await request('create_same_key', 'POST', '/api/runs', 202, create_body(), operator, 'document-boundary-create')
                check(report, 'idempotent_no_new_job', replay == created and len(await service.db.fetchall(
                    'SELECT * FROM execution_jobs WHERE run_id=?', (created['run_id'],))) == 1)
                team = original.inputs.model_copy(deep=True); team.workflow = 'team'
                await request('create_team_requires_docker', 'POST', '/api/runs', 503, create_body(team))
                await service.save_config(unrestricted, 'boundary: preserved full capabilities')
                await request('document_builder_requires_docker', 'POST', '/api/runs', 503, create_body())
                await request('save_without_execution', 'POST', '/api/runs', 202, create_body(start=False))
                role_variant = bounded.model_copy(deep=True); role_variant.agent('reviewer').role = 'builder'
                await service.save_config(role_variant, 'boundary: reviewer id with non-reviewer role')
                await request('role_not_id_requires_docker', 'POST', '/api/runs', 503, create_body())
                raw_variant = bounded.model_copy(deep=True); raw_variant.agent('reviewer').tools.append('sandbox_run')
                await service.save_config(raw_variant, 'boundary: raw reviewer tool is filtered by gateway')
                result = await request('filtered_raw_sandbox_tool', 'POST', '/api/runs', 202, create_body())
                await cancel_queued('filtered_raw_sandbox_tool', result['run_id'])
                extra = bounded.model_copy(deep=True); extra.agent('researcher').tools = ['run_check']
                await service.save_config(extra, 'boundary: disabled command-capable agent')
                result = await request('disabled_agent_ignored', 'POST', '/api/runs', 202, create_body())
                await cancel_queued('disabled_agent_ignored', result['run_id'])
                extra.agent('researcher').enabled = True
                await service.save_config(extra, 'boundary: enabled command-capable agent')
                await request('unselected_enabled_agent_requires_docker', 'POST', '/api/runs', 503, create_body())
                selected = original.inputs.model_copy(deep=True); selected.selected_agent_ids = ['builder', 'reviewer']
                selected_run = await request('selected_team_applied', 'POST', '/api/runs', 202, create_body(selected))
                await cancel_queued('selected_team_applied', selected_run['run_id'])
                await service.save_config(bounded, 'boundary: file-only capabilities')
                invalid = original.inputs.model_copy(deep=True); invalid.selected_agent_ids = ['researcher']
                count_before = (await service.db.fetchone('SELECT count(*) n FROM subject_admissions'))['n']
                blocked = await request('invalid_selection_preserves_blocked', 'POST', '/api/runs', 409, create_body(invalid), operator)
                check(report, 'invalid_selection_preserves_reservation', blocked['status'] == 'blocked' and
                      (await service.db.fetchone('SELECT count(*) n FROM subject_admissions'))['n'] == count_before + 1)
                await request('resume_preserved_full_requires_docker', 'POST', f'/api/runs/{failed.run_id}/resume', 503)
                child = await request('fork_current_file_only', 'POST', f'/api/runs/{failed.run_id}/fork', 202, {'start': True})
                await cancel_queued('fork_current_file_only', child['run_id'])
                await service.save_config(unrestricted, 'boundary: current full capabilities differ from saved child')
                await request('resume_saved_file_only', 'POST', f'/api/runs/{child["run_id"]}/resume', 200)
                await cancel_queued('resume_saved_file_only', child['run_id'])
                await request('fork_current_full_requires_docker', 'POST', f'/api/runs/{failed.run_id}/fork', 503, {'start': True})
                child_selected = await request('fork_selected_saved_config', 'POST', f'/api/runs/{selected_run["run_id"]}/fork', 202, {'start': True})
                await cancel_queued('fork_selected_saved_config', child_selected['run_id'])
                await service.save_config(bounded, 'boundary: override and stable snapshot')
                override = {'budget_usd': bounded.limits.budget_usd / 2}
                child_override = await request('fork_allowed_override', 'POST', f'/api/runs/{failed.run_id}/fork', 202,
                                               {'start': True, 'overrides': override})
                stored = await service.runs.get_run(child_override['run_id'])
                check(report, 'fork_override_saved', load_config_text(stored.config_snapshot['config_yaml']).limits.budget_usd == override['budget_usd'])
                await cancel_queued('fork_allowed_override', child_override['run_id'])
                await request('fork_invalid_override_conservative_guard', 'POST', f'/api/runs/{failed.run_id}/fork', 503,
                              {'start': True, 'overrides': {'budget_usd': 'invalid'}})
                await request('fork_invalid_override_preserves_error', 'POST', f'/api/runs/{failed.run_id}/fork', 409,
                              {'start': False, 'overrides': {'budget_usd': 'invalid'}})
                # Real config replacement, not timing manipulation or method replacement.
                resolved = service.manager.creation_config(original.inputs)
                await service.save_config(unrestricted, 'boundary: replace config after create resolution')
                saved, problems = await service.manager.create_run(original.goal, original.inputs, resolved_config=resolved)
                check(report, 'create_resolved_snapshot_survives_config_change', not problems and
                      saved.config_snapshot['config_yaml'] == config_to_yaml(resolved[0]) and
                      not requires_command_sandbox(resolved[0], original.inputs.workflow))
                await service.save_config(bounded, 'boundary: resolve fork before replacement')
                resolved_fork = service.manager.fork_config(failed, override)
                await service.save_config(unrestricted, 'boundary: replace config after fork resolution')
                saved = await service.manager.fork(failed.run_id, overrides=override, resolved_config=resolved_fork)
                check(report, 'fork_resolved_snapshot_survives_config_change',
                      saved.config_snapshot['config_yaml'] == config_to_yaml(resolved_fork) and
                      not requires_command_sandbox(resolved_fork, failed.inputs.workflow))
            check(report, 'before_release_all_jobs_cancelled', not await service.db.fetchall(
                "SELECT * FROM execution_jobs WHERE state IN ('queued','leased')"))
            check(report, 'before_release_no_model', db_state(service.db.path)['model_events'] == initial['model_events'])
            while held:
                service.manager._run_slots.release(); held -= 1
            await asyncio.sleep(1.1)  # Real dispatcher gets one turn after cancellation.
            check(report, 'after_release_no_model_or_runtime', db_state(service.db.path)['model_events'] == initial['model_events']
                  and not service.manager.live and not await service.db.fetchall("SELECT * FROM execution_jobs WHERE state IN ('queued','leased')"))
            server.should_exit = True
            await asyncio.wait_for(server_task, 15)
        await gateway_checks(records, args.root, report)
        log_text = '\n'.join((args.root / name).read_text() for name in ('service.log', 'stderr.log'))
        check(report, 'service_logs_no_error', not any(token in log_text for token in ('ERROR', 'Traceback', 'database is locked')))
        records.verify_unchanged()
        check(report, 'implementation_unchanged', all(sha((REPO / name).read_bytes()) == digest
                                                     for name, digest in report['implementation_sha256'].items()))
        report['status'] = 'PASS'
    except BaseException as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        if service is not None and hasattr(service, 'manager') and server_task and not server_task.done():
            try:
                # Keep slots held until every queued job is cancelled and all owned
                # runtime tasks are stopped, including on an assertion/HTTP failure.
                for job in await service.db.fetchall("SELECT run_id FROM execution_jobs WHERE state='queued'"):
                    await service.manager.jobs.cancel_queued(job['run_id'])
                await asyncio.wait_for(service.manager.shutdown(), 10)
                while held:
                    service.manager._run_slots.release(); held -= 1
                server.should_exit = True
                await asyncio.wait_for(server_task, 15)
            except BaseException as error:
                report.update(status='FAIL', cleanup_error_type=type(error).__name__, cleanup_traceback=traceback.format_exc())
        report['cleanup']['service_stopped'] = bool(server_task and server_task.done())
        if port:
            with socket.socket() as sock:
                sock.settimeout(.2); report['cleanup']['port_closed'] = sock.connect_ex(('127.0.0.1', port)) != 0
        if initial is not None:
            try:
                final = db_state(args.root / 'data/agentteam.sqlite')
                report['model_event_delta'] = final['model_events'] - initial['model_events']
                report['cleanup']['pending_jobs'] = sum(final['jobs'].get(s, 0) for s in ('queued', 'leased'))
                report['job_state_counts'] = final['jobs']
            except (OSError, sqlite3.Error):
                report['status'] = 'FAIL'
        if records is not None:
            report['source_sha256'] = {str(Path(p).relative_to(args.source)): v for p, v in records.hashes.items()}
            try:
                records.verify_unchanged(); report['source_unchanged'] = True
            except (AssertionError, OSError):
                report.update(status='FAIL', source_unchanged=False)
        if not (report['cleanup']['service_stopped'] and report['cleanup']['port_closed']
                and report['cleanup']['pending_jobs'] == 0 and report['model_event_delta'] == 0):
            report['status'] = 'FAIL'
        report['finished_at'] = now()
        write_json(args.root / 'report.json', report)
        safe = {key: report.get(key) for key in ['status', 'started_at', 'finished_at', 'revision', 'implementation_sha256',
                'source_sha256', 'source_unchanged', 'python', 'sqlite', 'config_sha256', 'checks', 'queues', 'model_execution',
                'model_event_delta', 'job_state_counts', 'cleanup', 'error_type', 'cleanup_error_type', 'limits',
                'human_acceptance', 'business_quality_accepted']}
        safe['http_statuses'] = [{'id': x['id'], 'status': x['status']} for x in report['http']]
        write_json(args.root / 'safe-report.json', safe)
    return report['status'] == 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=lambda p: Path(p).expanduser().resolve(), required=True)
    parser.add_argument('--root', type=lambda p: Path(p).expanduser().resolve(), required=True)
    args = parser.parse_args()
    try:
        ok = asyncio.run(verify(args))
        print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'safe_report': str(args.root / 'safe-report.json')}))
        return 0 if ok else 1
    except BaseException as error:
        # No raw exception/config/token on CI stdout or stderr.
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
