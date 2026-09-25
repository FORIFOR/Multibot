# 実装・検証状況

## 2026-09-26 決定論的テストと画面の検証

ブランチ `fix/product-improvements-20260925` の時点で、次を実行しました。以下の過去の節にある件数は、その日の記録として残しています。

| 種別 | 結果 |
| --- | --- |
| バックエンドの決定論的テスト（scripted provider） | 210 passed / 4 skipped（Docker と age が必要なテストはこの Mac では未実行、CI で実行） |
| `ruff check agentteam`（pyflakes 規則のみ） | 0 件 |
| フロントエンドの単体テスト 6 本・型検査・ビルド | すべて成功。lint は警告 20 件、エラー 0 件 |
| ブラウザ回帰 5 本（ui-polish / three-step / ui / workroom / a11y） | すべて成功。axe の 0 件は適合を意味しません |
| 人による手動 GUI 確認・実機 iPhone・実モデルでの受入 | 未実施 |

scripted provider は実モデルの挙動を証明しません。業務品質・L2/L3 の判定は上の数値から行いません。

## 2026-09-15 最新の実資料試験

受入系列を commit `c60fa71` に固定し、ローカル Ollama の `agentteam-qwen35-9b-16k` を使い、実際の `PRODUCTION_PLAN.md` と運用資料だけを入力にした系列を確認しました。v18の第1・2回は旧配信契約では機械検証とReviewer提出を通過しましたが、出力に「パイン」「ロカル」「アデュータ」「actual-source」などの翻訳崩れが残る契約の抜けを確認したため停止しました。[v18証跡](evidence/real-readiness-v18-qwen35-fixed-2026-09-15/README.md)を保存し、現行コードの配信境界に検出語と領域別の根拠語チェックを追加しました。修復例を明示したv20を1回再試験しましたが、`パイン`、`ステール`、`演算主体`などが残り現行契約でfailとなったため、Reviewer前に停止しています。[v20証跡](evidence/real-readiness-v20-qwen35-fixed-2026-09-15/README.md)。現行の決定論的テストは **107 passed / 1 skipped**。10回すべてと意味品質の独立評価が揃うまで、L1の反復条件・L2・L3を達成扱いにしません。

## 2026-09-14 監査更新

[企業紹介・有償PoC・本番の判定基準](ENTERPRISE_READINESS.md)を分離しました。L1資料はありますが、同一代表業務10回の条件は未達。L2・L3も未到達です。

本番化では、認証・SSO・権限・永続キュー・削除・暗号化復元・監査収集と監視画面を実装し、[更新とロールバックの13項目](evidence/release-operations-2026-09-14/README.md)も実機で確認しました。[通信経路の修正後は102件pass](evidence/provider-transport-2026-09-14/README.md)。実資料の初回業務試験では、日本語要約の欠落をReviewerが見逃し、誤完了しました。[元の失敗を保持](evidence/real-readiness-v1-2026-09-14/README.md)し、依頼者の必須条件を実行基盤でも検査する修正を加えています。本番の設置先・企業IdP・業務品質・運用条件の受入は未完了です。

修正版では、Reviewer's `run_check(json_schema)` が依頼者の保存済みSchemaを直接使えるようにし、不正Schemaを `blocked` として記録します。現行の決定論的テストは **105 passed / 1 skipped**。実資料のQwenローカル試験v3は[3実行分を保存](evidence/real-readiness-v3-2026-09-14/README.md)し、旧ランタイムの合格を再監査で不合格にした語崩れを次系列の配信Schemaへ反映しました。

qwen2.5-7Bの次系列は[実能力プローブで停止](evidence/real-readiness-v4-qwen25-2026-09-14/README.md)しました。JSON Schemaは通過しましたがtool callingを通過せず、実資料runや成果物を受入れに算入していません。

tool callingを通過したqwen3.5の[実資料v5系列](evidence/real-readiness-v5-qwen35-2026-09-14/README.md)を開始し、1回目は初版不合格→revision 2修正、Reviewer全条件pass、機械判定passで完了しました。10回条件の残りは継続中で、本番導入可能判定はしていません。

強化契約の[v6](evidence/real-readiness-v6-qwen35-2026-09-14/README.md)は英語原文コピー後にmodel callが停止し、[v7](evidence/real-readiness-v7-qwen35-2026-09-14/README.md)は4revisionを公開したものの監査領域の必須語不足で停止しました。両方ともReviewer未実行で、10回条件には算入していません。現在の反復受入は、これらの停止系列とは別の固定チェックアウトで実行します。

v8は初回計画を受理し、初版を公開したものの、`stale`と「アクター監査」の混在を検出後に修正ループが`max_tokens`へ達しました。Builderをpartial、Reviewerをcancelledとして停止し、成果物とイベントを[保存](evidence/real-readiness-v8-qwen35-2026-09-14/README.md)しました。10回条件には算入していません。

v10は実Ollamaの初版`readiness.json`が依頼者Schemaをpassしましたが、Masterが受入条件IDを出力パスとして宣言したためpartialで停止しました。計画Validatorにこの誤りの拒否を追加し、証跡を[保存](evidence/real-readiness-v10-qwen35-2026-09-14/README.md)しました。Reviewer受入と10回条件は未達です。

v11ではその計画誤りを拒否して再生成し、run 1・2が実Ollamaで初版不合格→revision 2、Schema pass、独立Reviewer pass、`completed`まで到達しました。run 3はSchema不合格後にBuilderがpartialとなり、Reviewer起動前に停止しました。[全証跡](evidence/real-readiness-v11-qwen35-2026-09-14/README.md)を保存しています。受入済みは2/10で、10回条件とL2/L3は未達です。

v12ではRuntimeの`max_tokens`後コンテキスト圧縮を実Ollamaで検証しました。run 1は旧契約では初版の監査用語違反を検出後、revision 2、Schema pass、独立Reviewer pass、`completed`まで到達しました。[全証跡](evidence/real-readiness-v12-qwen35-2026-09-14/README.md)を保存しています。run 1の出力にはReviewerが検出できなかった「キーcloak」「パインされた」「バックス」が残ったため、最新契約で再監査すると不合格となり、これらを契約で拒否する回帰テストを追加しました。run 2は英語`remaining`と必須語不足を検出後、1200秒の壁時計上限で`interrupted`となり、Reviewer未実行として保存しました。run 3も系列停止時に`interrupted`となりました。旧契約での受入はv11/v12合計3/20ですが、現行契約での受入済みは2/20です。10回条件とL2/L3は未達です。

50課題×3回の比較は、追加記録を反映した最新ペアでチーム69 completed / 5 partial / 76 failed、単一150 completedです。上限の影響は79ペア。前回47/3/100の記録も残し、重複を除くチーム252試行を台帳に含めています。元の採点ではチームにも完了後不合格が1件あり、誤完了ゼロとは主張しません。

[追加記録・Reviewer試験の限界・再開手順](evidence/readiness-2026-09-14/README.md)。週次上限の停止判定と重複スナップショットの集計を、実記録を用いた6テストで確認しました。以下は過去時点の記録を含みます。

## 検証の種別
| 種別 | 状態 | 根拠 |
| --- | --- | --- |
| 決定論的テスト（fake provider） | **53 件 PASS**（CI では Linux の Docker 隔離テストも実行） | `cd backend && .venv/bin/python -m pytest -q`（Docker サンドボックスのテストは daemon がある時のみ実行） |
| 実 LLM 協働スモーク | **実施（claude_cli / claude-opus-5）** | 2026-09-13。run 1: 成果物 3 点・検証 12 件 pass・handoff 2 件・$1.69（定価換算）・760 秒。最終状態は `partial`（複数ターゲットレビューのバグ、修正済み）。run 2/3 は計画呼出の `max_turns` と `max_model_calls=30` の上限で失敗 → いずれも修正・調整済み。証拠: `docs/evidence/run1-*` |
| 実 API の疎通確認（probe） | **実施（claude_cli）** | tool calling / JSON schema ともに pass、`model_reported=claude-opus-5` |
| ブラウザ UI スモーク（headless Chrome） | 実施（fake provider、**CI で毎 push、JA/EN**） | `frontend/scripts/ui-smoke.mjs`：Home → 依頼開始 → Run 画面（チャット/時系列/報告）→ 設定 → run が completed になるまで待機。console/page error 0 件、エラー時は exit 1 |
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
| J. Acceptance | 一部 | 実LLMスモーク・比較記録あり。全受入条件の達成と業務成功率の確立は未完了（冒頭の監査参照） |

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
| 同一総予算 single-agent 比較 | 実装済み、比較試験は利用上限の影響あり（上記監査参照） |
| 共有 Replay（マスク付き公開） | 未実装（初期 OFF のまま） |

## セキュリティ要件（docs/blueprint/SECURITY.md）
- 実装: key 参照のみ保存、秘匿処理、SSRF ガード（private/loopback/metadata・redirect 各 hop）、tool scope、write scope、
  macOS seatbelt（ネットワーク遮断・workspace 外書込禁止）、生成 HTML の sandbox CSP + iframe sandbox、承認の hash/nonce/期限。
- 未実装: capability token による多ユーザ分離、外部署名付きログ、保存期限・削除ポリシー。
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

## 再現性評価（2026-09-13 午後、同一依頼 × 3 回、`docs/evidence/scenarios/rerun-2026-09-13/`）

v0.2.0 の 5 シナリオは各 1 回だけだったので、4 シナリオを同じ依頼文・同じ設定（claude_cli / opus、予算 $6、上限 120 呼出）で 3 回ずつ、4 プロセス並列で実行しました。
`backend/scripts/eval_scenarios.py` で実行し、`backend/scripts/summarize_evals.py` で集計。**フィルタなし**（失敗も含めて全 run を数えています）。
「検証」は run 中に走った全 check イベントの累計で、途中 revision で fail → 修正 → pass した分も含みます（最終レビューは別列）。費用は定価換算です。

| シナリオ | runs | completed | partial | failed | タスク数 | 検証 pass | レビュー pass | 呼出 | 費用 | 時間 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| コード生成（CLI + unittest + README） | 3 | **3** | 0 | 0 | 2 | 48/48 | 22/22 | 53–64 | $2.09–3.14 | 16–19 min |
| 複数ファイル制作（4 ファイルの静的サイト） | 3 | **3** | 0 | 0 | 2 | 91/93 | 22/22 | 59–66 | $1.62–1.72 | 15–17 min |
| LP + 投稿案 | 3 | **2** | 1 | 0 | 2–6 | 67/78 | 38/39 | 42–123 | $1.70–5.67 | 20–37 min |
| 出典付き調査（3 URL 比較） | 3 | **0** | 3 | 0 | 4–5 | 105/129 | 21/24 | 87–128 | $5.48–6.11 | 31–35 min |

| シナリオ | # | run_id | 結果 | タスク | 成果物 | 検証 | レビュー | 呼出 | 費用 | 時間 | 失敗理由 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| code | 1 | run_1a098ec7bb2ee0af056 | completed | 2 | 4 | 16/16 | 7/7 | 64 | $3.14 | 15m32s | — |
| code | 2 | run_1a098fab5737a95b69f | completed | 2 | 3 | 16/16 | 7/7 | 57 | $2.64 | 18m35s | — |
| code | 3 | run_1a0990bb8d5338c80c1 | completed | 2 | 4 | 16/16 | 8/8 | 53 | $2.09 | 16m36s | — |
| long | 1 | run_1a098ec768186667b20 | completed | 2 | 4 | 32/32 | 7/7 | 63 | $1.67 | 17m27s | — |
| long | 2 | run_1a098fc717cfd424acd | completed | 2 | 4 | 27/27 | 8/8 | 59 | $1.62 | 16m11s | — |
| long | 3 | run_1a0990b44109604a46d | completed | 2 | 4 | 32/34 | 7/7 | 66 | $1.72 | 15m16s | — |
| lp | 1 | run_1a098ec7a10d7e2b8bb | completed | 2 | 2 | 15/16 | 9/9 | 42 | $1.70 | 20m26s | — |
| lp | 2 | run_1a098ff306b6fc46ca1 | completed | 2 | 3 | 22/30 | 11/11 | 60 | $2.27 | 22m40s | — |
| lp | 3 | run_1a09913ef4bdd072a5f | partial | 6 | 7 | 30/32 | 18/19 | 123 | $5.67 | 36m32s | 当初計画 2 task は $1.29 で accepted。milestone 2 回で文言修正 task を 4 つ追加し、最後の Builder が 120 呼出上限に到達 |
| research | 1 | run_1a098ec78e37565599e | partial | 4 | 4 | 16/28 | 8/10 | 87 | $5.97 | 34m45s | 当初計画 2 task は accepted。milestone 追加の t3/t4 が予算 $6 到達 |
| research | 2 | run_1a0990c4854336a2ff3 | partial | 5 | 7 | 22/26 | 7/8 | 103 | $6.11 | 34m44s | 当初計画 2 task + 追加 t3/t4 は accepted。追加 t5（訂正メモ）が予算 $6 到達 |
| research | 3 | run_1a0992c15d5de322963 | partial | 4 | 3 | 67/75 | 6/6 | 128 | $5.48 | 31m27s | 当初計画 2 task は accepted。追加 t4 が 120 呼出上限に到達 |

**独立確認**: code 3 run の生成テストを私が手元で `python3 -m unittest` 実行 → 18 / 19 / 17 件すべて OK。long 3 run の 4 ファイルを自前スクリプトで検査 → 内部リンク切れ 0、外部 URL 0、全ページ title と viewport あり。

**読み方**
- コードと複数ファイル制作は 3/3 完走、計画は毎回 Builder 1 + Reviewer 1 で安定。費用・時間のばらつきも小さい。
- LP は 3 回中 2 回完走。partial の 1 回は成果物が受入済みのあとに Master が「表現の根拠」の磨き込みを 2 回追加し、上限に当たったもの。
- 出典付き調査は 3 回とも partial。**共通原因は 2 つ**: (1) Reviewer の既定ツールに `web_fetch` が無く、依頼文が求める「出典に実在するか」の照合ができない → Master が代替 task（生取得ログ・機械照合）を追加 → (2) 追加 task が予算 $6 または 120 呼出に到達。3 回とも**当初計画の research.md は accepted** で、成果物自体は出ています。

**この評価から入れた修正**（すべて評価後、決定論的テストで確認。実 run での再確認は下の「修正後 1 回」のみ）
| 問題 | 修正 |
| --- | --- |
| Reviewer が出典を取得できない | 既定の Reviewer ツールに `web_fetch` を追加、Reviewer プロンプトに「出典は取得して照合、取得不可は unverified」を追記 |
| 残予算・残呼出が 1 セッション分に満たないのに milestone 再計画が task を追加し、その task が上限で失敗して run が partial になる | 残予算 < `max_session_cost_usd` または残呼出 < `max_session_turns` なら再計画をスキップし、`plan.milestone` イベントに `skipped: limits` と理由を記録 |
| Master が受入済みの成果物の磨き込みを追加し続ける | milestone プロンプトに残予算をセッション数で提示し、「成果物が全て受入済みで残るのが表現の磨きだけなら何も追加しない」「予算で完走できない task は追加しない」を明記 |
| partial / failed の run に理由が無い（`reason: None`） | 未受入 task とその理由を 1 行にまとめて run の `blocked_reason` に記録。当初計画が全て accepted なら、その旨を先頭に付ける |

**修正後 1 回**（research、同一依頼・同一設定）: **completed**（`research-postfix/research-run_1a0994af796a48c111f`）。計画は Researcher 1 + Reviewer 1、Reviewer が `web_fetch` で 3 出典を実際に再取得して 5/5 pass、milestone は「追加タスクなし」で終了。24 呼出、$2.05、8m44s。修正前 3 回の平均（$5.85、33 分、partial）に対して費用 1/3・時間 1/4 で完走。**ただし 1 回だけの結果**で、3 回シリーズの再実施はしていません。

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
