"""Aggregation regression using existing real-provider records only."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('summary', ROOT / 'backend/scripts/summarize_benchmark.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def recorded(path):
    return [json.loads(line) for line in (ROOT / 'docs/evidence' / path).read_text().splitlines()]


def test_overlapping_real_snapshots_keep_history_without_double_counting():
    original = recorded('benchmark-2026-09-13/team-results.jsonl')
    latest = recorded('readiness-2026-09-14/team-latest-results.jsonl')
    attempts = summary.unique_attempts(original + latest)
    assert len(attempts) == 252
    pairs = summary.latest_pairs(attempts)
    assert len(pairs) == 150
    stats = summary.stats(pairs)
    assert (stats['completed'], stats['partial'], stats['failed']) == (69, 5, 76)
    assert summary.stats(attempts)['cost_total'] > stats['cost_total']


def test_single_agent_pilots_are_not_extra_task_pairs():
    raw = recorded('benchmark-2026-09-13/single-results.jsonl')
    assert len(summary.unique_attempts(raw)) == 152
    pairs = summary.latest_pairs(raw)
    assert len(pairs) == 150
    assert summary.stats(pairs)['correct'] == 146
