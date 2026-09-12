"""Approval pause/resume, cancel + resume, workspace boundary, tool-scope denial, snapshot isolation."""
import asyncio
import json

import pytest

from agentteam.providers.fake_driver import text_response, tool_response
from tests.conftest import Harness, default_script, turn_of


def builder_with(steps_attempt1, steps_attempt2=None):
    def script(req):
        md = req.metadata
        if md.get("agent_id") == "builder" and md.get("mode") == "task":
            seq = steps_attempt1 if md.get("attempt", 1) == 1 else (steps_attempt2 or steps_attempt1)
            t = turn_of(req)
            return seq[t] if t < len(seq) else text_response("done")
        return None
    return script


GOOD_BUILD = [
    tool_response("workspace_write", {"path": "index.html", "content": "<html><head><title>D</title><meta name='viewport' content='w'></head><body><h1>x</h1><a href='https://e.com'>e</a></body></html>"}),
    tool_response("publish_artifact", {"path": "index.html"}),
    tool_response("workspace_write", {"path": "posts.md", "content": "# P\n1\n2\n3"}),
    tool_response("publish_artifact", {"path": "posts.md"}),
    tool_response("finish_task", {"summary": "ok"}),
]


def reviewer_pass(req):
    md = req.metadata
    if md.get("agent_id") == "reviewer" and md.get("mode") == "task":
        seq = [tool_response("run_check", {"kind": "html_basic", "artifact_id": "index.html"}),
               tool_response("submit_review", {"target_task_id": "t2", "results": [
                   {"acceptance_id": "c2", "status": "pass", "evidence": "check"}, {"acceptance_id": "c3", "status": "pass", "evidence": "read"}]}),
               tool_response("finish_task", {"summary": "pass"})]
        t = turn_of(req)
        return seq[t] if t < len(seq) else text_response("done")
    return None


def combine(*scripts):
    def s(req):
        for sc in scripts:
            r = sc(req)
            if r is not None:
                return r
        return default_script(req)
    return s


async def test_workspace_boundary_and_tool_scope_denied(tmp_path):
    steps = [tool_response("workspace_read", {"path": "../t1/brief.md"}),           # other task's private workspace
             tool_response("workspace_write", {"path": "/tmp/evil.txt", "content": "x"}),
             tool_response("sandbox_run", {"command": "sudo ls"}),
             tool_response("web_fetch", {"url": "http://169.254.169.254/latest/meta-data"}),  # not in builder tools → scope denial
             *GOOD_BUILD]
    async with Harness(tmp_path, script=combine(builder_with(steps), reviewer_pass)) as h:
        run = await h.run_goal()
        assert run.status == "completed"
        evs = await h.events.list(run.run_id)
        tool_evs = [e for e in evs if e.type == "tool.called" and e.actor_id == "builder"]
        previews = [e.payload["result_preview"] for e in tool_evs]
        assert previews[0].startswith("DENIED (path_scope)")
        assert previews[1].startswith("DENIED (path_scope)")
        assert previews[2].startswith("DENIED")
        denied = [e for e in evs if e.type == "policy.denied"]
        assert denied and denied[0].payload["tool"] == "web_fetch" and denied[0].payload["code"] == "tool_scope"


async def test_approval_pauses_run_then_resumes_after_resolution(tmp_path):
    steps = [tool_response("request_approval", {"action": "post_to_x", "description": "投稿する", "payload": {"text": "hello"}, "estimated_cost_usd": 0}),
             tool_response("report_blocker", {"reason": "approval pending", "needed": "human decision"})]
    async with Harness(tmp_path, script=combine(builder_with(steps, GOOD_BUILD), reviewer_pass), approval_wait=0.5) as h:
        run, problems = await h.manager.create_run("post something")
        assert not problems
        h.manager.start(run.run_id)
        run = await h.manager.wait(run.run_id)
        assert run.status == "approval_required", run.status
        aps = await h.runs.list_approvals(run.run_id, status="pending")
        assert len(aps) == 1 and aps[0].payload_hash
        # tamper: wrong hash is refused
        with pytest.raises(ValueError):
            await h.manager.resolve_approval(aps[0].approval_id, "approve", expected_hash="0" * 64)
        ap = await h.manager.resolve_approval(aps[0].approval_id, "approve", expected_hash=aps[0].payload_hash, nonce=aps[0].nonce)
        assert ap.status == "approved"
        run = await h.manager.wait(run.run_id)  # auto-resumed
        assert run.status == "completed", run.blocked_reason
        evs = await h.events.list(run.run_id)
        types = [e.type for e in evs]
        assert "approval.requested" in types and "approval.resolved" in types and "run.resumed" in types
        # no external side effect was executed by the runtime itself
        assert not any(e.type == "tool.called" and e.payload["tool"] == "post_to_x" for e in evs)


async def test_cancel_then_resume_keeps_accepted_work(tmp_path):
    steps1 = [tool_response("read_messages", {"wait_seconds": 30})]  # will block; we cancel meanwhile
    async with Harness(tmp_path, script=combine(builder_with(steps1, GOOD_BUILD), reviewer_pass)) as h:
        run, _ = await h.manager.create_run("build")
        h.manager.start(run.run_id)
        for _ in range(200):
            await asyncio.sleep(0.02)
            tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
            if tasks.get("t2") and tasks["t2"].status == "running":
                break
        assert await h.manager.cancel(run.run_id)
        run = await h.manager.wait(run.run_id)
        assert run.status == "cancelled"
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert tasks["t1"].status == "accepted" and tasks["t2"].status in ("cancelled", "interrupted")
        calls_before = len(h.provider.calls)
        await h.manager.resume(run.run_id)
        run = await h.manager.wait(run.run_id)
        assert run.status == "completed", run.blocked_reason
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert tasks["t1"].attempt == 1, "accepted research was not re-run"
        assert tasks["t2"].attempt == 2
        assert len(h.provider.calls) > calls_before
        brief = [m for m in await h.artifacts.list(run.run_id) if m.artifact_id == "brief.md"]
        assert len(brief) == 1


async def test_config_snapshot_survives_later_edits(tmp_path):
    async with Harness(tmp_path, script=combine(builder_with(GOOD_BUILD), reviewer_pass)) as h:
        run, _ = await h.manager.create_run("x")
        h.config.agents[2].model = "changed-later"  # edit "current" config after run creation
        h.manager.start(run.run_id)
        run = await h.manager.wait(run.run_id)
        assert run.status == "completed"
        assert run.config_snapshot["agents"]["builder"]["model"] == "fake-model"
        evs = await h.events.list(run.run_id, types=["model.called"])
        assert all(e.payload["model_requested"] == "fake-model" for e in evs)


async def test_fork_reuses_accepted_tasks_and_reruns_selected(tmp_path):
    async with Harness(tmp_path, script=combine(builder_with(GOOD_BUILD), reviewer_pass)) as h:
        run = await h.run_goal()
        assert run.status == "completed"
        child = await h.manager.fork(run.run_id, overrides={"rerun_tasks": ["t2"]})
        await h.manager.start_fork(child.run_id)
        child = await h.manager.wait(child.run_id)
        assert child.status == "completed" and child.parent_run_id == run.run_id
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(child.run_id)}
        assert tasks["t1"].status == "accepted" and tasks["t1"].attempt == 1
        assert tasks["t2"].attempt == 1 and tasks["t3"].attempt == 1
        evs = await h.events.list(child.run_id, types=["model.called"])
        assert not any(e.actor_id == "researcher" for e in evs), "kept task must not call the model again"
        assert await h.artifacts.get(child.run_id, "brief.md") is not None


async def test_master_exception_accepts_partial_when_worker_blocks(tmp_path):
    steps = [tool_response("report_blocker", {"reason": "brief lacks target audience", "needed": "audience"})]

    def master_exc(req):
        md = req.metadata
        if md.get("agent_id") == "master" and md.get("mode") == "exception":
            seq = [tool_response("update_task", {"task_id": "t2", "action": "accept_partial", "note": "need audience from user"}),
                   tool_response("finish_task", {"summary": "partial"})]
            t = turn_of(req)
            return seq[t] if t < len(seq) else text_response("done")
        return None
    async with Harness(tmp_path, script=combine(master_exc, builder_with(steps))) as h:
        run = await h.run_goal()
        assert run.status == "partial"
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert tasks["t2"].status == "partial" and tasks["t3"].status == "cancelled"
        assert run.final_report["status"] == "partial"
        evs = await h.events.list(run.run_id)
        assert any(e.type == "blocker.reported" for e in evs)


async def test_budget_exhaustion_ends_run_without_fabricated_success(tmp_path):
    async with Harness(tmp_path, config_yaml=Harness.__init__.__defaults__[1].replace("budget_usd: 5.0", "budget_usd: 0.004")) as h:
        run = await h.run_goal()
        assert run.status in ("failed", "partial")
        evs = await h.events.list(run.run_id)
        assert any(e.type in ("task.failed", "run.failed") and "budget" in json.dumps(e.payload) for e in evs)


async def test_auto_finish_when_outputs_published_but_no_finish_task(tmp_path):
    """Weaker models often publish everything and then stop talking; the runtime accepts published outputs and records it."""
    steps = [tool_response("workspace_write", {"path": "index.html", "content": "<html><head><title>D</title><meta name='viewport' content='w'></head><body><h1>x</h1></body></html>"}),
             tool_response("publish_artifact", {"path": "index.html"}),
             tool_response("workspace_write", {"path": "posts.md", "content": "# P\n1\n2\n3"}),
             tool_response("publish_artifact", {"path": "posts.md"}),
             text_response("All done."), text_response("Done."), text_response("Finished.")]
    async with Harness(tmp_path, script=combine(builder_with(steps), reviewer_pass)) as h:
        run = await h.run_goal()
        assert run.status == "completed", run.blocked_reason
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert tasks["t2"].status == "accepted" and "auto-finished" in tasks["t2"].result.summary
        evs = await h.events.list(run.run_id)
        assert any(e.type == "task.updated" and e.payload.get("action") == "auto_finish" for e in evs)
