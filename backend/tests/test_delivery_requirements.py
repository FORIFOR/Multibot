"""Recheck the actual local-model false completion against requester-owned rules."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

from agentteam.api.service import AppService
from agentteam.contracts import DeliveryRequirement, Run, TaskState
from agentteam.runtime.checks import isolated_check
from agentteam.runtime.context import SessionContext
from agentteam.runtime.delivery import verify_delivery, failures
from agentteam.runtime.tools import ToolGateway
from agentteam.runtime.worker import auto_finish_if_outputs_published
from .test_server_security import EVIDENCE, PROFILE, provision

REAL = EVIDENCE.parent / 'real-readiness-v1-2026-09-14'
V5 = EVIDENCE.parent / 'real-readiness-v5-qwen35-2026-09-14'


def test_observed_v5_translation_drift_is_rejected_by_the_current_contract():
    """The real second run exposed garbled terms that the first contract missed."""
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'production_workflow.py'
    module_spec = importlib.util.spec_from_file_location('translation_contract_workflow', script)
    workflow = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(workflow)
    expected = workflow.source_rows((EVIDENCE.parents[1] / 'PRODUCTION_PLAN.md').read_text())
    raw = (V5 / '02-run_1a09e007b47ce3b4033' / 'artifact-001.bin').read_bytes()
    result = workflow.json_schema_check(raw, workflow.delivery_schema(expected))
    assert result['status'] == 'fail'
    assert any(term in problem for problem in result['problems'] for term in ('バイントーリング', 'レジャーリー', 'アデュータ', 'コッレクター'))


async def test_actual_english_remaining_cannot_finish_or_auto_finish_and_final_status_is_partial(tmp_path):
    access, _ = provision(tmp_path)
    svc = await AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access).start()
    detail = json.loads((REAL / 'run.json').read_text())
    run = Run.model_validate(detail)
    script = Path(__file__).resolve().parents[1] / 'scripts/production_workflow.py'
    module_spec = importlib.util.spec_from_file_location('delivery_workflow', script)
    workflow = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(workflow)
    expected = workflow.source_rows((REAL / 'inputs/PRODUCTION_PLAN.md').read_text())
    run.inputs.delivery_requirements = [DeliveryRequirement(logical_path='readiness.json', json_schema=workflow.delivery_schema(expected))]
    await svc.runs.create_run(run)
    raw = (REAL / 'readiness.json').read_bytes()
    artifact = await svc.artifacts.publish(run.run_id, 'readiness.json', raw, agent_id='builder', task_id='t1')
    assert artifact.sha256 == 'dd68d14539ccb1549eb1abc539eab12c54f398a2a52fccd489902941d6d531ee'
    rt = svc.manager._build_runtime(run, svc.config)
    try:
        for data in detail['tasks']:
            task = TaskState.model_validate(data); rt.tasks[task.spec.id] = task
            await svc.runs.upsert_task(task)
        task = rt.tasks['t1']
        ctx = SessionContext(rt=rt, agent=rt.agents['builder'], mode='task', task=task, tools=rt.agents['builder'].tools)
        reply = await ToolGateway(ctx).call('finish_task', {'summary': task.result.summary})
        assert reply.startswith('REJECTED: requester delivery requirements failed') and 'evidence_quote' in reply and ctx.finished is None
        # A reviewer can invoke the registered requester schema directly. The
        # preserved v1 artifact is expected to fail the contract, but must not
        # be blocked by a model-generated/malformed schema.
        reviewer_ctx = SessionContext(rt=rt, agent=rt.agents['reviewer'], mode='task', task=rt.tasks['t2'], tools=rt.agents['reviewer'].tools)
        review_check = await ToolGateway(reviewer_ctx).call('run_check', {
            'kind': 'json_schema', 'artifact_id': 'readiness.json', 'revision': 1,
        })
        assert '"status": "fail"' in review_check
        assert 'invalid schema' not in review_check
        assert 'repair_hint' in review_check and '失敗したフィールドだけ' in review_check
        assert await auto_finish_if_outputs_published(ctx, 'rechecking actual prior completion') is None
        assert len(failures(await verify_delivery(rt))) == 1
        # The real saved run already consumed these calls. Exhaust that actual
        # budget so deterministic finalization cannot invoke another model.
        rt.config.limits.max_model_calls = run.usage.model_calls
        await svc.manager._finish(rt, run.status)
        saved = await svc.runs.get_run(run.run_id)
        assert saved.status == 'partial' and 'requester delivery requirements failed' in saved.blocked_reason
        assert saved.final_report['evidence']['delivery_checks'][-1]['result']['status'] == 'fail'
        report = await svc.artifacts.get(run.run_id, 'final-report.md')
        assert b'Requester delivery requirements' in svc.artifacts.read_bytes(report)
        assert svc.artifacts.read_bytes(artifact) == raw
    finally:
        await rt.providers.aclose(); await svc.stop()


async def test_original_attachment_reads_are_hashed_and_do_not_create_artifact_revisions(tmp_path):
    access, _ = provision(tmp_path)
    svc = await AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access).start()
    run = Run.model_validate_json((REAL / 'run.json').read_text()); await svc.runs.create_run(run)
    rt = svc.manager._build_runtime(run, svc.config)
    try:
        ctx = SessionContext(rt=rt, agent=rt.agents['reviewer'], mode='task', tools=rt.agents['reviewer'].tools)
        gateway = ToolGateway(ctx)
        original = next(f for f in run.inputs.files if f['name'] == 'PRODUCTION_PLAN.md')['content']
        hint = await gateway.call('read_artifact', {'artifact_id': 'PRODUCTION_PLAN.md', 'revision': 1})
        assert hint.startswith('NOT FOUND') and 'read_input_file' in hint
        response = await gateway.call('read_input_file', {'name': 'PRODUCTION_PLAN.md', 'max_chars': 1000})
        assert response.endswith(original[:1000]) and hashlib.sha256(original.encode()).hexdigest() in response
        assert await svc.artifacts.list(run.run_id) == []
        events = await svc.events.list(run.run_id)
        assert any(e.type == 'input.read' and e.payload['end_char'] == 1000 for e in events)
    finally:
        await rt.providers.aclose(); await svc.stop()


async def test_hostile_pattern_on_actual_source_is_bounded_in_a_real_process():
    # Deliberate hostile constraint, actual source bytes: exercises a core
    # availability boundary without creating dummy business records.
    raw = (REAL / 'readiness.json').read_bytes()[:1000]
    async with asyncio.timeout(7):
        result = await isolated_check('regex_count', raw, {'pattern': r'([\s\S]+)+\x00'})
    assert result['status'] == 'blocked' and 'resource limit' in result['problems'][0]
