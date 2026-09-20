"""Serve a separate copy of an actual committed model run for UI/byte verification.

Never call a provider, invent model events or upgrade the recorded outcome. The
historical outcome is not evidence that a new request succeeds on current code.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.contracts import Run, TaskState
from agentteam.store.db import dumps

ROOT = Path(__file__).resolve().parents[2]


async def import_record(source: Path, data: Path):
    profile = (ROOT / 'docs/config/local-qwen35-9b-team.yaml').read_text()
    svc = await AppService(data, config_yaml=profile).start()
    try:
        record = json.loads((source / 'run.json').read_text())
        run = Run.model_validate(record)
        if await svc.runs.get_run(run.run_id):
            return run.run_id
        await svc.runs.create_run(run)
        for task in record['tasks']:
            await svc.runs.upsert_task(TaskState.model_validate(task))
        manifests = json.loads((source / 'artifacts.json').read_text())
        for manifest in manifests:
            payload = (source / manifest['evidence_file']).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == manifest['sha256']
            published = await svc.artifacts.publish(run.run_id, manifest['logical_path'], payload,
                agent_id=manifest['agent_id'], task_id=manifest['task_id'], media_type=manifest['media_type'], sources=manifest['sources'])
            assert published.revision == manifest['revision']
            await svc.artifacts.set_event(run.run_id, published.artifact_id, published.revision, manifest['event_id'])
        for line in (source / 'events.jsonl').read_text().splitlines():
            event = json.loads(line)
            assert event['run_id'] == run.run_id
            fields = ['run_id','seq','event_id','recorded_at','actor_id','actor_kind','task_id','causation_id','type']
            await svc.db.execute('INSERT INTO events('+','.join(fields)+',payload_json) VALUES('+','.join('?' for _ in range(10))+')',
                                 tuple(event.get(k) for k in fields)+(dumps(event['payload']),))
        print(json.dumps({'run_id':run.run_id,'source':str(source),'recorded_status':run.status,'provider_calls':0,'mode':'actual recorded run copy'}),flush=True)
        return run.run_id
    finally:
        await svc.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8797)
    args = parser.parse_args()
    asyncio.run(import_record(args.source.resolve(),args.data_dir.resolve()))
    import uvicorn
    uvicorn.run(create_app(AppService(args.data_dir)),host='127.0.0.1',port=args.port,proxy_headers=False,access_log=False)
