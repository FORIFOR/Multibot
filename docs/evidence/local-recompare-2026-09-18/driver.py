"""Local-only paired re-comparison (team vs single), restricted to tasks whose inputs are
real public sources (research) or programming specs graded by tests (code).
Mirrors backend/scripts/local_benchmark_campaign.py; differences: task subset, 1 repetition,
and an equal 1800s wall-clock limit for both modes. No cloud provider is contacted."""
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent
CHECKOUT = BASE / 'checkout'
ROOT = BASE / 'campaign'
PY = sys.executable  # the recorded run used the repository's backend/.venv interpreter
sys.path.insert(0, str(CHECKOUT / 'evals/benchmark'))
import tasks
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1
CATS = ('research', 'code')
SEL = [t for t in tasks.TASKS if t['category'] in CATS]

def recorded(mode, task, rep):
    p = ROOT / mode / 'results.jsonl'
    return p.exists() and any(r['task'] == task and r['rep'] == rep for r in
        (json.loads(l) for l in p.read_text().splitlines() if l.strip()))

def status(state, **extra):
    (ROOT / 'campaign-status.json').write_text(json.dumps(
        {'state': state, 'updated_at': datetime.now(timezone.utc).isoformat(),
         'target_runs': len(SEL) * 2 * REPS, **extra}, indent=2) + '\n')

fp = {m: hashlib.sha256((ROOT / m / 'agents.yaml').read_bytes()).hexdigest() for m in ('team', 'single')}
fp['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT, text=True).strip()
fp['tasks'] = [t['id'] for t in SEL]
fp['timeout_seconds'] = 1800
fp['ollama_version'] = json.load(urlopen('http://127.0.0.1:11434/api/version', timeout=10))['version']
man = ROOT / 'campaign-fingerprint.json'
if man.exists() and json.loads(man.read_text()) != fp:
    raise SystemExit('fingerprint changed; start a new campaign directory')
man.write_text(json.dumps(fp, indent=2) + '\n')

for rep in range(1, REPS + 1):
    for i, t in enumerate(SEL):
        for mode in (('team', 'single') if (rep + i) % 2 else ('single', 'team')):
            if (ROOT / 'STOP').exists():
                status('paused'); raise SystemExit(0)
            if recorded(mode, t['id'], rep):
                continue
            status('running', task=t['id'], rep=rep, mode=mode)
            print(f'{datetime.now():%H:%M:%S} {mode} {t["id"]} #{rep}', flush=True)
            with (ROOT / f'{mode}-campaign.log').open('a') as log:
                try:
                    rc = subprocess.run([PY, str(CHECKOUT / 'backend/scripts/benchmark.py'),
                        '--data-dir', str(ROOT / mode), '--tasks', t['id'], '--repeat', '1',
                        '--rep-start', str(rep), '--parallel', '1', '--timeout', '1800',
                        '--budget', '6', '--resume'], stdout=log, stderr=subprocess.STDOUT,
                        timeout=2700).returncode
                except subprocess.TimeoutExpired:
                    rc = 124
            if rc or not recorded(mode, t['id'], rep):
                status('blocked', task=t['id'], rep=rep, mode=mode, exit_code=rc)
                raise SystemExit(2)
status('completed')
