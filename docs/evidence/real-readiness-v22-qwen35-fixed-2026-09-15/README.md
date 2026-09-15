# Real-source local-Qwen acceptance series v22 (stopped)

確認日時: 2026-09-15 JST。修正済み commit `09418e4`、実際のリポジトリ資料 `PRODUCTION_PLAN.md` と `docs/evidence/operations-2026-09-14/README.md`、ローカル Ollama の `agentteam-qwen35-9b-16k` を使用した。Claude、クラウドLLM、架空データ、合成入力は使用していない。

3回の実行を同じ固定条件で行った。いずれも1200秒の壁時計上限までに独立Reviewerの提出がなく、10回の受入条件には算入しない。第2回は機械的な配信契約だけは通過したが、Reviewer提出が0件のため受入成立とは扱わない。第1回と第3回は生成された要約の用語・言語条件に違反した。各回の生イベント、成果物、実行状態は個別証跡として保持している。

| repetition | run | result | reason |
| --- | --- | --- | --- |
| 1 | `run_1a0a1964e3f679affc5` | 中断、機械契約 fail | 1200秒上限。`アーチファクト`、`audit`、`監査者`、`カーソル` などの要約条件違反、Reviewer提出0件 |
| 2 | `run_1a0a1a8a0ef7ee39c1b` | 中断、機械契約 pass | 1200秒上限。Reviewer提出0件のため受入未成立 |
| 3 | `run_1a0a1baf5fb29456212` | 中断、機械契約 fail | 1200秒上限。英語・途中翻訳語の混入など要約条件違反、Reviewer提出0件 |
| 4–10 | — | 未実行 | 第4回の入場時にHTTP 503。保護されたコマンド実行にはDocker分離が必要だが、実行時のDockerデーモンが利用できなかったため停止 |

この系列は10回の合格条件を満たさず、L1の実資料受入、L2、有償PoC、本番導入可能性を示さない。Dockerが利用可能になった場合も、同じ系列を自動再開せず、新しい固定commit・証跡ルートで再評価する。`access.json`、秘密鍵、Cookie、SQLite状態、モデル資格情報はリポジトリに含めていない。
