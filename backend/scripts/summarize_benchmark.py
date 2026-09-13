"""Summarize benchmark results.jsonl files (team and single-agent) into comparison tables.

    .venv/bin/python scripts/summarize_benchmark.py ~/.cache/agentteam-bench/team/results.jsonl ~/.cache/agentteam-bench/single/results.jsonl \
        [--reviewer ~/.cache/agentteam-bench/reviewer/results.jsonl]

Per mode: runs, completed, correct (grader), false completions (status completed but grader failed), mean score,
retries, cost and wall time (mean and p95). Then per category, then per task. Nothing is filtered.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(p: str) -> list[dict]:
    return [json.loads(l) for l in Path(p).expanduser().read_text().splitlines() if l.strip()]


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
            "correct": sum(1 for r in rows if r.get("correct")), "false_completion": sum(1 for r in rows if r.get("false_completion")),
            "errors": sum(1 for r in rows if r.get("status") in ("error", "blocked")),
            "score": (sum(r.get("score", 0.0) for r in rows) / n) if n else 0.0,
            "retries": sum(r.get("retries", 0) for r in rows), "milestones": sum(r.get("milestones", 0) for r in rows),
            "cost_mean": (sum(cost) / n) if n else 0.0, "cost_p95": p95(cost), "cost_total": sum(cost),
            "wall_mean": (sum(wall) / n) if n else 0.0, "wall_p95": p95(wall), "calls_mean": (sum(calls) / n) if n else 0.0}


def row(label: str, s: dict) -> str:
    return (f"| {label} | {s['runs']} | {s['completed']} ({pct(s['completed'], s['runs'])}) | **{s['correct']} ({pct(s['correct'], s['runs'])})** | "
            f"{s['false_completion']} | {s['errors']} | {s['score']:.2f} | {s['retries']} | ${s['cost_mean']:.2f} / ${s['cost_p95']:.2f} | "
            f"{s['wall_mean']:.1f} / {s['wall_p95']:.1f} min |")


HEAD = ("| mode | runs | completed | correct (grader) | false completion | error/blocked | mean score | retries | cost mean / p95 | time mean / p95 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")


def main(args) -> int:
    modes: dict[str, list[dict]] = {}
    for p in args.results:
        rows = load(p)
        if not rows:
            continue
        modes[rows[0].get("team_mode", "team")] = rows
    print("## Overall\n" + HEAD)
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
        print(f"\n## Reviewer evidence (ungraded)\n{len(rows)} runs, {planted} planted errors, catch rate not measured, "
              f"runs completed {sum(1 for r in rows if r.get('status') == 'completed')}/{len(rows)}, "
              f"memo verbatim {sum(1 for r in rows if r.get('memo_verbatim'))}/{len(rows)}, "
              f"cost total ${sum(r.get('usage', {}).get('cost_usd', 0) for r in rows):.2f}")
        hits = sum(r.get("keyword_hit_count", 0) for r in rows)
        legacy = sum(1 for r in rows if r.get("caught") is not None)
        print(f"keyword matches: {hits}; inspect the raw findings against the source before grading detection.")
        if legacy:
            print(f"{legacy} legacy rows used keyword matches as caught counts; those counts are not a validated catch rate.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--reviewer", default=None)
    raise SystemExit(main(ap.parse_args()))
