#!/usr/bin/env python3
"""Real-record Workroom read-only browser regression; no model/VM or mocks.

Imports preserved v62 rep3/2/9 run/events/artifact bytes into fresh SQLite and
uses real issued operator/viewer credentials, AppService, frontend/dist and
Chrome. Only safe-report.json may be published. Logs, DB, credentials, browser
report and all screenshots are private, including on failure.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import redirect_stderr
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import time
import traceback

import httpx
import uvicorn

from check_message_handoff import REPO, Sources, require, sha, write_json
from check_public_service import run_browser_process
import agentteam.api.app as app_module
from agentteam.api.service import AppService
from agentteam.contracts import ArtifactManifest
from agentteam.store.artifact_store import ArtifactStore
from agentteam.store.event_store import EventStore
from agentteam.security.accounts import issue_key
from agentteam.store.db import Database, dumps
from agentteam.store.run_store import RunStore

ROLES = {'operator': ('result-reading-operator', 'write'), 'viewer': ('result-reading-viewer', 'read')}
REPS = {3: 'completed', 2: 'failed', 9: 'interrupted'}
BROWSER_CHECKS = {'default_results', 'artifact_bytes', 'main_destinations', 'navigation_menu', 'navigation_escape', 'navigation_outside', 'filename_h2', 'team_closed', 'keyboard_open', 'poll_preserves_open',
                  'keyboard_close', 'conversation_roundtrip', 'incomplete_warning', 'from_filter', 'overflow', 'permission_controls'}
STAGES = ('source_import', 'provision', 'service_start', 'served_build', 'browser', 'business_invariants', 'cleanup')


def now():
    return datetime.now(timezone.utc).isoformat()


def file_hashes(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}


def implementation_hashes():
    paths = [Path(__file__), REPO / 'frontend/scripts/result-reading.mjs',
             *[REPO / 'backend' / name for name in ['scripts/check_public_service.py', 'scripts/check_message_handoff.py',
                'agentteam/api/app.py', 'agentteam/api/service.py', 'agentteam/api/responses.py', 'agentteam/store/db.py']],
             *[p for p in (REPO / 'frontend/src').rglob('*') if p.suffix in ('.ts', '.tsx', '.css')],
             REPO / 'frontend/package.json', *[p for p in (REPO / 'frontend').glob('*lock*') if p.is_file()]]
    return {str(p.relative_to(REPO)): sha(p.read_bytes()) for p in paths}


def snapshot(data):
    with sqlite3.connect((data / 'agentteam.sqlite').as_uri() + '?mode=ro', uri=True) as conn:
        state = {table: conn.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                 for table in ('runs', 'events', 'artifacts')}
        state['model_events'] = conn.execute("SELECT count(*) FROM events WHERE type LIKE 'model.%'").fetchone()[0]
        state['jobs'] = conn.execute('SELECT count(*) FROM execution_jobs').fetchone()[0]
    state['artifact_bytes'] = file_hashes(data / 'runs')
    return state


async def import_records(records, data):
    data.mkdir(mode=0o700)
    db = await Database(data / 'agentteam.sqlite').connect()
    runs = RunStore(db)
    result = []
    try:
        for rep, status in REPS.items():
            folder, run, events, inventory = records.record(rep)
            require(run.status == status and run.provider_kind == 'real', 'unexpected original run state/provider')
            await runs.create_run(run)
            require(await runs.get_run(run.run_id) == run, 'import changed an original run field')
            for event in events:
                await db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)',
                                 (event.run_id, event.seq, event.event_id, event.recorded_at, event.actor_id, event.actor_kind,
                                  event.task_id, event.causation_id, event.type, dumps(event.payload)))
            require(await EventStore(db).list(run.run_id, limit=10000) == events, 'import changed an original event field')
            deliverables = []
            for item in inventory:
                artifact = ArtifactManifest.model_validate(item)
                body = records.read(folder / item['evidence_file'])
                require(sha(body) == artifact.sha256 and len(body) == artifact.size, 'artifact source bytes mismatch')
                dest = data / 'runs' / artifact.storage_path
                require(dest.resolve().is_relative_to((data / 'runs').resolve()), 'artifact escaped private import root')
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(body)
                await db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (artifact.run_id, artifact.artifact_id, artifact.revision, artifact.sha256, artifact.media_type,
                                  artifact.size, artifact.logical_path, artifact.storage_path, artifact.task_id, artifact.agent_id,
                                  artifact.created_at, artifact.event_id, dumps(artifact.sources)))
                if artifact.artifact_id != 'final-report.md':
                    deliverables.append(artifact)
                stored = await ArtifactStore(db, data / 'runs').get(run.run_id, artifact.artifact_id, artifact.revision)
                require(stored == artifact, 'import changed original artifact metadata')
            require(len(deliverables) == 1, 'this preserved series must contain one real deliverable per run')
            for subject, permission in ROLES.values():
                await db.execute('INSERT INTO run_access(run_id,subject,permission) VALUES(?,?,?)', (run.run_id, subject, permission))
            result.append({'rep': rep, 'run_id': run.run_id, 'status': status,
                           'artifact_name': deliverables[0].logical_path, 'artifact_sha256': deliverables[0].sha256,
                           'event_count': len(events), 'artifact_count': len(inventory)})
            if rep == 3:
                (data / 'agents.yaml').write_text(run.config_snapshot['config_yaml'])
        require(not await db.fetchall('SELECT * FROM execution_jobs'), 'no execution job may be imported')
    finally:
        await db.close()
    records.verify_unchanged()
    return result


def safe_body_samples(samples, expected, records):
    result = []
    placeholders = {'ja_loading': sha('読み込み中…'.encode()), 'en_loading': sha('Loading…'.encode())}
    for sample in samples:
        digest, size = sample.get('sha256'), sample.get('utf8_bytes')
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest)
                and isinstance(size, int) and size >= 0, 'invalid body diagnostic')
        result.append({'sha256': digest, 'utf8_bytes': size, 'matches_target_source': digest == expected,
                       'matching_source_reps': [r['rep'] for r in records if r['artifact_sha256'] == digest],
                       'placeholder_matches': [name for name, value in placeholders.items() if digest == value]})
    return result


def safe_browser(browser, records=()):
    cases = []
    diagnostics = []
    for item in browser.get('cases', []):
        require(item.get('role') in ROLES and item.get('width') in (320, 390) and item.get('rep') in REPS,
                'unexpected browser case identity')
        checks = []
        for value in item.get('checks', []):
            require(value.get('id') in BROWSER_CHECKS and value.get('status') in ('PASS', 'FAIL', 'UNVERIFIED'), 'unexpected check')
            checks.append({'id': value['id'], 'status': value['status']})
        expected = next((r['artifact_sha256'] for r in records if r['rep'] == item['rep']), None)
        for phase, samples in [
            *[(v['id'], v.get('measurement', {}).get('samples', [])) for v in item.get('checks', [])
              if v['id'] in ('artifact_bytes', 'poll_preserves_open')],
            ('failed_byte_wait', item.get('hash_samples', [])),
        ]:
            if samples:
                diagnostics.append({'role': item['role'], 'width': item['width'], 'rep': item['rep'], 'phase': phase,
                                    'expected_sha256': expected, 'samples': safe_body_samples(samples, expected, records)})
        cases.append({'role': item['role'], 'width': item['width'], 'rep': item['rep'],
                      'status': item['status'], 'checks': checks})
    flat = [check for case in cases for check in case['checks']]
    return {'status': browser.get('status', 'UNVERIFIED'), 'planned_cases': 12,
            'attempted_cases': sum(c['status'] != 'UNVERIFIED' for c in cases),
            'passed_cases': sum(c['status'] == 'PASS' for c in cases),
            'failed_cases': sum(c['status'] == 'FAIL' for c in cases),
            'unattempted_cases': 12 - sum(c['status'] != 'UNVERIFIED' for c in cases),
            'planned_checks': 12 * len(BROWSER_CHECKS),
            'passed_checks': sum(c['status'] == 'PASS' for c in flat),
            'failed_checks': sum(c['status'] == 'FAIL' for c in flat),
            'unverified_checks': 12 * len(BROWSER_CHECKS) - sum(c['status'] != 'UNVERIFIED' for c in flat),
            'chrome_version': browser.get('chrome_version'), 'cases': cases,
            'body_diagnostics': diagnostics,
            'http_status_counts': dict(Counter(str(x['status']) for x in browser.get('http', []))),
            'page_error_count': len(browser.get('page_errors', [])),
            'console_error_count': len(browser.get('console_errors', [])),
            'network_summary': {k: browser.get('network_summary', {}).get(k) for k in
                                ('http_errors', 'expected_auth_401', 'failed_requests', 'navigation_aborts', 'unexpected_console_errors', 'unauthorized_write_requests')},
            'cleanup': [{'id': c['id'], 'status': c['status']} for c in browser.get('cleanup', [])]}


def safe_report(report, source):
    # Never copy exception text, HTTP bodies, credentials, database rows or screenshot paths.
    return {**{key: report.get(key) for key in ('status', 'started_at', 'finished_at', 'revision', 'implementation_sha256',
             'dist_sha256', 'stages', 'checks', 'error_type', 'cleanup_error_type', 'source_unchanged', 'model_event_delta',
             'jobs', 'business_unchanged', 'cleanup', 'browser', 'served_assets', 'limits')},
            'source_sha256': {str(Path(p).relative_to(source)): value for p, value in report.get('source_sha256', {}).items()},
            'model_execution_requested': False,
            'model_execution': None if report.get('model_event_delta') is None else report['model_event_delta'] > 0,
            'human_acceptance': 'not_performed', 'business_quality_accepted': False}


async def verify(args):
    os.umask(0o077)
    require(not args.root.is_relative_to(args.source) and not args.root.is_relative_to(REPO), 'fresh private root is required')
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = {'status': 'RUNNING', 'started_at': now(), 'stages': {name: 'UNVERIFIED' for name in STAGES}, 'checks': [],
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'implementation_sha256': None, 'source_unchanged': None, 'model_event_delta': None,
              'jobs': None, 'business_unchanged': None,
              'cleanup': {'api_started': False, 'api_stopped': None, 'port_closed': None, 'browser_processes': []},
              'browser': safe_browser({}),
              'limits': ['Original v62 rep3 completed / rep2 failed / rep9 interrupted are storage imports, not new business runs.',
                         'Run fields, complete event logs and immutable artifact bytes are preserved. Task rows are not reconstructed from incomplete checkpoints.',
                         'Only real login/session/audit writes are allowed; business run/events/artifact state must remain identical.',
                         'No artifact-none or multi-version case exists in these source records; none is fabricated.',
                         'Identical artifact bytes across source runs cannot distinguish prior-run text; SHA matching proves rendered bytes, not unique run provenance.',
                         'Viewport and keyboard checks do not establish semantic quality, screen-reader quality, a physical mobile-device result or human acceptance.',
                         'Adoption and ZIP operations are intentionally not performed in this read-only CI regression.',
                         'All screenshots, raw browser errors, service logs, SQLite and keys remain private; upload only safe-report.json.']}
    records = Sources(args.source)
    service = server = server_task = None
    port = None
    baseline = None
    raw_browser = None
    source_complete = False
    imported = []
    active_stage = None
    dist = REPO / 'frontend/dist'
    data = args.root / 'data'
    shutil.copyfile(__file__, args.root / 'runner-source.py')
    def stage(name):
        nonlocal active_stage
        active_stage = name; report['stages'][name] = 'RUNNING'
    def checked(name, good):
        report['checks'].append({'id': name, 'passed': bool(good)})
        require(good, name)
    try:
        async with asyncio.timeout(args.timeout_seconds):
            stage('source_import')
            report['implementation_sha256'] = implementation_hashes()
            imported = await import_records(records, data)
            source_complete = True
            write_json(args.root / 'import.json', {'records': imported, 'source_sha256': records.hashes})
            baseline = snapshot(data)
            checked('imported_three_original_states', len(imported) == 3 and baseline['jobs'] == 0)
            report['stages']['source_import'] = 'PASS'
            stage('provision')
            require((dist / 'index.html').is_file(), 'build frontend/dist before the real browser check')
            report['dist_sha256'] = file_hashes(dist)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            origin = f'http://127.0.0.1:{port}'
            access = args.root / 'access.json'
            # Real access configuration requires one administrator. This key is
            # bootstrap-only and is never supplied to the read-only browser.
            issue_key(access, 'result-reading-admin', 'admin', args.root / 'admin.key',
                      organization='Real result-reading verification', public_origin=origin)
            for role, (subject, _) in ROLES.items():
                issue_key(access, subject, role, args.root / f'{role}.key', organization='Real result-reading verification', public_origin=origin)
            service = AppService(data, access_file=access)
            # Use the actual freshly built UI, not the older packaged agentteam/ui.
            app_module.FRONTEND_DIST = dist
            log_config = {'version': 1, 'disable_existing_loggers': False,
                          'formatters': {'timed': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
                          'handlers': {'private': {'class': 'logging.FileHandler', 'filename': str(args.root / 'service.log'),
                                                  'formatter': 'timed', 'encoding': 'utf-8'}},
                          'loggers': {'uvicorn': {'handlers': ['private'], 'level': 'INFO', 'propagate': False},
                                      'uvicorn.error': {'level': 'INFO'},
                                      'uvicorn.access': {'handlers': ['private'], 'level': 'INFO', 'propagate': False}}}
            logging.Formatter.converter = time.gmtime
            server = uvicorn.Server(uvicorn.Config(app_module.create_app(service), host='127.0.0.1', port=port,
                                                 log_config=log_config, access_log=True))
            report['stages']['provision'] = 'PASS'
            with (args.root / 'stderr.log').open('w') as stderr, redirect_stderr(stderr):
                stage('service_start')
                server_task = asyncio.create_task(server.serve())
                for _ in range(100):
                    if server.started:
                        break
                    require(not server_task.done(), 'service stopped during startup')
                    await asyncio.sleep(.05)
                checked('actual_api_started', server.started)
                report['cleanup']['api_started'] = True
                checked('no_imported_execution_jobs', snapshot(data)['jobs'] == 0)
                report['stages']['service_start'] = 'PASS'
                stage('served_build')
                async with httpx.AsyncClient(base_url=origin, timeout=15, trust_env=False) as client:
                    response = await client.get('/')
                    checked('served_index_matches_frontend_dist', response.status_code == 200 and sha(response.content) == report['dist_sha256']['index.html'])
                    assets = sorted(set(re.findall(r'(?:src|href)="(/assets/[^"?#]+)', response.text)))
                    require(bool(assets), 'no compiled frontend assets found')
                    report['served_assets'] = []
                    for path in assets:
                        response = await client.get(path)
                        match = response.status_code == 200 and sha(response.content) == report['dist_sha256'].get(path.lstrip('/'))
                        report['served_assets'].append({'path': path, 'status': response.status_code, 'hash_matches': match})
                        checked('served_asset_matches_dist', match)
                report['stages']['served_build'] = 'PASS'
                stage('browser')
                write_json(args.root / 'browser-config.json', {'origin': origin, 'records': imported,
                    'credentials': {role: str(args.root / f'{role}.key') for role in ROLES}, 'output': str(args.root / 'browser')})
                env = {**os.environ, 'RESULT_READING_CONFIG': str(args.root / 'browser-config.json')}
                require(shutil.which('node') is not None, 'Node is required')
                with (args.root / 'browser.log').open('xb') as log:
                    code = await run_browser_process(['node', str(REPO / 'frontend/scripts/result-reading.mjs')],
                        cwd=REPO / 'frontend', env=env, log=log, cleanup=report['cleanup']['browser_processes'],
                        timeout=min(240, args.timeout_seconds - 30))
                raw_browser = json.loads((args.root / 'browser/report.json').read_text())
                report['browser'] = safe_browser(raw_browser, imported)
                checked('all_browser_cases_passed', code == 0 and raw_browser['status'] == 'PASS'
                        and report['browser']['passed_cases'] == 12 and report['browser']['passed_checks'] == 12 * len(BROWSER_CHECKS))
                report['stages']['browser'] = 'PASS'
            stage('business_invariants')
            after = snapshot(data)
            report.update(model_event_delta=after['model_events'] - baseline['model_events'], jobs=after['jobs'],
                          business_unchanged=after == baseline)
            checked('no_business_or_artifact_change', report['business_unchanged'])
            checked('no_models_or_jobs', report['model_event_delta'] == 0 and report['jobs'] == 0)
            checked('implementation_hashes_unchanged', report['implementation_sha256'] == implementation_hashes())
            checked('frontend_dist_unchanged', report['dist_sha256'] == file_hashes(dist))
            records.verify_unchanged(); report['source_unchanged'] = True
            report['stages']['business_invariants'] = 'PASS'
            report['status'] = 'PASS'
    except BaseException as error:
        if active_stage:
            report['stages'][active_stage] = 'FAIL'
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        report['stages']['cleanup'] = 'RUNNING'
        if server_task is not None:
            try:
                server.should_exit = True
                await asyncio.wait_for(server_task, 15)
                report['cleanup']['api_stopped'] = server_task.done()
            except BaseException as error:
                report.update(status='FAIL', cleanup_error_type=type(error).__name__, cleanup_traceback=traceback.format_exc())
                report['cleanup']['api_stopped'] = False
                if service is not None and getattr(service, '_process_lock', None):
                    try:
                        await asyncio.wait_for(service.stop(), 10)
                    except BaseException:
                        pass
            with socket.socket() as sock:
                sock.settimeout(.2); report['cleanup']['port_closed'] = sock.connect_ex(('127.0.0.1', port)) != 0
        if baseline is not None:
            try:
                after = snapshot(data)
                report.update(model_event_delta=after['model_events'] - baseline['model_events'], jobs=after['jobs'], business_unchanged=after == baseline)
                if not report['business_unchanged'] or report['model_event_delta'] != 0 or report['jobs'] != 0:
                    report['status'] = 'FAIL'
            except (OSError, sqlite3.Error):
                report['status'] = 'FAIL'
        if source_complete:
            try:
                records.verify_unchanged(); report['source_unchanged'] = True
            except (OSError, AssertionError):
                report.update(status='FAIL', source_unchanged=False)
        report['source_sha256'] = records.hashes
        if raw_browser is None and (args.root / 'browser/report.json').exists():
            try:
                raw_browser = json.loads((args.root / 'browser/report.json').read_text()); report['browser'] = safe_browser(raw_browser, imported)
            except (OSError, ValueError, AssertionError):
                report['status'] = 'FAIL'
        clean = ((server_task is None or (report['cleanup']['api_stopped'] and report['cleanup']['port_closed']))
                 and all(x['status'] == 'PASS' for x in report['cleanup']['browser_processes']))
        if not clean:
            report['status'] = 'FAIL'
        report['stages']['cleanup'] = 'PASS' if clean else 'FAIL'
        logs = '\n'.join(p.read_text(errors='replace') for p in (args.root / 'service.log', args.root / 'stderr.log') if p.exists())
        report['cleanup']['runtime_error_markers'] = sum(logs.count(word) for word in ('ERROR', 'Traceback', 'database is locked'))
        if report['cleanup']['runtime_error_markers']:
            report['status'] = 'FAIL'
        report['finished_at'] = now()
        write_json(args.root / 'report.json', report)
        safe = safe_report(report, args.source)
        encoded = json.dumps(safe, ensure_ascii=False, indent=2).encode()
        require(not any(p.read_bytes().strip() in encoded for p in args.root.glob('*.key')), 'credential leaked into safe projection')
        write_json(args.root / 'safe-report.json', safe)
    return report['status'] == 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=lambda s: Path(s).expanduser().resolve(), required=True)
    parser.add_argument('--source', type=lambda s: Path(s).expanduser().resolve(), default=REPO / 'docs/evidence/real-readiness-v62-qwen35-fixed-20261002')
    parser.add_argument('--timeout-seconds', type=int, default=150)
    args = parser.parse_args()
    if not 60 <= args.timeout_seconds <= 540:
        print(json.dumps({'status': 'FAIL', 'error_type': 'InvalidTimeout'})); return 1
    try:
        passed = asyncio.run(verify(args))
        print(json.dumps({'status': 'PASS' if passed else 'FAIL', 'safe_report': str(args.root / 'safe-report.json')}))
        return 0 if passed else 1
    except BaseException as error:
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
