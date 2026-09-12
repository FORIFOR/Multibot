# 実装・検証状況（2026-09-12）

## 検証の種別
| 種別 | 状態 | 根拠 |
| --- | --- | --- |
| 決定論的テスト（fake provider） | **36 件 PASS** | `cd backend && .venv/bin/python -m pytest -q` |
| 実 LLM 協働スモーク | **未実施** | この作業環境に API キー・`ant` CLI・Ollama が無い。`backend/scripts/smoke_real_llm.py` を用意 |
| 実 API の疎通確認（probe） | **未実施** | 同上。UI の「疎通確認」または `agentteam probe` |
| ブラウザ UI スモーク（headless Chrome） | 実施（fake provider） | `frontend/scripts/ui-smoke.mjs`：Home → 依頼開始 → Run 画面（チャット/時系列/報告）→ 設定。console/page error 0 件 |
| 手動 GUI スモーク（人手） | 未実施 | — |

**fake provider はテスト・UI 確認専用**で、設定ファイルからは選べません（`AGENTTEAM_ALLOW_FAKE_PROVIDER=1` + コード注入のみ）。
fake を使った run は `provider_kind=fake` として保存され、UI に赤いバッジが出ます。実 LLM が動いた証拠にはなりません。

## ブループリント P0 に対する実装
| 項目 | 状態 | 備考 |
| --- | --- | --- |
| A. Contracts | 実装 | `contracts.py`、`schemas/`（event enum は拡張） |
| B. Event Store | 実装 | run 単位 seq、UTC、SQLite WAL、cursor、秘匿。transactional outbox は単一プロセス前提で未実装 |
| C. Provider Adapter | 実装 | anthropic_messages / openai_compatible_chat / ollama。`openai_responses` `google_genai` は未実装（開始前に拒否） |
| D. Worker | 実装 | 独立 state、mailbox、task scope、sandbox、実 tool calling |
| E. Master → DAG 検査 | 実装 | schema / 循環 / owner / tool / write scope / 上限。差し戻し 1 回 |
| F. Delivery | 実装 | `send_message` を宛先 mailbox に実配送しイベント化。質問には返信セッションが応答 |
| G. Artifacts | 実装 | atomic publish、revision/SHA-256、review・check を revision に紐付け |
| H. UI | 実装 | 一行依頼、実行中状態（SSE）、成果物プレビュー（sandbox iframe）、チームチャット、時系列、設定 |
| I. Final | 実装 | 証拠（イベント投影）+ Master/Reporter の短い要約。要約が失敗しても証拠のみで報告を生成 |
| J. Acceptance | 一部 | 決定論的テストのみ。実 LLM スモークは未実施（上表） |

## P1
| 項目 | 状態 |
| --- | --- |
| 停止・cancel・checkpoint resume | 実装（再開は未完了 task を新 attempt で再実行。会話途中の状態は復元しない） |
| 二重実行防止 | 同一プロセス内で実装。サーバ再起動時は `running` を `interrupted` に変更（自動再開しない） |
| budget reservation | 実装 |
| 権限拡大・外部書込の approval | `request_approval`（hash・nonce・期限、改ざん時は再承認）。外部書込の実行器自体は未実装（草案までの製品範囲） |
| 設定 revision / user_locked prompt / 楽観的排他 | 実装 |
| Replay / JSONL・Markdown export | 実装（Replay = 保存イベントの表示。LLM 呼出なし） |
| 初回接続診断・実 model attribution | 実装（probe、`model_reported` を毎呼出記録） |
| 同一総予算 single-agent 比較 | 未実装 |
| 共有 Replay（マスク付き公開） | 未実装（初期 OFF のまま） |

## セキュリティ要件（docs/blueprint/SECURITY.md）
- 実装: key 参照のみ保存、秘匿処理、SSRF ガード（private/loopback/metadata・redirect 各 hop）、tool scope、write scope、
  macOS seatbelt（ネットワーク遮断・workspace 外書込禁止）、生成 HTML の sandbox CSP + iframe sandbox、承認の hash/nonce/期限。
- 未実装: Docker 等の OS 横断サンドボックス、CPU/RAM 制限、capability token による多ユーザ分離、外部署名付きログ、保存期限・削除ポリシー。
  `subprocess` バックエンドは隔離ではありません（結果に backend 名を記録）。

## ブループリントからの逸脱
- Deep Agents / LangGraph は採用せず、自前の薄い AgentRunner + Provider SDK。理由は `docs/IMPLEMENTATION_PLAN.md`。
- Anthropic のサーバ側 refusal fallback は接続設定で明示 ON にした場合のみ（既定 OFF、`fallback: explicitly_approved_only` に整合）。
- 既定モデルは `claude-opus-5`（価格表同梱）。ただし疎通確認に合格するまで開始不可。
