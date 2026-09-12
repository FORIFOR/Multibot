"""End-to-end collaboration with the scripted provider: plan → research → build (with a real peer Q&A) → review (fail) → revise → review (pass)."""
import json

import pytest

from agentteam.projections.views import chat_view, timeline_view


async def test_three_agent_collaboration(harness):
    async with harness() as h:
        run = await h.run_goal()
        assert run.status == "completed", (run.status, run.blocked_reason)
        assert run.provider_kind == "fake"
        tasks = {t.spec.id: t for t in await h.runs.list_tasks(run.run_id)}
        assert tasks["t1"].status == "accepted" and tasks["t2"].status == "accepted" and tasks["t3"].status == "accepted"
        assert tasks["t2"].attempt == 2, "builder should have revised once after the failed review"
        assert tasks["t3"].attempt == 2
        # artifacts: index.html has two immutable revisions with different hashes
        index = [m for m in await h.artifacts.list(run.run_id) if m.artifact_id == "index.html"]
        assert [m.revision for m in index] == [1, 2] and index[0].sha256 != index[1].sha256
        assert b"viewport" in h.artifacts.read_bytes(index[1])
        # review bound to the revision it checked
        events = await h.events.list(run.run_id)
        reviews = [e for e in events if e.type == "review.submitted"]
        assert len(reviews) == 2
        assert reviews[0].payload["target_artifacts"][0]["revision"] == 1
        assert reviews[1].payload["target_artifacts"][0]["revision"] == 2
        # real message delivery incl. a question/answer round trip with reply_to
        chat = chat_view(events)
        purposes = [c["purpose"] for c in chat]
        assert purposes == ["handoff", "question", "answer", "finding"]
        q = next(c for c in chat if c["purpose"] == "question")
        a = next(c for c in chat if c["purpose"] == "answer")
        assert a["reply_to"] is not None and a["from"] == "researcher" and a["to"] == "builder"
        # builder actually received the answer through read_messages (tool result contains it)
        reads = [e for e in events if e.type == "tool.called" and e.payload["tool"] == "read_messages" and e.actor_id == "builder"]
        assert any("対象読者は個人開発者です" in e.payload["result_preview"] for e in reads)
        # seq monotonic & causation present on messages
        seqs = [e.seq for e in events]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
        # checks bound to revision
        checks = [e for e in events if e.type == "check.completed"]
        assert checks[0].payload["target"]["revision"] == 1 and checks[0].payload["result"]["status"] == "fail"
        assert checks[1].payload["target"]["revision"] == 2 and checks[1].payload["result"]["status"] == "pass"
        # final report exists as an artifact and references evidence
        rep = run.final_report
        assert rep and rep["status"] == "completed"
        assert any(d["artifact_id"] == "index.html" and d["revision"] == 2 for d in rep["deliverables"])
        final = await h.artifacts.get(run.run_id, "final-report.md")
        assert final is not None and "index.html" in h.artifacts.read_text(final)
        # usage accounted, model attribution recorded
        assert run.usage.model_calls > 5 and run.usage.cost_usd > 0
        mc = [e for e in events if e.type == "model.called"]
        assert all(e.payload["model_reported"] == "fake-model" and e.payload["provider_kind"] == "fake" for e in mc)
        # timeline projection works
        tl = timeline_view(events, include_tool_calls=False)
        assert any(x["type"] == "run.completed" for x in tl)


async def test_replay_makes_no_model_calls(harness):
    async with harness() as h:
        run = await h.run_goal()
        n = len(h.provider.calls)
        events = await h.events.list(run.run_id)
        chat_view(events); timeline_view(events)
        run2 = await h.runs.get_run(run.run_id)
        assert run2 is not None and len(h.provider.calls) == n
