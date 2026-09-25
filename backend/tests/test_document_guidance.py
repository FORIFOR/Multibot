"""Guidance written for the readiness acceptance series must not reach other document requests."""
import json
from pathlib import Path

from agentteam.api.service import AppService
from agentteam.contracts import Run, RunInputs
from agentteam.runtime.context import SessionContext
from agentteam.runtime.planner import document_plan
from agentteam.runtime.scheduler import Scheduler
from agentteam.runtime.worker import build_system_prompt, document_reviewer_tool_nudge

ROOT = Path(__file__).resolve().parents[2]
SERIES_ONLY = ["production_ready", "L3", "PRODUCTION_PLAN", "readiness.json", "evidence_quote"]


async def _guidance(tmp_path, logical_path, schema):
    svc = await AppService(tmp_path, config_yaml=(ROOT / 'docs/config/local-qwen35-9b-team.yaml').read_text()).start()
    try:
        inputs = RunInputs(text="議事メモの元資料", workflow='document', delivery_requirements=[
            {'logical_path': logical_path, 'input_format': 'json', 'json_schema': schema}])
        run, problems = await svc.manager.create_run("会議メモを要約して", inputs)
        rt = svc.manager._build_runtime(run, svc.config)
        plan = await document_plan(rt)
        rt.run.plan = plan
        await Scheduler(rt).init_from_plan()
        reviewer_task = rt.tasks[plan.tasks[1].id]
        reviewer = rt.agents[reviewer_task.spec.owner]
        ctx = SessionContext(rt, reviewer, 'task', reviewer_task, tools=reviewer.tools)
        criteria = " ".join(c.description for c in plan.tasks[0].acceptance)
        return criteria, build_system_prompt(ctx), await document_reviewer_tool_nudge(ctx, reviewer.tools, 1)
    finally:
        await svc.stop()


async def test_other_documents_get_general_review_guidance(tmp_path):
    criteria, prompt, nudge = await _guidance(tmp_path, 'minutes.json', {'type': 'object'})
    for text in (criteria, prompt, nudge):
        for term in SERIES_ONLY:
            assert term not in text, (term, text[:200])
    assert "## Document review only" in prompt and "json_schema" in prompt
    assert "Missing required content is a failure" in criteria


async def test_readiness_series_keeps_its_guidance(tmp_path):
    criteria, prompt, nudge = await _guidance(tmp_path, 'readiness.json', {'type': 'object'})
    assert "production_ready=false, L3未達" in criteria
    assert "evidence_quote field is required to remain the exact English" in prompt
    assert "PRODUCTION_PLAN.md" in nudge
    assert "## Readiness assessment series" in prompt and "production_ready=false" in prompt


def test_bundled_role_prompts_carry_no_series_guidance():
    for name in ("builder.md", "reviewer.md", "master.md", "researcher.md", "reporter.md"):
        text = (ROOT / "backend/agentteam/prompts" / name).read_text()
        for term in SERIES_ONLY:
            assert term not in text, (name, term)
