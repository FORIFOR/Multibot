"""Real documents and recorded outputs; no generated fixture/model response."""
import json
import httpx
from agentteam.api.app import create_app
from pathlib import Path

from agentteam.contracts import DeliveryRequirement, Run, RunInputs, TaskState
from agentteam.api.service import AppService
from agentteam.runtime.checks import isolated_check
from agentteam.runtime.context import SessionContext
from agentteam.runtime.delivery import verify_delivery, failures
from agentteam.runtime.worker import AgentRunner
from agentteam.runtime.tools import ToolGateway

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'docs/evidence/real-readiness-v12-qwen35-2026-09-14/02-run_1a09e84a3449aa4c8f5'


async def test_text_schema_uses_actual_unicode_bytes_and_keeps_json_default():
    raw = (ROOT/'docs/quality/integration.md').read_bytes()
    length = len(raw.decode('utf-8'))
    result = await isolated_check('json_schema', raw, {'input_format':'text','schema':{'type':'string','minLength':length,'maxLength':length}})
    assert result['status'] == 'pass'
    assert result['unicode_code_points'] == length
    assert result['utf8_bytes'] == len(raw)
    result = await isolated_check('json_schema', raw, {'input_format':'text','schema':{'type':'string','minLength':400,'maxLength':700}})
    assert result['status'] == 'fail'
    assert (await isolated_check('json_schema', raw, {'schema':{'type':'string'}}))['status'] == 'fail'
    recorded = (SOURCE/'run.json').read_bytes()
    assert (await isolated_check('json_schema',recorded,{'schema':{'type':'object','required':['run_id','status']}}))['status']=='pass'
    legacy = {'logical_path':'run.json','json_schema':{'type':'object'}}
    assert DeliveryRequirement.model_validate(legacy).model_dump() == legacy
    assert DeliveryRequirement.model_validate({**legacy,'input_format':'json'}).model_dump()==legacy
    assert DeliveryRequirement.model_validate({**legacy,'input_format':'text'}).model_dump()['input_format']=='text'


async def test_actual_delivery_rejection_and_task_specific_recovery(tmp_path):
    svc = await AppService(tmp_path, config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        record = json.loads((SOURCE/'run.json').read_text())
        run = Run.model_validate(record)
        task = TaskState.model_validate(record['tasks'][0])
        path = task.spec.output_paths[0]
        # Apply the requested strict text limit to a real source document; it must fail.
        requirement = DeliveryRequirement(logical_path=path, input_format='text', json_schema={'type':'string','maxLength':700})
        run.inputs.delivery_requirements = [requirement]
        await svc.runs.create_run(run)
        await svc.runs.upsert_task(task)
        rt = svc.manager._build_runtime(run,svc.config)
        rt.tasks[task.spec.id]=task
        meta = await svc.artifacts.publish(run.run_id,path,(ROOT/'docs/quality/integration.md').read_bytes(),agent_id=task.spec.owner,task_id=task.spec.id)
        ctx=SessionContext(rt,rt.agents[task.spec.owner],'task',task)
        gateway=ToolGateway(ctx)
        ctx.workspace.mkdir(parents=True,exist_ok=True)
        write_reply=await gateway.t_workspace_write({'path':path,'content':(ROOT/'docs/quality/integration.md').read_text()},None)
        assert 'not published yet' in write_reply and 'too long' in write_reply
        unchanged=await gateway.t_workspace_write({'path':path,'content':(ROOT/'docs/quality/integration.md').read_text()},None)
        assert 'UNCHANGED' in unchanged and 'too long' in unchanged
        assert (ctx.workspace/path).read_text()==(ROOT/'docs/quality/integration.md').read_text()
        workspace_checked=json.loads(await gateway.t_run_check({'kind':'json_schema','path':path},None))
        assert workspace_checked['result']['status']=='fail'
        assert 'too long' in str(workspace_checked['result'])
        checked=json.loads(await gateway.t_run_check({'kind':'json_schema','artifact_id':meta.artifact_id,'revision':meta.revision},None))
        assert checked['result']['status']=='fail'
        assert failures(await verify_delivery(rt))
        assert (await gateway.t_finish_task({'summary':run.goal},None)).startswith('REJECTED: requester delivery')
        assert ctx.finished is None
        newer=await svc.artifacts.publish(run.run_id,path,(ROOT/'README.md').read_bytes(),agent_id=task.spec.owner,task_id=task.spec.id)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(svc)),base_url='http://127.0.0.1') as client:
            old=(await client.get(f'/api/artifacts/{run.run_id}/{meta.artifact_id}/versions/{meta.revision}')).json()
            current=(await client.get(f'/api/artifacts/{run.run_id}/{newer.artifact_id}/versions/{newer.revision}')).json()
            required=[e for e in old['checks'] if e['type']=='delivery.checked']
            assert required and all(e['payload']['result']['status']=='fail' for e in required)
            assert all(e['payload']['target']['sha256']==meta.sha256 for e in required)
            assert not current['checks']  # never attach an old revision's verdict to new bytes
        runner=AgentRunner(ctx)
        runner.nudges=2
        await runner._compact_delivery_repair()
        rebuilt=runner.messages[0]['content'][0]['text']
        assert run.goal in rebuilt and task.spec.objective in rebuilt
        assert runner.nudges==2
        assert 'Readiness' not in rebuilt or 'Readiness' in run.goal
        assert 'English source quotation' not in rebuilt
        assert '修正版' not in rebuilt or '修正版' in run.goal
    finally:
        await svc.stop()


def test_real_recorded_plan_preserves_requester_delivery_paths():
    from agentteam.contracts import TeamPlan
    from agentteam.config.loader import load_config_text
    from agentteam.runtime.planner import validate_plan
    record = json.loads((SOURCE/'run.json').read_text())
    plan = TeamPlan.model_validate(record['plan'])
    cfg = load_config_text(record['config_snapshot']['config_yaml'])
    enabled = [a.id for a in cfg.agents if a.enabled]
    roles = {a.id:a.role for a in cfg.agents if a.enabled}
    existing = [p for t in plan.tasks for p in t.output_paths]
    assert existing
    assert not validate_plan(plan,enabled,roles,cfg.limits.max_tasks,required_paths=existing)
    # The current user's explicit delivery path is absent from this real prior plan.
    assert 'guide.md' not in existing
    errors = validate_plan(plan,enabled,roles,cfg.limits.max_tasks,required_paths=['guide.md'])
    assert any("requester delivery path 'guide.md' is missing" in e for e in errors)


async def test_document_workflow_compiles_actual_request_without_provider_calls(tmp_path):
    import pytest
    from pydantic import ValidationError
    from agentteam.runtime.planner import document_plan, PlanError
    from agentteam.runtime.scheduler import Scheduler
    raw = (ROOT/'docs/quality/integration.md').read_text()
    legacy = {'text':raw,'urls':[],'files':[],'delivery_requirements':[]}
    assert RunInputs.model_validate(legacy).model_dump() == legacy
    requirement = {'logical_path':'guide.md','input_format':'text','json_schema':{'type':'string','minLength':400,'maxLength':700}}
    inputs = RunInputs(text=raw,delivery_requirements=[requirement],workflow='document')
    assert inputs.model_dump()['workflow'] == 'document'
    json_inputs = RunInputs(text=raw, delivery_requirements=[{
        'logical_path': 'guide.json', 'json_schema': {'type': 'object'}, 'input_format': 'json'
    }], workflow='document')
    assert json_inputs.model_dump()['workflow'] == 'document'
    with pytest.raises(ValidationError):
        RunInputs(text=raw,workflow='document')
    with pytest.raises(ValidationError):
        RunInputs(delivery_requirements=[requirement],workflow='document')
    svc = await AppService(tmp_path,config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        run = Run.model_validate(json.loads((SOURCE/'run.json').read_text()))
        run.inputs = inputs
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run,svc.config)
        before = rt.policy.usage.model_calls
        plan = await document_plan(rt)
        assert plan.goal == run.goal and plan.tasks[0].objective == run.goal
        assert plan.tasks[0].output_paths == ['guide.md']
        assert plan.tasks[1].depends_on == [plan.tasks[0].id]
        assert rt.agents[plan.tasks[0].owner].role == 'builder'
        assert rt.agents[plan.tasks[1].owner].role == 'reviewer'
        assert rt.policy.usage.model_calls == before
        rt.run.plan = plan
        scheduler = Scheduler(rt)
        await scheduler.init_from_plan()
        assert scheduler.unreviewed_final_tasks() == [plan.tasks[0].id]
        producer_task = rt.tasks[plan.tasks[0].id]
        producer = rt.agents[producer_task.spec.owner]
        producer_gateway = ToolGateway(SessionContext(rt, producer, 'task', producer_task, tools=producer.tools))
        write_spec = next(t for t in producer_gateway.specs() if t.name == 'workspace_write')
        assert write_spec.input_schema['properties']['content']['minLength'] == 400
        assert write_spec.input_schema['properties']['content']['maxLength'] == 700
        assert write_spec.input_schema['properties']['path']['enum'] == plan.tasks[0].output_paths
        # Advertising a constraint must not mutate another run's generic tools.
        from agentteam.runtime.tools import TOOL_SPECS
        assert 'maxLength' not in TOOL_SPECS['workspace_write'].input_schema['properties']['content']
        reviewer_task = rt.tasks[plan.tasks[1].id]
        reviewer = rt.agents[reviewer_task.spec.owner]
        review_ctx = SessionContext(rt, reviewer, 'task', reviewer_task, tools=reviewer.tools)
        gateway = ToolGateway(review_ctx)
        assert 'workspace_write' not in {tool.name for tool in gateway.specs()}
        assert 'submit_review' in {tool.name for tool in gateway.specs()}
        denied = await gateway.call('workspace_write', {'path':'guide.md','content':raw})
        assert denied.startswith('DENIED')
        assert not (review_ctx.workspace / 'guide.md').exists()
        denied = await gateway.call('run_check', {'kind':'command','args':{'command':'pwd'}})
        assert denied.startswith('DENIED')
        # Existing general-team review permissions are unchanged.
        rt.run.inputs.workflow = 'team'
        assert 'workspace_write' in {tool.name for tool in gateway.specs()}
        rt.run.inputs.workflow = 'document'
        rt.agents[plan.tasks[1].owner].enabled = False
        with pytest.raises(PlanError):
            await document_plan(rt)
    finally:
        await svc.stop()


async def test_review_rejects_old_foreign_and_changed_real_revisions(tmp_path):
    from agentteam.runtime.scheduler import Scheduler
    source = ROOT/'docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/01'
    record = json.loads((source/'run.json').read_text())
    svc = await AppService(tmp_path,config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        run = Run.model_validate(record)
        await svc.runs.create_run(run)
        rt = svc.manager._build_runtime(run,svc.config)
        for entry in record['tasks']:
            task = TaskState.model_validate(entry)
            rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        target, reviewer = rt.tasks['t1'],rt.tasks['t2']
        for meta in json.loads((source/'artifacts.json').read_text()):
            if meta['logical_path'] == 'readiness.json':
                await svc.artifacts.publish(run.run_id,meta['logical_path'],(source/meta['evidence_file']).read_bytes(),agent_id=target.spec.owner,task_id=target.spec.id)
        ctx = SessionContext(rt,rt.agents[reviewer.spec.owner],'task',reviewer)
        gateway = ToolGateway(ctx)
        # Reuse actual recorded review and artifact bytes; this tests reference binding,
        # not a new claim that the recorded semantic verdict is correct.
        args = target.review.model_dump()
        stale = {**args,'target_artifacts':[{'artifact_id':'readiness.json','revision':1}]}
        assert (await gateway.t_submit_review(stale,None)).startswith('REJECTED:')
        assert not ctx.reviews
        foreign = await svc.artifacts.publish(run.run_id,'integration.md',(ROOT/'docs/quality/integration.md').read_bytes(),agent_id=reviewer.spec.owner,task_id=reviewer.spec.id)
        assert (await gateway.t_submit_review({**args,'target_artifacts':[foreign.ref().model_dump()]},None)).startswith('REJECTED:')
        assert (await gateway.t_submit_review(args,None)).startswith('OK:')
        accepted = ctx.reviews[0]
        assert accepted.target_artifacts == target.review.target_artifacts
        # An actual write after submission must invalidate that review at acceptance.
        await svc.artifacts.publish(run.run_id,'readiness.json',(ROOT/'docs/quality/integration.md').read_bytes(),agent_id=target.spec.owner,task_id=target.spec.id)
        scheduler = Scheduler(rt)
        await scheduler._apply_review(reviewer,accepted)
        assert target.status == 'partial' and target.review is None
        assert reviewer.status == 'partial'
        assert 'require a new review' in target.blocked_reason
    finally:
        await svc.stop()

async def test_literal_exclusions_apply_to_real_text_at_delivery_boundary(tmp_path):
    """A requester can forbid literal wording through standard JSON Schema."""
    import re
    from agentteam.runtime.delivery import verify_delivery, failures
    record = json.loads((SOURCE/'run.json').read_text())
    run = Run.model_validate(record)
    task = TaskState.model_validate(record['tasks'][0])
    raw = (ROOT/'docs/design/brief.md').read_bytes()
    phrase = 'Agent Team'  # Actual product name in the source, no generated output.
    requirement = DeliveryRequirement(logical_path=task.spec.output_paths[0], input_format='text',
        json_schema={'type':'string','not':{'anyOf':[{'pattern':re.escape(phrase)}]}})
    run.inputs.delivery_requirements = [requirement]
    svc = await AppService(tmp_path,config_yaml=(ROOT/'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        await svc.runs.create_run(run)
        await svc.runs.upsert_task(task)
        rt = svc.manager._build_runtime(run,svc.config)
        rt.tasks[task.spec.id] = task
        await svc.artifacts.publish(run.run_id,requirement.logical_path,raw,
                                   agent_id=task.spec.owner,task_id=task.spec.id)
        checks = await verify_delivery(rt)
        assert failures(checks), 'A model cannot override a requester-owned exclusion'
    finally:
        await svc.stop()
