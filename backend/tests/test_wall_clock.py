"""The run's wall clock bounds every model call, including planning and the final report."""
import asyncio
import time

from tests.conftest import FAKE_CONFIG, default_script

SHORT = FAKE_CONFIG.replace("timeout_seconds: 120", "timeout_seconds: 1")


async def test_slow_planning_call_is_stopped_at_the_run_deadline(harness):
    assert SHORT != FAKE_CONFIG

    async def script(req):
        if req.metadata.get("mode") == "plan":
            await asyncio.sleep(10)
        return default_script(req)

    async with harness(script=script, config_yaml=SHORT) as h:
        started = time.monotonic()
        run = await h.run_goal()
        elapsed = time.monotonic() - started
        assert elapsed < 5, elapsed
        assert str(run.status) == "failed" and "wall-clock" in (run.blocked_reason or ""), run.blocked_reason
        failed = await h.events.list(run.run_id, types=["model.failed"])
        assert any(e.payload.get("kind") == "timeout" and "wall-clock" in e.payload["message"] for e in failed)


async def test_report_after_the_deadline_keeps_the_evidence_report(harness):
    async def script(req):
        if req.metadata.get("mode") == "report":
            await asyncio.sleep(10)
        return default_script(req)

    async with harness(script=script, config_yaml=FAKE_CONFIG.replace("timeout_seconds: 120", "timeout_seconds: 3")) as h:
        started = time.monotonic()
        run = await h.run_goal()
        assert time.monotonic() - started < 8
        assert run.final_report is not None and run.final_report["narrative"] is None
        assert run.final_report["deliverables"], "the evidence-only report still lists the published files"
