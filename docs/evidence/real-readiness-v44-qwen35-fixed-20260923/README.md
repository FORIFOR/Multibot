# 実ローカルLLM受入証拠 — v44

- 固定系列: `real-readiness-v44-qwen35-fixed-20260923`
- 固定コード: `fd8183f`
- モデル接続確認: Ollama `agentteam-qwen35-9b-16k`（実行前プローブ成功）
- 目標: 同じ代表文書ワークフロー10回
- 状態: 1回目の受付でHTTP 422。LLMワークフローは開始せず、Reviewer提出0、受入0。L3判定なし。

## 観測

v43で確認したワークフロー指定漏れを修正した後、文書入力検証がJSON形式の配信契約を拒否した。エラーは `document workflow requires supplied text/files, no URL inputs, and exactly one text delivery contract` で、今回の入力は有効なJSON契約を使う設計だった。これは実装側の入力バリデーション条件の不整合であり、モデルの出力結果ではない。受付失敗のレスポンス、ヘルス確認、実行前プローブを [`admission-failure-rep01.json`](admission-failure-rep01.json)、[`probe.json`](probe.json)、[`status.json`](status.json)、[`attempts.json`](attempts.json) に保存した。

JSON文書契約を許可する修正を `cef86aa` で実装した。v44は業務品質、顧客受入、L3の証拠ではない。

## 保持場所

完全なSQLite、設定、受付失敗記録はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v44-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
