"""Real HTTP/SQLite concurrency regression, using preserved document records.

No model execution, job, mocked response, or invented business record is requested. A real
issued key creates login/audit records via AppService. The later SQLite-only
phase repeats one recorded audit INSERT in a separate copy to exercise locking;
it does NOT repeat the request or business operation described by that row.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import redirect_stderr
from datetime import datetime, timezone
import hashlib
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

from check_message_handoff import REPO, Sources, require, sha, write_json
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.contracts import ArtifactManifest
from agentteam.security.accounts import issue_key
from agentteam.store.db import Database, dumps
from agentteam.store.run_store import RunStore
from agentteam.store.usage_store import UsageStore

SUBJECT = 'concurrency-operator'
AUDIT_SQL = ('INSERT INTO audit_log(recorded_at,request_id,subject,method,route,run_id,outcome,status,details_json) '
             'VALUES(?,?,?,?,?,?,?,?,?)')


def now():
    return datetime.now(timezone.utc).isoformat()


def snapshot(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        return {
            'runs': conn.execute('SELECT run_id,status,usage_json FROM runs ORDER BY run_id').fetchall(),
            'events': conn.execute('SELECT run_id,seq,event_id,type,payload_json FROM events ORDER BY run_id,seq').fetchall(),
            'model_events': conn.execute("SELECT count(*) FROM events WHERE type LIKE 'model.%'").fetchone()[0],
            'jobs': conn.execute('SELECT count(*) FROM execution_jobs').fetchone()[0],
        }


def copy_database(source, target):
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def safe_report(report, source):
    """Allowlisted CI evidence. Raw errors, HTTP bodies and traceback stay private."""
    http = report['http']
    direct = report['direct']
    return {
        'status': report['status'], 'started_at': report['started_at'], 'finished_at': report['finished_at'],
        'revision': report['revision'], 'implementation_sha256': report['implementation_sha256'],
        'source_sha256': {str(Path(name).relative_to(source)): digest
                          for name, digest in report.get('source_sha256', {}).items()},
        'source_unchanged': report.get('source_unchanged'),
        'python': report['python'], 'sqlite': report['sqlite'],
        'model_execution': False, 'business_quality_accepted': False, 'human_acceptance': 'not_performed',
        'http': {'planned': report['planned_http'], 'attempted': len(http),
                 'passed': sum(x.get('status') == 200 for x in http),
                 'failed': sum(x.get('status') != 200 for x in http),
                 'unattempted': report['planned_http'] - len(http),
                 'status_counts': dict(Counter(str(x.get('status', 'exception')) for x in http)),
                 'exception_types': dict(Counter(x['error_type'] for x in http if 'error_type' in x)),
                 'missing_or_incomplete_terminal_audit': (len(report['audit_missing_or_incomplete'])
                                                        if 'audit_missing_or_incomplete' in report else None),
                 'audit_check_completed': 'audit_missing_or_incomplete' in report},
        'direct_parallel': {'planned': report['planned_direct'], 'attempted': len(direct),
                            'passed': sum(x['ok'] for x in direct), 'failed': sum(not x['ok'] for x in direct),
                            'unattempted': report['planned_direct'] - len(direct),
                            'errors': [{'operation': x['kind'], 'error_type': x['error_type'],
                                        'sqlite_errorcode': x.get('sqlite_errorcode'),
                                        'sqlite_errorname': x.get('sqlite_errorname')}
                                       for x in direct if not x['ok']]},
        'error_type': report.get('error_type'), 'runtime_log_error': report.get('runtime_log_error'),
        'new_model_events': report.get('new_model_events'), 'jobs': report.get('jobs'),
        'cleanup': report['cleanup'],
        'limits': ['This is an implementation regression, not a model-quality or human acceptance result.',
                   'Direct audit row insertions are storage replays, not repeats of the original HTTP/business operation.',
                   'This does not prove that the earlier incompletely logged HTTP error had the identical cause.'],
    }


async def import_records(source, data):
    records = Sources(source)
    data.mkdir(mode=0o700)
    db = await Database(data / 'agentteam.sqlite').connect()
    runs = RunStore(db)
    try:
        for rep in (1, 2, 9):
            path, run, events, artifacts = records.record(rep)
            require(run.status in ('completed', 'failed', 'interrupted'), 'live runs are not allowed')
            await runs.create_run(run)
            for event in events:
                await db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)',
                                 (event.run_id, event.seq, event.event_id, event.recorded_at, event.actor_id,
                                  event.actor_kind, event.task_id, event.causation_id, event.type, dumps(event.payload)))
            for item in artifacts:
                artifact = ArtifactManifest.model_validate(item)
                body = records.read(path / item['evidence_file'])
                require(sha(body) == artifact.sha256 and len(body) == artifact.size, 'artifact bytes changed')
                dest = data / 'runs' / artifact.storage_path
                require(dest.resolve().is_relative_to((data / 'runs').resolve()), 'artifact path escaped import')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(body)
                await db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (artifact.run_id, artifact.artifact_id, artifact.revision, artifact.sha256,
                                  artifact.media_type, artifact.size, artifact.logical_path, artifact.storage_path,
                                  artifact.task_id, artifact.agent_id, artifact.created_at, artifact.event_id,
                                  dumps(artifact.sources)))
            await db.execute('INSERT INTO run_access(run_id,subject,permission) VALUES(?,?,?)',
                             (run.run_id, SUBJECT, 'read'))
            if rep == 1:
                (data / 'agents.yaml').write_text(run.config_snapshot['config_yaml'])
    finally:
        await db.close()
    records.verify_unchanged()
    return records


async def direct_parallel(path, batches):
    """Ordinary public Database operations; no patch, forced cursor, or artificial delay."""
    db = await Database(path).connect()
    usage, observations = UsageStore(db), []
    try:
        audit = await db.fetchone('SELECT recorded_at,request_id,subject,method,route,run_id,outcome,status,details_json '
                                 "FROM audit_log WHERE subject=? AND outcome='response' LIMIT 1", (SUBJECT,))
        require(audit is not None, 'a successful real HTTP audit row is required')
        row = tuple(audit)
        run_id = (await db.fetchone('SELECT run_id FROM runs LIMIT 1'))['run_id']

        async def call(kind, batch):
            start = time.monotonic()
            item = {'kind': kind, 'batch': batch, 'started_at': now()}
            try:
                if kind == 'fetchall':
                    await db.fetchall('SELECT * FROM audit_log ORDER BY id LIMIT 2000')
                elif kind == 'fetchone':
                    await db.fetchone('SELECT * FROM runs WHERE run_id=?', (run_id,))
                elif kind == 'usage':
                    await usage.summary(SUBJECT, 20, 2)
                else:
                    await db.execute(AUDIT_SQL, row)
                item['ok'] = True
            except Exception as error:
                item.update(ok=False, error_type=type(error).__name__, error=str(error),
                            sqlite_errorcode=getattr(error, 'sqlite_errorcode', None),
                            sqlite_errorname=getattr(error, 'sqlite_errorname', None),
                            traceback=traceback.format_exc())
            item['elapsed_ms'] = round((time.monotonic() - start) * 1000, 3)
            observations.append(item)

        for batch in range(batches):
            await asyncio.gather(*(call(kind, batch) for kind in ['fetchall', 'fetchone', 'usage', 'audit_insert'] * 8))
            if any(not item['ok'] for item in observations):
                break
        return observations
    finally:
        await db.close()


async def verify(args):
    os.umask(0o077)
    require(not args.root.is_relative_to(args.source) and not args.root.is_relative_to(REPO),
            'verification root must be outside the source and repository')
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = {'started_at': now(), 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'actor': 'AI-operated regression', 'human_acceptance': 'not_performed', 'model_execution': False,
              'business_quality_accepted': False, 'python': sys.version, 'sqlite': sqlite3.sqlite_version,
              'source_scope': 'Preserved v62 rep1/2/9 runs, events and artifacts; no execution jobs or task reconstruction',
              'implementation_sha256': {name: sha((REPO / name).read_bytes()) for name in
                ('backend/agentteam/store/db.py', 'backend/agentteam/store/job_store.py',
                 'backend/agentteam/store/usage_store.py', 'backend/agentteam/security/server.py',
                 'backend/scripts/check_database_concurrency.py')},
              'audit_replay_limit': 'The SQLite-only phase copies a recorded audit row; it does not repeat its HTTP or business operation.',
              'planned_http': args.batches * 24, 'planned_direct': args.batches * 32,
              'http': [], 'direct': [], 'status': 'RUNNING'}
    write_json(args.root / 'report.json', report)
    shutil.copyfile(__file__, args.root / 'runner-source.py')
    records = None
    server_task = None
    service_stopped = False
    try:
        data = args.root / 'data'
        records = await import_records(args.source, data)
        baseline = snapshot(data / 'agentteam.sqlite')
        require(baseline['jobs'] == 0, 'no execution jobs may be imported')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        access = args.root / 'access.json'
        for subject, role in [('concurrency-admin', 'admin'), (SUBJECT, 'operator')]:
            issue_key(access, subject, role, args.root / f'{subject}.key',
                      organization='Actual SQLite concurrency verification', public_origin=origin)
        service = AppService(data_dir=data, access_file=access)
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
            try:
                for _ in range(100):
                    if server.started:
                        break
                    require(not server_task.done(), 'service stopped before startup')
                    await asyncio.sleep(.05)
                require(server.started, 'service did not start')
                async with httpx.AsyncClient(base_url=origin, timeout=20, trust_env=False) as client:
                    login = await client.post('/api/auth/login', headers={'Origin': origin},
                                              json={'token': (args.root / f'{SUBJECT}.key').read_text().strip()})
                    require(login.status_code == 200, 'real issued-key login failed')

                    async def get(path, batch):
                        start = time.monotonic()
                        item = {'path': path, 'batch': batch, 'started_at': now()}
                        try:
                            response = await client.get(path, headers={'X-AgentTeam-Subject': SUBJECT})
                            body = response.content
                            item.update(status=response.status_code, request_id=response.headers.get('x-request-id'),
                                        body_sha256=hashlib.sha256(body).hexdigest())
                        except Exception as error:
                            item.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
                        item['elapsed_ms'] = round((time.monotonic() - start) * 1000, 3)
                        report['http'].append(item)
                        with (args.root / 'http.jsonl').open('a') as output:
                            output.write(json.dumps(item, ensure_ascii=False) + '\n')

                    for batch in range(args.batches):
                        await asyncio.gather(*(get(path, batch) for path in ['/api/config', '/api/usage', '/api/runs'] * 8))
                        if any(item.get('status') != 200 for item in report['http']):
                            break
                audit_rows = await service.db.fetchall('SELECT request_id,outcome,status FROM audit_log')
                by_id = {}
                for row in audit_rows:
                    by_id.setdefault(row['request_id'], []).append((row['outcome'], row['status']))
                report['audit_missing_or_incomplete'] = [item for item in report['http']
                    if sorted(by_id.get(item.get('request_id'), [])) != [('authorized', 0), ('response', 200)]]
            finally:
                server.should_exit = True
                await asyncio.wait_for(server_task, 15)
                service_stopped = True
        require(snapshot(data / 'agentteam.sqlite') == baseline, 'HTTP changed business/model/job state')
        direct = args.root / 'direct.sqlite'
        copy_database(data / 'agentteam.sqlite', direct)
        report['direct'] = await direct_parallel(direct, args.batches)
        require(snapshot(direct) == baseline, 'direct regression changed business/model/job state')
        records.verify_unchanged()
        report.update(source_sha256=records.hashes, source_unchanged=True, new_model_events=0, jobs=0,
                      http_request_count=len(report['http']), direct_call_count=len(report['direct']))
        require(all(item.get('status') == 200 for item in report['http']), 'non-200/error in parallel HTTP')
        require(not report['audit_missing_or_incomplete'], 'missing terminal audit for a response')
        require(all(item['ok'] for item in report['direct']), 'SQLite error in ordinary parallel operations')
        log_text = '\n'.join((args.root / name).read_text() for name in ('service.log', 'stderr.log'))
        report['runtime_log_error'] = any(token in log_text for token in ('ERROR', 'Traceback', 'database is locked'))
        require(not report['runtime_log_error'], 'server error logged')
        report['status'] = 'PASS'
    except BaseException as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        with socket.socket() as sock:
            sock.settimeout(1)
            closed = 'port' not in locals() or sock.connect_ex(('127.0.0.1', port)) != 0
        report['cleanup'] = {'service_stopped': service_stopped, 'port_closed': closed, 'browser_started': False}
        if not service_stopped or not closed:
            report['status'] = 'FAIL'
        if records:
            report['source_sha256'] = records.hashes
            try:
                records.verify_unchanged()
                report['source_unchanged'] = True
            except (AssertionError, OSError):
                report['source_unchanged'] = False
                report['source_verification_traceback'] = traceback.format_exc()
                report['status'] = 'FAIL'
        log_paths = [args.root / name for name in ('service.log', 'stderr.log')]
        if all(path.is_file() for path in log_paths):
            try:
                log_text = '\n'.join(path.read_text() for path in log_paths)
                report['runtime_log_error'] = any(token in log_text for token in ('ERROR', 'Traceback', 'database is locked'))
                if report['runtime_log_error']:
                    report['status'] = 'FAIL'
            except OSError:
                report['log_verification_traceback'] = traceback.format_exc()
                report['runtime_log_error'] = None
                report['status'] = 'FAIL'
        report['finished_at'] = now()
        write_json(args.root / 'report.json', report)
        write_json(args.root / 'safe-report.json', safe_report(report, args.source))
    require(report['status'] == 'PASS', 'verification or cleanup failed; inspect the private report')
    print(json.dumps({'status': report['status'], 'http_requests': report['http_request_count'],
                      'direct_calls': report['direct_call_count'], 'source_unchanged': True,
                      'new_model_events': 0, 'jobs': 0, 'cleanup': report['cleanup']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=REPO / 'docs/evidence/real-readiness-v62-qwen35-fixed-20261002')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--batches', type=int, default=20)
    args = parser.parse_args()
    args.source, args.root = args.source.resolve(), args.root.resolve()
    if not 1 <= args.batches <= 100:
        parser.error('--batches must be between 1 and 100')
    try:
        asyncio.run(verify(args))
    except BaseException as error:
        # CI stdout must not expose exception text, private paths or traceback.
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__,
                          'details': 'inspect the private report; upload only safe-report.json'}))
        sys.exit(1)
