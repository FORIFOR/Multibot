# Real local-Qwen readiness evidence — v35

- 固定系列: `real-readiness-v35-qwen35-fixed-20260923`
- 固定コード: `ea946a0`
- 実行日時: 2026-09-23 00:43–01:55 JST
- モデル: Ollama `agentteam-qwen35-9b-16k`（同時実行なし、クラウドフォールバックなし）
- 目標: 10回（1回目で停止）
- 実行: 1回、716.09秒、モデル17回・ツール16回
- 状態: 中断（停止時の `server shutting down`）。受入合格には数えない。

## 観測結果

Builderは依頼された `readiness.json` ではなく `MULTIBOT-PRODUCTION-SUMMARY.md` を公開した。公開成果物のSHA-256は `3f275a7d8315389fa9a437dfc03a23b2179af4d77c77425c2cfcabd940a6b70f` で、依頼者のJSON契約に適合しないことを実行中のスキーマ検査が記録している。Reviewerの判定は提出されていない。

成果物のバイト列は[観測成果物](observed-artifact.md)にそのまま保存した。これは試験の証拠であり、成功扱いにするための編集は行っていない。

## 保持場所

完全なSQLite、イベント、設定、作業領域はローカルの `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v35-qwen35-fixed-20260923` に保持している。合成比較や顧客環境の証拠には使用しない。
