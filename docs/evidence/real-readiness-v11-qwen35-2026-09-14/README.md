# 実資料ワークフロー証跡 v11（qwen3.5 / 2026-09-14）

計画検査、短いSchema修正ヒント、用語固定を含むcheckout `af15e98` で、実Ollamaモデル `agentteam-qwen35-9b-16k` を使った10回目標の系列を開始した。能力プローブはtool calling / JSON Schemaともにpassした。

## run 1 / run 2

初回計画はReviewer依存の不足で拒否され、MasterがBuilder→Reviewerの計画を再生成して受理された。Builderの初版はDeploymentの「アドバイザリ」不足で不合格になったが、検査結果を受けたrevision 2を公開し、依頼者Schemaをpassした。Reviewerはrevision 2を再読し、8領域、`evidence_quote`の原文一致、日本語要約、Schema passを確認して全条件をpassした。RuntimeはBuilderとReviewerを`accepted`として記録し、runを`completed`にした。

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e54e396dd8adf35` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| 初版 | 契約不合格（Deploymentの必須語不足） |
| 受入revision | readiness.json r2、SHA-256 `54a8d048ca706d26e16d04cc78d7296b00601c58c4513913800dd3170582a2f6` |
| Reviewer | 1件、全条件pass |
| 実測 | 17 model calls、14 tool calls、入力200,445 tokens、出力8,381 tokens、778.55秒 |
| 終了状態 | `completed`、mechanical pass、false completionなし |

run 2も同じ固定条件で完了した。初版は英語混在と必須語不足で不合格だったが、revision 2（SHA-256 `48afe8e2e861e878cae265162278fa952f213443b75b2885b6a9d281ad15768e`）がSchemaをpassし、Reviewerが全13条件をpassした。実測は19 model calls、17 tool calls、入力233,966 tokens、出力9,239 tokens、869.70秒である。

2/10回が受入済みであり、L1の10回反復条件、L2、L3の達成を意味しない。`production_ready`は資料どおり`false`で、外部IdP、TLS/DNS、独立攻撃レビュー、可用性、保持・RPO/RTO、アラート運用、SLO/SLAは未検証のまま記録されている。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`: 系列固定値と実能力プローブ
- `01-run_1a09e54e396dd8adf35/`: run JSON、全イベント、初版・修正版・最終レポートの実bytesとSHA台帳
- `02-run_1a09e60c5aa5e243693/`: run 2の同一形式の実行証跡
