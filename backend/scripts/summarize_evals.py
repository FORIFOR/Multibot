"""Aggregate results.jsonl files written by eval_scenarios.py into a reproducibility table.

    .venv/bin/python scripts/summarize_evals.py ~/.cache/agentteam-evals-r3/*/results.jsonl

Prints, per scenario: runs, completed/partial/failed counts, plan size range, checks and review pass ratios,
model-call / cost / wall-time ranges. Nothing is filtered: every recorded run counts.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def load(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        for line in Path(p).expanduser().read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def rng(values: list[float], fmt: str = "{:.0f}") -> str:
    if not values:
        return "—"
    lo, hi = min(values), max(values)
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)}–{fmt.format(hi)}"


def main(paths: list[str]) -> int:
    rows = load(paths)
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["scenario"]].append(r)
    print("| scenario | runs | completed | partial | failed | tasks | checks pass | review pass | calls | cost | time |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, rs in by.items():
        st = [r.get("status") for r in rs]
        cp = sum(r.get("checks_pass", 0) for r in rs)
        ct = sum(r.get("checks_total", 0) for r in rs)
        rp = sum(r.get("review_pass", 0) for r in rs)
        rt = sum(r.get("review_total", 0) for r in rs)
        print(f"| {name} | {len(rs)} | {st.count('completed')} | {st.count('partial')} | "
              f"{st.count('failed') + st.count('blocked')} | {rng([len(r.get('plan_tasks', [])) for r in rs])} | "
              f"{cp}/{ct} | {rp}/{rt} | {rng([r.get('usage', {}).get('model_calls', 0) for r in rs])} | "
              f"${rng([r.get('usage', {}).get('cost_usd', 0) for r in rs], '{:.2f}')} | "
              f"{rng([r.get('wall_s', 0) / 60 for r in rs], '{:.0f}')} min |")
    print()
    print("| scenario | # | run_id | status | tasks | artifacts | checks | review | calls | cost | time | failures |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, rs in by.items():
        for i, r in enumerate(rs, 1):
            u = r.get("usage", {})
            fails = "; ".join(f"{t}: {m[:60]}" for t, m in r.get("failures", [])[:3]) or "—"
            print(f"| {name} | {i} | {r.get('run_id', '—')} | {r.get('status')} | {len(r.get('plan_tasks', []))} | "
                  f"{len(r.get('artifacts', []))} | {r.get('checks_pass', 0)}/{r.get('checks_total', 0)} | "
                  f"{r.get('review_pass', 0)}/{r.get('review_total', 0)} | {u.get('model_calls', 0)} | "
                  f"${u.get('cost_usd', 0):.2f} | {r.get('wall_s', 0) // 60}m{r.get('wall_s', 0) % 60:02d}s | {fails} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [str(Path.home() / ".cache" / "agentteam-evals" / "results.jsonl")]))
