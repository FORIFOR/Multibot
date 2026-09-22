# Real local-Qwen readiness evidence — v39

- 固定系列: `real-readiness-v39-qwen35-fixed-20260923`
- 固定コード: `ac1bea0`
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、クラウドフォールバックなし）
- 目標: 10回（同じ失敗が3回続いたため4回目の計画中に停止）
- 状態: 受入0。Reviewer提出0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | モデル/ツール | 主な観測 |
|---:|---|---:|---:|---|
| 1 | 失敗 | 1,026.71秒 | 24 / 11 | `readiness.json` なし、Builderが完了処理を反復 |
| 2 | 中断 | 1,200.85秒 | 13 / 8 | `readiness.json` なし |
| 3 | 中断 | 1,200.61秒 | 17 / 16 | `readiness.json` なし |
| 4 | 停止 | — | — | 3回連続の形式未達を確認し、起動直後に停止 |

1回目は依頼されたJSONではなく `final-report.md` を公開し、機械判定は `readiness.json missing or invalid JSON` で不合格だった。観測成果物のSHA-256は `6169518093f1c01c733b029fe5ed7767176cc2d801252a51d3ac0c2bd2f1fdd8` で、[生成バイト列](observed-artifact.bin)にそのまま保存した。後から成功扱いにする編集は行っていない。

## 変更の評価

v39はv38の例文追加に加え、Builderプロンプトへトップレベルと行ごとのJSON項目を明記した系列である。3回ともJSON成果物へ到達せず、スキーマの再発見や完了処理の反復が続いたため、例文とプロンプトの明示だけではローカルモデルの納品契約を安定化できないことを確認した。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v39-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
