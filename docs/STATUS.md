# 実装・検証状況（2026-09-12）

## 検証の種別
| 種別 | 状態 | 根拠 |
| --- | --- | --- |
| 決定論的テスト（fake provider） | **46 件 PASS** | `cd backend && .venv/bin/python -m pytest -q`（Docker サンドボックスのテストは daemon がある時のみ実行） |
| 実 LLM 協働スモーク | **実施（claude_cli / claude-opus-5）** | 2026-09-13。run 1: 成果物 3 点・検証 12 件 pass・handoff 2 件・$1.69（定価換算）・760 秒。最終状態は `partial`（複数ターゲットレビューのバグ、修正済み）。run 2/3 は計画呼出の `max_turns` と `max_model_calls=30` の上限で失敗 → いずれも修正・調整済み。証拠: `docs/evidence/run1-*` |
| 実 API の疎通確認（probe） | **実施（claude_cli）** | tool calling / JSON schema ともに pass、`model_reported=claude-opus-5` |
| ブラウザ UI スモーク（headless Chrome） | 実施（fake provider） | `frontend/scripts/ui-smoke.mjs`：Home → 依頼開始 → Run 画面（チャット/時系列/報告）→ 設定。console/page error 0 件 |
| 手動 GUI スモーク（人手） | 未実施 | — |

**fake provider はテスト・UI 確認専用**で、設定ファイルからは選べません（`AGENTTEAM_ALLOW_FAKE_PROVIDER=1` + コード注入のみ）。
fake を使った run は `provider_kind=fake` として保存され、UI に赤いバッジが出ます。実 LLM が動いた証拠にはなりません。

## ブループリント P0 に対する実装
| 項目 | 状態 | 備考 |
| --- | --- | --- |
| A. Contracts | 実装 | `contracts.py`、`schemas/`（event enum は拡張） |
| B. Event Store | 実装 | run 単位 seq、UTC、SQLite WAL、cursor、秘匿。transactional outbox は単一プロセス前提で未実装 |
| C. Provider Adapter | 実装 | claude_cli（ローカル Claude Code、キー不要）/ anthropic_messages / openai_compatible_chat / ollama。`openai_responses` `google_genai` は未実装（開始前に拒否） |
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

## 実 LLM run で見つかった問題と対応（2026-09-13）
| run | 事象 | 対応 |
| --- | --- | --- |
| 1 | Reviewer が t1・t2 の両方を検証したが、Runtime が最後の判定しか適用せず t1 が `review_pending` のまま → `partial` | `submit_review` をターゲットごとに蓄積し、全判定を適用。`finish_task` は全ターゲットの判定が揃うまで拒否 |
| 2 | Master の計画呼出（構造化出力・1 ショット）が `error_max_turns` | `--max-turns 3`、`max_turns` 系エラーを再試行対象に |
| 3 | Reviewer 起動時に `max_model_calls=30` 到達（Opus の Builder 1 セッション ≈ 10〜15 ターン） | 既定を 120 呼出 / 200 ツール呼出に変更（ブループリントの初期候補値を実測で調整） |
| 4 | **completed**。Builder 1 + Reviewer 1 の計画、検証 10 件 pass、レビュー 6/6 pass、メッセージ 2 件、39 ターン、$1.66、1117 秒 | 証拠 `docs/evidence/run4-*` |

## 2026-09-13 「足りないこと」7 項目への対応

| # | 項目 | 対応 | 検証 |
| --- | --- | --- | --- |
| 1 | 実証の幅 | `scripts/eval_scenarios.py` を追加し、コード生成（unittest 実行付き）・出典付き調査・複数ファイル制作の 3 種を実 run | 下表「シナリオ評価」 |
| 2 | 安全性が macOS 限定 | Docker サンドボックス backend（`--network none`、read-only root、host uid、cap-drop、CPU/メモリ/pid 制限、workspace のみ mount）。自動選択 docker → seatbelt → **拒否**（`AGENTTEAM_SANDBOX=subprocess` で明示的に隔離なしを選択） | Colima の実エンジンで書込範囲・ネットワーク遮断のテスト pass |
| 3 | 導入の摩擦 | UI・prompts・skills・schemas を wheel に同梱。`agentteam quickstart`（probe → serve → ブラウザ）。`uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart` の 1 コマンド | uvx からのインストールと quickstart を実行確認。PyPI 公開はトークン未所持のため未実施 |
| 4 | プロバイダ実証 | OpenAI 互換（`gpt-4.1-mini`）と Ollama（`qwen2.5:7b`）で実 run | 下表「プロバイダ別」 |
| 5 | 成果の安定性 | Master の計画に「既定の形（Builder 1 + Reviewer 1、Researcher は出典が必要な時のみ、分割は独立かつ大きい成果物のみ）」を明記。`docs/config/cost-optimized.yaml`（Reviewer/Master に sonnet）を追加 | 計画の分散は継続観測（同一依頼で 2〜3 タスク） |
| 6 | UI の言語混在 | アプリ UI に EN/JA 辞書と切替（ブラウザ言語を既定） | headless Chrome で英語表示を確認（残る日本語はデータのみ） |
| 7 | 大きなタスク | Master のマイルストーン再計画（DAG 完了後に目標未達なら task 追加、`max_replans`）、検証種類の追加（html_links / json_schema / python_syntax / file_size_max / regex_count）、出力が全て公開済みなら finish_task 無しでも受入（弱いモデル対策、イベントに明記） | 決定論的テスト 44 件 pass、Ollama 7B run で milestone が実際に task を追加 |

### プロバイダ別（同じ LP 依頼）
| 経路 | モデル（プロバイダ報告） | 結果 | 呼出 | 費用 | 時間 | 備考 |
| --- | --- | --- | --- | --- | --- | --- |
| claude_cli | claude-opus-5 | completed | 39 | $1.66 | 18m37s | `docs/evidence/run4-*` |
| openai_compatible_chat | gpt-4.1-mini-2025-04-14 | completed | 14 | $0.02 | 29s | `docs/evidence/openai-*`。検証 4 件 pass、レビュー 4/4 |
| ollama | qwen2.5:7b | partial | 30 | $0 | 9m29s | `docs/evidence/ollama7b-run2-*`。LP と投稿 3 案は公開・検証済み。milestone で追加した Reviewer task が起動できないバグ → 修正済み（次回 run で再確認） |
| ollama | qwen2.5:3b | 不採用 | — | — | — | 計画 JSON の agent 名に説明文を混ぜる等、3B では計画が安定しない（正規化を追加したが推奨は 7B 以上） |

### シナリオ評価（claude_cli / claude-opus-5、2026-09-13、`docs/evidence/scenarios/`）
| シナリオ | 結果 | タスク | 成果物 | 検証 | レビュー | 呼出 | 費用 | 時間 | 備考 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LP + 投稿案（run 4） | completed | 2 | 4 | 10/10 | 6/6 | 39 | $1.66 | 18m37s | `docs/evidence/run4-*` |
| コード生成（CLI + unittest 5 件以上 + README） | completed | 2 | 4 | 14/14 | 7/7 | 48 | $1.87 | 16m16s | Reviewer が Docker サンドボックス内で `python3 -m unittest` を再実行。私が独立に実行しても 16 テスト OK |
| 出典付き調査（3 URL 比較） 1 回目 | **failed** | 3 | 2 | 0/0 | 0/0 | 13 | $0.91 | 5m02s | 依存関係がダイヤモンド型（t2→t1、t3→t1,t2）で Runtime がデッドロック → **修正** |
| 出典付き調査 2 回目（修正後） | partial | 7 | 5 | 10/13 | 5/8 | 91 | $6.07 | 23m52s | Reviewer 指摘 3 件を修正した最終版 `research-final-r2.md` を公開。セッション予算上限（$1.0）に 2 回当たり Master が partial 受入 → 上限を $1.5 に引上げ、予算超過時は 1 回継続するよう修正。予算 $6 を使い切った |
| 複数ファイル制作（4 ファイルの静的サイト） | completed | 2 | 5 | 39/39 | 12/12 | 89 | $3.03 | 14m50s | 3 ページのリンクを headless Chrome で確認。途中 1 セッションが予算上限で失敗 → Master の例外処理で再試行して完走 |

**読み方**: 完走 3 / 5 種（LP・コード・複数ファイル）、partial 1（調査、成果物あり・一部未検証）、failed 1（Runtime バグ、修正済み）。すべて同じ依頼文を 1 回ずつ。ベンチマークではなく、失敗も含めた記録です。

### 実 run で見つかった Runtime の問題（2026-09-13、すべて修正・テスト追加済み）
| 発見元 | 問題 | 対応 |
| --- | --- | --- |
| run 1 | Reviewer が複数タスクを検証すると最後の判定のみ適用 | 判定をターゲットごとに蓄積 |
| run 2 | 構造化出力の 1 ショット呼出が `max_turns` | `--max-turns 3` + 再試行 |
| run 3 | `max_model_calls=30` に到達 | 既定 120 |
| Ollama 7B | milestone で追加した Reviewer task が起動しない（対象が accepted 済み） | Reviewer の依存は accepted も可 |
| Ollama 7B | Reviewer が判定を出さずに終了すると対象が `review_pending` のまま | 判定なしで終わった場合は対象を partial（未検証）に |
| 調査 1 回目 | t2→t1、Reviewer→t1,t2 のダイヤモンド依存でデッドロック | 依存先が `review_pending` なら下流を開始可能に |
| 調査 2 回目 | セッション予算上限で task 失敗 | 予算超過は 1 回継続、既定上限 $1.5 |
| 弱いモデル全般 | 出力を全て公開したのに finish_task を呼ばず失敗 | 出力が揃っていれば受入し、イベントに「runtime が推定」と明記 |
