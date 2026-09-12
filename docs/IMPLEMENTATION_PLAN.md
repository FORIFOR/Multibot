# 実装計画（2026-09-12 作成）

ブループリント `docs/blueprint/` を根拠に、P0 全項目と P1 の主要項目を実装する。

## 調査で確認したこと
- ブループリントは設計・契約・初期プロンプトのみ。アプリ本体は無い。
- 実行環境に LLM API キー、`ant` CLI、Ollama は存在しない。実 LLM 疎通は本セッションでは未検証のまま残す。
- Python 3.12 / uv、Node 25 / pnpm、Docker は利用可能。macOS `sandbox-exec` は利用可能。

## 設計判断（ブループリントからの逸脱を含む）
1. Worker 実行基盤は Deep Agents / LangGraph を使わず、自前の薄い `AgentRunner`（Provider SDK 直接呼び出し）にする。
   理由: ブループリント §11 が求める「独立 session と mailbox を持つ worker 管理」「Runtime による権限強制」「framework 内部状態への非依存」を、
   同期 subagent 前提のフレームワーク上で満たすより、契約を小さく自前で持つ方が検証可能で差分も小さい。Deep Agents は候補であり必須ではない（IMPLEMENTATION_BRIEF §11 / REFERENCES）。
2. Anthropic ドライバは公式 SDK (`anthropic` 1.x)、互換 API は `httpx` で `openai_compatible_chat` ドライバを実装する。base URL だけで差を吸収しない。
3. 承認済み fallback 以外のモデル切替は行わない。Anthropic のサーバ側 refusal fallback も既定 OFF（接続設定で明示的に ON にできる）。
4. `fake` ドライバはテスト専用。設定ファイルからは選べず、環境変数 `AGENTTEAM_ALLOW_FAKE_PROVIDER=1` かつコード上の注入でのみ使える。UI には「fake」と表示する。
5. event.schema.json の type enum はブループリントの 11 種を含む上位集合に拡張する（task.accepted, model.called, tool.called など）。

## ステップ
1. contracts / config / secrets
2. EventStore / ArtifactStore / RunStore (SQLite WAL)
3. ProviderAdapter (anthropic_messages, openai_compatible_chat, fake[test])
4. PolicyEngine / Redaction / MessageBus / ToolGateway / Sandbox / Checks / Web tools
5. AgentRunner / Planner(Master) / Scheduler / Orchestrator / Report
6. FastAPI (runs, events, stream, cancel, resume, fork, approvals, agents, connections, artifacts)
7. pytest（決定論的、fake provider）
8. React + TS UI（依頼入力 / 成果物 / チーム / チャット / 時系列 / 設定 / 承認）
9. README / SECURITY / 実 LLM スモーク手順
