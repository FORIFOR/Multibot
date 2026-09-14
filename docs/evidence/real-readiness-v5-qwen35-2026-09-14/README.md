# 実資料ワークフロー証跡 v5（qwen3.5 / 2026-09-14）

現行の受入契約を含む固定checkout `a176479c774fe1e16e8a8d321ae4a420f626256b` で、実際のローカルOllamaモデル `agentteam-qwen35-9b-16k` を使って、実資料（`PRODUCTION_PLAN.md` と検証済み`README.md`）から `readiness.json` を作成する系列を開始した。目標は10回の独立実行である。

能力プローブはtool callingとJSON Schemaの両方が`true`で通過した。1回目はBuilderが初版を生成したが、保存済みの依頼者Schemaが`アドバザリ`という不正な語を検出して不合格にした。Builderは初版を残したままrevision 2を作り、同じSchemaとJSON妥当性検査にpassした。Reviewerはrevision 2を再読し、8領域、`evidence_quote` の原文一致、事実に基づく日本語要約、L3未達判定を確認して全3条件をpassした。

## 実測（進行中）

現在2/10回が完了し、どちらも現行機械契約と独立Reviewerをpassした。3回目以降は同じ固定条件で継続中である。

### 1回目

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09df28c7909636216` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| Ollama | `0.33.3` |
| 結果 | `completed` |
| 成果物 | `readiness.json` revision 2 |
| 成果物SHA-256 | `57dd274d31e2ccc7a7b206479bd0fdbbc143177474cbf2d0ceaed79655106eee` |
| 現行機械判定 | pass |
| Reviewer | 1件、t1a1〜t1a3すべてpass |
| 誤完了（機械判定） | false |
| 実行時間 | 912.107秒 |
| 使用量 | 19 model calls / 15 tool calls / 205,152 input tokens / 10,121 output tokens |

### 2回目

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e007b47ce3b4033` |
| 結果 | `completed` |
| 成果物 | `readiness.json` revision 1 |
| 成果物SHA-256 | `425152f28e2ec8341c63b96fdf8f8006ea2992481fce237316b3e503ccaee1e5` |
| 現行機械判定 | pass |
| Reviewer | 1件、t2a1 pass |
| 誤完了（機械判定） | false |
| 実行時間 | 599.494秒 |
| 使用量 | 20 model calls / 15 tool calls / 204,880 input tokens / 6,382 output tokens |

1回目は10回条件の1回分にすぎず、L1の10回再現条件、L2、L3の達成を意味しない。`readiness.json` 内の`production_ready`も資料どおり`false`である。本番TLS/DNS、企業IdP、独立攻撃レビュー、負荷・可用性、保持・RPO/RTO、アラート運用、SLO/SLAなどの外部受入条件は未達のまま記録されている。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`: 系列固定値と能力プローブ
- `01-run_1a09df28c7909636216/`: run JSON、イベントJSONL、全revisionのアーティファクトbytes、SHA台帳
- `artifact-000.bin`: runtimeが生成した最終レポート
- `artifact-001.bin`: 不合格だった初版
- `artifact-002.bin`: Reviewerが確認したrevision 2

3回目以降は同じモデルdigest・checkout・Schemaでバックグラウンド実行中である。各runは完了後に個別の証跡として追加し、失敗・中断・部分完了を成功へ書き換えない。
