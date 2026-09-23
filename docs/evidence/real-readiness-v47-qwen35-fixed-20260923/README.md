# 実ローカルLLM受入証拠 — v47

- 固定系列: `real-readiness-v47-qwen35-fixed-20260923`
- 固定コード: `2b18649`
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、Claude/クラウドフォールバックなし）
- 目標: 同じ代表文書ワークフロー10回
- 状態: 3回目の実行中、同じ形式未達が2回連続したため停止。1回目は1,200秒超で中断、2回目は1,104秒で失敗、3回目は停止時点の状態を保存した。Reviewer提出0、受入0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | 主な観測 |
|---:|---|---:|---|
| 1 | 中断 | 1,200.98秒 | `readiness.json` が無い、または有効なJSONでない |
| 2 | 失敗 | 1,104.23秒 | `final-report.md` のみを公開し、`readiness.json` は無い |
| 3 | 停止 | — | 2回の同一失敗を保存して停止。結果オブジェクトは未確定 |

2回目に公開された `final-report.md` の観測バイト列は [`rep2-artifact.bin`](rep2-artifact.bin) にそのまま保存し、SHA-256は `2b66fb04e50cccaaa20ec468d29158c69c277281fd82e2def2880808dd4524d5` である。完全な試行記録は [`attempts.json`](attempts.json) と [`status.json`](status.json) に保存した。生成物を成功扱いのために編集していない。

## 変更の評価

v45で確認した長大なJSON Schemaエラーがモデルの修正判断を阻害していたため、固定コード `2b18649` では配信チェックの会話用フィードバックを欄単位の短い指示へ圧縮した。v47はその変更を実ローカルLLMで検証したが、モデルは必須フィールドや厳密な引用を満たす `readiness.json` を公開できず、Reviewerへ進まなかった。この結果を受け、RequesterのJSON Schemaを `workspace_write_json` の動的ツール入力スキーマにも広告する修正を `00059ef` として実装した。v47の結果は業務品質、顧客受入、L3の証拠ではない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v47-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
