# 実資料ワークフロー証跡 v4（qwen2.5-7B / 2026-09-14）

この系列は、現行の本番受入契約を含む固定checkout `425723ed73b7080e0b9576c9c49038ed6e96c792` で、実際のローカルOllamaモデル `agentteam-qwen25-7b-16k` を使って開始した。目標は10回の実資料ワークフローだった。

実行開始前の能力プローブで、JSON Schema出力は確認できたが、OpenAI互換ドライバが受け取るtool calling形式を確認できなかった（`tool_calling=false`）。そのためワークフローを1回も受入れず、Builder、Reviewer、アーティファクトは生成していない。プローブ失敗を無視して続行することは、本番導入判定を偽るため行わなかった。

| 項目 | 結果 |
| --- | --- |
| モデル | `agentteam-qwen25-7b-16k` |
| モデルdigest | `f0e20bb85d433457a801ea7c0e28034c59e686ac230fdb6eb692a62ca8745dfa` |
| Ollama | `0.33.3` |
| 目標試行回数 | 10 |
| tool calling | `false` |
| JSON Schema | `true` |
| admitted runs | 0 |
| 判定 | 停止（能力不足。成功扱いなし） |

## 収録ファイル

- `fingerprint.json`: checkout、資料、設定、モデルdigestの固定値
- `probe.json`: 実モデル能力プローブの全結果
- `goal.txt`: 実行時の依頼文
- `delivery-requirements.json`: 実行時に登録された受入スキーマ
- `result.json`: 停止理由とプロセス結果

この結果はqwen2.5-7BがMultibotの現行プロバイダ境界で使用可能だと示すものではない。tool calling形式を実際に通過した別のローカルモデル系列で、同じ資料と受入スキーマを再試験する必要がある。L1の10回再現、L2、L3の達成根拠には算入しない。
