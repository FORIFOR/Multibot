"""Summarize benchmark results.jsonl files (team and single-agent) into comparison tables.

    .venv/bin/python scripts/summarize_benchmark.py ~/.cache/agentteam-bench/team/results.jsonl ~/.cache/agentteam-bench/single/results.jsonl \
        [--reviewer ~/.cache/agentteam-bench/reviewer/results.jsonl]

Per mode: latest attempt per task/repetition, plus all-attempt accounting. Failed attempts remain in the ledger.
Pass original and regraded results separately: they are different grading versions, not new model runs.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(p: str) -> list[dict]:
    return [json.loads(l) for l in Path(p).expanduser().read_text().splitlines() if l.strip()]


def unique_attempts(rows: list[dict]) -> list[dict]:
    """Overlapping snapshots contain the same run; it must not be charged twice."""
    by_id = {}
    for i, r in enumerate(rows):
        by_id[r.get("run_id") or ("unidentified", i)] = r
    return list(by_id.values())


def latest_pairs(rows: list[dict]) -> list[dict]:
    latest = {}
    for r in rows:
        latest[r["task"], r["rep"]] = r
    return list(latest.values())


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "—"


def p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    cost = [r.get("usage", {}).get("cost_usd", 0.0) for r in rows]
    wall = [r.get("wall_s", 0) / 60 for r in rows]
    calls = [r.get("usage", {}).get("model_calls", 0) for r in rows]
    return {"runs": n, "completed": sum(1 for r in rows if r.get("status") == "completed"),
            "failed": sum(1 for r in rows if r.get("status") == "failed"),
            "partial": sum(1 for r in rows if r.get("status") == "partial"),
            "correct": sum(1 for r in rows if r.get("correct")), "false_completion": sum(1 for r in rows if r.get("false_completion")),
            "errors": sum(1 for r in rows if r.get("status") in ("error", "blocked")),
            "score": (sum(r.get("score", 0.0) for r in rows) / n) if n else 0.0,
            "retries": sum(r.get("retries", 0) for r in rows), "milestones": sum(r.get("milestones", 0) for r in rows),
            "cost_mean": (sum(cost) / n) if n else 0.0, "cost_p95": p95(cost), "cost_total": sum(cost),
            "wall_mean": (sum(wall) / n) if n else 0.0, "wall_p95": p95(wall), "calls_mean": (sum(calls) / n) if n else 0.0}


def row(label: str, s: dict) -> str:
    return (f"| {label} | {s['runs']} | {s['completed']} ({pct(s['completed'], s['runs'])}) | **{s['correct']} ({pct(s['correct'], s['runs'])})** | "
            f"{s['false_completion']} | {s['failed']} / {s['partial']} / {s['errors']} | {s['score']:.2f} | {s['retries']} | ${s['cost_mean']:.2f} / ${s['cost_p95']:.2f} | "
            f"{s['wall_mean']:.1f} / {s['wall_p95']:.1f} min |")


HEAD = ("| mode | runs | completed | correct (grader) | false completion (grader) | failed / partial / error-blocked | mean score | retries | cost mean / p95 | time mean / p95 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")


def main(args) -> int:
    modes: dict[str, list[dict]] = {}
    for p in args.results:
        rows = load(p)
        if not rows:
            continue
        modes.setdefault(rows[0].get("team_mode", "team"), []).extend(rows)
    print("## Attempt ledger\nSnapshots must be supplied oldest first; use one grading version per report.\n")
    print("| mode | unique attempts | task/repetition pairs | failed | partial | total list-price estimate |\n| --- | --- | --- | --- | --- | --- |")
    for m, rows in modes.items():
        attempts = unique_attempts(rows)
        latest = latest_pairs(attempts)
        s = stats(attempts)
        print(f"| {m} | {len(attempts)} | {len(latest)} | {s['failed']} | {s['partial']} | ${s['cost_total']:.2f} |")
        modes[m] = latest
    print("\n## Latest attempt per task/repetition\nEarlier failed attempts remain included in the ledger above. "
          "Completion and programmatic grading are separate measures; neither establishes enterprise reliability.\n" + HEAD)
    for m, rows in modes.items():
        print(row(m, stats(rows)))
    print("\n## By category\n| category | mode | runs | correct | false completion | mean score | cost mean | time mean |\n| --- | --- | --- | --- | --- | --- | --- | --- |")
    cats = sorted({r["category"] for rows in modes.values() for r in rows})
    for c in cats:
        for m, rows in modes.items():
            s = stats([r for r in rows if r["category"] == c])
            print(f"| {c} | {m} | {s['runs']} | {s['correct']} ({pct(s['correct'], s['runs'])}) | {s['false_completion']} | {s['score']:.2f} | ${s['cost_mean']:.2f} | {s['wall_mean']:.1f} min |")
    print("\n## By task\n| task | mode | correct | statuses | failed checks (first run with a failure) | cost mean | time mean |\n| --- | --- | --- | --- | --- | --- | --- |")
    tasks = sorted({r["task"] for rows in modes.values() for r in rows})
    for t in tasks:
        for m, rows in modes.items():
            rs = [r for r in rows if r["task"] == t]
            if not rs:
                continue
            s = stats(rs)
            fails = next((r.get("failed_checks") or [r.get("error", "")] for r in rs if not r.get("correct")), [])
            print(f"| {t} | {m} | {s['correct']}/{s['runs']} | {', '.join(r.get('status', '?') for r in rs)} | {'; '.join(str(f) for f in fails)[:160]} | ${s['cost_mean']:.2f} | {s['wall_mean']:.1f} min |")
    if args.reviewer:
        rows = load(args.reviewer)
        planted = sum(r.get("planted", 0) for r in rows)
        caught = sum(r.get("caught", 0) for r in rows)
        print(f"\n## Reviewer legacy regex matches (not validated detection rate)\n"
              "Includes pilot/repeated attempts. A mention of a wrong value can match without identifying an error. "
              "Precision and false-positive rate were not measured.\n"
              f"{len(rows)} runs, {planted} scored opportunities, {caught} regex matches ({pct(caught, planted)}), "
              f"runs completed {sum(1 for r in rows if r.get('status') == 'completed')}/{len(rows)}, "
              f"memo verbatim {sum(1 for r in rows if r.get('memo_verbatim'))}/{len(rows)}, "
              f"cost total ${sum(r.get('usage', {}).get('cost_usd', 0) for r in rows):.2f}")
        missed = defaultdict(int)
        for r in rows:
            for k, v in (r.get("caught_detail") or {}).items():
                if not v:
                    missed[f"{r['doc']}:{k}"] += 1
        if missed:
            print("missed: " + ", ".join(f"{k}×{v}" for k, v in sorted(missed.items())))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--reviewer", default=None)
    raise SystemExit(main(ap.parse_args()))
