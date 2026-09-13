"""Provision an isolated installation with real keys and a previously recorded local run."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentteam.api.service import AppService
from agentteam.contracts import Run
from agentteam.security.accounts import issue_key


async def provision(root, origin):
    root.mkdir(parents=True, mode=0o700)
    (root / 'security').mkdir(mode=0o700)
    access = root / 'security/access.json'
    for subject, role in [('forifor', 'admin'), ('verification-operator', 'operator')]:
        issue_key(access, subject, role, root / (subject + '.key'), organization='FORIFOR/Multibot', public_origin=origin)
    docs = ROOT.parent / 'docs'
    svc = await AppService(root / 'data', config_yaml=(docs / 'config/local-qwen35-9b-team.yaml').read_text(), access_file=access).start()
    try:
        run = Run.model_validate_json((docs / 'evidence/local-fixes-2026-09-14/thinking-interruption.json').read_text())
        await svc.runs.create_run(run)
        artifact = json.loads((docs / 'evidence/local-qwen35-9b-2026-09-14/thinking-team-quality-audit.json').read_text())
        metadata = await svc.artifacts.publish(run.run_id, 'email.md', artifact['artifact_text'].encode(), agent_id='builder', task_id='t1')
        assert metadata.sha256 == artifact['sha256']
        print(json.dumps({'root': str(root), 'run_id': run.run_id, 'artifact_sha256': metadata.sha256}))
    finally:
        await svc.stop()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--origin', default='http://127.0.0.1:8796')
    args = p.parse_args()
    asyncio.run(provision(args.root.resolve(), args.origin))
