"""Regressions from saved Ollama runs. No stub or scripted provider is used."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from agentteam.contracts import TeamPlan
from agentteam.runtime.planner import plan_from_output, validate_plan
from agentteam.runtime.tools import TOOL_SPECS
from agentteam.runtime.worker import consecutive_no_tool_turns

EVIDENCE = Path(__file__).resolve().parents[2] / 'docs/evidence/local-fixes-2026-09-14'
ROLES = {n: n for n in ['master', 'researcher', 'builder', 'reviewer']}


async def test_revised_workspace_cannot_finish_with_old_publication(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    from agentteam.runtime.worker import auto_finish_if_outputs_published
    evidence = EVIDENCE.parent / 'trading-plan-2026-09-20'
    record = json.loads((evidence / 'stale-publication.json').read_text())
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    rt = None
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for saved in record['run']['tasks']:
            task = TaskState.model_validate(saved)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        task = rt.tasks['t2']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task, tools=rt.agents[task.spec.owner].tools)
        gateway = ToolGateway(ctx)
        for path in ['architecture.md', 'decisions.md']:
            saved_path = 'architecture-round5-r1.md' if path == 'architecture.md' else 'decisions-r1.md'
            content = (evidence / saved_path).read_text()
            await gateway.call('workspace_write', {'path': path, 'content': content})
            assert (await gateway.call('publish_artifact', {'path': path})).startswith('PUBLISHED')
        await gateway.call('workspace_write', {'path': 'architecture.md', 'content':
                           (evidence / 'architecture-revision-draft.md').read_text()})
        # Actual round5 handoff has no structured refs. Even a delivered handoff
        # must not make an older publication count as the revised workspace.
        handoff = next(e['payload'] for e in record['events'] if e['seq'] == 153)
        args = {k: handoff[k] for k in ['text', 'purpose', 'artifact_refs']}
        args['to'] = handoff['to_agent_id']
        assert (await gateway.call('send_message', args)).startswith('DELIVERED')
        result = await gateway.call('finish_task', {'summary': handoff['text']})
        assert result.startswith('REJECTED: unpublished workspace changes'), result
        assert ctx.finished is None
        assert await auto_finish_if_outputs_published(ctx, 'empty turn') is None
        from agentteam.runtime.worker import AgentRunner
        runner = AgentRunner(ctx)
        await runner._compact_delivery_repair()
        recovery = runner.messages[0]['content'][0]['text']
        assert 'Saved edits not yet published\narchitecture.md' in recovery
        assert 'Read these files with workspace_read before editing' in recovery
        from agentteam.runtime.worker import build_task_message
        restored = await build_task_message(ctx, task)
        assert 'Saved edits not yet published\narchitecture.md' in restored
        assert 'architecture.md (revision 1,' in restored
        assert (await gateway.call('publish_artifact', {'path': 'architecture.md'})).startswith('PUBLISHED')
        restored = await build_task_message(ctx, task)
        assert 'architecture.md (revision 2,' in restored
        assert 'Saved edits not yet published' not in restored
        args['artifact_refs'] = [ctx.published[-1].ref().model_dump()]
        assert (await gateway.call('send_message', args)).startswith('DELIVERED')
        assert await gateway.call('finish_task', {'summary': handoff['text']}) == 'OK: task finished'
        ctx.finished = None
        assert await auto_finish_if_outputs_published(ctx, 'empty turn') is not None
        from agentteam.runtime.delivery import unpublished_workspace_changes
        assert await unpublished_workspace_changes(ctx) == []
        path = ctx.workspace / 'architecture.md'
        raw = path.read_bytes()
        path.unlink()
        assert await unpublished_workspace_changes(ctx) == []  # immutable publication survives draft cleanup
        outside = tmp_path / 'outside.md'
        outside.write_bytes(raw)
        path.symlink_to(outside)
        assert await unpublished_workspace_changes(ctx) == ['architecture.md']  # identical bytes do not bypass scope
        path.unlink()
        path.write_bytes(raw)
        (ctx.workspace / 'unpublished-notes.md').write_bytes(raw)
        assert await unpublished_workspace_changes(ctx) == []  # scratch work is not a declared publication
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_actual_prepublication_handoff_requires_current_revision_delivery(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    record = json.loads((EVIDENCE.parent / 'trading-plan-2026-09-20/prepublication-handoff.json').read_text())
    events = {e['seq']: e for e in record['events']}
    assert events[42]['payload']['ok'] is False
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for saved in record['run']['tasks']:
            task = TaskState.model_validate(saved)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        task = rt.tasks['t1']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task, tools=rt.agents[task.spec.owner].tools)
        gateway = ToolGateway(ctx)
        args = events[33]['payload']['args']
        assert (await gateway.call('send_message', args)).startswith('DELIVERED')
        assert 'builder' in ctx.communicated_to
        # Event argument previews are truncated. Replay the hash-verified actual
        # published bytes, not the shortened workspace_write log preview.
        draft = {**events[30]['payload']['args'], 'content':
                 (EVIDENCE.parent / 'trading-plan-2026-09-20/research-round5-r1.md').read_text()}
        await gateway.call('workspace_write', draft)
        published = await gateway.call('publish_artifact', events[40]['payload']['args'])
        assert 'Messages sent before this publication' in published
        assert not ctx.communicated_to
        rejected = await gateway.call('finish_task', events[42]['payload']['args'])
        assert 'Missing recipients: builder' in rejected
        assert 'Reading your inbox does not deliver' in rejected
        assert ctx.finished is None
        assert len(await svc.runs.list_messages(run.run_id)) == 1
        # Reuse the actual delivered text; add the real published revision reference.
        meta = ctx.published[-1]
        assert meta.sha256 == events[39]['payload']['sha256']
        assert (await gateway.call('send_message', {**args, 'artifact_refs': [meta.ref().model_dump()]})).startswith('DELIVERED')
        assert await gateway.call('finish_task', events[42]['payload']['args']) == 'OK: task finished'
        assert ctx.finished is not None
        assert len(await svc.runs.list_messages(run.run_id)) == 2
        assert rt.artifacts.read_bytes(meta).decode() == draft['content']
    finally:
        await svc.stop()


def records(name):
    return json.loads((EVIDENCE / (name + '.json')).read_text())


def test_actual_master_owned_unreviewed_plan_is_rejected():
    plan = TeamPlan.model_validate(records('pilot-team')[0]['plan'])
    errors = validate_plan(plan, list(ROLES), ROLES, 12, require_review=True)
    assert any('coordinates or reports' in e for e in errors)
    assert any('final deliverables need a reviewer' in e for e in errors)


def test_actual_research_plan_cannot_skip_final_review():
    plan = TeamPlan.model_validate(records('research-team')[0]['plan'])
    assert any('final deliverables need a reviewer' in e for e in
               validate_plan(plan, list(ROLES), ROLES, 12, require_review=True))


def test_actual_trading_plan_rejects_unwritable_output_before_dispatch():
    evidence = EVIDENCE.parent / 'trading-plan-2026-09-20/rejected-plan.json'
    event = json.loads(evidence.read_text())
    assert event['run_id'] == 'run_1a0bb7aa7af52628b54'
    plan = plan_from_output(event['payload']['plan'], list(ROLES))
    errors = validate_plan(plan, list(ROLES), ROLES, 12, require_review=True)
    assert any("invalid output path '/tmp/research.md'" in e for e in errors)
    assert any('final deliverables need a reviewer' in e for e in errors)


def test_actual_coordinator_attachment_reference_is_not_a_published_revision():
    evidence = EVIDENCE.parent / 'trading-plan-2026-09-20/coordinator-refs.json'
    rejected, delivered = json.loads(evidence.read_text())
    validator = Draft202012Validator(TOOL_SPECS['send_message'].input_schema)
    errors = list(validator.iter_errors(rejected['payload']['args']))
    assert any(list(e.path) == ['artifact_refs', 0, 'revision'] and e.validator == 'minimum'
               for e in errors)
    assert not list(validator.iter_errors(delivered['payload']['args']))


async def test_actual_invented_review_ids_are_exposed_as_invalid_before_generation(tmp_path):
    import copy
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    record = json.loads((EVIDENCE.parent / 'trading-plan-2026-09-20/rejected-review.json').read_text())
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        rt.tasks = {t['spec']['id']: TaskState.model_validate(t) for t in record['run']['tasks']}
        task = rt.tasks[record['event']['task_id']]
        agent = rt.agents[task.spec.owner]
        gateway = ToolGateway(SessionContext(rt, agent, 'task', task, tools=agent.tools))
        original = copy.deepcopy(TOOL_SPECS['submit_review'].input_schema)
        schema = next(t.input_schema for t in gateway.specs() if t.name == 'submit_review')
        args = record['event']['payload']['args']
        errors = list(Draft202012Validator(schema).iter_errors(args))
        assert any(e.validator == 'enum' and list(e.path)[-1] == 'acceptance_id' for e in errors)
        accepted = record['accepted_event']
        assert accepted['payload']['ok'] is True
        assert not list(Draft202012Validator(schema).iter_errors(accepted['payload']['args']))
        wrong_target = record['wrong_target_event']['payload']['args']
        assert any(e.validator == 'enum' and list(e.path) == ['target_task_id']
                   for e in Draft202012Validator(schema).iter_errors(wrong_target))
        assert 'does not depend on' in await gateway.t_submit_review(wrong_target, None)
        target = rt.tasks[args['target_task_id']]
        result_schema = schema['properties']['results']
        assert result_schema['minItems'] == result_schema['maxItems'] == len(target.spec.acceptance)
        assert result_schema['items']['properties']['acceptance_id']['enum'] == sorted(c.id for c in target.spec.acceptance)
        assert schema['properties']['target_task_id']['enum'] == task.spec.depends_on
        assert schema['required'] == original['required']
        assert TOOL_SPECS['submit_review'].input_schema == original
        # The unchanged execution layer also rejects the real bad request.
        reply = await gateway.t_submit_review(args, None)
        assert reply.startswith('REJECTED: unknown acceptance ids')
        assert not gateway.ctx.reviews and target.review is None
        # Replay the real pre-review finding followed by the real accepted review.
        # Recovery must not count that earlier finding as the required handoff.
        published_refs = []
        for name in ('architecture', 'decisions'):
            raw = (EVIDENCE.parent / f'trading-plan-2026-09-20/{name}-r1.md').read_bytes()
            published = await rt.artifacts.publish(run.run_id, f'{name}.md', raw,
                                                   agent_id=target.spec.owner, task_id=target.spec.id)
            published_refs.append(published.ref().model_dump())
        # A real review's partial artifact list must remain rejected, with an
        # actionable complete scope rather than repeated blind rereads.
        partial = copy.deepcopy(accepted['payload']['args'])
        partial['target_artifacts'] = published_refs[:1]
        before_rejection = await rt.events.list(run.run_id)
        reply = await gateway.t_submit_review(partial, None)
        assert reply.startswith('REJECTED: review must cover exactly')
        required = json.loads(reply.split('Required target_artifacts: ', 1)[1])
        assert sorted(required, key=lambda r: r['artifact_id']) == sorted(published_refs, key=lambda r: r['artifact_id'])
        assert not gateway.ctx.reviews
        assert await rt.events.list(run.run_id) == before_rejection
        finding = record['prior_finding']['payload']
        sent = await gateway.t_send_message({'to': finding['to_agent_id'], 'task_id': finding['task_id'],
                                            'purpose': finding['purpose'], 'text': finding['text'],
                                            'artifact_refs': finding['artifact_refs']}, None)
        assert sent.startswith('DELIVERED') and target.spec.owner in gateway.ctx.communicated_to
        reply = await gateway.t_submit_review(accepted['payload']['args'], None)
        assert reply.startswith('OK: review recorded')
        assert target.spec.owner not in gateway.ctx.communicated_to
        from agentteam.runtime.worker import AgentRunner
        runner = AgentRunner(gateway.ctx)
        runner.nudges = 2
        before = await rt.events.list(run.run_id)
        original_review = gateway.ctx.reviews[0].model_dump()
        await runner._compact_delivery_repair('ended without a tool after submitting review findings')
        recovered = runner.messages[0]['content'][0]['text']
        assert 'Reviews already submitted in this session' in recovered
        assert json.dumps(original_review, ensure_ascii=False) in recovered
        assert f"artifact references to: {target.spec.owner}; then finish_task" in recovered
        assert gateway.ctx.reviews[0].model_dump() == original_review
        assert target.spec.owner not in gateway.ctx.communicated_to
        assert await rt.events.list(run.run_id) == before and runner.nudges == 2
        finish = await gateway.t_finish_task({'summary': original_review['summary']}, None)
        assert 'Missing recipients: builder' in finish and gateway.ctx.finished is None
    finally:
        await svc.stop()


async def test_actual_literal_failure_is_not_changed_by_semantic_guidance(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    source = EVIDENCE.parent / 'trading-plan-2026-09-20'
    record = json.loads((source / 'lexical-check.json').read_text())
    svc = await AppService(tmp_path).start()
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        task = TaskState.model_validate(record['task'])
        rt.tasks[task.spec.id] = task
        raw = (source / 'architecture-r1.md').read_bytes()
        meta = await rt.artifacts.publish(run.run_id, 'architecture.md', raw,
                                         agent_id=task.spec.owner, task_id=task.spec.id)
        expected = record['event']['payload']
        assert meta.ref().model_dump() == expected['target']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task)
        reply = json.loads(await ToolGateway(ctx).t_run_check({
            'kind': expected['kind'], 'args': expected['args'],
            'artifact_id': meta.artifact_id, 'revision': meta.revision,
        }, None))
        assert reply['result'] == expected['result']
        assert reply['result']['status'] == 'fail'
        assert reply['target'] == expected['target']
        assert 'not meaning' in reply['interpretation']
        assert rt.artifacts.read_bytes(meta) == raw
        event = (await rt.events.list(run.run_id))[-1]
        assert event.type == 'check.completed' and event.payload == expected
    finally:
        await svc.stop()


async def test_actual_unconstrained_document_recovers_durable_context(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import ArtifactRef, Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.worker import AgentRunner, build_system_prompt, supports_document_recovery
    source = EVIDENCE.parent / 'trading-plan-2026-09-20'
    record = json.loads((source / 'output-limit.json').read_text())
    truncated = [e for e in record['events'] if e['type'] == 'model.called']
    assert len(truncated) == 3
    assert all(e['payload']['stop_reason'] == 'max_tokens' and not e['payload']['tool_calls']
               for e in truncated)
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    try:
        run = Run.model_validate(record['run'])
        assert not run.inputs.delivery_requirements
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        assert supports_document_recovery(rt.agents['builder'].tools)
        assert supports_document_recovery(rt.agents['reviewer'].tools)
        assert not supports_document_recovery(rt.agents['master'].tools)
        task = TaskState.model_validate(record['task'])
        await svc.runs.upsert_task(task)
        rt.tasks[task.spec.id] = task
        for event in record['events']:
            payload = event['payload']
            if event['type'] == 'instruction.received':
                await rt.events.append(run.run_id, event['type'], payload,
                                       actor_id=event['actor_id'], actor_kind=event['actor_kind'])
            elif event['type'] == 'message.sent':
                message = await rt.bus.send(**{**payload, 'artifact_refs': [
                    ArtifactRef.model_validate(r) for r in payload['artifact_refs']]})
                await rt.bus.mark_read([message], message.to_agent_id)
        raw = (source / 'architecture-r1.md').read_bytes()
        meta = await rt.artifacts.publish(run.run_id, 'architecture.md', raw,
                                         agent_id=task.spec.owner, task_id=task.spec.id)
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task)
        (ctx.workspace / 'architecture.md').write_bytes(raw)
        runner = AgentRunner(ctx)
        ctx.tools = ctx.agent.tools
        system = build_system_prompt(ctx)
        usage = rt.policy.usage.model_dump()
        events_before = await rt.events.list(run.run_id)
        for streak in (1, 2):
            runner.nudges = streak
            await runner._compact_delivery_repair()
            text = runner.messages[0]['content'][0]['text']
            assert run.goal in text and task.spec.objective in text
            assert all(c.description in text for c in task.spec.acceptance)
            assert all(f['content'] in text for f in run.inputs.files)
            for event in record['events']:
                if event['type'] in ('instruction.received', 'message.sent'):
                    assert event['payload']['text'] in text
            assert 'Your existing published outputs' in text and meta.artifact_id in text
            assert 'workspace_list/workspace_read' in text
            assert runner.nudges == streak and ctx.finished is None
        assert build_system_prompt(ctx) == system
        assert rt.policy.usage.model_dump() == usage
        assert await rt.events.list(run.run_id) == events_before
        assert (ctx.workspace / 'architecture.md').read_bytes() == raw
        assert rt.artifacts.read_bytes(meta) == raw
        assert await runner._can_compact_task(runner.gateway.specs())
        # Execute a real read-only command through run_check; even this excludes
        # the new recovery path because shell effects are not reconstructed.
        result = await runner.gateway.call('run_check', {'kind': 'command', 'args': {'command': 'pwd'}})
        assert json.loads(result)['result']['status'] == 'pass'
        assert not await runner._can_compact_task(runner.gateway.specs())
    finally:
        await svc.stop()


def test_real_tool_turn_resets_the_previous_no_tool_streak():
    run = next(r for r in records('research-single') if 'Python 3.13' in r['plan']['goal'])
    streak = 0
    counts = []
    for e in run['events']:
        if e['type'] == 'model.called':
            streak = consecutive_no_tool_turns(streak, e['payload']['tool_calls'])
            counts.append(streak)
    assert counts == [0, 1, 2, 0, 1]


def test_actual_missing_content_has_actionable_schema_error():
    events = [e for r in records('research-single') for e in r['events']]
    args = next(e['payload']['args'] for e in events if e['type'] == 'tool.called'
                and e['payload']['tool'] == 'workspace_write' and 'content' not in e['payload']['args'])
    errors = list(Draft202012Validator(TOOL_SPECS['workspace_write'].input_schema).iter_errors(args))
    # Complete content and an exact edit are alternatives; neither may be omitted.
    nested = [child.message for error in errors for child in error.context]
    assert "'content' is a required property" in nested
    assert "'edit' is a required property" in nested


async def test_recorded_unverified_review_persists_partial_not_accepted(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Review, Run, RunInputs, RunStatus
    from agentteam.runtime.scheduler import Scheduler

    record = records('unverified-review')
    created = record['run_created']
    # Replay a real review through production SQLite stores and scheduler, without calling a model.
    svc = await AppService(tmp_path).start()
    rt = None
    try:
        run = Run(run_id=created['run_id'], status=RunStatus.running, goal=created['payload']['goal'],
                  inputs=RunInputs(), created_at=created['recorded_at'], plan=plan_from_output(record['plan']))
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        scheduler = Scheduler(rt)
        await scheduler.init_from_plan()
        event = record['event']
        review = Review.model_validate(event['payload'])
        # Restore the real reviewed bytes as well as its verdict. Otherwise the
        # current revision guard correctly rejects the incomplete replay first.
        source_dir = EVIDENCE.parents[2] / Path(record['source']).parent
        for ref in review.target_artifacts:
            original = await rt.artifacts.publish(
                run.run_id, ref.artifact_id,
                (source_dir / f'{ref.artifact_id}.r{ref.revision}').read_bytes(),
                agent_id=rt.tasks[review.target_task_id].spec.owner,
                task_id=review.target_task_id,
            )
            assert original.ref() == ref
        await scheduler._apply_review(rt.tasks[event['task_id']], review)
        saved = {t.spec.id: t for t in await svc.runs.list_tasks(run.run_id)}
        assert saved[review.target_task_id].status == 'partial'
        assert 'unverified' in saved[review.target_task_id].blocked_reason
        assert scheduler.final_status() == RunStatus.partial
        events = await svc.events.list(run.run_id)
        assert events[-1].type == 'task.partial'
        assert events[-1].payload['unverified'] == [r.acceptance_id for r in review.results if r.status != 'pass']
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_recorded_reviewer_cannot_replace_producer_artifact_or_skip_dependency(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, RunInputs, RunStatus, TaskSpec
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.scheduler import Scheduler
    from agentteam.runtime.tools import ToolGateway

    record = records('intermediate-pilot')
    # Reconstruct the first accepted plan; later tasks were added by the faulty milestone path.
    initial = dict(record['plan'], tasks=record['plan']['tasks'][:2])
    svc = await AppService(tmp_path).start()
    rt = None
    try:
        run = Run(run_id=record['run_id'], status=RunStatus.running, goal=record['goal'], inputs=RunInputs(),
                  created_at=record['created_at'], plan=TeamPlan.model_validate(initial))
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        scheduler = Scheduler(rt)
        await scheduler.init_from_plan()
        events = record['events']
        producer_write = next(e for e in events if e['type'] == 'tool.called' and e['actor_id'] == 'builder'
                              and e['payload']['tool'] == 'workspace_write')
        args = producer_write['payload']['args']
        original = await rt.artifacts.publish(run.run_id, args['path'], args['content'].encode(),
                                              agent_id='builder', task_id=producer_write['task_id'])
        reviewer_write = next(e for e in events if e['type'] == 'tool.called' and e['actor_id'] == 'reviewer'
                              and e['payload']['tool'] == 'workspace_write')
        ctx = SessionContext(rt=rt, agent=rt.agents['reviewer'], mode='task', task=rt.tasks['t2'],
                             tools=rt.agents['reviewer'].tools)
        gateway = ToolGateway(ctx)
        assert (await gateway.call('workspace_write', reviewer_write['payload']['args'])).startswith('OK')
        denied = await gateway.call('publish_artifact', {'path': args['path']})
        assert denied.startswith('REJECTED:') and 'another task' in denied
        latest = await rt.artifacts.get(run.run_id, original.artifact_id)
        assert latest.revision == 1 and latest.sha256 == original.sha256
        assert (await svc.events.list(run.run_id))[-1].payload['ok'] is False
        bad_task = next(t for t in record['plan']['tasks'] if t['owner'] == 'reviewer' and not t['depends_on'])
        assert 'must depend' in await scheduler.add_task(TaskSpec.model_validate(bad_task))
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_real_local_profile_keeps_thinking_setting_when_connection_is_edited(tmp_path):
    import httpx
    from agentteam.api.app import create_app
    from agentteam.api.service import AppService
    from agentteam.config.loader import load_config_file

    config_path = EVIDENCE.parents[1] / 'config/local-qwen35-9b-team.yaml'
    svc = AppService(tmp_path, config_yaml=config_path.read_text())
    app = create_app(svc)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
            # A client that does not yet expose this option must not reset it on save.
            original = svc.config.connection('ollama')
            observation = json.loads((EVIDENCE.parent / 'trading-plan-2026-09-20/sampling-observation.json').read_text())
            parameters = observation['configured_parameters']
            sampling = {'ollama_temperature': parameters['temperature'], 'ollama_top_p': parameters['top_p']}
            r = await client.put('/api/connections/ollama', json={
                'expected_revision': svc.config_revision, 'driver': original.driver,
                'base_url': original.base_url, **sampling})
            assert r.status_code == 200, r.text
            from agentteam.providers.registry import ProviderRegistry
            registry = ProviderRegistry(svc.config)
            try:
                adapter = registry.adapter('ollama')
                assert adapter.temperature == parameters['temperature']
                assert adapter.top_p == parameters['top_p']
            finally:
                await registry.aclose()
            r = await client.put('/api/connections/ollama', json={
                'expected_revision': svc.config_revision, 'driver': original.driver, 'base_url': original.base_url})
            assert r.status_code == 200, r.text
            assert load_config_file(svc.config_path).connection('ollama').ollama_thinking is False
            persisted = load_config_file(svc.config_path).connection('ollama')
            assert {name: getattr(persisted, name) for name in sampling} == sampling
            r = await client.put('/api/connections/ollama', json={
                'expected_revision': svc.config_revision, 'driver': original.driver, 'base_url': original.base_url,
                'ollama_thinking': None, 'ollama_temperature': None, 'ollama_top_p': None})
            assert r.status_code == 200, r.text
            assert load_config_file(svc.config_path).connection('ollama').ollama_thinking is None
            persisted = load_config_file(svc.config_path).connection('ollama')
            assert persisted.ollama_temperature is None and persisted.ollama_top_p is None


async def test_actual_attachment_reaches_planner_and_duplicate_review_is_rejected(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, RunInputs, RunStatus
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.planner import planning_message
    from agentteam.runtime.scheduler import Scheduler
    from agentteam.runtime.tools import ToolGateway

    record = records('qwen35-review-input')
    svc = await AppService(tmp_path).start()
    rt = None
    try:
        run = Run(run_id=record['run_id'], status=RunStatus.running, goal=record['goal'],
                  inputs=RunInputs.model_validate(record['inputs']), created_at=record['created_at'],
                  plan=TeamPlan.model_validate(record['plan']))
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        await Scheduler(rt).init_from_plan()
        assert run.inputs.files[0]['content'] in planning_message(rt), 'the planner must see the real source, not only its filename'
        ctx = SessionContext(rt=rt, agent=rt.agents['reviewer'], mode='task', task=rt.tasks['t2'],
                             tools=rt.agents['reviewer'].tools)
        result = await ToolGateway(ctx).call('submit_review', record['review'])
        assert result.startswith('REJECTED: duplicate acceptance ids')
        assert not ctx.reviews
        assert (await svc.events.list(run.run_id))[-1].payload['ok'] is False
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_terminal_status_waits_for_report_and_complete_event_log(tmp_path):
    import asyncio
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, RunStatus

    record = records('single-finalization')
    profile = EVIDENCE.parents[1] / 'config/local-qwen25-7b-single.yaml'
    svc = await AppService(tmp_path, config_yaml=profile.read_text()).start()
    rt = None
    try:
        run = Run.model_validate(record)
        run.status = RunStatus.running
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        # The real single profile has no report agent: production code builds the deterministic report.
        async def watch_terminal():
            while True:
                saved = await svc.runs.get_run(run.run_id)
                if saved.status == RunStatus.completed:
                    events = await svc.events.list(run.run_id)
                    assert saved.final_report is not None
                    assert events[-1].type == 'run.completed'
                    assert any(e.type == 'report.generated' for e in events)
                    return
                await asyncio.sleep(0)
        watcher = asyncio.create_task(watch_terminal())
        try:
            await svc.manager._finish(rt, RunStatus.completed)
            await asyncio.wait_for(watcher, timeout=5)
        finally:
            if not watcher.done():
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_cancel_during_report_preparation_is_not_published_as_completed(tmp_path):
    import asyncio
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, RunStatus

    profile = EVIDENCE.parents[1] / 'config/local-qwen25-7b-single.yaml'
    svc = await AppService(tmp_path, config_yaml=profile.read_text()).start()
    rt = None
    try:
        run = Run.model_validate(records('single-finalization'))
        run.status = RunStatus.running
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        queue = svc.events.subscribe(run.run_id)
        async def cancel_after_report_generated():
            while True:
                event = await queue.get()
                if event.type == 'report.generated':
                    rt.policy.cancel()
                    return
        cancellation = asyncio.create_task(cancel_after_report_generated())
        try:
            await svc.manager._finish(rt, RunStatus.completed)
            await asyncio.wait_for(cancellation, 5)
        finally:
            if not cancellation.done():
                cancellation.cancel()
                await asyncio.gather(cancellation, return_exceptions=True)
            svc.events.unsubscribe(run.run_id, queue)
        saved = await svc.runs.get_run(run.run_id)
        assert saved.status == RunStatus.cancelled
        assert saved.final_report['status'] == 'cancelled'
        assert (await svc.events.list(run.run_id))[-1].type == 'run.cancelled'
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_real_timeout_preserves_reason_and_emits_one_interruption(tmp_path):
    import time
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, RunStatus
    from agentteam.runtime.scheduler import Scheduler

    profile = EVIDENCE.parents[1] / 'config/local-qwen35-9b-thinking-team.yaml'
    svc = await AppService(tmp_path, config_yaml=profile.read_text()).start()
    rt = None
    try:
        run = Run.model_validate(records('thinking-interruption'))
        elapsed = run.usage.wall_seconds
        run.status = RunStatus.running
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        # Replay the actual exhausted wall-clock budget, without waiting ten minutes or faking a provider.
        rt.started_monotonic = time.monotonic() - elapsed
        scheduler = Scheduler(rt)
        await scheduler.init_from_plan()
        status = await scheduler.run()
        reason = await svc.manager._status_reason(rt, status)
        await svc.manager._finish(rt, status, reason=reason)
        saved = await svc.runs.get_run(run.run_id)
        interruptions = [e for e in await svc.events.list(run.run_id) if e.type == 'run.interrupted']
        assert saved.status == RunStatus.interrupted
        assert saved.blocked_reason == 'wall-clock limit reached'
        assert len(interruptions) == 1
        assert interruptions[0].payload['reason'] == saved.blocked_reason
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


def test_no_tool_nudge_names_the_next_call_for_a_narrating_reviewer():
    """2026-09-18 local recompare, code-wc-plus: the reviewer wrote "まず wc_plus.py を読みます" three times with
    zero tool calls, so a correct deliverable ended partial. The reminder now names the call to make."""
    from agentteam.runtime.worker import no_tool_nudge
    tools = ['read_artifact', 'run_check', 'submit_review', 'finish_task', 'report_blocker']
    first = no_tool_nudge('reviewer', tools, 1)
    assert 'starting with read_artifact' in first and 'read_artifact → run_check → submit_review → finish_task' in first
    assert 'last reminder' not in first and 'last reminder' in no_tool_nudge('reviewer', tools, 2)
    # Never name a tool the agent does not have; unknown roles keep the original wording.
    assert 'run_check' not in no_tool_nudge('reviewer', ['read_artifact', 'submit_review', 'finish_task'], 1)
    assert no_tool_nudge('master', tools, 1).endswith('otherwise continue with tools.')

async def test_actual_same_owner_other_task_output_is_not_renamed_or_published(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    from agentteam.runtime.worker import build_task_message
    source = EVIDENCE.parent / 'adaptive-team-2026-09-20/same-owner-output.json'
    record = json.loads(source.read_text())
    run = Run.model_validate(record['run'])
    svc = await AppService(tmp_path, config_yaml=run.config_snapshot['config_yaml']).start()
    try:
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        rt.tasks = {t['spec']['id']: TaskState.model_validate(t) for t in record['run']['tasks']}
        task = rt.tasks[record['write']['task_id']]
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task)
        gateway = ToolGateway(ctx)
        assert rt.tasks['t2'].spec.owner == task.spec.owner
        await gateway.t_workspace_write(record['write']['payload']['args'], None)
        before = await rt.artifacts.list(run.run_id)
        reply = await gateway.t_publish_artifact(record['publish']['payload']['args'], None)
        assert 'your separate task t2, not current task t1' in reply
        assert 'Do not rename' in reply
        assert await rt.artifacts.list(run.run_id) == before
        prompt = await build_task_message(ctx, task)
        assert 'Your other scheduled tasks (not this session)' in prompt
        assert '- t2: decisions.md' in prompt
        assert 'do not publish their files here or rename them' in prompt
        assert ctx.finished is None
    finally:
        await svc.stop()


async def test_real_artifact_character_ranges_preserve_revision_and_full_read(tmp_path):
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    record = json.loads((EVIDENCE.parent / 'adaptive-team-2026-09-20/same-owner-output.json').read_text())
    # Real saved Japanese draft; publish in its declared t2 workspace for this
    # storage contract check, not as a new live model-produced deliverable.
    args = record['write']['payload']['args']
    content = args['content']
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    rt = None
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for saved in record['run']['tasks']:
            task = TaskState.model_validate(saved)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        task = rt.tasks['t2']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task, tools=rt.agents[task.spec.owner].tools)
        gateway = ToolGateway(ctx)
        assert (await gateway.call('workspace_write', args)).startswith('OK:')
        assert (await gateway.call('publish_artifact', {'path': args['path']})).startswith('PUBLISHED')
        ref = {'artifact_id': args['path'], 'revision': 1}
        full = await gateway.call('read_artifact', ref)
        assert full.split('\n---\n', 1)[1] == content
        assert 'start_char=' not in full.split('\n---\n', 1)[0]
        chunks = []
        for start in range(0, len(content), 777):
            reply = await gateway.call('read_artifact', {**ref, 'start_char': start, 'max_chars': 777})
            header, body = reply.split('\n---\n', 1)
            assert 'revision=1' in header and f'sha256={ctx.published[-1].sha256}' in header
            assert f'start_char={start}' in header and 'partial=true' in header
            assert body == content[start:start + 777]
            chunks.append(body)
        assert ''.join(chunks) == content
        empty = await gateway.call('read_artifact', {**ref, 'start_char': len(content) + 1})
        assert empty.endswith('\n---\n') and 'more=false' in empty
        default = await gateway.call('read_artifact', {**ref, 'start_char': 1})
        assert default.split('\n---\n', 1)[1] == content[1:4001]
        events = [e for e in await rt.events.list(rt.run_id) if e.type == 'artifact.read']
        assert 'partial' not in events[0].payload
        assert all(e.payload['partial'] for e in events[1:])
        assert all(e.payload['total_chars'] == len(content) for e in events[1:])
        before = len(events)
        for bad in [{'start_char': -1}, {'max_chars': 0}, {'max_chars': 20001}]:
            result = await gateway.call('read_artifact', {**ref, **bad})
            assert result.startswith('REJECTED: invalid tool arguments:'), result
        assert len([e for e in await rt.events.list(rt.run_id) if e.type == 'artifact.read']) == before
        # Boundary mutation of runtime output capacity, using the same actual
        # saved bytes. No partial-success metadata may precede silent truncation.
        rt.config.limits.max_tool_output_chars = 1024
        rejected = await gateway.call('read_artifact', {**ref, 'max_chars': 20000})
        assert rejected.startswith('REJECTED: requested artifact range exceeds')
        assert len([e for e in await rt.events.list(rt.run_id) if e.type == 'artifact.read']) == before
        bounded = await gateway.call('read_artifact', {**ref, 'max_chars': 500})
        assert bounded.split('\n---\n', 1)[1] == content[:500]
        assert 'end_char=500' in bounded and 'more=true' in bounded
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()


async def test_exact_draft_edit_rejects_stale_ambiguous_and_mixed_inputs(tmp_path):
    import hashlib
    from agentteam.api.service import AppService
    from agentteam.contracts import Run, TaskState
    from agentteam.runtime.context import SessionContext
    from agentteam.runtime.tools import ToolGateway
    record = json.loads((EVIDENCE.parent / 'adaptive-team-2026-09-20/same-owner-output.json').read_text())
    saved = record['write']['payload']['args']
    content = saved['content']
    svc = await AppService(tmp_path, config_yaml=record['run']['config_snapshot']['config_yaml']).start()
    rt = None
    try:
        run = Run.model_validate(record['run'])
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run, svc.config)
        for item in record['run']['tasks']:
            task = TaskState.model_validate(item)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        task = rt.tasks['t2']
        ctx = SessionContext(rt, rt.agents[task.spec.owner], 'task', task, tools=rt.agents[task.spec.owner].tools)
        gateway = ToolGateway(ctx)
        original = content.encode('utf-8')
        sha = hashlib.sha256(original).hexdigest()
        full = await gateway.call('workspace_write', saved)
        assert full.startswith('OK:') and f'sha256={sha}' in full
        path = ctx.workspace / saved['path']
        # Boundary mutations of real saved model output: remove its unique
        # heading, reject repeated newline and stale digest. No live output edited.
        heading = content.splitlines(keepends=True)[0]
        assert content.count(heading) == 1 and content.count('\n') > 1
        edit = {'expected_sha256': sha, 'old_text': heading, 'new_text': ''}
        for args in [
            {'path': saved['path'], 'edit': {**edit, 'old_text': '\n'}},
            {'path': saved['path'], 'edit': {**edit, 'old_text': ''}},
            {'path': saved['path'], 'edit': edit, 'content': content},
            {'path': saved['path']},
        ]:
            assert (await gateway.call('workspace_write', args)).startswith('REJECTED')
            assert path.read_bytes() == original
        result = await gateway.call('workspace_write', {'path': saved['path'], 'edit': edit})
        expected = content[len(heading):].encode('utf-8')
        assert result.startswith('OK:') and path.read_bytes() == expected
        assert hashlib.sha256(expected).hexdigest() in result
        assert await rt.artifacts.list(rt.run_id) == []  # editing does not publish
        stale = await gateway.call('workspace_write', {'path': saved['path'], 'edit': edit})
        assert stale.startswith('REJECTED: draft SHA mismatch')
        assert path.read_bytes() == expected
        assert (await gateway.call('workspace_write', saved)).startswith('OK:')
        assert path.read_bytes() == original  # old complete-write contract retained
        # Extract an actual Markdown divider for the overlapping-match boundary.
        divider = next(line for line in content.splitlines() if line == '---')
        assert (await gateway.call('workspace_write', {'path': saved['path'], 'content': divider})).startswith('OK:')
        overlap = {'expected_sha256': hashlib.sha256(divider.encode()).hexdigest(),
                   'old_text': divider[:2], 'new_text': ''}
        assert (await gateway.call('workspace_write', {'path': saved['path'], 'edit': overlap})).startswith('REJECTED: old_text')
        assert path.read_text() == divider
    finally:
        if rt:
            await rt.providers.aclose()
        await svc.stop()
