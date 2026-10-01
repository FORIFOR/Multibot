"""Run actual HTTP/SQLite and browser boundaries without executing a model.

The input profile and documents come from retained repository evidence. Its old
probe is used only to exercise admission; no current provider health is claimed.
Credentials, SQLite and logs remain in a new private root. Upload only report.json
and the named result JSON/screenshots, never the entire verification directory.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

from check_subject_admission import verify
from check_public_responses import check

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from agentteam.security.accounts import issue_key
from agentteam.api.app import create_app
from agentteam.api.service import AppService
import uvicorn


def process_snapshot():
    """Use process metadata only: command arguments can contain credentials."""
    rows = subprocess.check_output(
        ['ps', '-axo', 'pid=,ppid=,pgid=,lstart=,stat='], text=True,
        env={**os.environ, 'LC_ALL': 'C'}, timeout=5)
    result = {}
    for line in rows.splitlines():
        fields = line.split()
        if len(fields) == 9:
            result[int(fields[0])] = (int(fields[1]), int(fields[2]), ' '.join(fields[3:8]), fields[8])
    return result


async def run_browser_process(command, *, cwd, env, log, cleanup, timeout=180, grace=10):
    """Track actual ancestry, including Playwright's detached Chrome groups.

    A new Node session alone is insufficient: Chrome creates its own group. A
    signal is sent only after rechecking an observed PID's start time, never by
    executable name or a machine-wide process match.
    """
    process = await asyncio.create_subprocess_exec(
        *command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True)
    owned = {}
    signals = 0
    waiter = asyncio.create_task(process.wait())

    def remember():
        current = process_snapshot()
        if not owned and process.pid in current:
            owned[process.pid] = current[process.pid][2]
        known = {pid for pid, birth in owned.items() if pid in current and current[pid][2] == birth}
        while True:
            children = {pid for pid, row in current.items() if row[0] in known} - known
            if not children:
                break
            for pid in children:
                owned[pid] = current[pid][2]
            known.update(children)
        return {pid: current[pid] for pid in known if 'Z' not in current[pid][3]}

    def send_owned(sig):
        nonlocal signals
        live = remember()
        # Group leaders first, so newly spawned descendants in their groups
        # are stopped too. Recheck identity immediately before each signal.
        groups = {pid for pid, row in live.items() if pid == row[1]}
        for pid in [*groups, *[pid for pid in live if live[pid][1] not in groups]]:
            current = process_snapshot().get(pid)
            if not current or current[2] != owned[pid] or 'Z' in current[3]:
                continue
            try:
                if pid in groups and current[1] == pid:
                    os.killpg(pid, sig)
                else:
                    os.kill(pid, sig)
                signals += 1
            except ProcessLookupError:
                pass

    try:
        deadline = time.monotonic() + timeout
        while not waiter.done():
            remember()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('browser verification exceeded its deadline')
            try:
                await asyncio.wait_for(asyncio.shield(waiter), min(.1, remaining))
            except TimeoutError:
                pass
        return waiter.result()
    finally:
        send_owned(signal.SIGTERM)
        deadline = time.monotonic() + grace
        while remember() and time.monotonic() < deadline:
            await asyncio.sleep(.1)
        if remember():
            send_owned(signal.SIGKILL)
        deadline = time.monotonic() + 5
        while remember() and time.monotonic() < deadline:
            await asyncio.sleep(.1)
        remaining = remember()
        cleanup.append({'program': Path(command[-1]).name, 'tracked_processes': len(owned),
                        'signals_sent': signals, 'remaining_processes': len(remaining),
                        'status': 'PASS' if not remaining else 'FAILED'})
        if remaining:
            raise RuntimeError('owned browser processes remain after cleanup; inspect the private verification root')
        await asyncio.wait_for(asyncio.shield(waiter), timeout=5)


@asynccontextmanager
async def running_browser_api(data, access, port, cleanup, private_root):
    """Own the actual in-process API task; never signal a port's other owner."""
    cleanup.update(status='RUNNING', startup_attempted=True, started=False,
                   service_stopped=None, server_task_done=None, port_closed=None,
                   lifespan_shutdown_failed=None, lifespan_error_occurred=None)
    service = server = task = None
    cleanup_errors = []
    try:
        service = AppService(data_dir=data, access_file=access)
        log_config = {'version': 1, 'disable_existing_loggers': False,
                      'handlers': {'private': {'class': 'logging.FileHandler',
                          'filename': str(private_root / 'browser-api.private.log'), 'encoding': 'utf-8'}},
                      'loggers': {'uvicorn': {'handlers': ['private'], 'level': 'ERROR', 'propagate': False},
                                  'uvicorn.error': {'level': 'ERROR'},
                                  'uvicorn.access': {'handlers': ['private'], 'level': 'ERROR', 'propagate': False}}}
        server = uvicorn.Server(uvicorn.Config(create_app(service), host='127.0.0.1', port=port,
                                             log_config=log_config, access_log=False, lifespan='on'))
        task = asyncio.create_task(server.serve())
        for _ in range(100):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError('owned API stopped before startup')
            await asyncio.sleep(.05)
        if not server.started:
            raise TimeoutError('owned API startup deadline')
        cleanup['started'] = True
        yield
    finally:
        if task is not None:
            server.should_exit = True
            try:
                await asyncio.wait_for(asyncio.shield(task), 15)
            except BaseException as error:
                cleanup_errors.append(type(error).__name__)
                try:
                    (private_root / 'api-shutdown.private.log').write_text(traceback.format_exc())
                except OSError:
                    cleanup_errors.append('PrivateLogWriteFailed')
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
                except BaseException as error:
                    cleanup_errors.append(type(error).__name__)
            cleanup['server_task_done'] = task.done()
        if service is not None and getattr(service, '_process_lock', None) is not None:
            try:
                await asyncio.wait_for(service.stop(), 5)
            except BaseException as error:
                cleanup_errors.append(type(error).__name__)
                try:
                    (private_root / 'service-shutdown.private.log').write_text(traceback.format_exc())
                except OSError:
                    cleanup_errors.append('PrivateLogWriteFailed')
        cleanup['service_stopped'] = service is None or getattr(service, '_process_lock', None) is None
        lifespan = getattr(server, 'lifespan', None)
        if lifespan is not None:
            cleanup['lifespan_shutdown_failed'] = lifespan.shutdown_failed
            cleanup['lifespan_error_occurred'] = lifespan.error_occurred
        for _ in range(50):
            with socket.socket() as sock:
                sock.settimeout(.2)
                cleanup['port_closed'] = sock.connect_ex(('127.0.0.1', port)) != 0
            if cleanup['port_closed']:
                break
            await asyncio.sleep(.1)
        cleanup['error_types'] = cleanup_errors
        good = (not cleanup_errors and not cleanup['lifespan_shutdown_failed']
                and not cleanup['lifespan_error_occurred'] and cleanup['service_stopped'] and cleanup['port_closed']
                and (task is None or cleanup['server_task_done']))
        cleanup['status'] = 'PASS' if good else 'FAILED'
        if not good:
            raise RuntimeError('owned API cleanup failed; inspect private evidence')


async def main(root: Path):
    os.umask(0o077)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'model_execution': False,
        'business_acceptance': False,
        'checks': [],
        'process_cleanup': [],
        'api_cleanup': {'scope': 'browser_verification_api', 'status': 'NOT_STARTED',
                        'startup_attempted': False, 'started': False, 'service_stopped': None,
                        'server_task_done': None, 'port_closed': None},
    }
    try:
        if not shutil.which('node') or not shutil.which('sqlite3'):
            raise RuntimeError('node and sqlite3 are required')
        recorded = REPO / 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-run.json'
        profile = root / 'recorded-profile.yaml'
        profile.write_text(json.loads(recorded.read_text())['config_snapshot']['config_yaml'])
        profile.chmod(0o600)
        report.update(recorded_profile_source=str(recorded.relative_to(REPO)),
                      recorded_profile_source_sha256=hashlib.sha256(recorded.read_bytes()).hexdigest(),
                      profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest())
        report['verification_files_sha256'] = {
            str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__), BACKEND / 'scripts/check_subject_admission.py',
                         BACKEND / 'scripts/check_public_responses.py',
                         *[REPO / 'frontend/scripts' / name for name in
                           ('auth-browser-isolation.mjs', 'auth-retry-reload.mjs', 'auth-parallel-login.mjs',
                            'auth-peer-tab-close.mjs')]]
        }
        await verify(root / 'admission', profile)
        report['checks'].append('actual HTTP/SQLite admission')
        await check(root / 'responses')
        report['checks'].append('actual-source response projection')
        data = root / 'browser-data'
        data.mkdir(mode=0o700)
        shutil.copyfile(profile, data / 'agents.yaml')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        access = root / 'browser-access.json'
        for subject, role in [('public-service-admin', 'admin'), ('public-service-operator', 'operator')]:
            issue_key(access, subject, role, root / f'{subject}.key',
                      organization='FORIFOR/Multibot', public_origin=origin)
        env = {**os.environ, 'AUTH_TEST_URL': origin,
               'AUTH_TEST_ADMIN_KEY_FILE': str(root / 'public-service-admin.key'),
               'AUTH_TEST_OPERATOR_KEY_FILE': str(root / 'public-service-operator.key'),
               'AUTH_TEST_DATA_DIR': str(data), 'AUTH_TEST_EVIDENCE_DIR': str(root / 'browser'),
               'AUTH_PEER_EXPECT': 'recovered'}
        async with running_browser_api(data, access, port, report['api_cleanup'], root):
            for script in ('auth-browser-isolation.mjs', 'auth-retry-reload.mjs', 'auth-parallel-login.mjs',
                           'auth-peer-tab-close.mjs'):
                with (root / f'{script}.log').open('xb') as log:
                    code = await run_browser_process(
                        ['node', str(REPO / 'frontend/scripts' / script)], cwd=REPO / 'frontend',
                        env=env, log=log, cleanup=report['process_cleanup'])
                    if code:
                        raise RuntimeError(f'{script} failed; inspect its private log and browser failure evidence')
                report['checks'].append(script)
        report['status'] = 'PASS'
    except BaseException as error:
        report['status'] = 'FAILED'
        report['error_type'] = type(error).__name__
        (root / 'failure.private.log').write_text(traceback.format_exc())
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'completed_stages': len(report['checks'])}))
    return report['status'] == 'PASS'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        passed = asyncio.run(main(args.root.resolve()))
    except BaseException as error:
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
    raise SystemExit(0 if passed else 1)
