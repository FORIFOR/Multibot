"""Fixed, answer-free document trials over real operator HTTP. Never probes a model.

prepare and preflight cannot start inference. run additionally requires a completed,
unlocked preceding series and explicit --allow-model-execution. See the companion doc.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
import fcntl
import hashlib
from importlib import metadata
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
import uuid
import zipfile

import httpx
from jsonschema import Draft202012Validator
import uvicorn

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.config.loader import config_to_yaml, effective_all, load_config_file, load_config_text
from agentteam.security.accounts import issue_key

SOURCE = 'docs/quality/integration.md'
OPERATOR = 'public-workflow-operator'
GOAL = ('添付した integration.md だけを根拠に、初めてAgent Teamを組み込む開発者向けの短い日本語導入ガイド guide.md を作ってください。'
        '見出しは「前提条件」「最初の手順」「制約・未確認」の3つ。合計400〜700字。HTTP 202は完了ではないこと、採用した版のZIP保存、'
        '応答喪失時の再送の注意を必ず含め、根拠の節名を示してください。新しいキーを使える条件や省略時の挙動を変えて説明しないでください。'
        '外部検索や外部送信は行わず、資料にない動作を断言しないでください。確認担当は本文と原資料を照合し、実測した文字数で検証してください。')
REQUIREMENTS = [{'logical_path': 'guide.md', 'input_format': 'text',
                 'json_schema': {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                                 'type': 'string', 'minLength': 400, 'maxLength': 700}}]
TERMINAL = {'completed', 'partial', 'failed', 'cancelled', 'interrupted', 'blocked', 'approval_required'}
TOOLS = {'master': ['create_task', 'update_task', 'send_message', 'read_messages', 'read_artifact', 'list_artifacts', 'report_blocker'],
         'builder': ['workspace_read', 'workspace_write', 'workspace_list', 'publish_artifact',
                     'send_message', 'read_messages', 'read_artifact', 'list_artifacts', 'report_blocker'],
         'reviewer': ['read_artifact', 'list_artifacts', 'workspace_read', 'run_check',
                      'send_message', 'read_messages', 'submit_review', 'report_blocker']}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    """Atomic, durable ledger updates; evidence snapshots use unique directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('xb') as handle:
        handle.write(value if isinstance(value, bytes) else encoded(value))
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path):
    return json.loads(Path(path).read_text())


def code_state():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=REPO)
    return {'commit': git('rev-parse', 'HEAD').decode().strip(),
            'status': git('status', '--porcelain').decode(),
            'diff_sha256': sha(git('diff', 'HEAD', '--binary')),
            'runner_sha256': sha(Path(__file__).read_bytes())}


def runtime_state():
    distributions = [{'name': dist.metadata.get('Name', ''), 'version': dist.version}
                     for dist in metadata.distributions()]
    return {'python_version': sys.version, 'implementation': sys.implementation.name,
            'executable': sys.executable, 'prefix': sys.prefix,
            'installed_distributions': sorted(distributions, key=lambda item: (item['name'].lower(), item['version']))}


async def model_state(model):
    # Metadata GETs only: neither /api/generate nor capability probes are used.
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=10, trust_env=False) as client:
        version = await client.get('/api/version'); version.raise_for_status()
        tags = await client.get('/api/tags'); tags.raise_for_status()
    match = next((m for m in tags.json()['models'] if m['name'] in (model, model + ':latest')), None)
    if not match:
        raise ValueError('the already installed local model is unavailable')
    return {'model': model, 'model_digest': match['digest'], 'ollama_version': version.json()['version']}


def effective(cfg):
    return {key: value.model_dump(mode='json') for key, value in effective_all(cfg).items()}


def restricted_profile(profile):
    prior = load_config_file(profile)
    conn = prior.connection(prior.defaults.connection_id)
    if (not conn or conn.driver != 'ollama' or conn.base_url.rstrip('/') != 'http://127.0.0.1:11434/v1'
            or conn.api_key_ref or conn.capability_check != 'passed'
            or (conn.capability_detail or {}).get('model_requested') != prior.defaults.model):
        raise ValueError('supply an unchanged real, successfully probed local Ollama profile; no probe is performed')
    cfg = load_config_file(REPO / 'docs/config/local-qwen35-9b-team.yaml')
    cfg.connections = [conn.model_copy(deep=True)]
    cfg.connections[0].allowed_fallback_connections = []
    cfg.connections[0].refusal_fallback = False
    cfg.defaults.connection_id = conn.id
    cfg.defaults.model = prior.defaults.model
    cfg.defaults.team_mode = 'team'
    cfg.defaults.require_independent_review = True
    cfg.profile_name = 'public-service-source-guide-no-answer-example'
    for agent in cfg.agents:
        agent.connection_id = 'inherit'; agent.model = 'inherit'
        agent.enabled = agent.role in TOOLS
        agent.tools = TOOLS.get(agent.role, [])
        # Prompts and skills come from this fixed code, never prior run answers.
        agent.system_prompt_override = None
    cfg.limits.max_tasks = 4; cfg.limits.max_active_workers = 1
    cfg.limits.max_model_calls = 30; cfg.limits.max_tool_calls = 80
    cfg.limits.max_replans = 0; cfg.limits.max_session_turns = 18
    cfg.limits.max_output_tokens = 1800; cfg.limits.timeout_seconds = 480
    cfg.limits.max_revision_rounds = 2
    return cfg


async def prepare(args):
    code = code_state()
    if code['status'] and not args.validation_only:
        raise ValueError('commit and freeze this checkout first; --validation-only can never run inference')
    cfg = restricted_profile(args.profile)
    model = await model_state(cfg.defaults.model)
    prior = read(args.prior_series / 'fingerprint.json')
    if any(prior.get(key) != value for key, value in model.items()):
        raise ValueError('model/version/digest differs from the preceding fixed series')
    args.root.mkdir(mode=0o700, parents=True, exist_ok=False)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    access = args.root / 'security/access.json'
    for subject, role, name in [('workflow-admin', 'admin', 'admin'), (OPERATOR, 'operator', 'operator')]:
        issue_key(access, subject, role, args.root / 'security' / (name + '.key'),
                  organization='FORIFOR/Multibot', public_origin=origin)
    policy = read(access)
    policy.update(max_active_runs=1, max_pending_runs=1)
    write(access, policy)
    body = {'goal': GOAL, 'inputs': {'files': [{'name': 'integration.md', 'content': (REPO / SOURCE).read_text()}],
                                     'workflow': 'document', 'delivery_requirements': REQUIREMENTS}, 'start': True}
    files = {'inputs/integration.md': (REPO / SOURCE).read_bytes(), 'goal.txt': GOAL.encode(),
             'delivery-requirements.json': encoded(REQUIREMENTS), 'request.json': encoded(body),
             'profile.yaml': config_to_yaml(cfg).encode(), 'effective-config.json': encoded(effective(cfg))}
    for name, data in files.items():
        write(args.root / name, data)
    files['security/access.json'] = access.read_bytes()
    manifest = {'schema_version': 1, 'target_runs': 10, 'code': code, 'runtime': runtime_state(),
                'validation_only': args.validation_only,
                'source': SOURCE, **model, 'origin': origin,
                'files_sha256': {name: sha(data) for name, data in files.items()},
                'profile_source': str(args.profile), 'profile_source_sha256': sha(args.profile.read_bytes()),
                'prior_series': str(args.prior_series), 'prior_fingerprint_sha256': sha((args.prior_series / 'fingerprint.json').read_bytes()),
                'credential_files': {'admin': 'security/admin.key', 'operator': 'security/operator.key'},
                'semantic_review': 'pending', 'business_quality_accepted': False}
    write(args.root / 'fingerprint.json', manifest)
    write(args.root / 'attempts.json', [])
    write(args.root / 'status.json', {'state': 'prepared', 'model_execution_started': False,
                                     'semantic_review': 'pending', 'business_quality_accepted': False})


def frozen(root):
    manifest = read(root / 'fingerprint.json')
    if manifest['code'] != code_state():
        raise ValueError('code changed; create a new fixed series')
    if manifest['runtime'] != runtime_state():
        raise ValueError('Python or installed distributions changed; create a new fixed series')
    for name, checksum in manifest['files_sha256'].items():
        if sha((root / name).read_bytes()) != checksum:
            raise ValueError('fixed input/configuration changed: ' + name)
    cfg = load_config_file(root / 'profile.yaml')
    if encoded(effective(cfg)) != (root / 'effective-config.json').read_bytes():
        raise ValueError('effective prompts/tools/configuration changed')
    for name in manifest['credential_files'].values():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError('credentials must remain regular private files')
    return manifest, cfg


@contextmanager
def launch_guard(manifest, allowed):
    if not allowed:
        raise ValueError('inference requires explicit --allow-model-execution')
    prior = Path(manifest['prior_series'])
    if sha((prior / 'fingerprint.json').read_bytes()) != manifest['prior_fingerprint_sha256']:
        raise ValueError('preceding series fingerprint changed')
    state, fingerprint = read(prior / 'status.json'), read(prior / 'fingerprint.json')
    if (state.get('state') != 'completed_mechanical_trials'
            or state.get('completed') != fingerprint.get('target_runs') or fingerprint.get('target_runs') != 10):
        raise ValueError('preceding ten-run series is not complete; no service or model execution started')
    if manifest['validation_only'] or manifest['code']['status']:
        raise ValueError('inference requires a clean frozen series; validation-only roots cannot execute models')
    attempts = read(prior / 'attempts.json')
    if sorted(a.get('rep', 0) for a in attempts) != list(range(1, 11)) or not all(a.get('result') for a in attempts):
        raise ValueError('preceding series does not retain ten completed attempt records')
    # Read-only open, no changes to the preceding series. Hold a shared lock so
    # its exclusive-lock runner cannot restart while this series is executing.
    with (prior / 'workflow.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        yield


def pending_jobs(root):
    path = root / 'data/agentteam.sqlite'
    if not path.exists():
        return 0
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        return db.execute("SELECT count(*) FROM execution_jobs WHERE state IN ('queued','leased')").fetchone()[0]


def check_database_before_start(root, cfg, attempts):
    """Validate persisted state before startup can recover any queued model work."""
    path = root / 'data/agentteam.sqlite'
    if not path.exists():
        return
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        saved = db.execute('SELECT config_yaml FROM config_revisions ORDER BY revision DESC LIMIT 1').fetchone()
        if saved and config_to_yaml(load_config_text(saved[0])) != config_to_yaml(cfg):
            raise ValueError('persisted configuration changed; service was not started')
        known = {a['run_id'] for a in attempts if a.get('run_id')}
        for attempt in attempts:
            scope = sha(json.dumps([OPERATOR, '/api/runs', attempt['request_key']]).encode())
            receipt = db.execute('SELECT run_id FROM request_receipts WHERE scope_key=?', (scope,)).fetchone()
            if receipt:
                known.add(receipt[0])
        queued = db.execute("SELECT run_id FROM execution_jobs WHERE state IN ('queued','leased')").fetchall()
        if any(row[0] not in known for row in queued):
            raise ValueError('unknown queued work; service was not started')


@asynccontextmanager
async def server(root, manifest, cfg):
    sock = socket.socket()
    # Allow this stopped server's TIME_WAIT sockets on explicit continuation;
    # without SO_REUSEPORT, an existing live listener still makes bind fail.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', urlsplit(manifest['origin']).port))
    svc = AppService(root / 'data', config_yaml=config_to_yaml(cfg), access_file=root / 'security/access.json')
    runner = uvicorn.Server(uvicorn.Config(create_app(svc), log_level='warning', access_log=False))
    task = asyncio.create_task(runner.serve(sockets=[sock]))
    try:
        deadline = time.monotonic() + 20
        while not runner.started:
            if task.done():
                await task
                raise RuntimeError('HTTP service did not start')
            if time.monotonic() > deadline:
                raise TimeoutError('HTTP service startup timed out')
            await asyncio.sleep(0.05)
        if config_to_yaml(svc.config) != config_to_yaml(cfg) or effective(svc.config) != effective(cfg):
            raise ValueError('persisted effective configuration differs from the frozen series')
        yield
    finally:
        runner.should_exit = True
        await task
        sock.close()


class EvidenceHTTP:
    def __init__(self, root, origin, evidence):
        self.client = httpx.AsyncClient(base_url=origin, timeout=30, trust_env=False, follow_redirects=False)
        self.tokens = {role: (root / 'security' / (role + '.key')).read_text().strip() for role in ('admin', 'operator')}
        self.evidence = evidence
        self.seq = 0

    async def request(self, method, path, *, role='operator', body=None, key=None):
        self.seq += 1
        prefix = self.evidence / 'http' / f'{self.seq:05d}'
        meta = {'method': method, 'path': path, 'role': role, 'idempotency_key': key, 'time': time.time()}
        headers = {'Authorization': 'Bearer ' + self.tokens[role]}
        if key:
            headers['Idempotency-Key'] = key
        try:
            response = await self.client.request(method, path, json=body, headers=headers)
        except Exception as error:
            write(prefix.with_suffix('.json'), {**meta, 'error_type': type(error).__name__, 'outcome': 'unknown'})
            raise
        write(prefix.with_suffix('.body'), response.content)
        write(prefix.with_suffix('.json'), {**meta, 'status': response.status_code,
              'body_sha256': sha(response.content), 'retry_after': response.headers.get('retry-after')})
        return response

    async def get(self, path, *, role='operator'):
        response = await self.request('GET', path, role=role)
        response.raise_for_status()
        return response.json()


async def wait_for_queue(http):
    """A terminal run status can precede the worker's final lease release."""
    deadline = time.monotonic() + 60
    while True:
        jobs = await http.get('/api/admin/jobs?limit=500', role='admin')
        if not any(job['state'] in ('queued', 'leased') for job in jobs):
            return
        if time.monotonic() > deadline:
            raise TimeoutError('queue has not drained; no next request was sent')
        await asyncio.sleep(1)


async def collect(http, run_id, folder):
    path = '/api/runs/' + quote(run_id, safe='')
    public = await http.get(path)
    private = await http.get(path, role='admin')
    write(folder / 'run.operator.json', public); write(folder / 'run.admin.json', private)
    event_sets = {}
    for role in ('operator', 'admin'):
        events, cursor = [], 0
        while True:
            batch = await http.get(path + f'/events?after_seq={cursor}&limit=10000', role=role)
            if not batch:
                break
            if batch[-1]['seq'] <= cursor:
                raise ValueError('event cursor did not advance')
            events.extend(batch); cursor = batch[-1]['seq']
        write(folder / f'events.{role}.jsonl', b''.join(encoded(e).replace(b'\n', b'') + b'\n' for e in events))
        event_sets[role] = events
    inventory, latest = [], None
    for index, item in enumerate(sorted(private['artifacts'], key=lambda a: (a['artifact_id'], a['revision']))):
        response = await http.request('GET', f'/api/artifacts/{quote(run_id, safe="")}/{quote(item["artifact_id"], safe="")}/versions/{item["revision"]}/raw')
        response.raise_for_status()
        if sha(response.content) != item['sha256']:
            raise ValueError('published artifact checksum mismatch')
        filename = f'artifact-{index:03d}.bin'
        write(folder / filename, response.content)
        inventory.append({**item, 'evidence_file': filename})
        if item['logical_path'] == 'guide.md' and (latest is None or item['revision'] > latest[0]['revision']):
            latest = (item, response.content)
    write(folder / 'artifacts.json', inventory)
    archive = await http.request('GET', path + '/export?fmt=zip')
    archive.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        if manifest.get('schema_version') != 1 or manifest.get('run_id') != run_id or manifest.get('selection') != 'latest':
            raise ValueError('unexpected latest ZIP manifest')
        expected = {}
        for artifact in private['artifacts']:
            existing = expected.get(artifact['artifact_id'])
            if existing is None or artifact['revision'] > existing['revision']:
                expected[artifact['artifact_id']] = {
                    'artifact_id': artifact['artifact_id'], 'revision': artifact['revision'],
                    'sha256': artifact['sha256'], 'path': 'artifacts/' + artifact['logical_path']}
        if sorted(manifest['artifacts'], key=lambda a: a['artifact_id']) != sorted(expected.values(), key=lambda a: a['artifact_id']):
            raise ValueError('latest ZIP omitted an artifact or differs from the recorded latest revision set')
        for artifact in manifest['artifacts']:
            if sha(bundle.read(artifact['path'])) != artifact['sha256']:
                raise ValueError('export checksum mismatch')
    write(folder / 'latest.zip', archive.content)
    measurement = {'status': 'missing'}
    if latest:
        text = latest[1].decode('utf-8', errors='strict')
        errors = [e.message for e in Draft202012Validator(REQUIREMENTS[0]['json_schema']).iter_errors(text)]
        measurement = {'status': 'fail' if errors else 'pass', 'problems': errors,
                       'unicode_code_points': len(text), 'utf8_bytes': len(latest[1]),
                       'revision': latest[0]['revision'], 'sha256': sha(latest[1])}
    reviews = [e for e in event_sets['admin'] if e['type'] == 'review.submitted']
    write(folder / 'model-reviews.json', reviews)
    return {'run_id': run_id, 'runtime_status': public['status'], 'usage': public['usage'],
            'format_check': measurement, 'model_review_count': len(reviews),
            'semantic_review': 'pending', 'business_quality_accepted': False,
            'human_acceptance': 'not_performed', 'selected_export': 'not_performed', 'evidence_dir': str(folder)}


async def execute(args, manifest, cfg):
    preflight = args.command == 'preflight'
    attempts = read(args.root / 'attempts.json')
    if preflight and (attempts or pending_jobs(args.root)):
        raise ValueError('preflight refuses a series with execution attempts or queued work')
    if any(a.get('admission_stopped') for a in attempts):
        raise ValueError('a previous admission failed; inspect the retained response instead of continuing with new keys')
    if not preflight and (args.root / 'STOP').exists():
        raise ValueError('STOP requested; service and queued work were not started')
    check_database_before_start(args.root, cfg, attempts)
    if not preflight:
        actual_model = await model_state(cfg.defaults.model)
        if any(manifest[key] != value for key, value in actual_model.items()):
            raise ValueError('model/version/digest changed')
    session = args.root / 'sessions' / (args.command + '-' + uuid.uuid4().hex)
    session.mkdir(parents=True, mode=0o700)
    http = EvidenceHTTP(args.root, manifest['origin'], session)
    try:
        async with server(args.root, manifest, cfg):
            identity = await http.get('/api/auth/me')
            if identity.get('role') != 'operator' or identity.get('subject') != OPERATOR:
                raise ValueError('execution identity is not the frozen operator')
            write(session / 'config.operator.json', await http.get('/api/config'))
            write(session / 'config.admin.json', await http.get('/api/config', role='admin'))
            body = read(args.root / 'request.json')
            if preflight:
                body['start'] = False
                response = await http.request('POST', '/api/runs', body=body, key='public-guide-preflight-v1')
                if response.status_code != 202:
                    raise ValueError('start:false preflight was rejected; inspect private HTTP evidence')
                run_id = response.json()['run_id']
                result = await collect(http, run_id, session / 'preflight')
                events = (session / 'preflight/events.admin.jsonl').read_text().splitlines()
                if result['runtime_status'] != 'created' or result['format_check']['status'] != 'missing' or pending_jobs(args.root) or any(json.loads(e)['type'] == 'model.called' for e in events):
                    raise ValueError('preflight did not remain an unstarted real request')
                write(args.root / 'preflight.json', {**result, 'start': False, 'model_calls': 0})
                return
            for rep in range(1, 11):
                if (args.root / 'STOP').exists():
                    raise ValueError('STOP requested; prior attempts retained')
                frozen(args.root)
                if await model_state(cfg.defaults.model) != {key: manifest[key] for key in ('model', 'model_digest', 'ollama_version')}:
                    raise ValueError('model changed during the series')
                attempt = next((a for a in attempts if a['rep'] == rep), None)
                if attempt and attempt.get('result'):
                    continue
                if attempt is None or not attempt['sent']:
                    await wait_for_queue(http)
                if attempt is None:
                    attempt = {'rep': rep, 'request_key': 'public-guide-' + uuid.uuid4().hex, 'sent': False}
                    attempts.append(attempt); write(args.root / 'attempts.json', attempts)
                write(args.root / 'status.json', {'state': 'running', 'rep': rep,
                      'semantic_review': 'pending', 'business_quality_accepted': False})
                if not attempt.get('run_id'):
                    if attempt['sent']:
                        scope = sha(json.dumps([OPERATOR, '/api/runs', attempt['request_key']]).encode())
                        with sqlite3.connect((args.root / 'data/agentteam.sqlite').as_uri() + '?mode=ro', uri=True) as db:
                            receipt = db.execute('SELECT run_id FROM request_receipts WHERE scope_key=?', (scope,)).fetchone()
                        if receipt is None:
                            raise ValueError('previous send has no durable receipt: ambiguous outcome; reconcile manually, do not issue another key')
                    attempt['sent'] = True; write(args.root / 'attempts.json', attempts)
                    response = await http.request('POST', '/api/runs', body=body, key=attempt['request_key'])
                    if response.status_code != 202:
                        attempt['http_status'] = response.status_code
                        attempt['admission_stopped'] = True
                        write(args.root / 'attempts.json', attempts)
                        try:
                            failed_run = response.json().get('run_id')
                        except (ValueError, AttributeError):
                            failed_run = None
                        if failed_run:
                            await collect(http, failed_run, session / f'admission-{rep:02d}')
                        raise ValueError('admission did not return 202; series stopped without a new key')
                    attempt['run_id'] = response.json()['run_id']; write(args.root / 'attempts.json', attempts)
                run_id = attempt['run_id']
                deadline = time.monotonic() + cfg.limits.timeout_seconds + 180
                while True:
                    current = await http.get('/api/runs/' + quote(run_id, safe=''))
                    if current['status'] in TERMINAL:
                        break
                    if current['status'] not in {'created', 'queued', 'planning', 'running'}:
                        raise ValueError('unknown runtime state; inspect evidence before continuing')
                    if time.monotonic() > deadline:
                        await collect(http, run_id, session / f'timeout-{rep:02d}')
                        raise TimeoutError('observation deadline reached; no automatic resume or new request')
                    await asyncio.sleep(1)
                try:
                    await wait_for_queue(http)
                finally:
                    attempt['result'] = await collect(http, run_id, session / f'{rep:02d}-{run_id}')
                    write(args.root / 'attempts.json', attempts)
                print(json.dumps({'rep': rep, **attempt['result']}, ensure_ascii=False), flush=True)
            await wait_for_queue(http)
            write(args.root / 'status.json', {'state': 'completed_trials', 'completed': len(attempts),
                  'semantic_review': 'pending', 'business_quality_accepted': False, 'human_acceptance': 'not_performed'})
    finally:
        await http.client.aclose()


async def main(args):
    os.umask(0o077)
    if args.command == 'prepare':
        await prepare(args)
        return
    # This lock is only in this new series, never the running preceding series.
    with (args.root / 'workflow.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest, cfg = frozen(args.root)
        try:
            if args.command == 'run':
                with launch_guard(manifest, args.allow_model_execution):
                    await execute(args, manifest, cfg)
            else:
                await execute(args, manifest, cfg)
        except BaseException as error:
            write(args.root / 'status.json', {'state': 'stopped', 'error_type': type(error).__name__,
                  'reason': 'inspect private evidence; no automatic retry, resume or quality acceptance',
                  'semantic_review': 'pending', 'business_quality_accepted': False})
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'preflight', 'run'):
        sub = commands.add_parser(name)
        sub.add_argument('--root', type=lambda p: Path(p).expanduser().resolve(), required=True)
        if name == 'prepare':
            sub.add_argument('--profile', type=lambda p: Path(p).expanduser().resolve(), required=True,
                             help='unchanged real probed-agents.yaml; only its local model/connection evidence is reused')
            sub.add_argument('--prior-series', type=lambda p: Path(p).expanduser().resolve(), required=True)
            sub.add_argument('--validation-only', action='store_true', help='allow dirty checkout for start:false verification; permanently disallow inference')
        if name == 'run':
            sub.add_argument('--allow-model-execution', action='store_true')
    asyncio.run(main(parser.parse_args()))
