"""Task ids come from model output (plans and master create_task) and become workspace directory names."""
import pytest

from agentteam.contracts import TaskSpec, task_id_problem
from agentteam.runtime.planner import plan_from_output, validate_plan
from agentteam.runtime.policy import PolicyViolation
from agentteam.runtime.scheduler import Scheduler
from tests.conftest import PLAN

ENABLED = ["master", "researcher", "builder", "reviewer"]
ROLES = {"master": "master", "researcher": "researcher", "builder": "builder", "reviewer": "reviewer"}
UNSAFE = ["../escape", "/Users/x", "a/b", "..", ".", ".hidden", "", "t 1", "a\\b", "x" * 65]


@pytest.mark.parametrize("tid", ["t1", "review-2", "t1.1", "T_3", "x" * 64])
def test_safe_task_ids_are_accepted(tid):
    assert task_id_problem(tid) is None


@pytest.mark.parametrize("tid", UNSAFE)
def test_unsafe_task_ids_are_named(tid):
    assert "task id" in task_id_problem(tid)


@pytest.mark.parametrize("tid", ["../escape", "/Users/x", "a/b"])
def test_plan_with_path_like_task_id_is_rejected(tid):
    data = {k: v for k, v in PLAN.items()}
    data["tasks"] = [dict(t) for t in PLAN["tasks"]]
    old = data["tasks"][0]["id"]
    data["tasks"][0]["id"] = tid
    for t in data["tasks"]:
        t["depends_on"] = [tid if d == old else d for d in t.get("depends_on", [])]
    errors = validate_plan(plan_from_output(data), ENABLED, ROLES, 12)
    assert any("task id" in e and repr(tid) in e for e in errors), errors


async def test_master_created_task_cannot_name_an_outside_directory(harness, tmp_path):
    async with harness() as h:
        run, problems = await h.manager.create_run("x")
        assert not problems
        rt = h.manager._build_runtime(run, h.config)
        try:
            scheduler = Scheduler(rt)
            spec = dict(id="../../outside", owner="builder", objective="write", depends_on=[], output_paths=["a.md"],
                        acceptance=[{"id": "c1", "description": "d", "check_kind": "model_review"}],
                        write_scope="workspaces/../../outside/")
            rejected = await scheduler.add_task(TaskSpec.model_validate(spec))
            assert rejected.startswith("REJECTED:") and "task id" in rejected
            bad_path = await scheduler.add_task(TaskSpec.model_validate({**spec, "id": "t9", "write_scope": "workspaces/t9/",
                                                                          "output_paths": ["../../x.md"]}))
            assert bad_path.startswith("REJECTED: invalid output path")
            assert rt.tasks == {}
            # Defence in depth: even an id that bypassed validation cannot create a directory outside workspaces/.
            for tid in ["../../outside", "/tmp/elsewhere", "a/b", "..", ""]:
                with pytest.raises(PolicyViolation) as ei:
                    rt.workspace(tid)
                assert ei.value.code == "path_scope" and ei.value.fatal
            assert not (tmp_path / "outside").exists()
            assert rt.workspace("t1").name == "t1"
        finally:
            await rt.providers.aclose()
