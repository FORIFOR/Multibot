#!/usr/bin/env python3
"""Replay preserved v62 tool arguments through real stores; no provider or service.

This is a transport/state regression, not a rerun or acceptance of the recorded
model's business-quality verdicts. Source records stay read-only. All replay
events live in a new private output directory and are labelled as replays.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.encoders import jsonable_encoder
from jsonschema import Draft202012Validator

from agentteam.api.responses import event_response
from agentteam.config.loader import load_config_text
from agentteam.config.models import EffectiveAgentConfig
from agentteam.contracts import ArtifactManifest, Event, Message, Run, TaskState
from agentteam.providers.registry import ProviderRegistry
from agentteam.projections.views import chat_view, timeline_view
from agentteam.runtime.communication import communication_targets
from agentteam.runtime.context import RunRuntime, SessionContext
from agentteam.runtime.mailbox import MessageBus
from agentteam.runtime.policy import PolicyEngine
from agentteam.runtime.redaction import Redactor
from agentteam.runtime.tools import TOOL_SPECS, ToolGateway
from agentteam.runtime.worker import AgentRunner
from agentteam.store.artifact_store import ArtifactStore
from agentteam.store.db import Database, dumps
from agentteam.store.event_store import EventStore
from agentteam.store.run_store import RunStore


REPO = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = '9eb798849cd8352ec645f6da2ed1e04d9729d63c'
CHECKED_FILES = [
    'backend/agentteam/contracts.py', 'backend/agentteam/store/db.py',
    'backend/agentteam/store/run_store.py', 'backend/agentteam/runtime/mailbox.py',
    'backend/agentteam/runtime/tools.py', 'backend/agentteam/runtime/worker.py',
    'backend/agentteam/runtime/communication.py', 'backend/agentteam/schemas/event.schema.json',
    'backend/scripts/check_message_handoff.py',
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class Sources:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.hashes: dict[str, str] = {}

    def read(self, path: Path) -> bytes:
        path = path.resolve()
        require(path.is_relative_to(self.root), 'source path escapes the preserved series')
        body = path.read_bytes()
        digest = sha(body)
        require(self.hashes.get(str(path), digest) == digest, 'source changed during replay')
        self.hashes[str(path)] = digest
        return body

    def record(self, rep: int):
        paths = sorted((self.root / 'evidence').glob(f'{rep:02d}-run_*'))
        require(len(paths) == 1, f'exactly one preserved rep {rep} is required')
        path = paths[0]
        run = Run.model_validate_json(self.read(path / 'run.json'))
        events = [Event.model_validate_json(line) for line in self.read(path / 'events.jsonl').splitlines()]
        artifacts = json.loads(self.read(path / 'artifacts.json'))
        require(run.provider_kind == 'real', 'only real provider records are allowed')
        require(all(e.run_id == run.run_id and e.seq == i for i, e in enumerate(events, 1)),
                'source events must be contiguous and belong to the recorded run')
        return path, run, events, artifacts

    def verify_unchanged(self):
        for name, digest in self.hashes.items():
            require(sha(Path(name).read_bytes()) == digest, f'source changed: {name}')


def tool(events, name, *, after=0, predicate=lambda e: True):
    return next(e for e in events if e.seq > after and e.type == 'tool.called'
                and e.payload.get('tool') == name and predicate(e))


def old_message(events, event: Event) -> Message:
    """Recover the real ID from its immediately following successful receipt."""
    receipt = events[event.seq]
    require(receipt.type == 'tool.called' and receipt.payload.get('tool') == 'send_message'
            and receipt.payload.get('ok') and receipt.actor_id == event.actor_id,
            f'ambiguous message receipt at {event.event_id}')
    match = re.search(r'DELIVERED message_id=(\S+) to=(\S+) task=(\S+)\.', receipt.payload['result_preview'])
    require(bool(match), 'recorded message ID is missing; do not invent one')
    require(match[2] == event.payload['to_agent_id'] and match[3] == event.task_id, 'receipt mismatch')
    return Message(message_id=match[1], run_id=event.run_id, seq=event.seq,
                   recorded_at=event.recorded_at, **event.payload)


class Replay:
    def __init__(self, sources: Sources, rep: int, root: Path, cutoff: int | None = None):
        self.sources, self.rep, self.root = sources, rep, root
        self.path, self.run, self.original, self.artifact_records = sources.record(rep)
        self.review_call = tool(self.original, 'submit_review', predicate=lambda e: e.payload.get('ok'))
        review_event = self.original[self.review_call.seq - 2]
        require(review_event.type == 'review.submitted', 'formal review must precede its tool receipt')
        self.cutoff = cutoff if cutoff is not None else review_event.seq - 1
        self.task_id = self.review_call.task_id
        self.owner = self.run.plan.tasks[0].owner
        self.send_call = tool(self.original, 'send_message', after=self.review_call.seq,
                              predicate=lambda e: e.payload.get('ok') and e.payload['args']['to'] == self.owner)
        self.finish_call = tool(self.original, 'finish_task', after=self.send_call.seq)
        if rep in (1, 3, 4):
            require(self.finish_call.payload['ok'] and 'task_id' not in self.send_call.payload['args'],
                    'expected the preserved omitted-task successful case')
        else:
            require(self.send_call.payload['args']['task_id'] != self.task_id
                    and 'Missing recipients: builder' in self.finish_call.payload['result_preview'],
                    'expected the preserved related-task handoff failure')
        self.calls = []

    async def __aenter__(self):
        self.root.mkdir()
        self.db = await Database(self.root / 'state.sqlite3').connect()
        self.runs = RunStore(self.db)
        await self.runs.create_run(self.run)
        prefix = [e for e in self.original if e.seq <= self.cutoff]
        for e in prefix:
            await self.db.execute(
                'INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)',
                (e.run_id, e.seq, e.event_id, e.recorded_at, e.actor_id, e.actor_kind,
                 e.task_id, e.causation_id, e.type, dumps(e.payload)))
            if e.type == 'message.sent':
                await self.runs.insert_message(old_message(self.original, e))
        for item in self.artifact_records:
            meta = ArtifactManifest.model_validate(item)
            if int(meta.event_id.rsplit(':', 1)[1]) > self.cutoff:
                continue
            data = self.sources.read(self.path / item['evidence_file'])
            require(sha(data) == meta.sha256 and len(data) == meta.size, 'artifact bytes differ from manifest')
            output = self.root / meta.storage_path
            require(output.resolve().is_relative_to(self.root.resolve()), 'artifact path escapes replay root')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            await self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (meta.run_id, meta.artifact_id, meta.revision, meta.sha256, meta.media_type,
                                  meta.size, meta.logical_path, meta.storage_path, meta.task_id,
                                  meta.agent_id, meta.created_at, meta.event_id, dumps(meta.sources)))
        # Reconstruct task status/attempt from the actual checkpoint and starts.
        checkpoint = [e for e in prefix if e.type == 'checkpoint.saved'][-1]
        tasks = {}
        for spec in self.run.plan.tasks:
            state = dict(checkpoint.payload['tasks'][spec.id])
            updated_at = checkpoint.recorded_at
            for e in prefix:
                if e.seq > checkpoint.seq and e.task_id == spec.id and e.type == 'task.started':
                    state.update(status='running', attempt=e.payload['attempt'])
                    updated_at = e.recorded_at
            task = TaskState(run_id=self.run.run_id, spec=spec, updated_at=updated_at, **state)
            tasks[spec.id] = task
            await self.runs.upsert_task(task)
        cfg = load_config_text(self.run.config_snapshot['config_yaml'])
        agents = {key: EffectiveAgentConfig.model_validate(value)
                  for key, value in self.run.config_snapshot['agents'].items()}
        policy = PolicyEngine(cfg.limits, usage=self.run.usage.model_copy(deep=True))
        policy.peer_messages = {key: await self.runs.count_messages_for_task(self.run.run_id, key) for key in tasks}
        redactor = Redactor()
        events = EventStore(self.db, redactor)
        self.rt = RunRuntime(self.run, cfg, agents, policy, events, ArtifactStore(self.db, self.root), self.runs,
                             MessageBus(self.run.run_id, self.runs, events), ProviderRegistry(cfg), redactor,
                             self.root, tasks=tasks)
        self.ctx = SessionContext(self.rt, agents[tasks[self.task_id].spec.owner], 'task',
                                  task=tasks[self.task_id], attempt=tasks[self.task_id].attempt,
                                  tools=agents[tasks[self.task_id].spec.owner].tools)
        self.gateway = ToolGateway(self.ctx)
        self.initial_model_calls = policy.usage.model_calls
        require(self.run.config_snapshot.get('communication_budget_version') is None,
                'v62 document records must preserve their original communication budget mode')
        return self

    async def call(self, source: Event):
        result = await self.gateway.call(source.payload['tool'], source.payload['args'])
        self.calls.append({'source_event_id': source.event_id, 'tool': source.payload['tool'], 'result': result})
        return result

    async def review(self):
        require((await self.call(self.review_call)).startswith('OK: review recorded'), 'saved formal review rejected')

    async def send(self):
        before = dict(self.rt.policy.peer_messages)
        result = await self.call(self.send_call)
        require(result.startswith('DELIVERED'), result)
        messages = await self.runs.list_messages(self.run.run_id)
        delivery = messages[-1]
        related = self.send_call.payload['args'].get('task_id') or self.task_id
        require(delivery.source_task_id == self.task_id and delivery.task_id == related, 'source/related task mismatch')
        expected = {**before, related: before[related] + 1}
        require(self.rt.policy.peer_messages == expected, 'delivery must charge exactly one related-task budget')
        require(await self.runs.count_messages_for_task(self.run.run_id, related) == expected[related], 'DB budget mismatch')
        require(self.owner in self.ctx.communicated_to, 'successful source task handoff not counted')
        ev = next(e for e in await self.rt.events.list(self.run.run_id, self.cutoff) if e.seq == delivery.seq)
        schema = json.loads((REPO / 'backend/agentteam/schemas/event.schema.json').read_text())
        Draft202012Validator(schema).validate(ev.model_dump(mode='json'))
        original = next(e for e in self.original if e.type == 'message.sent')
        Draft202012Validator(schema).validate(original.model_dump(mode='json'))
        public = event_response(jsonable_encoder(ev), administrator=False)
        require(public['task_id'] == related and public['payload']['source_task_id'] == self.task_id,
                'HTTP event projection lost additive task provenance')
        without_source = ev.model_copy(deep=True)
        without_source.payload.pop('source_task_id')
        require(chat_view([ev]) == chat_view([without_source])
                and timeline_view([ev]) == timeline_view([without_source]),
                'additive provenance changed existing chat/timeline response fields')
        wire = jsonable_encoder(delivery)
        require(Message.model_validate_json(json.dumps(wire)) == delivery, 'Message JSON roundtrip failed')
        legacy = dict(wire)
        legacy.pop('source_task_id')
        require(Message.model_validate(legacy).source_task_id is None, 'legacy JSON must not infer provenance')
        return delivery

    async def finished(self):
        require((await self.call(self.finish_call)) == 'OK: task finished', 'handoff still blocks valid completion')

    async def __aexit__(self, kind, value, tb):
        try:
            new_events = await self.rt.events.list(self.run.run_id, self.cutoff)
            require(not any(e.type.startswith('model.') for e in new_events), 'a new model event was created')
            require(not self.rt.providers._adapters, 'a provider was instantiated')
            require(self.rt.policy.usage.model_calls == self.initial_model_calls, 'model accounting changed')
            (self.root / 'replay-events.jsonl').write_text(''.join(e.model_dump_json() + '\n' for e in new_events))
            write_json(self.root / 'replay.json', {
                'kind': 'recorded-tool-argument-replay', 'source_run_id': self.run.run_id,
                'source_prefix_through_seq': self.cutoff, 'calls': self.calls,
                'original_run_status': self.run.status,
                'original_finish_result': self.finish_call.payload['result_preview'],
                'peer_messages': self.rt.policy.peer_messages, 'new_model_calls': 0,
                'business_quality_accepted': False, 'business_quality_review': 'not_performed',
                'passed': kind is None,
            })
        finally:
            await self.rt.providers.aclose()
            await self.db.close()


async def migration(sources: Sources, root: Path):
    # Read the exact frozen schema, not an invented approximation of an old DB.
    body = subprocess.check_output(['git', 'show', f'{SOURCE_COMMIT}:backend/agentteam/store/db.py'], cwd=REPO)
    tree = ast.parse(body)
    schema = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SCHEMA' for t in n.targets))
    require('source_task_id' not in schema, 'source schema is not the legacy schema')
    _, run, events, _ = sources.record(1)
    sent = next(e for e in events if e.type == 'message.sent')
    message = old_message(events, sent)
    path = root / 'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(schema)
        db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (message.message_id, message.run_id, message.seq, message.from_agent_id, message.to_agent_id,
                    message.task_id, message.purpose, message.text, dumps([r.model_dump() for r in message.artifact_refs]),
                    message.reply_to, message.recorded_at, message.read_at))
    db = await Database(path).connect()
    try:
        restored = await RunStore(db).list_messages(run.run_id)
        require(restored == [message] and restored[0].source_task_id is None, 'legacy message migration lost data')
    finally:
        await db.close()
    return {'schema_commit': SOURCE_COMMIT, 'schema_file_sha256': sha(body), 'source_message_event': sent.event_id}


async def main(args):
    sources = Sources(args.source_series)
    fingerprint = json.loads(sources.read(sources.root / 'fingerprint.json'))
    require(fingerprint['commit'] == SOURCE_COMMIT, 'unexpected preserved source code')
    root = args.root.resolve()
    require(not root.exists(), 'output must be a new directory; existing evidence is never overwritten')
    require(not root.is_relative_to(sources.root) and not root.is_relative_to(REPO), 'output must be outside source and repo')
    os.umask(0o077)
    root.mkdir(parents=True)
    report = {'business_quality_accepted': False, 'business_quality_review': 'not_performed', 'checks': []}
    try:
        report['legacy_migration'] = await migration(sources, root)
        report['checks'].append('legacy SQLite migration and absent source_task_id -> None')
        for rep in (1, 2, 3, 4, 5, 6, 7):
            async with Replay(sources, rep, root / f'rep-{rep:02d}') as replay:
                await replay.review()
                message = await replay.send()
                await replay.finished()
                # Context compaction uses durable source provenance without invoking the model.
                runner = AgentRunner(replay.ctx)
                await runner._compact_delivery_repair()
                require(message.message_id in runner.messages[-1]['content'][0]['text'],
                        'compaction lost related-task delivery')
            db = await Database(root / f'rep-{rep:02d}' / 'state.sqlite3').connect()
            try:
                messages = await RunStore(db).list_messages(replay.run.run_id)
                require(messages[-1] == message, 'delivery provenance did not survive DB reopen')
            finally:
                await db.close()
            report['checks'].append(f'rep{rep}: original review/send/finish; provenance, budget, JSON, reopen, compaction')
        async with Replay(sources, 6, root / 'review-reset') as replay:
            await replay.send()
            require('call submit_review' in await replay.call(replay.finish_call), 'handoff replaced formal review')
            await replay.review()
            require(replay.owner not in replay.ctx.communicated_to, 'formal review did not reset earlier handoff')
            require('Missing recipients: builder' in await replay.call(replay.finish_call), 'pre-review handoff remained valid')
            await replay.send()
            await replay.finished()
        report['checks'].append('pre-review delivery cannot replace review; review resets handoff; fresh delivery finishes')
        async with Replay(sources, 6, root / 'other-recipient') as replay:
            await replay.review()
            master = tool(replay.original, 'send_message', after=replay.review_call.seq,
                          predicate=lambda e: e.payload.get('ok') and e.payload['args']['to'] == 'master')
            require((await replay.call(master)).startswith('DELIVERED'), 'saved master delivery rejected')
            require(set(communication_targets(replay.ctx)) - replay.ctx.communicated_to == {replay.owner},
                    'unrelated recipient satisfied owner handoff')
            require('Missing recipients: builder' in await replay.call(replay.finish_call), 'owner guard disappeared')
            await replay.send()
            await replay.finished()
        report['checks'].append('delivery to master leaves required builder handoff missing')
        _, _, events, _ = sources.record(2)
        denied = tool(events, 'send_message', predicate=lambda e: 'DENIED (max_peer_messages)' in e.payload.get('result_preview', ''))
        async with Replay(sources, 2, root / 'budget-denial', denied.seq - 1) as replay:
            await replay.review()
            before = dict(replay.rt.policy.peer_messages)
            require(before['t1'] == replay.rt.config.limits.max_peer_messages_per_task, 'source is not at recorded budget limit')
            require((await replay.call(denied)).startswith('DENIED (max_peer_messages)'), 'existing budget limit was widened')
            require(not replay.ctx.communicated_to and before == replay.rt.policy.peer_messages, 'denial counted as handoff or changed budget')
            require(not any(e.type == 'message.sent' for e in await replay.rt.events.list(replay.run.run_id, replay.cutoff)),
                    'budget denial persisted a delivery')
        report['checks'].append('recorded exhausted related-task budget remains denied without handoff or delivery')
        async with Replay(sources, 2, root / 'invalid-recipient') as replay:
            unknown = tool(replay.original, 'send_message', after=replay.review_call.seq,
                           predicate=lambda e: 'unknown or disabled agent' in e.payload.get('result_preview', ''))
            before = dict(replay.rt.policy.peer_messages)
            require((await replay.call(unknown)).startswith('REJECTED: unknown'), 'unknown recipient accepted')
            require(not replay.ctx.communicated_to and before == replay.rt.policy.peer_messages, 'rejected recipient counted')
            spec = TOOL_SPECS['send_message'].input_schema
            require('source_task_id' not in spec['properties'] and spec['additionalProperties'] is False,
                    'source task can be model-supplied')
            result = await replay.gateway.call('send_message', {
                **replay.send_call.payload['args'], 'source_task_id': replay.task_id})
            require(result.startswith('REJECTED: invalid tool arguments') and not replay.ctx.communicated_to
                    and before == replay.rt.policy.peer_messages, 'model-supplied provenance was accepted')
        report['checks'].append('recorded unknown recipient rejected; model schema excludes source_task_id')
        sources.verify_unchanged()
        report.update(passed=True, new_model_calls=0, services_started=0)
    except Exception as exc:
        report.update(passed=False, error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['source_sha256'] = sources.hashes
        report['code_sha256'] = {name: sha((REPO / name).read_bytes()) for name in CHECKED_FILES}
        report['code_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
        write_json(root / 'result.json', report)
        print(json.dumps({'passed': report.get('passed'), 'checks': len(report['checks']), 'evidence': str(root / 'result.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-series', type=Path, required=True, help='preserved real v62 series directory')
    parser.add_argument('--root', type=Path, required=True, help='new private output directory outside the repo/source')
    asyncio.run(main(parser.parse_args()))
