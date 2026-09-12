"""Real-LLM acceptance smoke (evals/cases.jsonl: real-collaboration, first-run-input, real-llm-ci).

Requires a configured connection with a resolvable key, e.g. ANTHROPIC_API_KEY. It probes the connection
(costs a few hundred tokens), then runs one three-role request under the configured budget and prints the
evidence needed to claim a real run: provider models reported, usage, cost, artifacts, checks, messages.

    ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_real_llm.py --data-dir ./data --budget 1.5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentteam.api.service import AppService  # noqa: E402
from agentteam.contracts import RunInputs  # noqa: E402
from agentteam.projections.views import chat_view  # noqa: E402
from agentteam.providers.registry import ProviderRegistry  # noqa: E402

GOAL = ("この製品説明をもとに、日本語の紹介LP（index.html）とSNS投稿草案（posts.md、3案）を作ってください。"
        "不足情報は推定して前提として記録し、公開はせず草案まで。Reviewerに実検証させてください。")
TEXT = ("製品: Agent Team。一度の依頼からAIチーム（Master/Researcher/Builder/Reviewer）が実際に作業し、"
        "成果物とBot間の実メッセージ、時系列を同じ実行記録から表示するオープンソースのローカルファーストなツール。"
        "価格は未定。対象はソフトウェア開発者と個人開発者。")


async def main(args) -> int:
    svc = await AppService(args.data_dir).start()
    try:
        cid = args.connection or svc.config.defaults.connection_id
        model = args.model or svc.config.defaults.model
        reg = ProviderRegistry(svc.config)
        try:
            probe = await reg.adapter(cid).probe(model)
        finally:
            await reg.aclose()
        print("probe:", json.dumps(probe.__dict__, default=lambda o: o.__dict__, ensure_ascii=False))
        cfg = svc.config.model_copy(deep=True)
        c = cfg.connection(cid)
        c.capability_check = "passed" if probe.ok else "failed"
        c.capability_detail = {"model_requested": probe.model_requested, "model_reported": probe.model_reported,
                               "tool_calling": probe.tool_calling, "json_schema": probe.json_schema, "error": probe.error}
        if args.model:
            cfg.defaults.model = args.model
        if args.connection:
            cfg.defaults.connection_id = args.connection
        if args.timeout:
            cfg.limits.timeout_seconds = int(args.timeout)
        await svc.save_config(cfg, "smoke probe")
        if not probe.ok:
            print("probe failed; not starting a run")
            return 2
        run, problems = await svc.manager.create_run(GOAL, RunInputs(text=TEXT), budget_usd=args.budget)
        if problems:
            print("blocked:", problems)
            return 2
        print("run_id:", run.run_id)
        svc.manager.start(run.run_id)
        run = await svc.manager.wait(run.run_id)
        events = await svc.events.list(run.run_id)
        models = sorted({e.payload.get("model_reported") for e in events if e.type == "model.called"} - {None})
        evidence = {
            "status": str(run.status), "provider_kind": run.provider_kind, "models_reported_by_provider": models,
            "usage": run.usage.model_dump(),
            "artifacts": [{"id": m.artifact_id, "rev": m.revision, "sha256": m.sha256[:16], "by": m.agent_id} for m in await svc.artifacts.list(run.run_id)],
            "checks": [{"seq": e.seq, "kind": e.payload.get("kind"), "status": (e.payload.get("result") or {}).get("status")} for e in events if e.type == "check.completed"],
            "messages": [{"seq": m["seq"], "from": m["from"], "to": m["to"], "purpose": m["purpose"]} for m in chat_view(events)],
            "reviews": [e.payload.get("results") for e in events if e.type == "review.submitted"],
            "failures": [e.payload for e in events if e.type in ("model.failed", "task.failed", "plan.rejected")],
        }
        print(json.dumps(evidence, ensure_ascii=False, indent=1))
        return 0 if run.status == "completed" else 1
    finally:
        await svc.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="./data")
    ap.add_argument("--budget", type=float, default=1.5)
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=None, help="run wall-clock limit in seconds")
    ap.add_argument("--connection", default=None)
    sys.exit(asyncio.run(main(ap.parse_args())))
