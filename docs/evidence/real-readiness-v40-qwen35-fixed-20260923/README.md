# Real local-Qwen readiness evidence — v40

- 固定系列: `real-readiness-v40-qwen35-fixed-20260923`
- 固定コード: `ed31037`
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、クラウドフォールバックなし）
- 目標: 10回（同じ形式未達が続いたため4回目の途中で停止）
- 状態: 受入0。Reviewer提出0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | モデル/ツール | 主な観測 |
|---:|---|---:|---:|---|
| 1 | 失敗 | 478.69秒 | 13 / 6 | `final-report.md` のみ、`readiness.json` なし |
| 2 | 中断 | 1,200.48秒 | 21 / 14 | `readiness.json` なし |
| 3 | 中断 | 1,200.94秒 | 17 / 11 | JSONを書いたが構文エラーで不合格 |
| 4 | 停止 | — | — | 形式未達が反復したため停止 |

1回目の公開成果物SHA-256は `5a2bf5d8b349a3ce57990f7bf48dd276e73804d3ab4509b057db5c900a1aa3f7`、3回目は `62223e98763ac95b30bb94f105a1f958920534dc32cdbfc8a49714c8a9f56959` であり、[観測バイト列](rep1-artifact.bin)と[3回目のJSON候補](rep3-artifact.bin)にそのまま保存した。3回目の候補はJSON構文エラーで、成功扱いのために編集していない。

## 変更の評価

v40は、`workspace_write` 後の配信検査応答を短くし、次の `publish_artifact` を明示する実装変更を検証した。モデルは一部でJSON候補を書けるようになったが、公開成果物として有効なJSONには到達せず、独立レビューも提出されなかった。自動検査の記録は保持しているが、業務品質や本番導入可能性を示すものではない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v40-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
