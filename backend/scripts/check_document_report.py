#!/usr/bin/env python3
"""Replay real document report inputs into isolated SQLite; no model execution.

Preserves the original v62 reports (including their errors) and labels this as
an implementation regression. This is not a regenerated acceptance result.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess

from check_message_handoff import REPO, Replay, Sources, require, sha, write_json
from agentteam.runtime.orchestrator import RunManager

OBSERVED_CLAIM = '独立した WORM 保管とアラート配送が未実装'

async def verify(args):
    sources = Sources(args.source)
    summary = {'status': 'running', 'scope': 'real-record document report rendering regression',
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
               'original_series_unchanged': False, 'model_execution': False,
               'replay_limits': ['original final usage is carried forward, not recomputed before the report',
                                 'tasks use checkpoint status/attempts; task result/review/blocker fields are not fully reconstructed',
                                 'this is not a complete historical runtime reproduction or measured token saving'],
               'business_quality_accepted': False, 'human_acceptance': 'not_performed', 'records': []}
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    write_json(args.root / 'result.json', summary)
    try:
        for rep in (1, 6):
            path, run, events, inventory = sources.record(rep)
            require(run.inputs.workflow == 'document', 'only preserved document records are allowed')
            calls = [e for e in events if e.type == 'model.called' and e.payload.get('mode') == 'report']
            require(len(calls) == 1, 'expected one original post-review report call')
            original = next(a for a in inventory if a['artifact_id'] == 'final-report.md')
            original_bytes = sources.read(path / original['evidence_file'])
            require(sha(original_bytes) == original['sha256'], 'original report bytes changed')
            if rep == 6:
                require(OBSERVED_CLAIM in original_bytes.decode(),
                        'the observed original unsupported claim is absent')
            async with Replay(sources, rep, args.root / f'rep-{rep:02d}', cutoff=calls[0].seq - 1) as replay:
                rt = replay.rt
                before_events = await rt.events.list(rt.run_id)
                before_model = [e.model_dump(mode='json') for e in before_events if e.type.startswith('model.')]
                before_usage = rt.policy.usage.model_dump()
                before = await rt.artifacts.list(rt.run_id)
                manager = RunManager(runs=rt.runs, events=rt.events, artifacts=rt.artifacts,
                                     data_dir=rt.data_dir, config_getter=lambda: rt.config, redactor=rt.redactor)
                report = await manager._make_report(rt, run.status, run.blocked_reason)
                require(report['narrative'] is None and report['narrative_policy'] == 'runtime_evidence_only',
                        'document report must use only recorded evidence')
                require(report['narrative_omission_reason'] == 'document_workflow_has_no_post_review_interpretation',
                        'document report omission reason missing')
                require(report['status'] == run.status and report['reason'] == run.blocked_reason,
                        'the original failed/completed state was changed')
                after_events = await rt.events.list(rt.run_id)
                require([e.model_dump(mode='json') for e in after_events if e.type.startswith('model.')] == before_model
                        and rt.policy.usage.model_dump() == before_usage, 'report generation called a model or changed usage')
                generated = after_events[-1]
                require(generated.type == 'report.generated' and generated.payload['narrative_by'] is None
                        and generated.payload['narrative_policy'] == report['narrative_policy']
                        and generated.payload['narrative_omission_reason'] == report['narrative_omission_reason'],
                        'event must expose the same report policy')
                final = await rt.artifacts.get(rt.run_id, 'final-report.md')
                body = rt.artifacts.read_bytes(final)
                require('No additional model interpretation was generated.' in body.decode()
                        and OBSERVED_CLAIM not in body.decode(),
                        'report added an unsupported interpretation or lost the explanation')
                require(final.agent_id == 'runtime', 'document report author must identify runtime')
                for artifact in before:
                    require(sha(rt.artifacts.read_bytes(artifact)) == artifact.sha256,
                            'requested artifact bytes changed during report generation')
                require([(d['artifact_id'], d['revision'], d['sha256']) for d in report['deliverables']] ==
                        [(a.artifact_id, a.revision, a.sha256) for a in before], 'original deliverables differ')
                write_json(args.root / f'rep-{rep:02d}-report.json', report)
                (args.root / f'rep-{rep:02d}-report.md').write_bytes(body)
                summary['records'].append({'rep': rep, 'run_id': run.run_id, 'original_status': str(run.status),
                                           'event_prefix_through_seq': calls[0].seq - 1,
                                           'original_report_sha256': original['sha256'], 'replay_report_sha256': sha(body),
                                           'additional_model_calls': 0, 'original_deliverables_unchanged': True,
                                           'narrative': None, 'policy': report['narrative_policy']})
        sources.verify_unchanged()
        summary.update(status='PASS', original_series_unchanged=True, source_sha256=sources.hashes,
                       implementation_sha256={name: sha((REPO / name).read_bytes()) for name in
                         ('backend/agentteam/runtime/orchestrator.py', 'backend/scripts/check_document_report.py',
                          'backend/scripts/check_message_handoff.py')})
    except BaseException as error:
        summary.update(status='FAIL', error_type=type(error).__name__)
        raise
    finally:
        write_json(args.root / 'result.json', summary)
    print(json.dumps({'status': summary['status'], 'records': len(summary['records']), 'model_execution': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    args.source, args.root = args.source.resolve(), args.root.resolve()
    require(not args.root.is_relative_to(args.source) and not args.root.is_relative_to(REPO),
            'replay root must remain outside source and repository')
    os.umask(0o077)
    asyncio.run(verify(args))


if __name__ == '__main__':
    main()
