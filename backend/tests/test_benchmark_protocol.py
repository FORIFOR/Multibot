"""Review participation checks against actual saved provider events."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('benchmark', ROOT / 'backend/scripts/benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_local_team_mode_does_not_imply_independent_review():
    events = json.loads((ROOT / 'docs/evidence/local-qwen25-7b-2026-09-14/team-pilot-protocol-events.json').read_text())
    result = benchmark.protocol_evidence(events)
    assert result['model_actors'] == ['master']
    assert result['review_submissions'] == 0
    assert result['independent_review_submissions'] == 0


def test_real_research_reviews_are_counted_without_claiming_success():
    events = [json.loads(line) for line in (ROOT / 'docs/evidence/scenarios/research2/events.jsonl').read_text().splitlines()]
    result = benchmark.protocol_evidence(events)
    assert result['independent_review_submissions'] == 2
    assert result['independently_reviewed_tasks'] == ['t1', 't5']


def test_campaign_covers_existing_fifty_tasks_in_both_modes():
    spec = importlib.util.spec_from_file_location('campaign', ROOT / 'backend/scripts/local_benchmark_campaign.py')
    campaign = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(campaign)
    jobs = list(campaign.jobs())
    assert len(jobs) == len(set(jobs)) == 300
    assert len({task for task, _, _ in jobs}) == 50
    assert {rep for _, rep, _ in jobs} == {1, 2, 3}
    assert sum(mode == 'team' for _, _, mode in jobs) == 150
