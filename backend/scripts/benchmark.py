"""Run the 50-task benchmark (evals/benchmark/tasks.py) end to end and grade every run without a model.

    # team protocol (the data dir's config, probed on first use)
    .venv/bin/python scripts/benchmark.py --data-dir ~/.cache/agentteam-bench/team --tasks all --repeat 3 --parallel 4
    # single-agent baseline, same requests, same budget
    .venv/bin/python scripts/benchmark.py --data-dir ~/.cache/agentteam-bench/single --config ../docs/config/single-agent.yaml --tasks all --repeat 3 --parallel 4

One line per run is appended to <data-dir>/results.jsonl: status, grader verdict (correct / score / failed checks), cost,
model calls, wall time, plan size, attempts, failures. Artifacts and event logs go to <data-dir>/evidence/<task>-<run_id>/.
Nothing is filtered or retried: a crashed run is recorded as status=error.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "evals" / "benchmark"))

from agentteam.api.service import AppService  # noqa: E402
from agentteam.config.loader import load_config_text  # noqa: E402
from agentteam.contracts import RunInputs  # noqa: E402
import tasks as T  # noqa: E402


def provider_exhausted(result: dict) -> bool:
    """Only stop for provider-wide quota/auth failures, never an artifact grade."""
    detail = json.dumps({k: result.get(k) for k in ("reason", "error", "failures")}).lower()
    return any(s in detail for s in ("hit your session limit", "insufficient_quota", "credit balance is too low", "not logged in", "invalid_api_key"))


def pending_jobs(jobs: list, previous: list[dict], retry_exhausted: bool) -> list:
    # Last attempt determines resumability; preserve every earlier record on disk.
    latest = {(r["task"], r["rep"]): r for r in previous}
    return [(t, rep) for t, rep in jobs if (t["id"], rep) not in latest
            or (retry_exhausted and provider_exhausted(latest[t["id"], rep]))]


async def ensure_probed(svc: AppService, cfg):
    conn = cfg.connection(cfg.defaults.connection_id)
    if conn.capability_check != "passed":
        from agentteam.providers.registry import ProviderRegistry
        reg = ProviderRegistry(cfg)
        try:
            pr = await reg.adapter(conn.id).probe(cfg.defaults.model)
        finally:
            await reg.aclose()
        conn.capability_check = "passed" if pr.ok else "failed"
        conn.capability_detail = {"model_reported": pr.model_reported, "error": pr.error}
        print("probe:", pr.ok, pr.model_reported, pr.error or "", flush=True)
        if not pr.ok:
            raise SystemExit("probe failed")
    return cfg


async def run_task(svc: AppService, cfg, task: dict, rep: int, budget: float) -> dict:
    t0 = time.time()
    base = {"task": task["id"], "category": task["category"], "rep": rep, "profile": cfg.profile_name, "team_mode": cfg.defaults.team_mode}
    inputs = RunInputs(text=task["text"], urls=task["urls"], files=task["files"])
    run, problems = await svc.manager.create_run(task["goal"], inputs, budget_usd=budget, config=cfg)
    if problems:
        return {**base, "status": "blocked", "problems": problems, "wall_s": 0}
    svc.manager.start(run.run_id)
    run = await svc.manager.wait(run.run_id)
    events = await svc.events.list(run.run_id)
    states = await svc.runs.list_tasks(run.run_id)
    metas = await svc.artifacts.list(run.run_id, latest_only=True)
    arts: dict[str, str] = {}
    out_dir = svc.data_dir / "evidence" / f"{task['id']}-{run.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for m in metas:
        p = svc.artifacts.root / m.storage_path
        try:
            arts[m.logical_path] = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            arts[m.logical_path] = ""
        shutil.copy(p, out_dir / f"{m.artifact_id}.r{m.revision}")
    with open(out_dir / "events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e.model_dump(), ensure_ascii=False) + "\n")
    g = T.grade(task["id"], {k: v for k, v in arts.items() if k != "final-report.md"})
    checks = [(e.payload.get("kind"), (e.payload.get("result") or {}).get("status")) for e in events if e.type == "check.completed"]
    reviews = [r["status"] for e in events if e.type == "review.submitted" for r in e.payload.get("results", [])]
    status = str(run.status)
    return {**base, "run_id": run.run_id, "status": status, "reason": run.blocked_reason,
            "correct": g["correct"], "score": g["score"], "failed_checks": [c["name"] + (f" ({c['detail']})" if c["detail"] else "") for c in g["checks"] if not c["ok"]],
            "false_completion": status == "completed" and not g["correct"],
            "plan_tasks": len(run.plan.tasks) if run.plan else 0, "tasks_total": len(states),
            "attempts": sum(s.attempt for s in states), "retries": sum(max(0, s.attempt - 1) for s in states),
            "artifacts": [m.logical_path for m in metas if m.artifact_id != "final-report.md"],
            "runtime_checks": f"{sum(1 for _, s in checks if s == 'pass')}/{len(checks)}", "review": f"{sum(1 for s in reviews if s == 'pass')}/{len(reviews)}",
            "milestones": sum(1 for e in events if e.type == "plan.milestone" and e.payload.get("added_tasks")),
            "usage": run.usage.model_dump(), "wall_s": round(time.time() - t0),
            "failures": [(e.type, str(e.payload.get("reason") or e.payload.get("message") or e.payload.get("errors"))[:160]) for e in events
                         if e.type in ("task.failed", "task.blocked", "task.partial", "model.failed", "plan.rejected")]}


async def regrade(args) -> int:
    """Re-apply the graders to every recorded run (artifacts are re-read from the data dir's store) → results.regraded.jsonl.
    Use after fixing a grader; the original results.jsonl is left untouched so both can be compared."""
    svc = await AppService(args.data_dir).start()
    try:
        src = svc.data_dir / "results.jsonl"
        out = svc.data_dir / "results.regraded.jsonl"
        changed = 0
        with open(out, "w") as f:
            for line in src.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("run_id"):
                    metas = await svc.artifacts.list(r["run_id"], latest_only=True)
                    arts = {}
                    for m in metas:
                        try:
                            arts[m.logical_path] = (svc.artifacts.root / m.storage_path).read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            arts[m.logical_path] = ""
                    g = T.grade(r["task"], {k: v for k, v in arts.items() if k != "final-report.md"})
                    before = r.get("correct")
                    r["correct"], r["score"] = g["correct"], g["score"]
                    r["failed_checks"] = [c["name"] + (f" ({c['detail']})" if c["detail"] else "") for c in g["checks"] if not c["ok"]]
                    r["false_completion"] = r.get("status") == "completed" and not g["correct"]
                    r["regraded"] = True
                    changed += before != r["correct"]
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"regraded → {out} ({changed} verdicts changed)")
        return 0
    finally:
        await svc.stop()


async def main(args) -> int:
    if args.regrade:
        return await regrade(args)
    svc = await AppService(args.data_dir).start()
    try:
        if args.config:
            cfg = load_config_text(Path(args.config).read_text(encoding="utf-8"))
        else:
            cfg = svc.config.model_copy(deep=True)
        if args.timeout:
            cfg.limits.timeout_seconds = args.timeout
        cfg = await ensure_probed(svc, cfg)
        if not args.config:
            await svc.save_config(cfg, "benchmark")
        sel = T.TASKS
        if args.tasks != "all":
            wanted = set(args.tasks.split(","))
            sel = [t for t in T.TASKS if t["id"] in wanted or t["category"] in wanted]
        jobs = [(t, r) for r in range(args.rep_start, args.rep_start + args.repeat) for t in sel]
        print(f"{len(jobs)} runs: {len(sel)} tasks × {args.repeat}, parallel {args.parallel}, profile {cfg.profile_name} ({cfg.defaults.team_mode})", flush=True)
        sem = asyncio.Semaphore(args.parallel)
        results_path = svc.data_dir / "results.jsonl"
        if args.resume and results_path.exists():
            previous = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
            jobs = pending_jobs(jobs, previous, args.retry_exhausted)
            print(f"Resuming {len(jobs)} pending runs; previous attempts are preserved.", flush=True)
        exhausted = asyncio.Event()

        async def one(t, r):
            async with sem:
                if exhausted.is_set():
                    return
                print(f"=== start {t['id']} #{r}", flush=True)
                try:
                    res = await run_task(svc, cfg, t, r, args.budget)
                except Exception as e:  # record, never abort the batch
                    res = {"task": t["id"], "category": t["category"], "rep": r, "profile": cfg.profile_name, "team_mode": cfg.defaults.team_mode,
                           "status": "error", "error": f"{type(e).__name__}: {e}"[:300], "trace": traceback.format_exc()[-800:], "correct": False, "score": 0.0}
                with open(results_path, "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                if provider_exhausted(res):
                    exhausted.set()
                    print("Provider quota/authentication blocked the batch. Queued runs will not start; in-flight runs will finish. Resume after resolving the provider issue.", flush=True)
                u = res.get("usage", {})
                print(f"=== done  {t['id']} #{r}: {res['status']} correct={res.get('correct')} score={res.get('score')} "
                      f"${u.get('cost_usd', 0):.2f} {res.get('wall_s', 0)}s {res.get('failed_checks', res.get('error', ''))}", flush=True)

        await asyncio.gather(*(one(t, r) for t, r in jobs))
        return 2 if exhausted.is_set() else 0
    finally:
        await svc.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--config", default=None, help="config YAML (e.g. ../docs/config/single-agent.yaml); default: the data dir's config")
    ap.add_argument("--tasks", default="all", help="'all', or comma-separated task ids / categories")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--rep-start", type=int, default=1, help="first repetition number (to resume a series after a provider quota reset)")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--budget", type=float, default=6.0)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--regrade", action="store_true", help="re-grade recorded runs from the store instead of running anything")
    ap.add_argument("--resume", action="store_true", help="skip task/repetition pairs already recorded (append-only)")
    ap.add_argument("--retry-exhausted", action="store_true", help="with --resume, retry provider quota/auth failures; preserve original attempts")
    sys.exit(asyncio.run(main(ap.parse_args())))
