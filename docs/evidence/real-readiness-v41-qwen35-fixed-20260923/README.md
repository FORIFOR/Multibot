# Real local-Qwen readiness evidence — v41

- 固定系列: `real-readiness-v41-qwen35-fixed-20260923`
- 固定コード: `8b58dec`（引用内の二重引用符をJSON文字列としてエスケープする指示を追加）
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、Claude/クラウドフォールバックなし）
- 目標: 10回（8回目の途中で、同じ形式・内容の失敗が続いたため停止）
- 状態: 受入0。Reviewer提出0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | 主な観測 |
|---:|---|---:|---|
| 1 | 部分完了 | 806.73秒 | `readiness.json` を公開したがトップレベルが配列で、要求されたオブジェクト契約に不一致 |
| 2 | 失敗 | 86.15秒 | `readiness.json` なし。`final-report.md` のみ |
| 3 | 中断 | 1,204.84秒 | `readiness.json` なし |
| 4 | 中断 | 1,200.51秒 | JSONは公開したが、8領域・引用・日本語・禁止語などの契約に多数不一致 |
| 5 | 中断 | 1,200.95秒 | `readiness.json` なし |
| 6 | 失敗 | 1,215.90秒 | `readiness.json` なし。`final-report.md` のみ |
| 7 | 中断 | 1,200.11秒 | `readiness.json` なし |
| 8 | 停止 | — | 7回までの失敗を保存し、次の再実行を自動開始しないよう停止 |

1回目に公開されたJSON候補はSHA-256 `a9902c681685505a7d945cf3f2516ad933549f6e6a787c1c28f4e71d543e7642`、4回目は `9f89812f324ef5e309232471df419c9e42add2ec73e90a10d0d6622eca60dd72` である。[観測バイト列](rep1-readiness.bin)と[4回目の観測バイト列](rep4-readiness.bin)にそのまま保存し、成功扱いのための編集はしていない。完全な試行記録は [`attempts.json`](attempts.json) と [`status.json`](status.json) に保存した。

## 変更の評価

v41は、実資料の残条件に二重引用符が含まれる場合にRFC 8259のJSON文字列エスケープを明示した。1回目はJSONとして解析できたが配列を公開し、4回目はトップレベルや引用、英語混在、禁止語などの契約不一致が残った。引用エスケープの指示だけでは、ソースに忠実な日本語要約と配信形式を安定させられなかった。Reviewer提出と受入は0件であり、業務品質や本番導入可能性を示すものではない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v41-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
