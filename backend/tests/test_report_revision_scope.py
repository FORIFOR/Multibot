"""Replay a real partial run: r1 was rejected; published r3 was never reviewed."""
import json
from copy import deepcopy
from pathlib import Path

from agentteam.projections.views import artifact_review_ledger


SOURCE = Path(__file__).resolve().parents[2] / "docs/evidence/trading-plan-2026-09-20/unreviewed-r3.json"


def test_rejected_previous_revision_does_not_reject_current_artifacts():
    evidence = json.loads(SOURCE.read_text())
    ledger = artifact_review_ledger(evidence)
    current = [a for a in ledger if a["artifact_id"] in ("architecture.md", "decisions.md")]
    assert len(current) == 2
    assert all(a["revision"] == 3 for a in current)
    assert all(a["review_state"] == "unreviewed" and a["review_seq"] is None and not a["results"] for a in current)


def test_recorded_review_matches_original_revision_and_bytes_only():
    evidence = json.loads(SOURCE.read_text())
    review = evidence["reviews"][0]
    # Replay the actual r1 references saved in the submitted review event.
    original = deepcopy(evidence)
    original["artifacts"] = [{**ref, "task_id": review["target_task_id"]} for ref in review["target_artifacts"]]
    ledger = artifact_review_ledger(original)
    assert len(ledger) == 2
    assert all(a["review_state"] == "review_recorded" and a["review_seq"] == review["seq"] for a in ledger)
    assert all(a["results"][0]["status"] == "fail" for a in ledger)
    # A revision label alone cannot transfer a verdict to the real r3 bytes.
    for artifact in original["artifacts"]:
        artifact["sha256"] = next(a["sha256"] for a in evidence["artifacts"] if a["artifact_id"] == artifact["artifact_id"])
    assert all(a["review_state"] == "unreviewed" for a in artifact_review_ledger(original))


def test_legacy_review_without_revision_refs_is_not_current_verification():
    evidence = json.loads(SOURCE.read_text())
    for review in evidence["reviews"]:
        review.pop("target_artifacts")
    assert all(a["review_state"] == "unreviewed" for a in artifact_review_ledger(evidence))
