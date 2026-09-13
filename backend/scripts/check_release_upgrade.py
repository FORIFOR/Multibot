"""Real installed-wheel upgrade/rollback drill with original model artifacts.

Never points at a live installation: --root must be a new verification directory.
The retained release manifest supplies separately installed old/new wheel Pythons.
No model call, synthetic business record or replacement service is involved.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import quote

import httpx


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def prepare(args):
    # This mode runs under the old wheel's isolated Python, not the source tree.
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.security.accounts import issue_key
    access = args.root / 'security/access.json'
    for subject, role in [('forifor', 'admin'), ('upgrade-operator', 'operator')]:
        issue_key(access, subject, role, args.root / (subject + '.key'),
                  organization='FORIFOR/Multibot', public_origin='http://localhost')
    run = Run.model_validate_json((args.source / 'run.json').read_text())
    raw = args.source / 'readiness.json'
    inventory = json.loads((args.source / 'artifacts.json').read_text())
    original = next(a for a in inventory if a['logical_path'] == 'readiness.json')
    assert digest(raw) == original['sha256']
    svc = await AppService(args.root / 'data', config_yaml=args.profile.read_text(), access_file=access).start()
    try:
        await svc.runs.create_run(run)
        for task in json.loads((args.source / 'run.json').read_text())['tasks']:
            await svc.runs.upsert_task(TaskState.model_validate(task))
        artifact = await svc.artifacts.publish(run.run_id, 'readiness.json', raw.read_bytes(), agent_id='builder', task_id='t1')
        assert artifact.sha256 == original['sha256']
        (args.root / 'original.json').write_text(json.dumps(artifact.model_dump(mode='json'), indent=2) + '\n')
    finally:
        await svc.stop()


def serve(args):
    os.environ['AGENTTEAM_ACCESS_FILE'] = str(args.root / 'security/access.json')
    os.environ['AGENTTEAM_DATA_DIR'] = str(args.data)
    import uvicorn
    from agentteam.api.app import create_app
    from agentteam.api.service import AppService
    service = AppService(args.data, access_file=args.root / 'security/access.json')
    # The parent retains the bound socket: no free-port discovery/bind race.
    uvicorn.run(create_app(service), fd=args.fd, access_log=False, log_level='info', timeout_graceful_shutdown=30)


def stop(process):
    if process.poll() is not None:
        raise RuntimeError('verification server exited unexpectedly')
    process.send_signal(signal.SIGTERM)
    try:
        code = process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(timeout=10)
        raise RuntimeError('verification server did not stop gracefully')
    # Uvicorn 0.52 re-raises SIGTERM after a successful lifespan shutdown.
    # Require its actual shutdown-complete record as well as the expected code.
    if code not in (0, -signal.SIGTERM) or 'Application shutdown complete.' not in process.verification_log.read_text():
        raise RuntimeError('verification server stopped with failure')


def drill(args):
    args.root.mkdir(mode=0o700)  # refuse an existing installation
    releases = json.loads(args.releases.read_text())
    for release in releases.values():
        if digest(Path(release['wheel'])) != release['wheel_sha256']:
            raise ValueError('installed release wheel digest mismatch')
    script = str(Path(__file__).resolve())
    env = {**os.environ, 'AGENTTEAM_MODE': 'production'}
    env.pop('PYTHONPATH', None)
    def invoke(label, more, *, check=True):
        result = subprocess.run([releases[label]['python'], '-I', script, '--root', str(args.root), *more],
                                env=env, capture_output=True, text=True, timeout=60)
        if check and result.returncode:
            raise RuntimeError('release helper failed; inspect the private helper log')
        with (args.root / 'helper.log').open('a') as log:
            log.write(result.stdout + result.stderr)
        return result
    invoke('old', ['--mode', 'prepare', '--source', str(args.source), '--profile', str(args.profile)])
    metadata = json.loads((args.root / 'original.json').read_text())
    run_id = metadata['run_id']
    artifact_url = f'/api/artifacts/{run_id}/{quote(metadata["artifact_id"], safe="")}/versions/{metadata["revision"]}/raw'
    admin = (args.root / 'forifor.key').read_text().strip()
    original_operator = (args.root / 'upgrade-operator.key').read_text().strip()
    checks = []
    processes = []
    def record(name, ok, **detail):
        checks.append({'check': name, 'passed': bool(ok), **detail})
        if not ok:
            raise AssertionError(name)
    listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(128)
    base = f'http://127.0.0.1:{listener.getsockname()[1]}'
    def boot(label, data, name):
        log = (args.root / (name + '.log')).open('w')
        process = subprocess.Popen([releases[label]['python'], '-I', script, '--mode', 'serve', '--root', str(args.root),
                                    '--data', str(data), '--fd', str(listener.fileno())], env=env,
                                   pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT)
        process.verification_log = Path(log.name)
        log.close(); processes.append(process)
        started = time.monotonic()
        with httpx.Client(base_url=base, headers={'Host': 'localhost'}, trust_env=False, timeout=1) as client:
            while time.monotonic() - started < 20:
                if process.poll() is not None:
                    raise RuntimeError('verification server failed to start; inspect its private log')
                try:
                    if client.get('/api/health/live').status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                time.sleep(.05)
        raise RuntimeError('verification server did not become live')
    report = {'old_commit': releases['old']['commit'], 'new_commit': releases['new']['commit'],
              'releases': releases, 'source_artifact_sha256': metadata['sha256'], 'checks': checks,
              'scope': 'isolated macOS HTTP / installed wheels / SQLite; no production traffic, TLS, model calls or SLA measurement',
              'production_ready': False}
    try:
        with httpx.Client(base_url=base, headers={'Host': 'localhost', 'Origin': 'http://localhost'}, trust_env=False, timeout=10) as client:
            old = boot('old', args.root / 'data', 'old')
            record('old server refuses unauthenticated artifact access', client.get(artifact_url).status_code == 401)
            response = client.post('/api/auth/login', json={'token': admin})
            record('real old-version browser session', response.status_code == 200)
            before_cookies = httpx.Cookies(client.cookies)
            record('old artifact exact original bytes', hashlib.sha256(client.get(artifact_url).content).hexdigest() == metadata['sha256'])
            response = client.put(f'/api/runs/{run_id}/access', json={'subject': 'upgrade-operator', 'permission': 'read'})
            record('real run access grant', response.status_code == 200)
            live = invoke('new', ['--mode', 'backup', '--data', str(args.root / 'data'), '--destination', str(args.root / 'rejected-live-snapshot')], check=False)
            record('live offline backup rejected without output', live.returncode != 0 and not (args.root / 'rejected-live-snapshot').exists())
            start_upgrade = time.monotonic(); stop(old)
            invoke('new', ['--mode', 'backup', '--data', str(args.root / 'data'), '--destination', str(args.root / 'before-upgrade')])
            candidate = boot('new', args.root / 'data', 'new')
            response = client.get(artifact_url)
            record('upgrade preserves authenticated session and artifact', response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == metadata['sha256'], elapsed_seconds=round(time.monotonic()-start_upgrade, 3))
            client.cookies.clear()
            record('upgrade preserves operator access grant', client.get(artifact_url, headers={'Authorization': 'Bearer '+original_operator}).status_code == 200)
            invoke('new', ['--mode', 'rotate'])
            current_operator = (args.root / 'rotated-operator.key').read_text().strip()
            record('new credential rotation rejects the old key', client.get(artifact_url, headers={'Authorization': 'Bearer '+original_operator}).status_code == 401)
            record('new credential can read the preserved artifact', client.get(artifact_url, headers={'Authorization': 'Bearer '+current_operator}).status_code == 200)
            stop(candidate)
            # Controlled corruption of this disposable copy, never original evidence.
            with (args.root / 'data/runs' / metadata['storage_path']).open('ab') as data:
                data.write(b'\n')
            bad = invoke('new', ['--mode', 'backup', '--data', str(args.root / 'data'), '--destination', str(args.root / 'rejected-corrupt-snapshot')], check=False)
            record('candidate artifact corruption rejects backup', bad.returncode != 0 and not (args.root / 'rejected-corrupt-snapshot').exists())
            start_restore = time.monotonic()
            invoke('new', ['--mode', 'restore', '--data', str(args.root / 'before-upgrade'), '--destination', str(args.root / 'restored')])
            rollback = boot('old', args.root / 'restored', 'rollback')
            client.cookies = before_cookies
            record('rollback snapshot invalidates pre-restore browser sessions', client.get(artifact_url).status_code == 401)
            client.cookies.clear()
            record('rollback retains credential revocation from current access file', client.get(artifact_url, headers={'Authorization': 'Bearer '+original_operator}).status_code == 401)
            response = client.get(artifact_url, headers={'Authorization': 'Bearer '+current_operator})
            record('rollback restores original bytes and grants with current key', response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == metadata['sha256'], elapsed_seconds=round(time.monotonic()-start_restore, 3))
            stop(rollback)
        report['passed'] = True
    except BaseException as exc:
        report['passed'] = False; report['error_type'] = type(exc).__name__
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                stop(process)
        listener.close()
        (args.root / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'checks': len(checks), 'result': str(args.root / 'result.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', default='drill', choices=['drill', 'prepare', 'serve', 'backup', 'restore', 'rotate'])
    parser.add_argument('--releases', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--fd', type=int)
    args = parser.parse_args()
    if args.mode == 'prepare':
        asyncio.run(prepare(args))
    elif args.mode == 'serve':
        serve(args)
    elif args.mode == 'rotate':
        from agentteam.security.accounts import issue_key
        issue_key(args.root / 'security/access.json', 'upgrade-operator', 'operator', args.root / 'rotated-operator.key')
    elif args.mode in ('backup', 'restore'):
        from agentteam.operations.backup import backup, restore
        (backup if args.mode == 'backup' else restore)(args.data, args.destination)
    else:
        drill(args)
