"""Serial, resumable local-only paired evaluation using the existing 50 tasks.

Run from an immutable checkout. Each mode uses its own data store. A process lock
prevents duplicate campaign runners; every completed attempt stays in results.jsonl.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / 'evals/benchmark'))
from agentteam.config.loader import config_to_yaml, effective_all, load_config_file
from agentteam.providers.registry import ProviderRegistry
import tasks


def jobs():
    for rep in range(1, 4):
        for index, task in enumerate(tasks.TASKS):
            # Alternate the first mode to reduce a systematic warm-cache/order advantage.
            for mode in (('team', 'single') if (rep + index) % 2 else ('single', 'team')):
                yield task['id'], rep, mode


def recorded(root, mode, task, rep):
    p = root / mode / 'results.jsonl'
    if not p.exists():
        return False
    return any(r['task'] == task and r['rep'] == rep for r in
               (json.loads(line) for line in p.read_text().splitlines() if line.strip()))


async def probe_config(cfg):
    """Resolve capability metadata before freezing the config fingerprint."""
    conn = cfg.connection(cfg.defaults.connection_id)
    if conn.capability_check == 'passed':
        return
    registry = ProviderRegistry(cfg)
    try:
        result = await registry.adapter(conn.id).probe(cfg.defaults.model)
    finally:
        await registry.aclose()
    if not result.ok:
        raise ValueError(f'Local provider probe failed: {result.error}')
    conn.capability_check = 'passed'
    conn.capability_detail = {'model_reported': result.model_reported, 'error': result.error}


def main(root):
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'campaign.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = root / 'campaign-fingerprint.json'
    fingerprints = {}
    models = set()
    for mode in ('team', 'single'):
        p = root / mode / 'agents.yaml'
        cfg = load_config_file(p)
        assert cfg.defaults.team_mode == mode
        for agent in effective_all(cfg).values():
            if agent.driver != 'ollama' or agent.base_url != 'http://127.0.0.1:11434/v1':
                raise ValueError('Campaign requires loopback Ollama for every agent')
            models.add(agent.model)
        if not manifest.exists():
            asyncio.run(probe_config(cfg))
            p.write_text(config_to_yaml(cfg), encoding='utf-8')
        fingerprints[mode] = hashlib.sha256(p.read_bytes()).hexdigest()
    if len(models) != 1:
        raise ValueError('Both modes must use the same model')
    fingerprints['tasks'] = hashlib.sha256((ROOT.parent / 'evals/benchmark/tasks.py').read_bytes()).hexdigest()
    fingerprints['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    fingerprints['ollama_version'] = json.load(urlopen('http://127.0.0.1:11434/api/version', timeout=10))['version']
    tags = json.load(urlopen('http://127.0.0.1:11434/api/tags', timeout=10))['models']
    name = next(iter(models))
    fingerprints['model_digest'] = next(m['digest'] for m in tags if m['name'] in (name, name + ':latest'))
    if manifest.exists() and json.loads(manifest.read_text()) != fingerprints:
        raise ValueError('Configuration, code, task source, or model changed; start a new campaign directory')
    manifest.write_text(json.dumps(fingerprints, indent=2) + '\n')

    def status(state, **extra):
        value = {'state': state, 'updated_at': datetime.now(timezone.utc).isoformat(),
                 'target_runs': 300, **extra}
        tmp = root / 'campaign-status.tmp'
        tmp.write_text(json.dumps(value, indent=2) + '\n')
        tmp.replace(root / 'campaign-status.json')

    try:
        for task, rep, mode in jobs():
            if (root / 'STOP').exists():
                status('paused', reason='STOP file present; last in-flight run was preserved')
                return 0
            if recorded(root, mode, task, rep):
                continue
            # No changed model/runtime is silently introduced part-way through a series.
            for m in ('team', 'single'):
                if hashlib.sha256((root / m / 'agents.yaml').read_bytes()).hexdigest() != fingerprints[m]:
                    raise ValueError('Campaign configuration changed during execution')
            current = json.load(urlopen('http://127.0.0.1:11434/api/tags', timeout=10))['models']
            digest = next(m['digest'] for m in current if m['name'] in (name, name + ':latest'))
            version = json.load(urlopen('http://127.0.0.1:11434/api/version', timeout=10))['version']
            if digest != fingerprints['model_digest'] or version != fingerprints['ollama_version']:
                raise ValueError('Ollama version or model changed during execution')
            status('running', task=task, rep=rep, mode=mode)
            print(f'{mode} {task} #{rep}', flush=True)
            with (root / f'{mode}-campaign.log').open('a') as log:
                result = subprocess.run([
                    sys.executable, str(ROOT / 'scripts/benchmark.py'), '--data-dir', str(root / mode),
                    '--tasks', task, '--repeat', '1', '--rep-start', str(rep), '--parallel', '1',
                    '--timeout', '600', '--budget', '6', '--resume',
                ], stdout=log, stderr=subprocess.STDOUT, timeout=1500)
            if result.returncode or not recorded(root, mode, task, rep):
                status('blocked', task=task, rep=rep, mode=mode, exit_code=result.returncode)
                return 2
        status('completed')
        return 0
    except Exception as exc:
        status('blocked', error=f'{type(exc).__name__}: {exc}')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    raise SystemExit(main(parser.parse_args().data_root))
