"""Regression checks against recorded real-provider results, with no mock provider."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("benchmark_runner", ROOT / "backend/scripts/benchmark.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ROWS = [json.loads(line) for line in (ROOT / "docs/evidence/benchmark-2026-09-13/team-results.jsonl").read_text().splitlines()]
JOBS = [(task, rep) for rep in range(1, 4) for task in runner.T.TASKS]


def test_actual_provider_limit_includes_partial_review_failures():
    affected = [r for r in ROWS if runner.provider_exhausted(r)]
    assert len(affected) == 102
    assert sum(r["status"] == "failed" for r in affected) == 100
    assert sum(r["status"] == "partial" for r in affected) == 2


def test_resume_does_not_rerun_recorded_business_outcomes():
    assert runner.pending_jobs(JOBS, ROWS, False) == []
    pending = runner.pending_jobs(JOBS, ROWS, True)
    recorded = {(r["task"], r["rep"]): r for r in ROWS}
    assert len(pending) == 102
    assert all(recorded[t["id"], rep]["status"] != "completed" for t, rep in pending)
    assert ("doc-release-notes", 1) not in {(t["id"], rep) for t, rep in pending}


def test_resume_keeps_unattempted_repetitions():
    first_repetition = [r for r in ROWS if r["rep"] == 1]
    pending = runner.pending_jobs(JOBS, first_repetition, False)
    assert len(pending) == 100
    assert {rep for _, rep in pending} == {2, 3}
