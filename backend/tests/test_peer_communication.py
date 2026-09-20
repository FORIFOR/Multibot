"""Communication boundary with actual recorded work and real SQLite; no model mocks."""
import json
from pathlib import Path
from agentteam.api.service import AppService
from agentteam.contracts import Run, TaskState
from agentteam.runtime.context import SessionContext
from agentteam.runtime.tools import ToolGateway
from agentteam.runtime.worker import build_task_message, auto_finish_if_outputs_published
from agentteam.runtime.communication import communication_targets

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'docs/evidence/real-readiness-v2-2026-09-14/runs/01-run_1a09c8485503d406bf4'

def test_recorded_five_person_plan_requires_revision_communication_budget():
    from agentteam.contracts import TeamPlan
    from agentteam.runtime.communication import communication_budget_errors, task_communication_targets
    record = json.loads((ROOT / 'docs/evidence/adaptive-team-2026-09-20/communication-budget.json').read_text())
    plan = TeamPlan.model_validate(record['plan'])
    roles = record['roles']
    tasks = {t.id: t for t in plan.tasks}
    assert task_communication_targets(tasks['t1'], tasks, roles, set(roles)) == ['team_2', 'team_3', 'team_4']
    errors = communication_budget_errors(plan, roles, set(roles), 6, 2)
    assert len(errors) == 3  # t1, t2, t4 cannot reserve their configured revisions.
    assert any('task t1:' in e and '10 reserved messages' in e for e in errors)
    assert any('task t4:' in e and '22 reserved messages' in e for e in errors)
    # Explicit capacity boundaries on the recorded plan, not a fabricated DAG.
    assert communication_budget_errors(plan, roles, set(roles), 22, 2) == []
    assert len(communication_budget_errors(plan, roles, set(roles), 21, 2)) == 1
    assert communication_budget_errors(plan, roles, set(roles), 6, 0) == []

async def test_adaptive_future_review_handoffs_remain_reserved(tmp_path):
    from agentteam.contracts import Review
    from agentteam.runtime.communication import future_handoff_reserve
    data = json.loads((ROOT/'docs/evidence/adaptive-team-2026-09-20/communication-runtime.json').read_text())
    record = data['run']
    svc = await AppService(tmp_path, config_yaml=record['config_snapshot']['config_yaml']).start()
    try:
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            task = TaskState.model_validate(item)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        # Explicit budget boundary on a real plan; not changing the live run.
        rt.run.config_snapshot['communication_budget_version'] = 1
        rt.config.limits.max_peer_messages_per_task = 22
        rt.policy.limits.max_peer_messages_per_task = 22
        reviewer = rt.tasks['t4']
        reviewer.status = 'running'
        ctx = SessionContext(rt, rt.agents[reviewer.spec.owner], 'task', reviewer)
        gateway = ToolGateway(ctx)
        assert future_handoff_reserve(rt, reviewer) == 18
        by_seq = {e['seq']: e for e in data['events']}
        def args(seq):
            payload = by_seq[seq]['payload']
            return {'to': payload['to_agent_id'], 'task_id': payload['task_id'],
                    'purpose': payload['purpose'], 'text': payload['text']}
        coord = ToolGateway(SessionContext(rt, rt.agents['master'], 'coordination', tools=['send_message']))
        from jsonschema import Draft202012Validator
        schema = next(s.input_schema for s in coord.specs() if s.name == 'send_message')
        validator = Draft202012Validator(schema)
        assert not list(validator.iter_errors(args(24)))
        # Reproduce the observed coordinator omission before it reaches delivery.
        omitted = {key: value for key, value in args(24).items() if key != 'task_id'}
        assert any(e.validator == 'required' and 'task_id' in e.message for e in validator.iter_errors(omitted))
        assert (await coord.t_send_message(args(24), None)).startswith('DELIVERED')
        assert (await gateway.t_send_message(args(136), None)).startswith('REJECTED:')
        assert rt.policy.peer_messages['t4'] == 1
        # Hydrate actual recorded formal reviews; no fabricated verdicts.
        ctx.reviews = [Review.model_validate(by_seq[s]['payload']) for s in (142, 144, 146)]
        for seq in (149, 151, 153):
            assert (await gateway.t_send_message(args(seq), None)).startswith('DELIVERED')
        assert rt.policy.peer_messages['t4'] == 4
        assert (await gateway.t_send_message(args(136), None)).startswith('REJECTED:')
        reply = ToolGateway(SessionContext(rt, rt.agents['team_1'], 'reply', tools=['send_message']))
        # Cross-session charging cannot spend the future reservation either.
        assert (await reply.t_send_message(args(151), None)).startswith('REJECTED:')
        assert await svc.runs.count_messages_for_task(run.run_id, 't4') == 4
        for tid in ('t1', 't2', 't3'):
            rt.policy.revision_rounds[tid] = 2
        assert future_handoff_reserve(rt, reviewer) == 0
        # Explicit Q&A boundary mutations of recorded prose. Admission must
        # reserve the response and prevent optional messages stealing its slot.
        rt.policy.revision_rounds.clear()
        producer = rt.tasks['t1']
        producer_ctx = SessionContext(rt, rt.agents[producer.spec.owner], 'task', producer)
        producer_gateway = ToolGateway(producer_ctx)
        rt.config.limits.max_peer_messages_per_task = 11
        rt.policy.limits.max_peer_messages_per_task = 11
        question = {'to':'team_2', 'task_id':'t1', 'purpose':'question', 'text':producer.result.summary}
        import asyncio
        simultaneous = await asyncio.gather(*(producer_gateway.t_send_message(question, None) for _ in range(2)))
        assert sum(result.startswith('DELIVERED') for result in simultaneous) == 1
        assert sum(result.startswith('REJECTED:') for result in simultaneous) == 1
        messages = await svc.runs.list_messages(run.run_id, task_ids=['t1'])
        actual_question = messages[-1]
        assert len(messages) == 1
        assert (await producer_gateway.t_send_message(question, None)).startswith('REJECTED:')
        # Rehydrate the runtime from persisted messages with the answer pending.
        await svc.runs.update_run(run.run_id, config_snapshot=rt.run.config_snapshot)
        restored = svc.manager._build_runtime(await svc.runs.get_run(run.run_id), rt.config)
        await svc.manager._prepare_resume(restored)
        assert restored.policy.peer_messages['t1'] == 1
        rt = restored
        producer_ctx = SessionContext(rt, rt.agents['team_1'], 'task', rt.tasks['t1'])
        producer_gateway = ToolGateway(producer_ctx)
        assert (await producer_gateway.t_send_message(question, None)).startswith('REJECTED:')
        answering = ToolGateway(SessionContext(rt, rt.agents['team_2'], 'reply', tools=['send_message']))
        answer = {'to':'team_1', 'task_id':'t1', 'purpose':'answer',
                  'reply_to':actual_question.message_id, 'text':rt.tasks['t2'].result.summary}
        assert (await answering.t_send_message(answer, None)).startswith('DELIVERED')
        assert rt.policy.peer_messages['t1'] == 2
        assert (await producer_gateway.t_send_message(question, None)).startswith('REJECTED:')
    finally:
        await svc.stop()

async def test_saved_failed_review_reaches_resumed_producer(tmp_path):
    """Replay a real failed review across an actual SQLite service restart."""
    source = ROOT / 'docs/evidence/real-readiness-v2-2026-09-14/runs/02-run_1a09c924769e22ff807'
    record = json.loads((source / 'run.json').read_text())
    run = Run.model_validate(record)
    producer = next(TaskState.model_validate(t) for t in record['tasks']
                    if t.get('review') and any(r['status'] == 'fail' for r in t['review']['results']))
    original = producer.review.model_dump()
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        await svc.runs.create_run(run)
        for item in record['tasks']:
            await svc.runs.upsert_task(TaskState.model_validate(item))
    finally:
        await svc.stop()
    svc = await AppService(tmp_path).start()
    try:
        saved = await svc.runs.get_run(run.run_id)
        rt = svc.manager._build_runtime(saved, svc.config)
        await svc.manager._prepare_resume(rt)
        calls_before = rt.policy.usage.model_calls
        task = rt.tasks[producer.spec.id]
        assert task.review.model_dump() == original
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task)
        # No in-memory scheduler feedback or unread inbox is needed.
        for _ in range(2):
            message = await build_task_message(ctx, task)
            assert 'Review feedback on your previous revision' in message
            for result in task.review.results:
                if result.status != 'pass':
                    assert (result.note or result.evidence) in message
            for ref in task.review.target_artifacts:
                assert f'{ref.artifact_id}@r{ref.revision} sha256={ref.sha256}' in message
        assert task.review.model_dump() == original
        assert rt.policy.usage.model_calls == calls_before
    finally:
        await svc.stop()

async def test_reply_delivery_budget_survives_real_store_resume(tmp_path):
    """Recorded prose, with reply mode/purpose as explicit boundary mutations."""
    from agentteam.runtime.policy import PolicyViolation
    import pytest
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        record = json.loads((SOURCE/'run.json').read_text())
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            task = TaskState.model_validate(item)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        producer, reviewer = rt.tasks['t1'], rt.tasks['t2']
        ctx = SessionContext(rt, rt.agents[producer.spec.owner], 'reply', tools=['send_message'])
        args = {'to': reviewer.spec.owner, 'task_id': producer.spec.id, 'purpose': 'answer',
                'text': producer.result.summary}
        gateway = ToolGateway(ctx)
        assert (await gateway.t_send_message(args, None)).startswith('DELIVERED')
        assert rt.policy.peer_messages[producer.spec.id] == 1
        restored = svc.manager._build_runtime(await svc.runs.get_run(run.run_id), svc.config)
        await svc.manager._prepare_resume(restored)
        assert restored.policy.peer_messages[producer.spec.id] == 1
        assert await svc.runs.count_messages_for_task(run.run_id, producer.spec.id) == 1
        # Explicit limit boundary; no extra invented conversations are sent.
        rt.policy.limits.max_peer_messages_per_task = 1
        with pytest.raises(PolicyViolation):
            await gateway.t_send_message(args, None)
        assert await svc.runs.count_messages_for_task(run.run_id, producer.spec.id) == 1
    finally:
        await svc.stop()

async def test_real_handoff_required_and_cross_task_inbox(tmp_path):
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        record = json.loads((SOURCE/'run.json').read_text())
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            task = TaskState.model_validate(item)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        builder, reviewer = rt.tasks['t1'], rt.tasks['t2']
        ctx = SessionContext(rt, rt.agents[builder.spec.owner], 'task', builder)
        gateway = ToolGateway(ctx)
        artifact = json.loads((SOURCE/'artifacts.json').read_text())[-1]
        published = await svc.artifacts.publish(run.run_id, artifact['logical_path'], (SOURCE/artifact['evidence_file']).read_bytes(), agent_id=builder.spec.owner, task_id=builder.spec.id)
        lookup_ctx = SessionContext(rt, rt.agents[builder.spec.owner], 'task', builder,
                                    tools=['read_input_file', 'read_artifact'])
        lookup = ToolGateway(lookup_ctx)
        before_lookup = await rt.events.list(run.run_id)
        for name in {published.artifact_id, published.logical_path}:
            hint = await lookup.call('read_input_file', {'name': name})
            assert hint.startswith('NOT FOUND:') and 'generated artifact' in hint
            assert f"artifact_id={published.artifact_id!r}, revision={published.revision}" in hint
        hint = await lookup.call('read_artifact', {'artifact_id': Path(published.artifact_id).stem,
                                                  'revision': published.revision})
        assert hint.startswith('NOT FOUND:')
        assert f"{published.artifact_id!r}, revision={published.revision}" in hint
        # A correction hint neither reads the body nor invents source-read evidence.
        assert not any(e.type in ('input.read', 'artifact.read') for e in
                       (await rt.events.list(run.run_id))[len(before_lookup):])
        content = await lookup.call('read_artifact', {'artifact_id': published.artifact_id,
                                                     'revision': published.revision})
        assert published.sha256 in content
        reads = [e for e in (await rt.events.list(run.run_id))[len(before_lookup):] if e.type == 'artifact.read']
        assert len(reads) == 1 and reads[0].payload['sha256'] == published.sha256
        lookup_ctx.tools = ['read_input_file']
        assert 'read_artifact' not in await lookup.call('read_input_file', {'name': published.artifact_id})
        # Actual reviewer confusion: a producer's saved file is not in the
        # reviewer's workspace. A hint must not silently perform that read.
        lookup_ctx.tools = ['workspace_read', 'read_artifact']
        count_before = len(await rt.events.list(run.run_id, types=['artifact.read']))
        hint = await lookup.call('workspace_read', {'path': published.logical_path})
        assert 'NOT FOUND in your task workspace' in hint
        assert f"artifact_id={published.artifact_id!r}, revision={published.revision}" in hint
        assert len(await rt.events.list(run.run_id, types=['artifact.read'])) == count_before
        lookup_ctx.tools = ['workspace_read']
        assert 'read_artifact' not in await lookup.call('workspace_read', {'path': published.logical_path})
        # An actual local file still takes precedence over a published version.
        local = lookup_ctx.workspace / published.logical_path
        local.parent.mkdir(parents=True, exist_ok=True)
        raw = (SOURCE/artifact['evidence_file']).read_bytes()
        local.write_bytes(raw)
        assert await lookup.call('workspace_read', {'path': published.logical_path}) == raw.decode()
        local.unlink()
        assert communication_targets(ctx) == [reviewer.spec.owner]
        assert await auto_finish_if_outputs_published(ctx, 'recorded completion') is None
        result = await gateway.t_finish_task({'summary':builder.result.summary},None)
        assert 'Missing recipients: reviewer' in result
        assert ctx.finished is None
        # Deliver the actual recorded result summary, not invented conversation.
        messages_before = await svc.runs.list_messages(run.run_id)
        rejected = await gateway.t_send_message({'to':reviewer.spec.owner,'task_id':builder.spec.id,
            'purpose':'handoff','text':builder.result.summary,
            'artifact_refs':[{'artifact_id':Path(published.artifact_id).stem,'revision':published.revision}]},None)
        assert rejected.startswith('REJECTED:') and repr(published.artifact_id) in rejected
        assert await svc.runs.list_messages(run.run_id) == messages_before
        # Replay the dependency boundary: the reviewer is queued until the producer finishes.
        reviewer.status = 'queued'
        assert 'already delivered' not in gateway._pending_review_notice()
        sent = await gateway.t_send_message({'to':reviewer.spec.owner,'task_id':builder.spec.id,'purpose':'handoff','text':builder.result.summary,'artifact_refs':[published.ref().model_dump()]},None)
        assert sent.startswith('DELIVERED')
        assert 'Required handoffs are already delivered' in sent
        assert 'Do not resend the same findings under a different purpose' in sent
        assert 'call finish_task' in sent
        assert ctx.finished is None  # Delivery alone never finishes a task.
        recovered_prompt = await build_task_message(ctx, builder)
        assert 'Required handoffs are already delivered for the current work' in recovered_prompt
        assert 'Before finish_task, use send_message to each of:' not in recovered_prompt
        review_ctx = SessionContext(rt, rt.agents[reviewer.spec.owner], 'task', reviewer)
        inbox = await build_task_message(review_ctx, reviewer)
        assert '## Inbox' in inbox and builder.result.summary in inbox
        messages = await svc.runs.list_messages(run.run_id,to_agent_id=reviewer.spec.owner)
        assert len(messages) == 1 and messages[0].read_at is not None
        assert 'Missing recipients' not in await gateway.t_finish_task({'summary':builder.result.summary},None)
        assert ctx.finished is not None
        # A new session must communicate its own work; the previous handoff is insufficient.
        retry = SessionContext(rt,rt.agents[builder.spec.owner],'task',builder,attempt=2)
        assert 'Missing recipients' in await ToolGateway(retry).t_finish_task({'summary':builder.result.summary},None)
        assert communication_targets(review_ctx) == [builder.spec.owner]
        # A real configuration edit removing permission must block before a model call.
        from agentteam.runtime.scheduler import Scheduler
        rt.agents[builder.spec.owner].tools = [tool for tool in rt.agents[builder.spec.owner].tools if tool != 'send_message']
        model_calls_before = rt.policy.usage.model_calls
        scheduler = Scheduler(rt)
        task_id, denied_ctx, outcome = await scheduler._run_task(builder)
        assert outcome.kind == 'blocked' and outcome.detail.startswith('communication_configuration:')
        await scheduler._handle(task_id, denied_ctx, outcome)
        assert builder.status == 'blocked' and scheduler._fatal == outcome.detail
        assert rt.policy.usage.model_calls == model_calls_before
    finally:
        await svc.stop()

async def test_recorded_reviewer_does_not_wait_for_review_pending_producer(tmp_path):
    """The actual recorded producer cannot run again until its reviewer finishes."""
    import asyncio
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        record = json.loads((SOURCE/'run.json').read_text())
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            task = TaskState.model_validate(item)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        assert rt.tasks['t1'].status == 'review_pending'
        reviewer = rt.tasks['t2']
        gateway = ToolGateway(SessionContext(rt, rt.agents[reviewer.spec.owner], 'task', reviewer))
        result = await asyncio.wait_for(gateway.t_read_messages({'wait_seconds':30},None),timeout=2)
        assert 'cannot revise yet' in result and 'submit_review' in result and 'finish_task' in result
        assert '(waited' not in result
    finally:
        await svc.stop()

async def test_recorded_handoff_and_submitted_review_do_not_wait(tmp_path):
    """Replay real lifecycle boundaries from the committed v1 execution."""
    import asyncio
    from agentteam.contracts import Review
    source = ROOT / 'docs/evidence/real-readiness-v1-2026-09-14'
    record = json.loads((source / 'run.json').read_text())
    events = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    started = next(e for e in events if e['type'] == 'task.started')
    pending = next(e for e in events if e['type'] == 'task.review_pending')
    submitted = next(e for e in events if e['type'] == 'review.submitted')
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        # At the first task.started event, its dependent reviewer has not started.
        for item in record['tasks']:
            task = TaskState.model_validate(item)
            task.status = 'running' if task.spec.id == started['task_id'] else 'queued'
            rt.tasks[task.spec.id] = task
        producer = rt.tasks[started['task_id']]
        gateway = ToolGateway(SessionContext(rt, rt.agents[producer.spec.owner], 'task', producer))
        reply = await asyncio.wait_for(gateway.t_read_messages({'wait_seconds':30},None),timeout=2)
        assert 'cannot start until this task finishes' in reply
        assert '(waited' not in reply
        assert 'already delivered' not in reply
        # Replay the actual review-pending transition and recorded submission.
        rt.tasks[pending['task_id']].status = 'review_pending'
        reviewer = rt.tasks[submitted['task_id']]
        reviewer.status = 'running'
        ctx = SessionContext(rt, rt.agents[reviewer.spec.owner], 'task', reviewer)
        ctx.reviews = [Review.model_validate(submitted['payload'])]
        reply = await asyncio.wait_for(ToolGateway(ctx).t_read_messages({'wait_seconds':30},None),timeout=2)
        assert 'already submitted' in reply and 'Do not submit it again' in reply
        assert 'finish_task' in reply and '(waited' not in reply
    finally:
        await svc.stop()

async def test_coordinator_requires_real_deliveries_and_preserves_them_on_restart(tmp_path):
    from agentteam.runtime.communication import coordinate_team, delivered_coordination, complete_delivered_coordination
    record = json.loads((SOURCE / 'run.json').read_text())
    svc = await AppService(tmp_path, config_yaml=(ROOT / 'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    run = Run.model_validate(record)
    try:
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            t = TaskState.model_validate(item)
            rt.tasks[t.spec.id] = t
            await svc.runs.upsert_task(t)
        calls_before = rt.policy.usage.model_calls
        master = rt.agents['master']
        ctx = SessionContext(rt, master, 'coordination', tools=['send_message','finish_task'])
        gateway = ToolGateway(ctx)
        assert not await complete_delivered_coordination(ctx)
        assert (await gateway.call('finish_task', {'summary':run.goal})).startswith('REJECTED')
        first = next(iter(rt.tasks.values()))
        other_owner = next(t.spec.owner for t in rt.tasks.values() if t.spec.owner != first.spec.owner)
        denied = await gateway.call('send_message', {'to':other_owner,'task_id':first.spec.id,'purpose':'handoff','text':first.spec.objective})
        assert denied.startswith('REJECTED')
        # Configuration lacking permission must fail before a model is contacted.
        original_tools = master.tools
        master.tools = [t for t in original_tools if t != 'send_message']
        assert (await coordinate_team(rt)).kind == 'blocked'
        assert rt.policy.usage.model_calls == calls_before
        master.tools = original_tools
        for t in rt.tasks.values():
            if t.spec.owner in await delivered_coordination(ctx):
                continue
            args = {'to':t.spec.owner,'task_id':t.spec.id,'purpose':'handoff','text':t.spec.objective}
            assert (await gateway.call('send_message', args)).startswith('DELIVERED')
            assert (await gateway.call('send_message', args)).startswith('ALREADY DELIVERED')
        before = await svc.runs.list_messages(run.run_id)
        assert len(before) == len({t.spec.owner for t in rt.tasks.values()})
        assert await complete_delivered_coordination(ctx)
        assert rt.policy.usage.model_calls == calls_before
        # Delivery completion cannot leak into production task acceptance.
        production = SessionContext(rt, rt.agents[first.spec.owner], 'task', task=first)
        assert not await complete_delivered_coordination(production)
        assert production.finished is None
        claimed = json.loads((ROOT / 'docs/evidence/adaptive-team-2026-09-20/coordination-finish.json').read_text())
        task_states = {key: task.model_dump() for key, task in rt.tasks.items()}
        assert (await gateway.call('finish_task', claimed['payload']['args'])) == 'OK'
        assert ctx.finished is not None
        assert ctx.finished.summary == 'Coordinator handoffs verified in persisted delivery records'
        assert not ctx.finished.verified
        assert {key: task.model_dump() for key, task in rt.tasks.items()} == task_states
    finally:
        await svc.stop()
    svc = await AppService(tmp_path).start()
    try:
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['tasks']:
            t = TaskState.model_validate(item)
            rt.tasks[t.spec.id] = t
        assert (await coordinate_team(rt)).kind == 'finished'
        assert rt.policy.usage.model_calls == calls_before
        after = await svc.runs.list_messages(run.run_id)
        assert [m.message_id for m in after] == [m.message_id for m in before]
        assert all(m.from_agent_id == 'master' for m in after)
    finally:
        await svc.stop()

async def test_real_reviewer_reserves_final_message_for_formal_review_handoff(tmp_path):
    source = ROOT / 'docs/evidence/adaptive-team-2026-09-20'
    record = json.loads((source / 'peer-reservation.json').read_text())
    run = Run.model_validate(record['run'])
    svc = await AppService(tmp_path, config_yaml=run.config_snapshot['config_yaml']).start()
    try:
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        rt.tasks = {t['spec']['id']: TaskState.model_validate(t) for t in record['run']['tasks']}
        task = rt.tasks['t3']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task)
        gateway = ToolGateway(ctx)
        # Restore five real delivered messages, including the incoming handoff.
        for event in record['messages_before_last_slot']:
            p = event['payload']
            await rt.bus.send(from_agent_id=p['from_agent_id'], to_agent_id=p['to_agent_id'],
                              task_id=p['task_id'], purpose=p['purpose'], text=p['text'], artifact_refs=[])
        rt.policy.peer_messages['t3'] = await svc.runs.count_messages_for_task(run.run_id, 't3')
        assert rt.policy.peer_messages['t3'] == rt.config.limits.max_peer_messages_per_task - 1
        p = record['optional_message']['payload']
        args = {'to':p['to_agent_id'], 'purpose':p['purpose'], 'text':p['text'], 'task_id':'t3'}
        before = await svc.runs.list_messages(run.run_id)
        reply = await gateway.t_send_message(args, None)
        assert 'reserved for post-review handoffs' in reply and 'submit_review' in reply
        assert await svc.runs.list_messages(run.run_id) == before
        # The actual producer sent under t2. Exercise the cross-task boundary
        # with that saved handoff, changing only its task_id to t3.
        incoming = record['producer_handoff']['payload']
        producer = rt.tasks['t2']
        producer_gateway = ToolGateway(SessionContext(rt, rt.agents[producer.spec.owner], 'task', producer))
        reply = await producer_gateway.t_send_message({'to':ctx.agent.agent_id, 'task_id':'t3',
                                                       'purpose':incoming['purpose'], 'text':incoming['text']}, None)
        assert "reserved for its reviewer's required handoffs" in reply
        assert await svc.runs.list_messages(run.run_id) == before
        refs = []
        for name in ['architecture', 'decisions']:
            artifact = await svc.artifacts.publish(run.run_id, name+'.md', (source/(name+'-r1.md')).read_bytes(),
                                                   agent_id=rt.tasks['t2'].spec.owner, task_id='t2')
            refs.append(artifact.ref().model_dump())
        review = {**record['rejected_review']['payload']['args'], 'target_artifacts':refs}
        assert (await gateway.t_submit_review(review, None)).startswith('OK:')
        assert ctx.reviews[0].results[0].status == 'fail'
        assert 'reserved for required review handoffs' in await gateway.t_send_message(args, None)
        assert await svc.runs.list_messages(run.run_id) == before
        # Deliver the actual review summary to its actual owner; no invented chat.
        reply = await gateway.t_send_message({'to':rt.tasks['t2'].spec.owner, 'task_id':'t3',
                                              'purpose':'finding', 'text':review['summary'], 'artifact_refs':refs}, None)
        assert reply.startswith('DELIVERED')
        assert rt.policy.peer_messages['t3'] == rt.config.limits.max_peer_messages_per_task
        assert rt.tasks['t2'].spec.owner in ctx.communicated_to
        assert ctx.finished is None  # Capacity reservation never finishes work.
        assert len(await svc.runs.list_messages(run.run_id)) == len(before)+1
    finally:
        await svc.stop()
