"""Milestone replanning: after the DAG finishes, the Master may add tasks (bounded by max_replans)."""
from agentteam.providers.fake_driver import text_response, tool_response
from tests.conftest import FAKE_CONFIG, Harness, default_script, turn_of

PLAN1 = {"goal": "LP", "assumptions": [], "agents": ["master", "builder"], "tasks": [
    {"id": "t1", "owner": "builder", "objective": "index.html を作る", "depends_on": [], "output_paths": ["index.html"],
     "acceptance": [{"id": "c1", "description": "html_basic pass", "check_kind": "programmatic"}]}]}
HTML = "<html><head><title>D</title><meta name='viewport' content='w'></head><body><h1>x</h1></body></html>"


def script(req):
    md = req.metadata
    a, mode, attempt, turn = md.get("agent_id"), md.get("mode"), md.get("attempt", 1), turn_of(req)
    if mode == "plan":
        import json
        return text_response(json.dumps(PLAN1))
    if mode == "milestone":
        seq = [tool_response("create_task", {"id": "t2", "owner": "builder", "objective": "posts.md を追加", "depends_on": ["t1"],
                                             "output_paths": ["posts.md"], "acceptance": [{"id": "c2", "description": "3案", "check_kind": "model_review"}]}),
               tool_response("create_task", {"id": "t3", "owner": "reviewer", "objective": "t1 を検証", "depends_on": ["t1"],
                                             "output_paths": [], "acceptance": [{"id": "c3", "description": "verdict recorded", "check_kind": "programmatic"}]}),
               tool_response("finish_task", {"summary": "posts.md が不足していたので追加、t1 の検証も追加"})]
        return seq[turn] if turn < len(seq) else text_response("done")
    if a == "reviewer" and mode == "task":
        seq = [tool_response("submit_review", {"target_task_id": "t1", "results": [{"acceptance_id": "c1", "status": "pass", "evidence": "read"}]}),
               tool_response("finish_task", {"summary": "pass"})]
        return seq[turn] if turn < len(seq) else text_response("done")
    if a == "builder" and mode == "task":
        task_hint = "posts.md" if "posts.md" in req.messages[0]["content"][0]["text"] else "index.html"
        content = "# P\n1\n2\n3" if task_hint == "posts.md" else HTML
        seq = [tool_response("workspace_write", {"path": task_hint, "content": content}),
               tool_response("publish_artifact", {"path": task_hint}),
               tool_response("finish_task", {"summary": f"{task_hint} published"})]
        return seq[turn] if turn < len(seq) else text_response("done")
    return default_script(req)


async def test_master_milestone_adds_a_task_and_run_completes(tmp_path):
    async with Harness(tmp_path, script=script) as h:
        run = await h.run_goal("LP")
        assert run.status == "completed", run.blocked_reason
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert set(tasks) == {"t1", "t2", "t3"} and tasks["t2"].status == "accepted"
        assert tasks["t3"].status == "accepted", "a reviewer task added at a milestone for an accepted task must run"
        evs = await h.events.list(run.run_id)
        ms = [e for e in evs if e.type == "plan.milestone"]
        assert ms and ms[0].payload["added_tasks"] == ["t2", "t3"]
        assert len(ms) <= 2  # bounded by max_replans
        assert await h.artifacts.get(run.run_id, "posts.md") is not None


async def test_milestone_respects_max_replans_zero(tmp_path):
    cfg = FAKE_CONFIG.replace("max_revision_rounds: 2,", "max_revision_rounds: 2, max_replans: 0,")
    async with Harness(tmp_path, script=script, config_yaml=cfg) as h:
        run = await h.run_goal("LP")
        assert run.status == "completed"
        evs = await h.events.list(run.run_id)
        assert not any(e.type == "plan.milestone" for e in evs)
        assert {t.spec.id for t in await h.runs.list_tasks(run.run_id)} == {"t1"}


PLAN_DIAMOND = {"goal": "research", "assumptions": [], "agents": ["master", "builder", "reviewer"], "tasks": [
    {"id": "t1", "owner": "builder", "objective": "research.md", "depends_on": [], "output_paths": ["research.md"],
     "acceptance": [{"id": "c1", "description": "has headings", "check_kind": "programmatic"}]},
    {"id": "t2", "owner": "builder", "objective": "verification.md from t1", "depends_on": ["t1"], "output_paths": ["verification.md"],
     "acceptance": [{"id": "c2", "description": "has headings", "check_kind": "programmatic"}]},
    {"id": "t3", "owner": "reviewer", "objective": "review t1 and t2", "depends_on": ["t1", "t2"], "output_paths": [],
     "acceptance": [{"id": "c3", "description": "verdicts recorded", "check_kind": "programmatic"}]}]}


def diamond_script(req):
    import json
    md = req.metadata
    a, mode, turn = md.get("agent_id"), md.get("mode"), turn_of(req)
    if mode == "plan":
        return text_response(json.dumps(PLAN_DIAMOND))
    if mode == "milestone":
        return tool_response("finish_task", {"summary": "complete"}) if turn == 0 else text_response("done")
    if a == "builder" and mode == "task":
        path = "verification.md" if "verification.md" in req.messages[0]["content"][0]["text"] else "research.md"
        seq = [tool_response("workspace_write", {"path": path, "content": "# doc\n\nbody"}), tool_response("publish_artifact", {"path": path}),
               tool_response("finish_task", {"summary": path})]
        return seq[turn] if turn < len(seq) else text_response("done")
    if a == "reviewer" and mode == "task":
        seq = [tool_response("submit_review", {"target_task_id": "t1", "results": [{"acceptance_id": "c1", "status": "pass", "evidence": "read"}]}),
               tool_response("submit_review", {"target_task_id": "t2", "results": [{"acceptance_id": "c2", "status": "pass", "evidence": "read"}]}),
               tool_response("finish_task", {"summary": "pass"})]
        return seq[turn] if turn < len(seq) else text_response("done")
    return default_script(req)


async def test_dependent_task_starts_while_dependency_awaits_review(tmp_path):
    """t2 depends on t1, and the reviewer t3 depends on both: t2 must start once t1's outputs are published
    (review_pending), otherwise the DAG deadlocks (found by the real research scenario)."""
    async with Harness(tmp_path, script=diamond_script) as h:
        run = await h.run_goal("research")
        assert run.status == "completed", run.blocked_reason
        tasks = {t.spec.id: t.status for t in await h.runs.list_tasks(run.run_id)}
        assert tasks == {"t1": "accepted", "t2": "accepted", "t3": "accepted"}


async def test_milestone_skipped_when_budget_cannot_afford_one_session(tmp_path):
    """Both research re-runs ended partial because milestone-added tasks failed on budget. With less than one agent
    session's budget left, the Master is not asked to extend the plan and the record says why."""
    cfg = FAKE_CONFIG.replace("max_revision_rounds: 2,", "max_revision_rounds: 2, max_session_cost_usd: 100.0,")
    async with Harness(tmp_path, script=script, config_yaml=cfg) as h:
        run = await h.run_goal("LP")
        assert run.status == "completed"
        evs = await h.events.list(run.run_id)
        ms = [e for e in evs if e.type == "plan.milestone"]
        assert len(ms) == 1 and ms[0].payload["skipped"] == "limits" and "budget" in ms[0].payload["reason"]
        assert {t.spec.id for t in await h.runs.list_tasks(run.run_id)} == {"t1"}, "no task was added without a Master session"


async def test_milestone_skipped_when_model_calls_cannot_afford_one_session(tmp_path):
    """lp re-run 3: two milestone rounds of polish after every planned task was accepted ended at max_model_calls."""
    cfg = FAKE_CONFIG.replace("max_revision_rounds: 2,", "max_revision_rounds: 2, max_session_turns: 1000,")
    async with Harness(tmp_path, script=script, config_yaml=cfg) as h:
        run = await h.run_goal("LP")
        assert run.status == "completed"
        ms = [e for e in await h.events.list(run.run_id) if e.type == "plan.milestone"]
        assert len(ms) == 1 and ms[0].payload["skipped"] == "limits" and "model calls" in ms[0].payload["reason"]


async def test_partial_run_carries_a_reason_naming_the_unaccepted_task(tmp_path):
    def failing_script(req):
        md = req.metadata
        if md.get("agent_id") == "builder" and md.get("mode") == "task" and "posts.md" in req.messages[0]["content"][0]["text"]:
            raise RuntimeError("simulated provider outage")
        return script(req)
    async with Harness(tmp_path, script=failing_script) as h:
        run = await h.run_goal("LP")
        assert run.status in ("partial", "failed"), run.status
        assert run.blocked_reason and "t2" in run.blocked_reason, run.blocked_reason
