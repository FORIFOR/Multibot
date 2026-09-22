# Real local-Qwen readiness evidence — v36

- 固定系列: `real-readiness-v36-qwen35-fixed-20260923`
- 固定コード: `2f9093f`
- 実行日時: 2026-09-23 00:58–01:06 JST
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、クラウドフォールバックなし）
- 目標: 10回（1回目で停止）
- 実行: 1回、487.38秒、モデル7回・ツール5回
- 状態: 中断（停止時の `server shutting down`）。受入合格には数えない。

## 観測結果

ローカルモデルが `workspace_write` に内容と編集分岐を同時に送り、契約違反として拒否された。その後の実行にも公開成果物はなく、Reviewerの判定もない。成果物を直接書き換えて成功扱いにはしていない。

## 保持場所

完全なSQLite、イベント、設定、作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v36-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
