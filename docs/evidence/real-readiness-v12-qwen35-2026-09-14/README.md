# 実資料ワークフロー証跡 v12（qwen3.5 / 2026-09-14）

Runtimeのコンテキスト圧縮と、実行時の依頼者Schemaを固定したcheckout `1a4807d` で、実Ollamaモデル `agentteam-qwen35-9b-16k` を使った10回目標の系列を開始した。能力プローブはtool calling / JSON Schemaともにpassした。新しい受入試行は、ユーザーの条件に合わせてリポジトリの実資料だけを入力にしている。

## run 1

初回計画はReviewer依存の不足で拒否され、MasterがBuilder→Reviewerの計画を再生成して受理された。Builderの初版はAudit / monitoringの禁止語で不合格になった。Runtimeは失敗内容を短く圧縮してBuilderへ渡し、revision 2を公開した。revision 2は依頼者Schemaをpassし、Reviewerが原資料との照合、8領域の順序、引用の一致、日本語要約、L3未達判定を確認してpassした。

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e7a5cdc83e9f62a` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| 初版 | 契約不合格（Audit / monitoringの禁止語） |
| 受入revision | readiness.json r2、SHA-256 `cb26861ea8ecdf0167112a120c5b0db3a6a2071f74a886ae6f5725e67d4c07e1` |
| Reviewer | 1件、全条件pass |
| 実測 | 16 model calls、15 tool calls、入力184,542 tokens、出力6,331 tokens、673.17秒 |
| 終了状態 | `completed`、mechanical pass、false completionなし |

run 1の保存済みJSONには、後から確認できる半端な技術語（「キーcloak」「パインされた」「バックス」）が残った。Reviewerのpassだけでは自然な用語変換まで保証できないため、これらを検出する契約回帰テストを追加した。過去の合格記録は改変せず、次回系列からは同じ出力を自動不合格とする。

## run 2 / run 3

run 2は同じ固定条件で開始し、初版の`remaining`英語コピーと必須語不足を検出した。Builderは1200秒の壁時計上限までに修正版を公開できず、Reviewerは起動前だった。Runtimeは`interrupted`、`wall-clock limit reached`として保存し、機械判定はfail、review submissionは0件とした。受入には算入しない。

run 3はrun 2の停止後に開始されたが、系列停止のためサーバ終了時に`interrupted`となった。成果物を受入へ算入せず、run 2の全イベント・revision・利用量と、系列停止時のattempts/statusを収録した。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`: 系列固定値と実能力プローブ
- `01-run_1a09e7a5cdc83e9f62a/`: run 1の全イベント、初版・修正版・最終レポートの実bytesとSHA台帳
- `02-run_1a09e84a3449aa4c8f5/`: run 2の上限停止、初版成果物、全イベントとSHA台帳
- `series-status-at-stop.json`、`attempts-at-stop.json`: run 3停止時の系列状態と全試行記録

旧契約での受入はこの系列で1/10だったが、追加した最新契約でrun 1の用語崩れを再監査すると不合格になる。したがって現行契約での受入済みはv12では0/10、v11と合わせて2/20である。いずれもL1の10回反復条件、L2、L3の達成を意味しない。`production_ready`は資料どおり`false`で、外部IdP、TLS/DNS、独立攻撃レビュー、可用性、保持・RPO/RTO、アラート運用、SLO/SLAは未検証のまま記録されている。
