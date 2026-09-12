"""Deterministic test harness with a scripted fake provider. This never proves real-LLM behaviour."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

os.environ["AGENTTEAM_ALLOW_FAKE_PROVIDER"] = "1"
os.environ.setdefault("AGENTTEAM_NO_SEATBELT", "0")

from agentteam.config.loader import load_config_text
from agentteam.providers.base import LLMRequest, LLMResponse
from agentteam.providers.fake_driver import FakeProvider, text_response, tool_response
from agentteam.runtime.orchestrator import RunManager
from agentteam.runtime.redaction import Redactor
from agentteam.store.artifact_store import ArtifactStore
from agentteam.store.db import Database
from agentteam.store.event_store import EventStore
from agentteam.store.run_store import RunStore

FAKE_CONFIG = """
schema_version: 1
profile_name: test
defaults: {connection_id: fake, model: fake-model, language: ja, timezone: Asia/Tokyo}
connections:
- {id: fake, driver: fake, base_url: http://fake.invalid, api_key_ref: null, capability_check: passed}
limits: {max_active_workers: 3, max_tasks: 12, max_peer_messages_per_task: 6, max_revision_rounds: 2, max_model_calls: 60,
         max_tool_calls: 120, timeout_seconds: 120, budget_usd: 5.0, max_output_tokens: 4000, max_tool_output_chars: 12000}
policy: {external_mutation: approval, skill_install: approval, telemetry: 'off', share_replay: 'off', fallback: explicitly_approved_only}
agents:
- {id: master, role: master, enabled: true, connection_id: inherit, model: inherit, system_prompt_file: prompts/master.md, prompt_mode: auto_seed,
   skill_ids: [artifact-handoff], tools: [create_task, update_task, send_message, read_messages, read_artifact, list_artifacts, workspace_read, workspace_write, publish_artifact, request_approval, report_blocker]}
- {id: researcher, role: researcher, enabled: true, connection_id: inherit, model: inherit, system_prompt_file: prompts/researcher.md, prompt_mode: auto_seed,
   skill_ids: [source-grounded-research, artifact-handoff], tools: [web_search, web_fetch, send_message, read_messages, read_artifact, list_artifacts, workspace_read, workspace_write, publish_artifact, report_blocker]}
- {id: builder, role: builder, enabled: true, connection_id: inherit, model: inherit, system_prompt_file: prompts/builder.md, prompt_mode: auto_seed,
   skill_ids: [artifact-handoff], tools: [workspace_read, workspace_write, workspace_list, sandbox_run, run_check, send_message, read_messages, read_artifact, list_artifacts, publish_artifact, request_approval, report_blocker]}
- {id: reviewer, role: reviewer, enabled: true, connection_id: inherit, model: inherit, system_prompt_file: prompts/reviewer.md, prompt_mode: auto_seed,
   skill_ids: [evidence-review, artifact-handoff], tools: [read_artifact, list_artifacts, run_check, sandbox_run, workspace_read, workspace_write, send_message, read_messages, publish_artifact, submit_review, report_blocker]}
- {id: reporter, role: reporter, enabled: false, connection_id: inherit, model: inherit, system_prompt_file: prompts/reporter.md, prompt_mode: auto_seed,
   skill_ids: [], tools: [read_artifact, list_artifacts, read_events, publish_artifact]}
"""

PLAN = {
    "goal": "製品説明から紹介LPとSNS投稿草案を作る（公開しない）",
    "assumptions": ["日本語で作成する", "価格は掲載しない"],
    "agents": ["master", "researcher", "builder", "reviewer"],
    "tasks": [
        {"id": "t1", "owner": "researcher", "objective": "根拠付きbriefを作る", "depends_on": [], "output_paths": ["brief.md"],
         "acceptance": [{"id": "c1", "description": "入力にない数字を創作しない", "check_kind": "source_check"}]},
        {"id": "t2", "owner": "builder", "objective": "briefからLPと投稿草案を作る", "depends_on": ["t1"], "output_paths": ["index.html", "posts.md"],
         "acceptance": [{"id": "c2", "description": "HTMLにviewportとtitleがある", "check_kind": "programmatic"},
                        {"id": "c3", "description": "投稿草案が3案ある", "check_kind": "model_review"}]},
        {"id": "t3", "owner": "reviewer", "objective": "t2を受入条件と照合する", "depends_on": ["t2"], "output_paths": [],
         "acceptance": [{"id": "c4", "description": "各条件に証拠を紐付ける", "check_kind": "programmatic"}]},
    ],
}

HTML_BAD = "<html><head><title>Demo</title></head><body><h1>Demo</h1><a href='#'>x</a></body></html>"
HTML_GOOD = ("<html><head><title>Demo</title><meta name='viewport' content='width=device-width'></head>"
             "<body><h1>Demo</h1><a href='https://example.com/docs'>Docs</a></body></html>")


def turn_of(req: LLMRequest) -> int:
    return sum(1 for m in req.messages if m["role"] == "assistant")


def last_user_text(req: LLMRequest) -> str:
    for m in reversed(req.messages):
        if m["role"] == "user":
            return json.dumps(m["content"], ensure_ascii=False)
    return ""


def default_script(req: LLMRequest) -> LLMResponse:
    md = req.metadata
    agent, mode, attempt, turn = md.get("agent_id"), md.get("mode"), md.get("attempt", 1), turn_of(req)
    if mode == "plan":
        return text_response(json.dumps(PLAN, ensure_ascii=False))
    if mode == "report":
        return text_response(json.dumps({"summary": "LPと投稿草案を作成し検証した。", "deliverables": [{"artifact_id": "index.html", "revision": 2, "note": "LP"}],
                                         "verified": ["viewport/title"], "unresolved": [], "next_steps": []}, ensure_ascii=False))
    key = (agent, mode, attempt)
    seqs = {
        ("researcher", "task", 1): [
            tool_response("workspace_write", {"path": "brief.md", "content": "# Brief\n\n## 特徴\n- 一度の依頼でチームが作業する\n\n出典: 入力資料"}),
            tool_response("publish_artifact", {"path": "brief.md", "sources": ["user-input"]}),
            tool_response("send_message", {"to": "builder", "purpose": "handoff", "text": "brief.md r1 を作成しました。価格は掲載しないでください。",
                                           "artifact_refs": [{"artifact_id": "brief.md", "revision": 1}]}),
            tool_response("finish_task", {"summary": "brief.md を公開", "verified": ["出典は入力資料のみ"], "unverified": []}),
        ],
        ("researcher", "reply", 1): [
            tool_response("send_message", {"to": "builder", "task_id": "t2", "purpose": "answer", "text": "対象読者は個人開発者です。", "reply_to": "__REPLY_TO__"}),
            tool_response("finish_task", {"summary": "回答済み"}),
        ],
        ("builder", "task", 1): [
            tool_response("read_artifact", {"artifact_id": "brief.md"}),
            tool_response("send_message", {"to": "researcher", "purpose": "question", "text": "対象読者は誰ですか？"}),
            tool_response("read_messages", {"wait_seconds": 20}),
            tool_response("workspace_write", {"path": "index.html", "content": HTML_BAD}),
            tool_response("publish_artifact", {"path": "index.html"}),
            tool_response("workspace_write", {"path": "posts.md", "content": "# Posts\n1. a\n2. b\n3. c"}),
            tool_response("publish_artifact", {"path": "posts.md"}),
            tool_response("finish_task", {"summary": "LP v1 と投稿案を公開", "verified": [], "unverified": ["スマホ表示"]}),
        ],
        ("builder", "task", 2): [
            tool_response("workspace_write", {"path": "index.html", "content": HTML_GOOD}),
            tool_response("publish_artifact", {"path": "index.html"}),
            tool_response("finish_task", {"summary": "viewport を追加した LP v2 を公開", "verified": ["html_basic"], "unverified": []}),
        ],
        ("reviewer", "task", 1): [
            tool_response("read_artifact", {"artifact_id": "index.html"}),
            tool_response("run_check", {"kind": "html_basic", "artifact_id": "index.html"}),
            tool_response("submit_review", {"target_task_id": "t2", "results": [
                {"acceptance_id": "c2", "status": "fail", "evidence": "run_check html_basic: missing viewport", "note": "viewport meta を追加してください"},
                {"acceptance_id": "c3", "status": "pass", "evidence": "posts.md に3案", "note": ""}], "summary": "viewport 不足"}),
            tool_response("send_message", {"to": "builder", "purpose": "finding", "text": "index.html r1: viewport meta がありません。修正してください。",
                                           "artifact_refs": [{"artifact_id": "index.html", "revision": 1}]}),
            tool_response("finish_task", {"summary": "c2 fail"}),
        ],
        ("reviewer", "task", 2): [
            tool_response("run_check", {"kind": "html_basic", "artifact_id": "index.html"}),
            tool_response("submit_review", {"target_task_id": "t2", "results": [
                {"acceptance_id": "c2", "status": "pass", "evidence": "run_check html_basic pass on r2", "note": ""},
                {"acceptance_id": "c3", "status": "pass", "evidence": "posts.md", "note": ""}], "summary": "all pass"}),
            tool_response("finish_task", {"summary": "all pass"}),
        ],
    }
    seq = seqs.get(key)
    if seq is None or turn >= len(seq):
        return text_response("done")
    resp = seq[turn]
    # patch reply_to with the real message id found in the prompt
    for c in resp.tool_calls:
        if c.arguments.get("reply_to") == "__REPLY_TO__":
            import re
            m = re.search(r"\[(msg_[0-9a-f]+)\]", last_user_text(req))
            c.arguments["reply_to"] = m.group(1) if m else None
            for b in resp.raw_content:
                if b.get("type") == "tool_use":
                    b["input"] = c.arguments
    return resp


class Harness:
    def __init__(self, tmp: Path, script=None, config_yaml: str = FAKE_CONFIG, approval_wait: float = 2.0):
        self.tmp = tmp
        self.config = load_config_text(config_yaml, allow_fake=True)
        self.provider = FakeProvider(script or default_script)
        self.db: Database | None = None
        self.approval_wait = approval_wait

    async def __aenter__(self):
        self.db = await Database(self.tmp / "db.sqlite").connect()
        redactor = Redactor()
        self.events = EventStore(self.db, redactor)
        self.artifacts = ArtifactStore(self.db, self.tmp / "runs")
        self.runs = RunStore(self.db)
        self.manager = RunManager(runs=self.runs, events=self.events, artifacts=self.artifacts, data_dir=self.tmp / "runs",
                                  config_getter=lambda: self.config, redactor=redactor, fake_adapters={"fake": self.provider},
                                  approval_wait_seconds=self.approval_wait)
        return self

    async def __aexit__(self, *a):
        await self.db.close()

    async def run_goal(self, goal="製品説明から紹介LPとSNS投稿草案を作って", **kw):
        run, problems = await self.manager.create_run(goal, **kw)
        assert not problems, problems
        self.manager.start(run.run_id)
        return await self.manager.wait(run.run_id)


@pytest.fixture
def harness(tmp_path):
    return lambda **kw: Harness(tmp_path, **kw)
