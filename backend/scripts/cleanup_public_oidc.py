#!/usr/bin/env python3
"""Own and stop only this verification root's real services; no model execution.

Ownership/tracebacks/commands stay private. Upload only cleanup-report.json.
Container startup is restricted to disposable GitHub Actions runners. API startup
requires the actual prepared profile/access files and a previously absent DB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import traceback
import uuid

REPO = Path(__file__).resolve().parents[2]
LABEL = 'org.multibot.verification-owner'
IMAGE = 'quay.io/keycloak/keycloak@sha256:ff4257d0d64efbe99ed1ddfaf07765cc3c36dc7518bf8324d41961327f441c54'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def root_digest(root):
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()


def closed(port):
    with socket.socket() as sock:
        sock.settimeout(.2)
        return sock.connect_ex(('127.0.0.1', port)) != 0


def wait_until(predicate, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(.1)
    return predicate()


def process_identity(pid):
    result = subprocess.run(['ps', '-ww', '-p', str(pid), '-o', 'pgid=,lstart=,stat=,args='],
                            capture_output=True, text=True, timeout=5, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode == 1 and not result.stdout.strip():
        return None
    result.check_returncode()
    fields = result.stdout.split(None, 7)
    if len(fields) != 8:
        raise ValueError('invalid process metadata')
    if 'Z' in fields[6]:
        return None
    identity = {'pid': pid, 'pgid': int(fields[0]), 'birth': ' '.join(fields[1:6]),
                'command_sha256': hashlib.sha256(fields[7].strip().encode()).hexdigest()}
    proc = Path('/proc') / str(pid) / 'stat'
    if proc.exists():
        identity['start_ticks'] = proc.read_text().rsplit(')', 1)[1].split()[19]
    return identity


def group_members(pgid):
    result = subprocess.check_output(['ps', '-axo', 'pid=,pgid=,stat='], text=True, timeout=5)
    return [int(fields[0]) for line in result.splitlines() if len(fields := line.split()) == 3
            and int(fields[1]) == pgid and 'Z' not in fields[2]]


def docker(*args):
    return subprocess.check_output(['docker', *args], stderr=subprocess.PIPE, timeout=30, text=True).strip()


def start_api(args):
    root = args.root
    state = root / 'api-owner.private.json'
    if state.exists() or not (root / 'data/agents.yaml').is_file() or not (root / 'security/access.json').is_file():
        raise ValueError('actual prepared files and unused ownership path are required')
    if (root / 'data/agentteam.sqlite').exists() or not closed(args.api_port):
        raise ValueError('API startup requires an unused database and port')
    owner = {'state': 'starting', 'root_sha256': root_digest(root),
             'port': args.api_port, 'identity': None, 'ready_observed': False}
    write(state, owner)
    command = [sys.executable, '-m', 'agentteam.cli', 'serve', '--host', '127.0.0.1',
               '--port', str(args.api_port), '--data-dir', str(root / 'data')]
    with (root / 'server.private.log').open('xb') as log:
        process = subprocess.Popen(command, cwd=REPO, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True, env={**os.environ, 'AGENTTEAM_MODE': 'production',
                                   'AGENTTEAM_ACCESS_FILE': str(root / 'security/access.json'),
                                   'PYTHONPATH': str(REPO / 'backend')})
    try:
        identity = process_identity(process.pid)
        if not identity or identity['pgid'] != process.pid:
            raise RuntimeError('owned API identity unavailable')
        owner.update(state='started', identity=identity)
        write(state, owner)
        if not wait_until(lambda: process.poll() is not None or not closed(args.api_port), 30):
            raise TimeoutError('API startup deadline')
        if process.poll() is not None:
            raise RuntimeError('API exited before ready')
        settled = process_identity(process.pid)
        # macOS's Python launcher can replace its command representation before
        # imports finish. Finalize only while our original Popen is still alive
        # and PID/group/birth (plus Linux start ticks) retain the same identity.
        if not settled or any(settled.get(k) != identity.get(k)
                              for k in ('pid', 'pgid', 'birth', 'start_ticks')):
            raise RuntimeError('API process changed during startup')
        owner['identity'] = settled
        owner['ready_observed'] = True
        write(state, owner)
    except BaseException:
        # Popen itself proves ownership even if persisting metadata failed.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
        raise


def start_container(args):
    root = args.root
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('container startup is restricted to GitHub Actions')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}', args.container_name):
        raise ValueError('invalid container name')
    state = root / 'container-owner.private.json'
    if state.exists() or not closed(args.container_port):
        raise ValueError('container startup requires unused ownership path and port')
    owner = {'state': 'starting', 'root_sha256': root_digest(root), 'token': str(uuid.uuid4()), 'port': args.container_port,
             'name': args.container_name, 'container_id': None}
    write(state, owner)  # Label survives a lost docker-run response.
    command = ['docker', 'run', '-d', '--name', args.container_name, '--label', LABEL + '=' + owner['token'],
               '--cidfile', str(root / 'container-id.private'), '--user', '0:0', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--memory', '1g', '--pids-limit', '256',
               '--env-file', str(root / 'keycloak.env'), '-e', 'JAVA_OPTS_KC_HEAP=-Xms128m -Xmx512m',
               '-p', f'127.0.0.1:{args.container_port}:8080', '-v', str(root / 'keycloak-import') + ':/opt/keycloak/data/import:ro',
               IMAGE, 'start-dev', '--hostname', f'http://127.0.0.1:{args.container_port}', '--import-realm',
               '--log-console-color=false', '--http-access-log-enabled=true',
               '--http-access-log-pattern=OIDC-JWKS-ACCESS %m %U %s']
    with (root / 'container.private.log').open('xb') as log:
        subprocess.run(command, stdout=log, stderr=log, check=True, timeout=180)
    owner.update(state='started', container_id=(root / 'container-id.private').read_text().strip())
    if not re.fullmatch(r'[0-9a-f]{64}', owner['container_id']):
        raise ValueError('invalid actual container identity')
    write(state, owner)


def cleanup_api(root):
    path = root / 'api-owner.private.json'
    result = {'status': 'NOT_STARTED', 'started': False, 'signals_sent': 0,
              'identity_matches': None, 'process_absent': None, 'group_empty': None, 'port_closed': None}
    if not path.exists():
        return result
    state = json.loads(path.read_text())
    if state.get('root_sha256') != root_digest(root):
        raise ValueError('API ownership belongs to another root')
    result['started'] = state.get('state') == 'started'
    result['ready_observed'] = state.get('ready_observed', False)
    identity = state.get('identity')
    if not identity:
        raise ValueError('API launch intent has no verified identity')
    pid, pgid = identity['pid'], identity['pgid']
    current = process_identity(pid)
    result['identity_matches'] = current == identity if current is not None else None
    if current is not None and current != identity:
        raise ValueError('PID identity changed; refusing to signal')
    # This API starts from an absent DB and creates no model/job processes.
    # Unexpected group members are not signalled; they make cleanup fail.
    for sig, seconds in ((signal.SIGTERM, 15), (signal.SIGKILL, 5)):
        current = process_identity(pid)
        if current is None:
            break
        if current != identity:
            raise ValueError('PID identity changed during cleanup')
        try:
            os.kill(pid, sig); result['signals_sent'] += 1
        except ProcessLookupError:
            break
        if wait_until(lambda: process_identity(pid) is None, seconds):
            break
    result.update(process_absent=process_identity(pid) is None, group_empty=not group_members(pgid),
                  port_closed=wait_until(lambda: closed(state['port']), 5))
    log = (root / 'server.private.log').read_text(errors='replace')
    result['runtime_error_markers'] = sum(log.count(token) for token in ('ERROR:', 'Traceback', 'Application shutdown failed'))
    result['status'] = 'PASS' if (all(result[k] for k in ('process_absent', 'group_empty', 'port_closed'))
        and (not result['ready_observed'] or result['runtime_error_markers'] == 0)) else 'FAIL'
    return result


def cleanup_container(root):
    path = root / 'container-owner.private.json'
    result = {'status': 'NOT_STARTED', 'started': False, 'owned_count': None, 'removed_count': 0,
              'remaining_owned_count': None, 'port_closed': None}
    if not path.exists():
        return result
    state = json.loads(path.read_text())
    if state.get('root_sha256') != root_digest(root):
        raise ValueError('container ownership belongs to another root')
    token = str(uuid.UUID(state['token']))
    result['started'] = state.get('state') == 'started'
    def owned():
        output = docker('ps', '-aq', '--no-trunc', '--filter', 'label=' + LABEL + '=' + token)
        ids = output.splitlines() if output else []
        if any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in ids):
            raise ValueError('invalid container inventory')
        return ids
    ids = owned(); result['owned_count'] = len(ids)
    for container_id in ids:
        metadata = json.loads(docker('inspect', container_id))[0]
        if metadata['Id'] != container_id or metadata['Config'].get('Labels', {}).get(LABEL) != token:
            raise ValueError('container identity changed; refusing to remove')
        if state.get('container_id') and state['container_id'] != container_id:
            raise ValueError('container does not match recorded immutable ID')
        # Docker rm -f also removes a paused owned container; no broad unpause.
        docker('rm', '-f', container_id); result['removed_count'] += 1
    result['remaining_owned_count'] = len(owned())
    result['port_closed'] = wait_until(lambda: closed(state['port']), 5)
    # A timed-out docker-run with no observed ID may still be settling inside
    # the daemon. Empty inventory alone cannot prove that launch never happened.
    result['creation_outcome_verified'] = bool(state.get('container_id') or ids)
    result['status'] = 'PASS' if (result['creation_outcome_verified']
        and result['remaining_owned_count'] == 0 and result['port_closed']) else 'FAIL'
    return result


def cleanup(root):
    report = {'started_at': now(), 'status': 'RUNNING', 'model_execution_requested': False,
              'human_acceptance': 'not_performed', 'services': {},
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for name, action in (('api', cleanup_api), ('container', cleanup_container)):
        try:
            report['services'][name] = action(root)
        except BaseException as error:
            report['services'][name] = {'status': 'FAIL', 'error_type': type(error).__name__}
            try:
                (root / (name + '-cleanup.private.log')).write_text(traceback.format_exc())
            except OSError:
                report['services'][name]['private_log_write_failed'] = True
        finally:
            try:
                write(root / 'cleanup-report.json', report)
            except OSError:
                report['report_write_failed'] = True
    report['status'] = 'PASS' if (not report.get('report_write_failed')
        and all(s['status'] in ('PASS', 'NOT_STARTED') for s in report['services'].values())) else 'FAIL'
    report['finished_at'] = now()
    write(root / 'cleanup-report.json', report)
    return report['status'] == 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start-api', 'start-container', 'cleanup'))
    parser.add_argument('--root', type=lambda s: Path(s).expanduser().resolve(), required=True)
    parser.add_argument('--api-port', type=int, default=8798)
    parser.add_argument('--container-port', type=int, default=8801)
    parser.add_argument('--container-name', default='multibot-public-oidc')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.root.is_relative_to(REPO) or not all(0 < p < 65536 for p in (args.api_port, args.container_port)):
            raise ValueError('private root and valid ports required')
        args.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if args.action == 'cleanup':
            ok = cleanup(args.root)
        else:
            (start_api if args.action == 'start-api' else start_container)(args)
            ok = True
        print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'action': args.action}))
        return 0 if ok else 1
    except BaseException as error:
        if args.root.is_dir() and not args.root.is_relative_to(REPO):
            try:
                (args.root / (args.action + '-failure.private.log')).write_text(traceback.format_exc())
                write(args.root / (args.action + '-failure.json'), {'status': 'FAIL', 'action': args.action, 'error_type': type(error).__name__})
            except OSError:
                pass  # Still emit only the safe failure type and a nonzero exit.
        print(json.dumps({'status': 'FAIL', 'action': args.action, 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
