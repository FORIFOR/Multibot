# 実ローカルLLM受入証拠 — v46

- 固定系列: `real-readiness-v46-qwen35-fixed-20260923`
- 固定コード: `2b18649`
- モデル疎通: Ollama `agentteam-qwen35-9b-16k` の実プローブは成功
- 目標: 同じ代表文書ワークフロー10回
- 状態: 1回目の受付でHTTP 503。Docker隔離が停止していたため、LLMワークフローは開始せず、Reviewer提出0、受入0。L3判定なし。

## 観測

APIのヘルス確認は成功し、ローカルLLMの実プローブも `tool_calling=true`、`json_schema=true` で成功した。一方、実行受付は `secured command tools require Docker isolation` で拒否された。受付レスポンス、ヘルス、ディスク空き容量、プローブ、状態を [`admission-failure-rep01.json`](admission-failure-rep01.json)、[`probe.json`](probe.json)、[`status.json`](status.json)、[`attempts.json`](attempts.json) に保存した。これは環境の意図した停止であり、業務品質や本番導入可能性を示すものではない。

Docker隔離を復旧した後、同じコードで新しい固定系列v47を開始した。

## 保持場所

完全なSQLite、設定、受付失敗記録はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v46-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
