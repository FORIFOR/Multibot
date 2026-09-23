# 実ローカルLLM受入証拠 — v43

- 固定系列: `real-readiness-v43-qwen35-fixed-20260923`
- 固定コード: `3f428d0`
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、Claude/クラウドフォールバックなし）
- 目標: 同じ代表文書ワークフロー10回
- 状態: 10回を機械的に実行したが、全10回が `readiness.json missing or invalid JSON`。Reviewer提出0、受入0。L3判定なし。

## 観測

Masterに `workflow: document` が渡っておらず、文書ワークフローではなく通常の計画生成経路に入っていた。その結果、絶対 `/tmp` パスを含む計画や配信契約のない計画が生成され、Builder/Reviewerによる受入に進まなかった。これはモデル品質だけではなく、実装側のワークフロー指定漏れである。生成物を成功扱いのために書き換えていない。

完全な試行記録は [`attempts.json`](attempts.json) と [`status.json`](status.json) に保存した。1回目の観測バイト列は [`rep1-artifact.bin`](rep1-artifact.bin) にそのまま保存し、SHA-256は `e6f08be55ec7127cc8d1a2da0eb374b433cb001fb1f0d49c1c94637b18a2a621` である。

この観測を受け、文書ワークフローを明示する修正を `fd8183f` で実装した。v43の結果は業務品質、顧客受入、L3の証拠ではない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v43-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
