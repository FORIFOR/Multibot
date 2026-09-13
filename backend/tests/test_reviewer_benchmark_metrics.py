"""A quoted mistake is not proof that the reviewer detected it."""
import argparse
import json

from scripts.reviewer_catch_rate import DOCS, candidate_mentions
from scripts.summarize_benchmark import main


def test_repeating_the_wrong_memo_never_becomes_a_detection_score():
    for doc in DOCS.values():
        result = candidate_mentions(doc["memo"], doc["errors"])
        assert result["keyword_hit_count"] >= 9
        assert result["caught"] is None
        assert result["catch_rate"] is None
        assert result["grading_status"] == "pending_source_review"


def test_summary_does_not_promote_legacy_keyword_counts(tmp_path, capsys):
    results = tmp_path / "reviewer.jsonl"
    results.write_text(json.dumps({"doc": "A", "planted": 10, "caught": 10,
                                  "caught_detail": {"company_name": True}, "status": "completed"}) + "\n")
    assert main(argparse.Namespace(results=[], reviewer=str(results))) == 0
    output = capsys.readouterr().out
    assert "catch rate not measured" in output
    assert "legacy rows" in output
    assert "100%" not in output
    assert "10 caught" not in output
