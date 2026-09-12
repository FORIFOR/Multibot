# Agent Team

**An open-source AI team that ships real work — with a conversation you can follow.**

依頼は一度。Master が成果物と完了条件を決め、必要な Bot（Researcher / Builder / Reviewer）だけが実際に作業し、
成果物・Bot 間の実メッセージ・時系列・最終報告を **同じ実行記録（append-only Event Store）** から表示します。
台本の会話、ダミー成果物、固定の成功ログは使いません。

- 成果物を開くと、誰が作り、何を引き継ぎ、どの検証を通ったかまで辿れる
- 各 Bot の API 接続先・モデル・システムプロンプトを個別に上書きできる（共通設定を継承、手動固定あり）
- 停止・再開・分岐（Bot のモデルを変えて別案）・再生（LLM 呼出なし）・JSONL エクスポート
- 権限・予算・回数上限・承認は **プロンプトではなく Runtime が強制**

設計の根拠は `docs/blueprint/`（製品仕様・実装指示・セキュリティ要件・参考資料）、
実装判断は `docs/IMPLEMENTATION_PLAN.md`、検証状況は `docs/STATUS.md` を参照してください。

## 構成

```
backend/   Python 3.12 / FastAPI / SQLite(WAL) / SSE
  agentteam/contracts.py        契約（TeamPlan, Task, Event, Message, Artifact, Approval, Run）
  agentteam/config/             設定ロード・JSON Schema 検証・秘密参照の解決（値は保存しない）
  agentteam/store/              EventStore（seq 採番・秘匿）/ ArtifactStore（不変 revision・SHA-256・atomic publish）/ RunStore
  agentteam/providers/          ProviderAdapter: anthropic_messages（公式 SDK）, openai_compatible_chat / ollama（httpx）, fake（テスト専用）
  agentteam/runtime/            PolicyEngine / MessageBus / ToolGateway / Sandbox / Checks / Web tools / AgentRunner / Planner / Scheduler / RunManager
  agentteam/api/                REST + SSE + 静的 UI 配信
  prompts/ skills/ schemas/     ブループリント同梱の初期プロンプト・Skill・スキーマ
  tests/                        決定論的テスト（fake provider）36 件
  scripts/smoke_real_llm.py     実 LLM 受入スモーク（API キー必須）
frontend/  React + TypeScript / Vite（依頼・実行・設定の 3 画面、SSE ライブ更新）
docs/      ブループリント、実装計画、検証状況
evals/     受入評価計画（40 ケース）と対応表
```

## セットアップ

```bash
# backend
cd backend
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest -q            # 決定論的テスト（実 LLM は呼びません）

# frontend（本番 UI は backend が dist/ を配信）
cd ../frontend && pnpm install && pnpm build

# 起動（初回は data/agents.yaml が既定設定から生成されます）
cd ../backend
export ANTHROPIC_API_KEY=...             # 設定の api_key_ref は既定で env:ANTHROPIC_API_KEY
.venv/bin/agentteam serve --port 8787    # http://127.0.0.1:8787
```

初回の流れ: **設定 → 接続の「疎通確認」**（tool calling と JSON schema 出力を実 API で確認、少額）→ 依頼画面で一文入力 → 開始。
疎通確認が `passed` になるまで、価格不明のモデルやプレースホルダーのままでは開始できません（構造化された不足理由を返します）。

CLI:
```bash
.venv/bin/agentteam validate                       # 設定の検証
.venv/bin/agentteam probe [connection] --model ID  # 実疎通確認
.venv/bin/agentteam run "依頼" --url https://... --budget 1.5
```

## 仕組み（要点）

| 部品 | 責務 |
| --- | --- |
| **Master (planner)** | 依頼 → 成果物・前提・役割・task DAG（構造化出力）。Runtime が schema / 循環 / owner / tool / write scope / 上限を検査し、不正なら差し戻し |
| **AgentRunner** | Bot 1 セッション = 独立した会話状態 + ToolGateway 経由のツールループ。渡すのは担当 task・入力 artifact 参照・自分宛ての受信箱だけ |
| **MessageBus** | `send_message` を宛先 mailbox に実配送し `message.sent` として記録。質問は相手の返信セッションを起動（実際の往復） |
| **ArtifactStore** | `publish_artifact` で不変 revision（SHA-256）。Reviewer の判定・検証は対象 revision に紐付く |
| **Scheduler** | 依存解決・並列上限・レビュー不合格 → 修正 → 再レビュー（回数上限）・Master の例外判断・チェックポイント |
| **PolicyEngine** | 予算（実使用 + 実行中呼出の予約）、呼出回数、ツール権限、書込範囲、取消。価格不明のクラウドモデルは無料扱いしない |
| **Sandbox** | macOS では `sandbox-exec`（ネットワーク遮断・workspace 外書込禁止）。それ以外は subprocess（隔離ではないと明記） |

イベント型は `backend/schemas/event.schema.json` の enum（ブループリントの 11 種を含む上位集合）で、記録される全イベントがこのスキーマを満たすことをテストしています。

## セキュリティ・信頼境界

`docs/blueprint/SECURITY.md` の要件のうち、この版で実装したもの・していないものは `docs/STATUS.md` にまとめています。
API キーは参照（`env:` / `keychain:` / `file:`）のみ保存し、イベント・ツール結果・エラーは秘匿処理してから永続化します。
生成 HTML は `sandbox` CSP 付きの別エンドポイントから `<iframe sandbox>` で表示します。

## ライセンス

MIT（`LICENSE`）。同梱の初期プロンプト・Skill はこの製品向けの新規作成物で、外部プロンプトの転載ではありません（`docs/blueprint/REFERENCES.md`）。
