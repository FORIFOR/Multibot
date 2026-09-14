# Real-source local-Qwen acceptance series v20 (stopped after first failed run)

確認日時: 2026-09-15 JST. v19で追加した修復プロンプトを含む commit `696004e`、実際のリポジトリ資料 `PRODUCTION_PLAN.md` と `docs/evidence/operations-2026-09-14/README.md`、ローカル Ollama の `agentteam-qwen35-9b-16k` を使用した。Claude、クラウドLLM、架空データ、合成入力は使用していない。

1回目の成果物は `readiness.json` として公開されたが、現行の配信契約に失敗した。`パイン`、`ステール`、`演算主体` など、検出対象の翻訳ドリフトが残り、Data の `age` / `再開可能`、監査領域の用語条件も修正の過程で欠落した。モデルは検査失敗後に `production_ready` を変更しようとする応答も記録したため、成功扱いせず停止した。`mechanical-check.json` とイベントログに実際の失敗を保存している。

| repetition | run | result | reason |
| --- | --- | --- | --- |
| 1 | `run_1a0a167b9192a19065b` | 現行契約 fail、Reviewer未実行 | 実資料の要約品質とL3判定を安全に受入できないため停止 |
| 2–10 | — | 未実行 | 1回目の失敗を修正した新commitで再系列が必要 |

この証跡は10回の合格条件を満たさず、L1/L2/L3の到達を示さない。`access.json`、秘密鍵、Cookie、SQLite状態は含めていない。
