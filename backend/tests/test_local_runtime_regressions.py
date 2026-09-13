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
