"""Real local-LLM queue/crash drill. Uses a probed local config and original workplace request.

Requires an idle Ollama and an isolated new root. This deliberately kills only the
API process it starts. No stub, model response replacement or capability bypass.
These interrupted attempts measure execution delivery, not business success.
"""
import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentteam.config.loader import load_config_file
from agentteam.ids import new_id
from agentteam.security.accounts import issue_key


def main(root, profile):
    cfg = load_config_file(profile)
    assert all(c.driver == 'ollama' and c.base_url == 'http://127.0.0.1:11434/v1' and c.capability_check == 'passed' for c in cfg.connections)
    root.mkdir(mode=0o700, parents=True)
    data = root / 'data'; data.mkdir(mode=0o700)
    (data / 'agents.yaml').write_bytes(profile.read_bytes())
    access = root / 'access.json'
    origin = 'http://127.0.0.1:8810'
    issue_key(access, 'forifor', 'admin', root / 'forifor.key', organization='FORIFOR/Multibot', public_origin=origin)
    settings = json.loads(access.read_text()); settings.update(max_active_runs=1, max_pending_runs=4)
    access.write_text(json.dumps(settings))
    token = (root / 'forifor.key').read_text().strip()
    record = json.loads((ROOT.parent / 'docs/evidence/local-fixes-2026-09-14/thinking-interruption.json').read_text())
    body = {'goal': record['goal'], 'inputs': record['inputs'], 'start': True}
    client = httpx.Client(base_url=origin, headers={'Authorization': 'Bearer ' + token}, timeout=15)
    process = None
    attempts = []
    checks = []

    def rows(sql, params=()):
        with closing(sqlite3.connect(f'file:{data / "agentteam.sqlite"}?mode=ro', uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params)]

    def wait(predicate, label, seconds=180):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                print(label, flush=True); return
            if process is not None and process.poll() is not None:
                raise RuntimeError('owned API process exited before ' + label)
            time.sleep(.25)
        raise TimeoutError(label)

    def start():
        nonlocal process
        env = {**os.environ, 'AGENTTEAM_MODE': 'production', 'AGENTTEAM_ACCESS_FILE': str(access)}
        process = subprocess.Popen([str(ROOT / '.venv/bin/agentteam'), 'serve', '--port', '8810', '--data-dir', str(data)],
            env=env, cwd=ROOT.parent, stdout=(root / 'server.log').open('a'), stderr=subprocess.STDOUT, start_new_session=True)
        (root / 'process.json').write_text(json.dumps({'pid': process.pid, 'data_dir': str(data)}))
        def alive():
            try: return client.get('/api/health/live').status_code == 200
            except httpx.TransportError: return False
        wait(alive, 'owned API started', 20)

    def create():
        key = new_id('request')
        response = client.post('/api/runs', json=body, headers={'Idempotency-Key': key})
        assert response.status_code == 202, response.text[:400]
        run = response.json(); attempts.append(run['run_id'])
        return run, key

    def actual_model_call(run_id):
        return bool(rows("SELECT seq FROM events WHERE run_id=? AND type='model.called'", (run_id,)))

    def stop():
        nonlocal process
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        process = None

    try:
        start()
        a, _ = create()
        wait(lambda: bool(rows("SELECT job_id FROM execution_jobs WHERE run_id=? AND state='leased'", (a['run_id'],))), 'first job leased')
        b, key = create()
        repeated = client.post('/api/runs', json=body, headers={'Idempotency-Key': key})
        assert repeated.status_code == 202 and repeated.json() == b
        assert len(rows('SELECT job_id FROM execution_jobs')) == 2
        assert client.get('/api/runs/' + b['run_id']).json()['status'] == 'queued'
        checks.append('Atomic durable acceptance; a repeated real HTTP request returns the same run without another job')
        assert client.post('/api/runs/' + b['run_id'] + '/cancel').status_code == 200
        assert client.get('/api/runs/' + b['run_id']).json()['status'] == 'cancelled'
        assert not actual_model_call(b['run_id'])
        checks.append('Queued cancellation performs no model call')
        c, _ = create()
        assert client.get('/api/runs/' + c['run_id']).json()['status'] == 'queued'
        wait(lambda: actual_model_call(a['run_id']), 'actual local model returned on first job')
        assert client.get('/api/runs/' + a['run_id']).json()['status'] in ('running', 'planning')
        process.kill(); process.wait(timeout=5); process = None
        start()
        recovered = client.get('/api/runs/' + a['run_id']).json()
        assert recovered['status'] == 'interrupted'
        first_calls = len(rows("SELECT seq FROM events WHERE run_id=? AND type='model.called'", (a['run_id'],)))
        wait(lambda: actual_model_call(c['run_id']), 'queued job recovered and actual local model returned')
        assert client.get('/api/runs/' + a['run_id']).json()['status'] == 'interrupted'
        assert len(rows("SELECT seq FROM events WHERE run_id=? AND type='model.called'", (a['run_id'],))) == first_calls
        checks.append('SIGKILL preserves an ambiguous active job as interrupted and automatically dispatches only the unstarted queued job')
        assert client.post('/api/runs/' + c['run_id'] + '/cancel').status_code == 200
        wait(lambda: client.get('/api/runs/' + c['run_id']).json()['status'] in ('cancelled', 'interrupted'), 'active cancellation reached a stopped state', 30)
        checks.append('Active cancellation stops without reporting completion')
        stop()
        evidence = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'model': cfg.defaults.model, 'checks': checks,
                    'runs': rows('SELECT run_id,status,usage_json,blocked_reason FROM runs'),
                    'jobs': rows('SELECT job_id,run_id,state,created_at,started_at,finished_at,reason FROM execution_jobs'),
                    'business_success_claimed': False, 'fake_provider': False}
        (root / 'durable-local.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps({'passed': len(checks), 'runs': attempts, 'root': str(root)}), flush=True)
    except BaseException as exc:
        (root / 'failure.json').write_text(json.dumps({'type': type(exc).__name__, 'message': str(exc)[:500], 'completed_checks': checks, 'runs': attempts}, indent=2))
        raise
    finally:
        stop(); client.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--profile', type=Path, required=True)
    args = p.parse_args()
    main(args.root.resolve(), args.profile.resolve())
