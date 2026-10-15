#!/usr/bin/env python3
"""Hold real Workroom HTTP 200 responses in Chrome; no model/VM or response mocks.

Preserved v62 records are imported by the existing reading verifier. Only
safe-report.json is publishable; keys, SQLite, HTTP/browser data and logs stay private.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import traceback

import httpx

from check_message_handoff import REPO, Sources, require, sha, write_json
from check_public_service import running_browser_api, run_browser_process
from check_result_reading import ROLES, file_hashes, import_records, snapshot, implementation_hashes as reading_hashes
import agentteam.api.app as app_module
from agentteam.security.accounts import issue_key

SCRIPT = REPO / 'frontend/scripts/workroom-load-recovery.mjs'
CASES = ('manual_pending', 'deadline_detail', 'deadline_chat', 'deadline_events', 'loaded_poll')
CHECKS = ('issued_login', 'actual_200_held', 'pending_or_deadline_boundary', 'native_reload',
          'fresh_three_gets', 'original_artifact_bytes', 'old_requests_released',
          'identity_and_state_preserved', 'error_and_write_boundary')
STAGES = ('source_import', 'provision', 'service', 'served_build', 'browser', 'invariants', 'cleanup')
ERROR_TYPES = {'Error', 'AssertionError', 'TimeoutError', 'TypeError', 'ValueError', 'OSError',
               'FileNotFoundError', 'RuntimeError', 'CancelledError', 'ProtocolError', 'TargetClosedError'}


def now():
    return datetime.now(timezone.utc).isoformat()


def implementation_hashes():
    return {**reading_hashes(), **{str(p.relative_to(REPO)): sha(p.read_bytes()) for p in (Path(__file__), SCRIPT)}}


def safe_browser(raw=None):
    raw = raw or {}
    require(raw.get('status', 'UNVERIFIED') in ('UNVERIFIED', 'RUNNING', 'PASS', 'FAIL'), 'invalid browser status')
    cases = []
    for item in raw.get('cases', []):
        require(item.get('id') in CASES and item.get('status') in ('UNVERIFIED', 'RUNNING', 'PASS', 'FAIL'), 'invalid case')
        checks = []
        for check in item.get('checks', []):
            require(check.get('id') in CHECKS and check.get('status') in ('UNVERIFIED', 'PASS', 'FAIL'), 'invalid browser check')
            checks.append({'id': check['id'], 'status': check['status']})
        require(len(checks) == len(CHECKS) and {c['id'] for c in checks} == set(CHECKS), 'incomplete or duplicate check IDs')
        measurements = {}
        for key, value in item.get('measurements', {}).items():
            if key in ('deadline_error_after_hold_ms', 'predeadline_observed_after_hold_ms', 'enter_after_hold_ms',
                       'enter_after_initial_request_ms', 'recovery_after_enter_ms', 'old_cancelled_count', 'expected_abort_count',
                       'draft_source_codepoints', 'draft_excerpt_codepoints'):
                require(type(value) in (int, float) and value >= 0, 'invalid numeric observation'); measurements[key] = value
            elif key in ('draft_preserved', 'identity_status_last_seq_preserved'):
                require(value is None or isinstance(value, bool), 'invalid boolean observation'); measurements[key] = value
            elif key in ('artifact_sha256', 'draft_source_goal_sha256', 'draft_excerpt_sha256'):
                require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'invalid artifact hash'); measurements[key] = value
            elif key == 'held_200_by_route':
                require(set(value) == {'detail', 'chat', 'events'} and all(type(v) is int and v >= 0 for v in value.values()), 'invalid route counts')
                measurements[key] = value
        cases.append({'id': item['id'], 'status': item['status'], 'checks': checks, 'measurements': measurements})
    require(len({c['id'] for c in cases}) == len(cases), 'duplicate case')
    if raw:
        require({c['id'] for c in cases} == set(CASES), 'missing case IDs')
    chrome = raw.get('chrome_version')
    require(chrome is None or isinstance(chrome, str) and re.fullmatch(r'[0-9.]+', chrome), 'invalid Chrome version')
    require(all(type(x.get('status')) is int and 100 <= x['status'] <= 599 for x in raw.get('http', [])), 'invalid HTTP status')
    require(all(x.get('method') in ('POST', 'PUT', 'PATCH', 'DELETE', 'CONNECT', 'TRACE') for x in raw.get('writes', [])), 'invalid write method')
    flat = [c for item in cases for c in item['checks']]
    cleanup = []
    for entry in raw.get('cleanup', []):
        allowed = {'browser-close', 'owned-chrome-close', 'remaining-context'} | {
            f'{case}-{suffix}' for case in CASES for suffix in ('fetch-disable', 'pending-cdp', 'context')}
        require(entry.get('id') in allowed and entry.get('status') in ('PASS', 'FAIL'), 'invalid cleanup')
        cleanup.append({'id': entry['id'], 'status': entry['status']})
    return {'status': raw.get('status', 'UNVERIFIED'), 'planned_cases': len(CASES),
            'attempted_cases': sum(c['status'] != 'UNVERIFIED' for c in cases),
            'passed_cases': sum(c['status'] == 'PASS' for c in cases), 'failed_cases': sum(c['status'] == 'FAIL' for c in cases),
            'unattempted_cases': len(CASES) - sum(c['status'] != 'UNVERIFIED' for c in cases),
            'planned_checks': len(CASES) * len(CHECKS), 'passed_checks': sum(c['status'] == 'PASS' for c in flat),
            'failed_checks': sum(c['status'] == 'FAIL' for c in flat),
            'unverified_checks': len(CASES) * len(CHECKS) - sum(c['status'] != 'UNVERIFIED' for c in flat),
            'cases': cases, 'cleanup': cleanup, 'chrome_version': chrome,
            'http_status_counts': dict(Counter(str(x['status']) for x in raw.get('http', []))),
            'page_error_count': len(raw.get('errors', [])),
            'write_methods_and_routes': dict(Counter(f"{x['method']} {'login' if x['path'] == '/api/auth/login' else 'unexpected'}" for x in raw.get('writes', [])))}


def safe_report(report, source):
    fields = ('status', 'started_at', 'finished_at', 'revision', 'stages', 'implementation_sha256', 'dist_sha256',
              'checks', 'source_unchanged', 'business_unchanged', 'model_event_delta', 'jobs', 'browser',
              'api_cleanup', 'process_cleanup', 'served_assets', 'runtime_error_markers', 'limits')
    result = {key: report.get(key) for key in fields}
    result['error_type'] = report.get('error_type') if report.get('error_type') in ERROR_TYPES else ('Error' if report.get('error_type') else None)
    result['source_sha256'] = {str(Path(p).relative_to(source)): digest for p, digest in report.get('source_sha256', {}).items()}
    result.update(model_execution_requested=False, model_execution=None if report.get('model_event_delta') is None else report['model_event_delta'] > 0,
                  human_acceptance='not_performed', business_quality_accepted=False)
    return result


async def verify(args):
    os.umask(0o077)
    require(not args.root.is_relative_to(args.source) and not args.root.is_relative_to(REPO), 'fresh private root required')
    args.root.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (args.root / 'stderr.private.log').open('x') as stderr, (args.root / 'stdout.private.log').open('x') as stdout, redirect_stderr(stderr), redirect_stdout(stdout):
        return await verify_private(args)


async def verify_private(args):
    report = {'status': 'RUNNING', 'started_at': now(), 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'stages': {name: 'UNVERIFIED' for name in STAGES}, 'checks': [], 'browser': safe_browser(),
              'source_unchanged': None, 'business_unchanged': None, 'model_event_delta': None, 'jobs': None,
              'api_cleanup': {'scope': 'workroom_recovery_api', 'status': 'NOT_STARTED', 'startup_attempted': False,
                              'started': False, 'service_stopped': None, 'server_task_done': None, 'port_closed': None},
              'process_cleanup': [], 'limits': [
                  'Actual v62 rep3/2/9 run/events/artifacts are storage imports. Task rows are not reconstructed from incomplete checkpoints.',
                  'Only real issued-key login/session/audit writes are allowed; business records and original artifact bytes must remain unchanged.',
                  'The unsent draft is the first 1024 Unicode code points of the actual received original goal. Full goal and prefix hashes/lengths are retained; no invented text is added.',
                  'Real HTTP 200 responses are held at CDP Response stage without fabricated headers, bodies, notifications or credentials.',
                  'Product batch deadline is 15000 ms. Browser observation allows 22000 ms; it is not a change to the product deadline.',
                  'Deadline cases must still be pending after 12000 ms. Initial manual Enter occurs within 2000 ms of the first initial GET request; all three new real 200 responses must arrive within 3000 ms, before releasing the old request. This controlled interaction bound is not a performance SLA.',
                  'Browser suite deadline 160 s, owned child deadline 170 s, wrapper default 210 s plus bounded final cleanup. CI step ceiling 5 minutes.',
                  'Response-stage holding does not separately reproduce a partial response body stall.',
                  'Cancelled original requests may no longer be releasable; no claim that stale bytes reached React is made in that case.',
                  'Same recorded artifact bytes do not distinguish run IDs. Real API run_id/status/last_seq, URL and rendered state are checked separately.',
                  'Five selected cases, not all roles/languages/widths or natural network failures. No model, VM, semantic-quality or human acceptance.',
                  'Only safe-report.json is publishable. Raw HTTP/browser errors, credentials, profiles, SQLite and all logs remain private.']}
    sources = Sources(args.source); baseline = None; imported = []; source_complete = False; active = None
    data = args.root / 'data'; dist = REPO / 'frontend/dist'
    def stage(name):
        nonlocal active
        active = name; report['stages'][name] = 'RUNNING'
    def checked(name, value):
        report['checks'].append({'id': name, 'passed': bool(value)}); require(value, name)
    try:
        async with asyncio.timeout(args.timeout_seconds):
            stage('source_import'); report['implementation_sha256'] = implementation_hashes()
            shutil.copyfile(__file__, args.root / 'runner-source.py')
            shutil.copyfile(SCRIPT, args.root / 'browser-source.mjs')
            imported = await import_records(sources, data); source_complete = True; baseline = snapshot(data)
            checked('original_records_imported_no_jobs', len(imported) == 3 and baseline['jobs'] == 0)
            report['stages']['source_import'] = 'PASS'
            stage('provision'); require((dist / 'index.html').is_file(), 'build actual frontend first')
            report['dist_sha256'] = file_hashes(dist)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            origin = f'http://127.0.0.1:{port}'; access = args.root / 'access.json'
            issue_key(access, 'workroom-recovery-admin', 'admin', args.root / 'admin.key', organization='Workroom recovery verification', public_origin=origin)
            for role, (subject, _) in ROLES.items():
                issue_key(access, subject, role, args.root / f'{role}.key', organization='Workroom recovery verification', public_origin=origin)
            app_module.FRONTEND_DIST = dist
            report['stages']['provision'] = 'PASS'; stage('service')
            async with running_browser_api(data, access, port, report['api_cleanup'], args.root):
                report['stages']['service'] = 'PASS'; stage('served_build')
                async with httpx.AsyncClient(base_url=origin, timeout=15, trust_env=False) as client:
                    response = await client.get('/')
                    checked('actual_served_index_matches_dist', response.status_code == 200 and sha(response.content) == report['dist_sha256']['index.html'])
                    paths = sorted(set(re.findall(r'(?:src|href)="(/assets/[^"?#]+)', response.text)))
                    require(bool(paths), 'compiled assets missing'); report['served_assets'] = []
                    for path in paths:
                        response = await client.get(path)
                        matches = response.status_code == 200 and sha(response.content) == report['dist_sha256'].get(path.lstrip('/'))
                        report['served_assets'].append({'path': path, 'status': response.status_code, 'hash_matches': matches}); checked('actual_served_asset_matches_dist', matches)
                report['stages']['served_build'] = 'PASS'; stage('browser')
                write_json(args.root / 'browser-config.json', {'origin': origin, 'records': imported,
                    'credentials': {role: str(args.root / f'{role}.key') for role in ROLES}, 'output': str(args.root / 'browser')})
                with (args.root / 'browser.private.log').open('xb') as log:
                    code = await run_browser_process(['node', str(SCRIPT)], cwd=REPO / 'frontend',
                        env={**os.environ, 'WORKROOM_RECOVERY_CONFIG': str(args.root / 'browser-config.json')},
                        log=log, cleanup=report['process_cleanup'], timeout=170)
                raw = json.loads((args.root / 'browser/report.json').read_text()); report['browser'] = safe_browser(raw)
                checked('all_five_recovery_cases', code == 0 and raw['status'] == 'PASS' and report['browser']['passed_cases'] == len(CASES)
                        and report['browser']['passed_checks'] == len(CASES) * len(CHECKS))
                report['stages']['browser'] = 'PASS'
            stage('invariants')
            after = snapshot(data)
            report.update(business_unchanged=after == baseline, model_event_delta=after['model_events'] - baseline['model_events'], jobs=after['jobs'])
            checked('original_business_bytes_unchanged', report['business_unchanged'])
            checked('no_models_or_jobs', report['model_event_delta'] == report['jobs'] == 0)
            checked('implementation_unchanged', report['implementation_sha256'] == implementation_hashes())
            checked('frontend_dist_unchanged', report['dist_sha256'] == file_hashes(dist))
            sources.verify_unchanged(); report['source_unchanged'] = True
            report['stages']['invariants'] = 'PASS'; report['status'] = 'PASS'
    except BaseException as error:
        if active:
            report['stages'][active] = 'FAIL'
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        report['stages']['cleanup'] = 'RUNNING'
        if baseline is not None:
            try:
                after = snapshot(data)
                report.update(business_unchanged=after == baseline, model_event_delta=after['model_events'] - baseline['model_events'], jobs=after['jobs'])
                if not report['business_unchanged'] or report['model_event_delta'] != 0 or report['jobs'] != 0:
                    report['status'] = 'FAIL'
            except (OSError, sqlite3.Error):
                report['status'] = 'FAIL'
        if source_complete:
            try:
                sources.verify_unchanged(); report['source_unchanged'] = True
            except (AssertionError, OSError):
                report.update(status='FAIL', source_unchanged=False)
        report['source_sha256'] = sources.hashes
        if (args.root / 'browser/report.json').exists():
            try:
                report['browser'] = safe_browser(json.loads((args.root / 'browser/report.json').read_text()))
            except (ValueError, OSError, AssertionError):
                report['status'] = 'FAIL'
        cleanup = report['api_cleanup']
        clean = (cleanup['status'] in ('NOT_STARTED', 'PASS') and all(x['status'] == 'PASS' for x in report['process_cleanup']))
        report['stages']['cleanup'] = 'PASS' if clean else 'FAIL'
        sys.stderr.flush(); sys.stdout.flush()
        logs = '\n'.join(p.read_text(errors='replace') for p in args.root.glob('*.log'))
        report['runtime_error_markers'] = sum(logs.count(x) for x in ('Traceback (most recent call last)', 'database is locked', 'ERROR:'))
        if not clean or report['runtime_error_markers']:
            report['status'] = 'FAIL'
        report['finished_at'] = now(); write_json(args.root / 'report.private.json', report)
        safe = safe_report(report, args.source); encoded = json.dumps(safe, ensure_ascii=False).encode()
        require(not any(p.read_bytes().strip() in encoded for p in args.root.glob('*.key')), 'secret in safe report')
        write_json(args.root / 'safe-report.json', safe)
    return report['status'] == 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=lambda x: Path(x).expanduser().resolve(), required=True)
    parser.add_argument('--source', type=lambda x: Path(x).expanduser().resolve(), default=REPO / 'docs/evidence/real-readiness-v62-qwen35-fixed-20261002')
    parser.add_argument('--timeout-seconds', type=int, default=210)
    args = parser.parse_args()
    if not 200 <= args.timeout_seconds <= 240:
        print(json.dumps({'status': 'FAIL', 'error_type': 'InvalidTimeout'})); return 1
    try:
        passed = asyncio.run(verify(args)); print(json.dumps({'status': 'PASS' if passed else 'FAIL'})); return 0 if passed else 1
    except BaseException as error:
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__})); return 1


if __name__ == '__main__':
    raise SystemExit(main())
