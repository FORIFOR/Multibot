"""Single-agent baseline: defaults.team_mode=single → no planning call, no review, one task for the builder-role agent."""
import re

from agentteam.providers.fake_driver import text_response, tool_response
from tests.conftest import FAKE_CONFIG, Harness, turn_of

SINGLE_CONFIG = (FAKE_CONFIG
                 .replace("defaults: {connection_id: fake, model: fake-model, language: ja, timezone: Asia/Tokyo}",
                          "defaults: {connection_id: fake, model: fake-model, language: ja, timezone: Asia/Tokyo, team_mode: single}")
                 .replace("id: master, role: master, enabled: true", "id: master, role: master, enabled: false")
                 .replace("id: researcher, role: researcher, enabled: true", "id: researcher, role: researcher, enabled: false")
                 .replace("id: reviewer, role: reviewer, enabled: true", "id: reviewer, role: reviewer, enabled: false"))

modes_seen: list[str] = []


def solo_script(req):
    md = req.metadata
    modes_seen.append(md.get("mode"))
    turn = turn_of(req)
    seq = [tool_response("workspace_write", {"path": "answer.md", "content": "# Answer\n\nbody"}),
           tool_response("publish_artifact", {"path": "answer.md"}),
           tool_response("finish_task", {"summary": "answer.md published", "verified": ["headings"], "unverified": []})]
    return seq[turn] if turn < len(seq) else text_response("done")


async def test_single_agent_run_completes_without_planning_or_review(tmp_path):
    modes_seen.clear()
    async with Harness(tmp_path, script=solo_script, config_yaml=SINGLE_CONFIG) as h:
        run = await h.run_goal("Write answer.md")
        assert run.status == "completed", run.blocked_reason
        tasks = await h.runs.list_tasks(run.run_id)
        assert [t.spec.id for t in tasks] == ["t1"] and tasks[0].spec.owner == "builder" and tasks[0].spec.output_paths == ["*"]
        assert "plan" not in modes_seen and "milestone" not in modes_seen, modes_seen
        evs = await h.events.list(run.run_id)
        acc = next(e for e in evs if e.type == "plan.accepted")
        assert acc.payload["mode"] == "single_agent"
        assert not any(e.type == "review.submitted" for e in evs)
        assert await h.artifacts.get(run.run_id, "answer.md") is not None


def rejects_without_publish_script(req):
    turn = turn_of(req)
    seq = [tool_response("finish_task", {"summary": "done?"}),
           tool_response("workspace_write", {"path": "x.md", "content": "x"}),
           tool_response("publish_artifact", {"path": "x.md"}),
           tool_response("finish_task", {"summary": "x.md published"})]
    return seq[turn] if turn < len(seq) else text_response("done")


async def test_single_agent_finish_needs_at_least_one_artifact(tmp_path):
    async with Harness(tmp_path, script=rejects_without_publish_script, config_yaml=SINGLE_CONFIG) as h:
        run = await h.run_goal("Write something")
        assert run.status == "completed"
        evs = await h.events.list(run.run_id)
        texts = [e.payload.get("result_preview", "") for e in evs if e.type == "tool.called" and e.payload.get("tool") == "finish_task"]
        assert any(re.search(r"REJECTED: nothing published", t) for t in texts), texts
