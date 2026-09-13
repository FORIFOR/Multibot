"""Run several request types end to end through the configured connection and record honest results.

    .venv/bin/python scripts/eval_scenarios.py --data-dir ~/.cache/agentteam-evals --connection claude_cli --model opus \
        --scenarios code,research,long --budget 6 --timeout 2400

Each scenario runs once (or --repeat N). Results (status, plan shape, checks, cost, time, failures) are written to
<data-dir>/results.jsonl and printed as a Markdown table. Artifacts + event logs are exported per scenario.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentteam.api.service import AppService  # noqa: E402
from agentteam.contracts import RunInputs  # noqa: E402
from agentteam.projections.views import chat_view  # noqa: E402

SCENARIOS = {
    "lp": {"goal": "この製品説明をもとに、日本語の紹介LP（index.html）とSNS投稿草案（posts.md、3案）を作ってください。不足情報は推定して前提として記録し、公開はせず草案まで。Reviewerに実検証させてください。",
           "text": "製品: Agent Team。一度の依頼からAIチーム（Master/Researcher/Builder/Reviewer）が実際に作業し、成果物とBot間の実メッセージ、時系列を同じ実行記録から表示するオープンソースのローカルファーストなツール。価格は未定。対象はソフトウェア開発者と個人開発者。"},
    "code": {"goal": "Python で CLI ツール `wc_plus` を作ってください: 引数のテキストファイル群について行数・単語数・文字数と、最頻出の単語トップ5を表示する。標準ライブラリのみ。`wc_plus.py`（実装）、`test_wc_plus.py`（unittest、最低5ケース）、`README.md`（使い方）を出力し、Builder は sandbox_run で `python3 -m unittest -v` を実際に実行してから公開、Reviewer も同じテストを再実行して判定してください。",
             "text": ""},
    "research": {"goal": "次の3つの公開ページを実際に取得して読み、それぞれの「主張・対象読者・ライセンス（記載があれば）」を出典URL付きで比較した調査メモ `research.md` を日本語で作ってください。取得できなかったページは『取得不可』と明記し、本文を推測で埋めないでください。Reviewer は各主張が出典に実在するかを read_artifact と web_fetch で照合してください。",
                 "urls": ["https://github.com/langchain-ai/deepagents", "https://github.com/bytedance/deer-flow", "https://agentskills.io/specification"]},
    "long": {"goal": "小さな静的ドキュメントサイトを作ってください: `index.html`（トップ）、`docs/getting-started.html`、`docs/faq.html`、`styles.css` の4ファイル。内容は製品説明に基づく日本語。相互リンクが切れていないこと（html_links で検証）、各ページに title と viewport があること、外部 URL を書かないこと（プレースホルダ可）。Builder が全ファイルを公開し、Reviewer が全ページを検証してください。",
             "text": "製品: Agent Team。一度の依頼からAIチーム（Master/Researcher/Builder/Reviewer）が実際に作業し、成果物とBot間の実メッセージ、時系列を同じ実行記録から表示するオープンソースのローカルファーストなツール。Claude Code があれば API キー不要。価格は未定。対象はソフトウェア開発者と個人開発者。"},
}


async def run_one(svc: AppService, name: str, budget: float) -> dict:
    sc = SCENARIOS[name]
    t0 = time.time()
    run, problems = await svc.manager.create_run(sc["goal"], RunInputs(text=sc.get("text", ""), urls=sc.get("urls", [])), budget_usd=budget)
    if problems:
        return {"scenario": name, "status": "blocked", "problems": problems}
    svc.manager.start(run.run_id)
    run = await svc.manager.wait(run.run_id)
    events = await svc.events.list(run.run_id)
    tasks = await svc.runs.list_tasks(run.run_id)
    arts = await svc.artifacts.list(run.run_id, latest_only=True)
    checks = [(e.payload.get("kind"), (e.payload.get("result") or {}).get("status")) for e in events if e.type == "check.completed"]
    reviews = [r["status"] for e in events if e.type == "review.submitted" for r in e.payload.get("results", [])]
    models = sorted({e.payload.get("model_reported") for e in events if e.type == "model.called"} - {None})
    plan = run.plan
    out_dir = svc.data_dir / "evidence" / f"{name}-{run.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for m in await svc.artifacts.list(run.run_id):
        shutil.copy(svc.artifacts.root / m.storage_path, out_dir / f"{m.artifact_id}.r{m.revision}")
    with open(out_dir / "events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e.model_dump(), ensure_ascii=False) + "\n")
    res = {"scenario": name, "run_id": run.run_id, "status": str(run.status), "reason": run.blocked_reason,
           "profile": svc.config.profile_name, "team_mode": svc.config.defaults.team_mode,
           "models": models, "plan_tasks": [(t.id, t.owner) for t in (plan.tasks if plan else [])],
           "task_status": {t.spec.id: (str(t.status), t.attempt) for t in tasks},
           "artifacts": [f"{m.artifact_id}@r{m.revision}" for m in arts if m.artifact_id != "final-report.md"],
           "checks": checks, "checks_pass": sum(1 for _, s in checks if s == "pass"), "checks_total": len(checks),
           "review_pass": sum(1 for s in reviews if s == "pass"), "review_total": len(reviews),
           "messages": len(chat_view(events)), "milestones": sum(1 for e in events if e.type == "plan.milestone"),
           "usage": run.usage.model_dump(), "wall_s": round(time.time() - t0),
           "failures": [(e.type, str(e.payload.get("reason") or e.payload.get("message") or e.payload.get("errors"))[:200]) for e in events
                        if e.type in ("task.failed", "task.blocked", "task.partial", "model.failed", "plan.rejected")]}
    return res


async def main(args) -> int:
    svc = await AppService(args.data_dir).start()
    try:
        if args.config:  # e.g. docs/config/single-agent.yaml for the single-agent baseline
            from agentteam.config.loader import load_config_text
            cfg = load_config_text(Path(args.config).read_text(encoding="utf-8"))
        else:
            cfg = svc.config.model_copy(deep=True)
        if args.connection:
            cfg.defaults.connection_id = args.connection
        if args.model:
            cfg.defaults.model = args.model
        if args.timeout:
            cfg.limits.timeout_seconds = args.timeout
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
            print("probe:", pr.ok, pr.model_reported, pr.error or "")
        await svc.save_config(cfg, "eval")
        results = []
        for name in args.scenarios.split(","):
            for i in range(args.repeat):
                print(f"=== {name} #{i + 1}", flush=True)
                r = await run_one(svc, name, args.budget)
                results.append(r)
                with open(svc.data_dir / "results.jsonl", "a") as f:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print(json.dumps({k: r.get(k) for k in ("status", "plan_tasks", "artifacts", "checks_pass", "checks_total", "review_pass", "review_total", "wall_s")}, ensure_ascii=False), flush=True)
        print("\n| scenario | status | tasks | artifacts | checks | review | msgs | calls | cost | time |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in results:
            u = r.get("usage", {})
            print(f"| {r['scenario']} | {r['status']} | {len(r.get('plan_tasks', []))} | {len(r.get('artifacts', []))} | "
                  f"{r.get('checks_pass', 0)}/{r.get('checks_total', 0)} | {r.get('review_pass', 0)}/{r.get('review_total', 0)} | "
                  f"{r.get('messages', 0)} | {u.get('model_calls', 0)} | ${u.get('cost_usd', 0):.2f} | {r.get('wall_s', 0)}s |")
        return 0
    finally:
        await svc.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(Path.home() / ".cache" / "agentteam-evals"))
    ap.add_argument("--config", default=None, help="config YAML to load into the data dir first (e.g. docs/config/single-agent.yaml)")
    ap.add_argument("--connection", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--scenarios", default="code,research,long")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--budget", type=float, default=6.0)
    ap.add_argument("--timeout", type=int, default=2400)
    sys.exit(asyncio.run(main(ap.parse_args())))
