# 実ローカルLLM受入証拠 — v51

- 固定系列: `real-readiness-v51-qwen35-fixed-20260923`
- 固定コード: `8078758`
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、Claude/クラウドフォールバックなし）
- 目標: 同じ代表文書ワークフロー10回
- 状態: 7回目を開始したが、最初の6回が有効な`readiness.json`を生成できなかったため停止。Reviewer提出0、受入0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | 主な観測 |
|---:|---|---:|---|
| 1 | 中断 | 1,200.16秒 | 有効な`readiness.json`なし、Builderのツール呼出し2回 |
| 2 | 失敗 | 1,022.39秒 | 有効な`readiness.json`なし、Builder/Masterのツール呼出し2回 |
| 3 | 失敗 | 1,237.22秒 | 有効な`readiness.json`なし、Builder/Masterのツール呼出し2回 |
| 4 | 失敗 | 1,194.77秒 | 有効な`readiness.json`なし、Builder/Masterのツール呼出し2回 |
| 5 | 失敗 | 1,190.39秒 | 有効な`readiness.json`なし、Builder/Masterのツール呼出し2回 |
| 6 | 失敗 | 1,024.25秒 | 有効な`readiness.json`なし、Builder/Masterのツール呼出し2回 |
| 7 | 停止 | — | 6回連続の同一失敗を保存して停止。結果オブジェクトは未確定 |

完全な試行記録は [`attempts.json`](attempts.json) と [`status.json`](status.json) に保存した。各試行のイベント・アーティファクト記録と、モデルがツールへ渡したドラフトをそのまま保存した。生成物を成功扱いのために編集していない。

## 変更の評価

v51は、v50のスキーマ説明変更を戻し、生成要求の先頭と末尾で`workspace_write_json`の即時呼出しを明示した `8078758` で実行した。Builderは各回でツールを呼んだが、依頼契約を満たす有効な`readiness.json`を公開できなかった。6回連続で同じ結果となったため、7回目を停止した。これは業務品質、顧客受入、L3の証拠ではない。

7回目は停止後の実行記録が未確定であり、成功件数へ加算しない。旧合成比較とは系列を分離し、結果を混ぜていない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v51-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
