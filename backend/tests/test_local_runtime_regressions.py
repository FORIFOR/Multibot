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
    assert any("'content' is a required property" in e.message for e in errors)


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
