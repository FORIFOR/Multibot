"""Model answers in the wrong JSON shape are retried or dropped; they never fail a run as an internal error."""
import json

import pytest

from agentteam.providers.fake_driver import text_response
from agentteam.runtime.planner import _extract_json, _normalize_report
from tests.conftest import PLAN, default_script


@pytest.mark.parametrize("text", ['[{"summary": "x"}]', '"text"', "3", "null"])
def test_non_object_json_is_a_value_error(text):
    with pytest.raises(ValueError):
        _extract_json(text)


def test_object_inside_prose_is_still_extracted():
    assert _extract_json('Here it is: {"a": 1} done') == {"a": 1}


def test_report_is_normalized_to_the_reader_shape():
    out = _normalize_report({"summary": "ok", "deliverables": ["index.html", {"artifact_id": "a", "revision": "2"},
                                                               {"artifact_id": "b", "revision": True},
                                                               {"artifact_id": "c", "revision": 3, "note": 5}],
                             "verified": "all", "unresolved": ["x", 1], "extra": "dropped"})
    assert out == {"summary": "ok", "deliverables": [{"artifact_id": "c", "revision": 3, "note": ""}],
                   "verified": [], "unresolved": ["x"], "next_steps": []}
    with pytest.raises(ValueError):
        _normalize_report({"summary": ["not", "text"]})


async def test_report_answer_that_is_a_list_keeps_the_finished_run(harness):
    def script(req):
        if req.metadata.get("mode") == "report":
            return text_response('[{"summary": "a list, not an object"}]')
        return default_script(req)

    async with harness(script=script) as h:
        run = await h.run_goal()
        assert str(run.status) == "completed", run.blocked_reason
        assert run.final_report["narrative"] is None
        failed = await h.events.list(run.run_id, types=["model.failed"])
        assert any(e.payload.get("stage") == "report" for e in failed)


async def test_report_with_wrong_field_types_is_normalized(harness):
    def script(req):
        if req.metadata.get("mode") == "report":
            return text_response(json.dumps({"summary": "done", "deliverables": ["index.html"], "verified": "everything",
                                             "unresolved": ["posts need a human read"], "next_steps": None}))
        return default_script(req)

    async with harness(script=script) as h:
        run = await h.run_goal()
        assert str(run.status) == "completed", run.blocked_reason
        n = run.final_report["narrative"]
        assert n["deliverables"] == [] and n["verified"] == [] and n["next_steps"] == []
        assert n["unresolved"] == ["posts need a human read"]


async def test_plan_answer_with_non_object_tasks_is_retried(harness):
    calls = {"plan": 0}

    def script(req):
        if req.metadata.get("mode") == "plan":
            calls["plan"] += 1
            if calls["plan"] == 1:
                return text_response(json.dumps({**PLAN, "tasks": ["t1", "t2"]}, ensure_ascii=False))
        return default_script(req)

    async with harness(script=script) as h:
        run = await h.run_goal()
        assert calls["plan"] >= 2
        rejected = await h.events.list(run.run_id, types=["plan.rejected"])
        assert rejected and "unparseable plan" in rejected[0].payload["errors"][0]
        assert str(run.status) != "failed" or "internal error" not in (run.blocked_reason or "")
