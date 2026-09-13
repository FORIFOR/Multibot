"""Projections of the event log: chat, timeline, evidence for the final report. No LLM calls here."""
from __future__ import annotations

from typing import Any

from ..contracts import Event

TITLES = {
    "run.created": "依頼を受け付け", "run.started": "実行開始", "config.resolved": "設定を確定", "plan.proposed": "Masterが計画を提案",
    "plan.rejected": "Runtimeが計画を却下", "plan.accepted": "計画を承認", "task.created": "タスク作成", "task.ready": "タスク準備完了",
    "task.started": "タスク開始", "task.review_pending": "検証待ち", "task.accepted": "タスク受入", "task.partial": "タスク部分完了",
    "task.failed": "タスク失敗", "task.blocked": "タスク停止", "task.cancelled": "タスク取消", "task.updated": "タスク更新",
    "task.interrupted": "タスク中断", "model.called": "モデル呼び出し", "model.failed": "モデル呼び出し失敗", "tool.called": "ツール実行",
    "message.sent": "メッセージ配送", "message.read": "メッセージ既読", "artifact.published": "成果物を公開", "artifact.read": "成果物を参照",
    "check.completed": "検証を実行", "review.submitted": "レビュー判定", "approval.requested": "承認を要求", "approval.resolved": "承認を処理",
    "delivery.checked": "依頼者の必須条件を検査", "input.read": "元の添付資料を参照",
    "blocker.reported": "ブロッカー報告", "checkpoint.saved": "チェックポイント", "run.completed": "完了", "run.partial": "部分完了",
    "run.failed": "失敗", "run.cancelled": "取消", "run.interrupted": "中断", "run.resumed": "再開", "run.forked": "分岐",
    "run.blocked": "開始不可", "report.generated": "最終報告を生成", "budget.exceeded": "予算超過", "policy.denied": "権限拒否",
}


def chat_view(events: list[Event]) -> list[dict[str, Any]]:
    out = []
    for e in events:
        if e.type != "message.sent":
            continue
        p = e.payload
        out.append({"seq": e.seq, "event_id": e.event_id, "recorded_at": e.recorded_at, "from": p.get("from_agent_id"),
                    "to": p.get("to_agent_id"), "task_id": p.get("task_id"), "purpose": p.get("purpose"), "text": p.get("text"),
                    "artifact_refs": p.get("artifact_refs", []), "reply_to": p.get("reply_to"), "causation_id": e.causation_id})
    return out


def timeline_view(events: list[Event], *, include_tool_calls: bool = True) -> list[dict[str, Any]]:
    out = []
    for e in events:
        if not include_tool_calls and e.type in ("tool.called", "message.read", "artifact.read", "checkpoint.saved"):
            continue
        p = e.payload
        detail = ""
        if e.type == "tool.called":
            detail = f"{p.get('tool')} → {'ok' if p.get('ok') else 'error'}"
        elif e.type == "model.called":
            u = p.get("usage", {})
            detail = f"{p.get('model_requested')} (reported: {p.get('model_reported')}) in={u.get('input_tokens')} out={u.get('output_tokens')} ${p.get('cost_usd', 0):.4f}"
        elif e.type == "artifact.published":
            detail = f"{p.get('artifact_id')} r{p.get('revision')}"
        elif e.type == "message.sent":
            detail = f"{p.get('from_agent_id')} → {p.get('to_agent_id')} [{p.get('purpose')}]"
        elif e.type == "check.completed":
            detail = f"{p.get('kind')}: {(p.get('result') or {}).get('status')}"
        elif e.type == "delivery.checked":
            detail = f"{p.get('logical_path')}: {(p.get('result') or {}).get('status')}"
        elif e.type == "input.read":
            detail = f"{p.get('name')} characters {p.get('start_char')}–{p.get('end_char')}"
        elif e.type in ("task.failed", "task.blocked", "task.partial", "task.cancelled", "run.interrupted"):
            detail = str(p.get("reason", ""))[:200]
        elif e.type == "review.submitted":
            detail = f"target {p.get('target_task_id')}: " + ", ".join(f"{r['acceptance_id']}={r['status']}" for r in p.get("results", []))
        elif e.type == "plan.rejected":
            detail = "; ".join(p.get("errors", []))[:300]
        out.append({"seq": e.seq, "event_id": e.event_id, "recorded_at": e.recorded_at, "actor_id": e.actor_id,
                    "actor_kind": e.actor_kind, "task_id": e.task_id, "causation_id": e.causation_id, "type": e.type,
                    "title": TITLES.get(e.type, e.type), "detail": detail})
    return out


def evidence_view(run, tasks, artifacts, events: list[Event]) -> dict[str, Any]:
    checks = [{"seq": e.seq, "actor": e.actor_id, "task_id": e.task_id, "kind": e.payload.get("kind"),
               "target": e.payload.get("target"), "status": (e.payload.get("result") or {}).get("status"),
               "problems": (e.payload.get("result") or {}).get("problems")} for e in events if e.type == "check.completed"]
    reviews = [{"seq": e.seq, "by": e.actor_id, **{k: e.payload.get(k) for k in ("target_task_id", "results", "summary", "target_artifacts")}}
               for e in events if e.type == "review.submitted"]
    deliveries = [{"seq": e.seq, **e.payload} for e in events if e.type == "delivery.checked"]
    blockers = [{"seq": e.seq, "actor": e.actor_id, "task_id": e.task_id, **e.payload} for e in events if e.type == "blocker.reported"]
    approvals = [{"seq": e.seq, "task_id": e.task_id, **e.payload} for e in events if e.type in ("approval.requested", "approval.resolved")]
    failures = [{"seq": e.seq, "type": e.type, "task_id": e.task_id, "actor": e.actor_id, "reason": e.payload.get("reason") or e.payload.get("message")}
                for e in events if e.type in ("task.failed", "task.blocked", "task.partial", "model.failed", "policy.denied", "plan.rejected")]
    per_agent: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.type != "model.called":
            continue
        a = per_agent.setdefault(e.actor_id, {"calls": 0, "cost_usd": 0.0, "models_reported": set(), "model_requested": e.payload.get("model_requested"),
                                              "provider_kind": e.payload.get("provider_kind")})
        a["calls"] += 1
        a["cost_usd"] += float(e.payload.get("cost_usd") or 0)
        a["models_reported"].add(e.payload.get("model_reported"))
    for a in per_agent.values():
        a["models_reported"] = sorted(x for x in a["models_reported"] if x)
        a["cost_usd"] = round(a["cost_usd"], 6)
    msgs = [e for e in events if e.type == "message.sent"]
    return {
        "run": {"run_id": run.run_id, "goal": run.goal, "status": str(run.status), "started_at": run.started_at,
                "finished_at": run.finished_at, "usage": run.usage.model_dump(), "provider_kind": run.provider_kind,
                "assumptions": run.plan.assumptions if run.plan else []},
        "tasks": [{"id": t.spec.id, "owner": t.spec.owner, "objective": t.spec.objective, "status": str(t.status), "attempts": t.attempt,
                   "result": t.result.model_dump() if t.result else None, "blocked_reason": t.blocked_reason,
                   "acceptance": [c.model_dump() for c in t.spec.acceptance],
                   "review": t.review.model_dump() if t.review else None} for t in tasks],
        "artifacts": [{"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256, "media_type": m.media_type,
                       "logical_path": m.logical_path, "by": m.agent_id, "task_id": m.task_id, "size": m.size, "sources": m.sources}
                      for m in artifacts],
        "checks": checks, "reviews": reviews, "delivery_checks": deliveries, "blockers": blockers, "approvals": approvals, "failures": failures,
        "messages": {"count": len(msgs), "by_purpose": _count(m.payload.get("purpose") for m in msgs)},
        "model_usage_by_agent": per_agent,
    }


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[str(i)] = out.get(str(i), 0) + 1
    return out
