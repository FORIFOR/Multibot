"""Reviewer catch rate: how many deliberately planted errors does the Reviewer find?

Two documents, 10 planted errors each, against an attached source the Reviewer can read. The plan is fixed (no Master
planning call): t1 (builder) publishes the attached memo verbatim, t2 (reviewer) checks it against the source.
Keyword matches identify passages for later grading; they do not prove an error was caught. A Reviewer can repeat
the wrong memo and match every keyword. Detection counts remain ungraded until each finding is checked against
the source. Everything the Reviewer wrote is saved for that assessment.

    .venv/bin/python scripts/reviewer_catch_rate.py --data-dir ~/.cache/agentteam-bench/reviewer --repeat 3 --parallel 2
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "evals" / "benchmark"))

from agentteam.api.service import AppService  # noqa: E402
from agentteam.contracts import RunInputs, TaskSpec, TeamPlan  # noqa: E402
import tasks as T  # noqa: E402

SOURCE_A = T.PRESS_FACTS + "\n" + T.PRODUCT_NOTES
MEMO_A = """# 導入事例メモ: 株式会社ホシナ × Nocto

- 会社名: 株式会社ホシナ
- 発表日: 2026年10月11日
- 導入内容: 社内ナレッジ検索「Nocto」を自社導入。対象は営業・サポート・経理の3部門、利用者は約1,200名。
- 対応形式: PDF, Word, Markdown, Excel。
- 検索結果に出典ページ番号を表示。アクセス権はSSOのグループに追従。
- 価格: 月額1,980円/ユーザー。
- 対応言語: 日本語・英語・中国語。
- 効果: 検索にかかる時間を40%削減（発表時点の計測値）。
- 導入形態: クラウドSaaSとして提供。
- 問い合わせ先: pr@hoshina.example
"""
ERRORS_A = [("company_name", r"ホシナ"), ("date", r"10月11日|10/11|2026-10-11|11日"), ("user_count", r"1,?200"), ("departments", r"経理|3\s*部門"),
            ("format_excel", r"Excel"), ("price", r"1,?980|価格"), ("language_zh", r"中国語"), ("effect_40pct", r"40\s*%|削減|未計測"),
            ("saas", r"SaaS|クラウド"), ("email_typo", r"hoshina\.example|問い合わせ先|メール")]

SALES_CSV = T.to_csv(T.SALES, ["region", "month", "amount"])
MEMO_B = """# 2026年Q1 売上サマリ（sales.csv より）

## 地域別合計
| region | total |
| --- | --- |
| east | 3,450 |
| west | 3,530 |
| north | 1,780 |
| south | 4,590 |

- 全体合計: 13,460
- 対象地域は5地域。
- 最大の地域は west。
- south は3か月連続で前月比プラス。
- north の最大月は 2026-02。
- east の月平均は 1,250。
- 2026-04 の速報値も含めた見込みでは south が 6,000 を超える。
- south の全体に占める割合は約 30%。
- west の 2026-03 は 1,340。
- データ期間は 2026-01 〜 2026-03 の3か月。
"""
ERRORS_B = [("east_total", r"3,?450|3,?540"), ("west_total", r"3,?530|3,?350"), ("grand_total", r"13,?460|13,?260"), ("region_count", r"5\s*地域|4\s*地域"),
            ("largest_region", r"最大の地域|west.{0,30}(?:最大|largest)|south.{0,30}(?:最大|largest)"), ("south_monotonic", r"連続|前月比|1,?480"),
            ("north_max_month", r"2026-02|2026-03|最大月"), ("east_avg", r"1,?250|1,?180|月平均"), ("april", r"2026-04|4月|速報"), ("south_share", r"30\s*%|3[45]\s*%|割合")]

DOCS = {"A": {"source_name": "source.txt", "source": SOURCE_A, "memo": MEMO_A, "errors": ERRORS_A,
              "criteria": "memo.md の全ての記述（会社名・日付・人数・部門・対応形式・価格・言語・効果・導入形態・連絡先）が source.txt と一致する。source に無い記述は誤りとして列挙する。"},
        "B": {"source_name": "sales.csv", "source": SALES_CSV, "memo": MEMO_B, "errors": ERRORS_B,
              "criteria": "memo.md の全ての数値・順位・傾向の記述が sales.csv から計算した値と一致する（sandbox_run で再計算してよい）。合わない記述は全て列挙する。"}}


def plan_for(doc: str) -> TeamPlan:
    d = DOCS[doc]
    return TeamPlan(goal=f"添付の memo.md を {d['source_name']} と照合し、誤りを全て見つける", assumptions=["memo は添付のとおり（編集しない）"],
                    agents=["builder", "reviewer"], tasks=[
        TaskSpec(id="t1", owner="builder", objective="添付ファイル memo.md の内容を一字一句そのまま `memo.md` として workspace_write → publish_artifact してください。内容を直したり整えたりしないでください。",
                 depends_on=[], output_paths=["memo.md"], acceptance=[{"id": "a1", "description": "memo.md が添付と同一内容で公開されている", "check_kind": "programmatic"}],
                 write_scope="workspaces/t1/"),
        TaskSpec(id="t2", owner="reviewer", objective=f"t1 が公開した memo.md を read_artifact で読み、添付の {d['source_name']} と照合して、誤りを1件ずつ「誤りの箇所・memo の記述・正しい値・根拠」の形で全て列挙してください。{d['criteria']} 結果は submit_review の evidence/note に書き、加えて `review-findings.md` として公開してください。",
                 depends_on=["t1"], output_paths=["review-findings.md"], acceptance=[{"id": "a2", "description": d["criteria"], "check_kind": "source_check"}],
                 write_scope="workspaces/t2/")])


def reviewer_text(events, arts: dict[str, str]) -> str:
    parts = []
    for e in events:
        if e.actor_id != "reviewer":
            continue
        if e.type == "review.submitted":
            parts.append(e.payload.get("summary", ""))
            for r in e.payload.get("results", []):
                parts.append(f"{r.get('evidence', '')} {r.get('note', '')}")
        if e.type == "message.sent":
            parts.append(e.payload.get("text", ""))
        if e.type == "task.accepted" or e.type == "task.updated":
            parts.append(json.dumps(e.payload, ensure_ascii=False))
    for p, c in arts.items():
        if "review" in p:
            parts.append(c)
    return "\n".join(parts)


def candidate_mentions(text: str, errors: list[tuple[str, str]]) -> dict:
    hits = {name: bool(re.search(pat, text)) for name, pat in errors}
    return {"planted": len(errors), "keyword_hits": hits, "keyword_hit_count": sum(hits.values()),
            "caught": None, "catch_rate": None, "grading_status": "pending_source_review",
            "grading_note": "Keyword presence is not error detection. Check the identified claim, explicit correction, and source evidence."}


async def run_doc(svc: AppService, doc: str, rep: int, budget: float) -> dict:
    d = DOCS[doc]
    t0 = time.time()
    inputs = RunInputs(text="", files=[{"name": d["source_name"], "content": d["source"]}, {"name": "memo.md", "content": d["memo"]}])
    run, problems = await svc.manager.create_run(plan_for(doc).goal, inputs, budget_usd=budget)
    if problems:
        return {"doc": doc, "rep": rep, "status": "blocked", "problems": problems}
    await svc.runs.update_run(run.run_id, plan=plan_for(doc))  # fixed plan: no Master planning call
    svc.manager.start(run.run_id)
    run = await svc.manager.wait(run.run_id)
    events = await svc.events.list(run.run_id)
    metas = await svc.artifacts.list(run.run_id, latest_only=True)
    arts = {m.logical_path: (svc.artifacts.root / m.storage_path).read_text(encoding="utf-8", errors="replace") for m in metas}
    text = reviewer_text(events, arts)
    candidates = candidate_mentions(text, d["errors"])
    verdicts = [r["status"] for e in events if e.type == "review.submitted" for r in e.payload.get("results", [])]
    out_dir = svc.data_dir / "evidence" / f"{doc}-{run.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reviewer_text.md").write_text(text, encoding="utf-8")
    with open(out_dir / "events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e.model_dump(), ensure_ascii=False) + "\n")
    for p, c in arts.items():
        (out_dir / p.replace("/", "__")).write_text(c, encoding="utf-8")
    return {"doc": doc, "rep": rep, "run_id": run.run_id, "status": str(run.status), "reason": run.blocked_reason,
            **candidates, "verdicts": verdicts,
            "memo_verbatim": arts.get("memo.md", "").strip() == d["memo"].strip(),
            "usage": run.usage.model_dump(), "wall_s": round(time.time() - t0)}


async def main(args) -> int:
    svc = await AppService(args.data_dir).start()
    try:
        cfg = svc.config.model_copy(deep=True)
        conn = cfg.connection(cfg.defaults.connection_id)
        if conn.capability_check != "passed":
            from agentteam.providers.registry import ProviderRegistry
            reg = ProviderRegistry(cfg)
            try:
                pr = await reg.adapter(conn.id).probe(cfg.defaults.model)
            finally:
                await reg.aclose()
            conn.capability_check = "passed" if pr.ok else "failed"
            print("probe:", pr.ok, pr.model_reported, pr.error or "", flush=True)
            await svc.save_config(cfg, "reviewer catch rate")
        sem = asyncio.Semaphore(args.parallel)
        jobs = [(doc, r) for r in range(1, args.repeat + 1) for doc in DOCS]

        async def one(doc, r):
            async with sem:
                print(f"=== start {doc} #{r}", flush=True)
                try:
                    res = await run_doc(svc, doc, r, args.budget)
                except Exception as e:
                    res = {"doc": doc, "rep": r, "status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
                with open(svc.data_dir / "results.jsonl", "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                print(f"=== done  {doc} #{r}: {res['status']} keyword_hits={res.get('keyword_hit_count')}/{res.get('planted')} "
                      f"catch_rate=ungraded verbatim={res.get('memo_verbatim')} "
                      f"${res.get('usage', {}).get('cost_usd', 0):.2f} {res.get('wall_s', 0)}s", flush=True)

        await asyncio.gather(*(one(doc, r) for doc, r in jobs))
        return 0
    finally:
        await svc.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--budget", type=float, default=4.0)
    sys.exit(asyncio.run(main(ap.parse_args())))
