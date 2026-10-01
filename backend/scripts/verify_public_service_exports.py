"""Postflight only: real adopted ZIPs and recorded receipt replay, never new inference.

prepare checks completed, frozen records without starting a service. verify repeats
those checks, starts the real loopback API, and performs only the recorded same-key
POSTs and explicit artifact selection. Every invocation needs a fresh private root.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager, ExitStack, redirect_stderr, redirect_stdout
import fcntl
import io
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time
import traceback
from urllib.parse import quote, urlsplit
import zipfile

import httpx
import uvicorn

import public_service_workflow as workflow
from agentteam.api.app import CreateRunBody, create_app
from agentteam.api.responses import run_response
from agentteam.api.service import AppService
from agentteam.config.loader import config_to_yaml, load_config_text
from agentteam.security.accounts import digest, read_access_config
from agentteam.store.event_store import EventStore
from agentteam.store.run_store import RunStore

REPO = workflow.REPO
TABLES = ('runs', 'tasks', 'messages', 'artifacts', 'execution_jobs', 'request_receipts',
          'deleted_request_receipts', 'subject_admissions', 'config_revisions', 'run_access',
          'approvals', 'checkpoints')
ADOPTION_NOTE = 'AIによる保存経路の操作検証。人間受入・業務品質合格ではありません。'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def private_file(path):
    require(path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077,
            'required private regular file unavailable')
    return path


def contained(root, relative):
    path = root / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'record path escaped root')
    require(path.is_file(), 'required record is missing')
    return path


def db_open(root):
    path = contained(root, 'data/agentteam.sqlite')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def snapshot(root):
    """Exact durable state except audit/session metadata and explicit adoption events."""
    with db_open(root) as db:
        state = {}
        for table in TABLES:
            rows = [dict(row) for row in db.execute('SELECT * FROM ' + table)]
            state[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
        state['events_except_adoption'] = [dict(row) for row in db.execute(
            "SELECT * FROM events WHERE type!='artifact.adopted' ORDER BY run_id,seq")]
        state['model_events'] = db.execute("SELECT count(*) FROM events WHERE type LIKE 'model.%'").fetchone()[0]
        state['pending_jobs'] = db.execute("SELECT count(*) FROM execution_jobs WHERE state IN ('queued','leased')").fetchone()[0]
    return state


def state_summary(state):
    return {key: {'count': len(value), 'sha256': workflow.sha(workflow.encoded(value))}
            if isinstance(value, list) else value for key, value in state.items()}


def assert_unchanged(root, baseline, records):
    require(snapshot(root) == baseline, 'durable run/admission/job/model/output state changed')
    for name, checksum in records.items():
        require(workflow.sha(Path(name).read_bytes()) == checksum, 'original recorded evidence changed')
    workflow.frozen(root)


@contextmanager
def guards(root):
    manifest, cfg = workflow.frozen(root)
    require(not manifest.get('validation_only') and not manifest['code']['status'], 'clean fixed production series required')
    require(manifest.get('target_runs') == 10, 'exactly ten trials required')
    prior = Path(manifest['prior_series']).resolve()
    # The private old/new supervisors use this same global lock. Do not create a
    # different lock when the expected supervisor lock has never existed.
    require(root.parent == prior.parent and root != prior, 'series must share the supervised benchmark parent')
    with ExitStack() as stack:
        for path, mode in ((prior.parent / '.production-llm.lock', fcntl.LOCK_EX),
                           (prior / 'workflow.lock', fcntl.LOCK_SH),
                           (root / 'workflow.lock', fcntl.LOCK_EX)):
            handle = stack.enter_context(path.open('rb'))
            fcntl.flock(handle, mode | fcntl.LOCK_NB)
        require(workflow.sha((prior / 'fingerprint.json').read_bytes()) == manifest['prior_fingerprint_sha256'],
                'preceding fingerprint changed')
        old_status, old_manifest = workflow.read(prior / 'status.json'), workflow.read(prior / 'fingerprint.json')
        require(old_status.get('state') == 'completed_mechanical_trials'
                and old_status.get('completed') == old_manifest.get('target_runs') == 10,
                'preceding series is incomplete')
        old_attempts = workflow.read(prior / 'attempts.json')
        require(sorted(a.get('rep', 0) for a in old_attempts) == list(range(1, 11))
                and all(a.get('result') for a in old_attempts), 'preceding ten results missing')
        status, attempts = workflow.read(root / 'status.json'), workflow.read(root / 'attempts.json')
        require(status.get('state') == 'completed_trials' and status.get('completed') == 10,
                'new ten-run series is incomplete')
        require(sorted(a.get('rep', 0) for a in attempts) == list(range(1, 11))
                and all(a.get('result') and a.get('sent') and not a.get('admission_stopped') for a in attempts),
                'new ten completed results missing')
        require(len({a['run_id'] for a in attempts}) == len({a['request_key'] for a in attempts}) == 10,
                'trial run IDs or original keys are not unique')
        origin = urlsplit(manifest['origin'])
        require(origin.scheme == 'http' and origin.hostname == '127.0.0.1' and origin.port
                and not any((origin.username, origin.password, origin.path, origin.query, origin.fragment)),
                'frozen origin must be a plain loopback HTTP origin')
        key_path = contained(root, manifest['credential_files']['operator'])
        token = private_file(key_path).read_text().strip()
        access = read_access_config(root / 'security/access.json')
        require(access.public_origin == manifest['origin'] and any(
            user.subject == workflow.OPERATOR and user.role == 'operator' and not user.disabled
            and user.token_sha256 == digest(token) for user in access.users), 'original operator key does not match')
        # Also reject an existing process before even reading its mutable state.
        with (root / 'data/.service.lock').open('rb') as service_lock:
            fcntl.flock(service_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            body = workflow.read(root / 'request.json')
            require(body.get('start') is True, 'original started request missing')
            expected_hash = digest(json.dumps(CreateRunBody.model_validate(body).model_dump(),
                                              sort_keys=True, ensure_ascii=False))
            evidence, records = [], {}
            paths = [root / name for name in ('fingerprint.json', 'attempts.json', 'status.json')]
            paths += [contained(root, name) for name in manifest['files_sha256']]
            paths += [prior / name for name in ('fingerprint.json', 'attempts.json', 'status.json')]
            with db_open(root) as db:
                require(db.execute("SELECT count(*) FROM execution_jobs WHERE state IN ('queued','leased')").fetchone()[0] == 0,
                        'queued/leased work prevents service startup')
                require(db.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running','planning')").fetchone()[0] == 0,
                        'active run prevents service startup')
                # AppService prunes expired admissions at startup. Refuse before
                # that can alter the ledger being compared (five-minute margin).
                require(db.execute('SELECT count(*) FROM subject_admissions WHERE recorded_at<=?',
                                   (time.time() - 86400 + 300,)).fetchone()[0] == 0,
                        'admission expiry would change the original ledger; inspect separately')
                saved = db.execute('SELECT config_yaml FROM config_revisions ORDER BY revision DESC LIMIT 1').fetchone()
                require(saved and config_to_yaml(load_config_text(saved[0])) == config_to_yaml(cfg), 'persisted config differs')
                for attempt in sorted(attempts, key=lambda a: a['rep']):
                    run_id, result = attempt['run_id'], attempt['result']
                    require(re.fullmatch(r'[A-Za-z0-9._-]{8,128}', attempt['request_key']) is not None,
                            'original idempotency key is invalid')
                    require(result.get('run_id') == run_id and result.get('runtime_status') in workflow.TERMINAL,
                            'result is not a recorded terminal run')
                    current = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
                    require(current and current['status'] == result['runtime_status'] and current['provider_kind'] == 'real',
                            'persisted run differs from recorded real terminal run')
                    scope = digest(json.dumps([workflow.OPERATOR, '/api/runs', attempt['request_key']]))
                    receipt = db.execute('SELECT * FROM request_receipts WHERE scope_key=?', (scope,)).fetchone()
                    require(receipt and receipt['run_id'] == run_id and receipt['request_hash'] == expected_hash
                            and receipt['status'] == 202, 'exact original durable receipt unavailable; no POST allowed')
                    require(not db.execute("SELECT 1 FROM events WHERE run_id=? AND type='artifact.adopted'", (run_id,)).fetchone(),
                            'original unselected condition is unavailable; no reset or repeat adoption allowed')
                    folder = Path(result['evidence_dir']).resolve()
                    require(folder.is_dir() and folder.is_relative_to(root / 'sessions'), 'original result folder escaped series')
                    for path in folder.rglob('*'):
                        if path.is_file():
                            require(not path.is_symlink(), 'original evidence contains a symlink')
                            paths.append(path)
                    recorded = workflow.read(folder / 'run.admin.json')
                    require(recorded['run_id'] == run_id and recorded['status'] == current['status'], 'original run record differs')
                    require(all(recorded[key] == value for key, value in RunStore._run(current).model_dump(mode='json').items()),
                            'original run inputs, usage or persisted state differs')
                    artifacts = workflow.read(folder / 'artifacts.json')
                    rows = [dict(row) for row in db.execute('SELECT * FROM artifacts WHERE run_id=? ORDER BY artifact_id,revision', (run_id,))]
                    require(len(rows) == len(artifacts) == len(recorded['artifacts']), 'artifact inventory count differs')
                    identities = lambda items: {(item['artifact_id'], item['revision']) for item in items}
                    require(len(identities(artifacts)) == len(artifacts)
                            and identities(artifacts) == identities(rows) == identities(recorded['artifacts']),
                            'artifact inventory omitted or duplicated a revision')
                    for item in artifacts:
                        match = next((row for row in rows if (row['artifact_id'], row['revision']) ==
                                      (item['artifact_id'], item['revision'])), None)
                        require(match is not None and all(match[key] == item[key] for key in
                                ('sha256', 'size', 'logical_path', 'storage_path', 'agent_id', 'task_id')), 'artifact metadata differs')
                        original = contained(folder, item['evidence_file'])
                        stored = contained(root / 'data/runs', item['storage_path'])
                        require(workflow.sha(original.read_bytes()) == workflow.sha(stored.read_bytes()) == item['sha256']
                                and original.stat().st_size == item['size'], 'original artifact bytes differ')
                        paths.append(stored)
                    events = [json.loads(line) for line in (folder / 'events.admin.jsonl').read_text().splitlines()]
                    actual = [EventStore._row(row).model_dump(mode='json') for row in db.execute(
                        'SELECT * FROM events WHERE run_id=? ORDER BY seq', (run_id,))]
                    require(events == actual, 'original event record differs')
                    evidence.append({'attempt': attempt, 'folder': folder, 'artifacts': artifacts,
                                     'expected_receipt': run_response(json.loads(receipt['response_json']), administrator=False)})
            for path in paths:
                records[str(path)] = workflow.sha(path.read_bytes())
            baseline = snapshot(root)
        workflow.frozen(root)
        yield manifest, cfg, body, token, evidence, baseline, records


@asynccontextmanager
async def serve(root, manifest, cfg, baseline, records):
    class GuardedService(AppService):
        async def _start(self):
            # AppService.start has acquired the real process lock at this point.
            # This extra read-only gate closes the check/start race; startup and
            # every response still use the unmodified production service.
            assert_unchanged(root, baseline, records)
            require(not snapshot(root)['pending_jobs'], 'queued work appeared before startup')
            return await super()._start()

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    task = None
    try:
        sock.bind(('127.0.0.1', urlsplit(manifest['origin']).port))
        svc = GuardedService(root / 'data', config_yaml=config_to_yaml(cfg), access_file=root / 'security/access.json')
        server = uvicorn.Server(uvicorn.Config(create_app(svc), log_level='warning', access_log=False,
                                              timeout_graceful_shutdown=10))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        async with asyncio.timeout(20):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError('service failed to start')
                await asyncio.sleep(0.05)
        assert_unchanged(root, baseline, records)
        yield
    finally:
        try:
            if task is not None:
                server.should_exit = True
                try:
                    await asyncio.wait_for(asyncio.shield(task), 20)
                except TimeoutError:
                    task.cancel()
                    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
                    raise
        finally:
            sock.close()


class HTTP:
    def __init__(self, origin, token, session):
        self.client = httpx.AsyncClient(base_url=origin, headers={'Authorization': 'Bearer ' + token},
                                       trust_env=False, follow_redirects=False, timeout=20)
        self.session, self.seq = session, 0

    async def request(self, method, path, *, body=None, key=None):
        self.seq += 1
        prefix = self.session / 'http' / f'{self.seq:04d}'
        meta = {'method': method, 'path': path, 'request_key': key, 'at': time.time()}
        if body is not None:
            workflow.write(prefix.with_suffix('.request.body'), workflow.encoded(body))
        try:
            response = await self.client.request(method, path, json=body,
                                                 headers={'Idempotency-Key': key} if key else None)
        except Exception as error:
            workflow.write(prefix.with_suffix('.json'), {**meta, 'error_type': type(error).__name__, 'outcome': 'unknown'})
            raise
        workflow.write(prefix.with_suffix('.body'), response.content)
        workflow.write(prefix.with_suffix('.json'), {**meta, 'status': response.status_code,
                                                    'sha256': workflow.sha(response.content)})
        return response


async def verify(args, report, manifest, cfg, body, token, evidence, baseline, records):
    http = HTTP(manifest['origin'], token, args.session_root)
    try:
        report['service_start_attempted'] = True
        workflow.write(args.session_root / 'report.json', report)
        async with serve(args.root, manifest, cfg, baseline, records):
            report['service_started'] = True
            identity = await http.request('GET', '/api/auth/me')
            require(identity.status_code == 200 and identity.json().get('subject') == workflow.OPERATOR
                    and identity.json().get('role') == 'operator', 'unexpected real HTTP identity')
            for original in evidence:
                attempt, artifacts = original['attempt'], original['artifacts']
                run_id = attempt['run_id']
                path = '/api/runs/' + quote(run_id, safe='')
                item = {'rep': attempt['rep'], 'run_id': run_id, 'receipt_replay': 'not_performed',
                        'selected_export': 'not_performed', 'human_acceptance': 'not_performed'}
                report['results'].append(item)
                assert_unchanged(args.root, baseline, records)
                response = await http.request('POST', '/api/runs', body=body, key=attempt['request_key'])
                require(response.status_code == 202 and response.json() == original['expected_receipt']
                        and response.json().get('run_id') == run_id, 'same-key POST did not return the original receipt')
                assert_unchanged(args.root, baseline, records)
                item['receipt_replay'] = 'pass'
                unselected = await http.request('GET', path + '/export?fmt=zip&selection=adopted')
                require(unselected.status_code == 409 and unselected.json().get('detail') ==
                        'no selected files; choose a version before exporting', 'unselected ZIP did not return expected 409')
                guides = [artifact for artifact in artifacts if artifact['logical_path'] == 'guide.md']
                if not guides:
                    item['selected_export'] = 'unreachable_no_published_guide'
                    workflow.write(args.session_root / 'report.json', report)
                    continue
                guide = max(guides, key=lambda artifact: artifact['revision'])
                require(len({artifact['artifact_id'] for artifact in guides}) == 1, 'guide artifact identity is ambiguous')
                selected = await http.request('POST', '/api/artifacts/' + quote(run_id, safe='') + '/'
                                              + quote(guide['artifact_id'], safe='') + '/adopt', body={
                                                  'revision': guide['revision'], 'expected_selected_revision': 0,
                                                  'note': ADOPTION_NOTE})
                require(selected.status_code == 202, 'explicit latest guide selection failed')
                event = selected.json()['event']
                require(event['type'] == 'artifact.adopted' and event['actor_id'] == workflow.OPERATOR
                        and event['payload'] == {'artifact_id': guide['artifact_id'], 'revision': guide['revision'],
                                                  'sha256': guide['sha256'], 'logical_path': 'guide.md', 'note': ADOPTION_NOTE},
                        'adoption event does not identify the intended original revision')
                # events.jsonl legitimately adds the AI-operated selection event;
                # compare its actual operator export bytes, not old pre-adoption bytes.
                event_export = await http.request('GET', path + '/export?fmt=jsonl')
                require(event_export.status_code == 200, 'event export failed')
                raw_events = [json.loads(line) for line in event_export.content.splitlines()]
                prior_events = [json.loads(line) for line in (original['folder'] / 'events.operator.jsonl').read_text().splitlines()]
                require(raw_events[:-1] == prior_events and raw_events[-1] == event, 'ZIP event prefix differs from original record')
                expected = {'artifacts/guide.md': (original['folder'] / guide['evidence_file']).read_bytes(),
                            'events.jsonl': event_export.content}
                with zipfile.ZipFile(original['folder'] / 'latest.zip') as old_zip:
                    expected['final-report.md'] = old_zip.read('final-report.md')
                zip_response = await http.request('GET', path + '/export?fmt=zip&selection=adopted')
                require(zip_response.status_code == 200, 'adopted ZIP unavailable')
                expected_manifest = {'schema_version': 1, 'run_id': run_id, 'selection': 'adopted',
                                     'artifacts': [{'artifact_id': guide['artifact_id'], 'revision': guide['revision'],
                                                    'sha256': guide['sha256'], 'path': 'artifacts/guide.md'}]}
                expected['manifest.json'] = json.dumps(expected_manifest, ensure_ascii=False, indent=2).encode()
                with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                    names = archive.namelist()
                    require(len(names) == len(set(names)) == len(expected) and set(names) == set(expected),
                            'ZIP entries duplicate, omit, or add unrecorded content')
                    require(json.loads(archive.read('manifest.json')) == expected_manifest, 'adopted manifest differs')
                    hashes = {}
                    for name, data in expected.items():
                        require(archive.read(name) == data, 'ZIP bytes differ from recorded expected content')
                        hashes[name] = workflow.sha(data)
                assert_unchanged(args.root, baseline, records)
                item.update(selected_export='pass', artifact_id=guide['artifact_id'], revision=guide['revision'],
                            artifact_sha256=guide['sha256'], zip_sha256=workflow.sha(zip_response.content),
                            entry_sha256=hashes, adoption_event_id=event['event_id'])
                workflow.write(args.session_root / 'report.json', report)
        assert_unchanged(args.root, baseline, records)
        with db_open(args.root) as db:
            adopted = [dict(row) for row in db.execute("SELECT * FROM events WHERE type='artifact.adopted' ORDER BY run_id,seq")]
        new_ids = {item['adoption_event_id'] for item in report['results'] if item['selected_export'] == 'pass'}
        # Other (non-trial) runs can already have selections; ensure trial rows
        # contain exactly the explicitly recorded operations and no extras.
        trial_ids = {item['run_id'] for item in report['results']}
        require({row['event_id'] for row in adopted if row['run_id'] in trial_ids} == new_ids,
                'unexpected adoption events appeared')
        report.update(status='completed', same_key_replays_passed=10,
                      selected_exports_passed=len(new_ids), selected_exports_unreachable=10 - len(new_ids),
                      durable_state_unchanged=True, original_evidence_unchanged=True, additional_model_calls=0)
    finally:
        await http.client.aclose()


async def main(args, report):
    with guards(args.root) as (manifest, cfg, body, token, evidence, baseline, records):
        report['preconditions'] = 'passed'
        report['fixed_commit'] = manifest['code']['commit']
        report['baseline'] = state_summary(baseline)
        workflow.write(args.session_root / 'original-records.sha256.json', records)
        workflow.write(args.session_root / 'report.json', report)
        if args.command == 'prepare':
            report['status'] = 'prepared_without_service'
            report['additional_model_calls'] = 0
            return
        await verify(args, report, manifest, cfg, body, token, evidence, baseline, records)


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify'))
    parser.add_argument('--root', type=lambda value: Path(value).expanduser().resolve(), required=True)
    parser.add_argument('--session-root', type=lambda value: Path(value).expanduser().resolve(), required=True)
    args = parser.parse_args()
    os.umask(0o077)
    report = {'status': 'not_started', 'preconditions': 'not_checked', 'service_started': False,
              'service_start_attempted': False,
              'receipt_replay_scope': 'new same-key reconciliation of recorded acceptance; original response loss not induced',
              'adoption_actor': 'AI-operated real operator API; API actor_kind is not human acceptance evidence',
              'business_quality_accepted': False, 'human_acceptance': 'not_performed',
              'additional_model_calls': None, 'results': []}
    created = False
    try:
        require(not args.session_root.is_relative_to(args.root) and not args.session_root.is_relative_to(REPO)
                and not args.root.is_relative_to(args.session_root), 'postflight root must be fresh and outside series/repository')
        if (args.root / 'fingerprint.json').is_file():
            prior = Path(workflow.read(args.root / 'fingerprint.json')['prior_series']).resolve()
            require(not args.session_root.is_relative_to(prior) and not prior.is_relative_to(args.session_root),
                    'postflight root must remain outside the preceding series')
        args.session_root.mkdir(parents=True, mode=0o700, exist_ok=False)
        created = True
        workflow.write(args.session_root / 'report.json', report)
        with (args.session_root / 'execution.private.log').open('x') as log, redirect_stdout(log), redirect_stderr(log):
            try:
                asyncio.run(main(args, report))
            except BaseException as error:
                traceback.print_exc()
                report.update(status='failed', error_type=type(error).__name__)
            finally:
                workflow.write(args.session_root / 'report.json', report)
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__)
        if created:
            workflow.write(args.session_root / 'report.json', report)
    # Never print original content, credential values, HTTP bodies or raw errors.
    print(json.dumps({key: report.get(key) for key in ('status', 'preconditions', 'service_started', 'error_type')}))
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(cli())
