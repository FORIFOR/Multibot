# Real local-Qwen readiness evidence — v42

- 固定系列: `real-readiness-v42-qwen35-fixed-20260923`
- 固定コード: `33b20be`（JSON配列禁止の明示と、ローカルOllama温度0の再現条件を追加）
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、Claude/クラウドフォールバックなし）
- 目標: 10回（4回目の途中で、同じ形式未達が続いたため停止）
- 状態: 受入0。Reviewer提出0。L3判定なし。

## 結果

| 回 | 状態 | 実行時間 | 主な観測 |
|---:|---|---:|---|
| 1 | 失敗 | 660.90秒 | `final-report.md` のみ。`readiness.json` なし |
| 2 | 中断 | 1,200.30秒 | `readiness.json` なし |
| 3 | 中断 | 1,200.20秒 | `readiness.json` なし |
| 4 | 停止 | — | 3回連続の形式未達を保存し、次の実行を自動開始しないよう停止 |

1回目の公開成果物SHA-256は `32772652c2d1e87edba346257cf122f3007debe473f6be4d902b0ffbc9ea8227` であり、[観測バイト列](rep1-artifact.bin)にそのまま保存した。完全な試行記録は [`attempts.json`](attempts.json) と [`status.json`](status.json) に保存した。成果物を成功扱いのために編集していない。

## 変更の評価

v42は、v41で確認した配列形式を明示的に禁止し、ローカルモデルの温度を0に固定して再現性を上げた。しかし、3回とも要求された `readiness.json` を公開できず、配信経路に入る前の形式遵守が改善しなかった。Reviewer提出と受入は0件であり、業務品質や本番導入可能性を示すものではない。

## 保持場所

完全なSQLite、イベント、設定、全試行の作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v42-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
