# Real-source local-Qwen acceptance series v23

確認日時: 2026-09-15 JST。commit `21633c8`、実際のリポジトリ資料 `PRODUCTION_PLAN.md` と `docs/evidence/operations-2026-09-14/README.md`、ローカル Ollama の `agentteam-qwen35-9b-16k`、Docker 分離を使用した。Claude、クラウドLLM、架空データ、合成入力は使用していない。

同じ実資料を10回実行した。3回は成果物が完成し、機械契約とReviewer提出まで到達したが、`semantic_review` は実行スクリプト上で pending のままだった。保存した3成果物を修正後の配信契約で再検査したところ、いずれも混在語・誤記を含み不合格となった。したがって、10回の実行自体は確認できるが、受入成立数は0件であり、L1の業務品質条件やL2/L3を満たさない。

| repetition | run | runtime result | mechanical contract | Reviewer submissions | post-run finding |
| --- | --- | --- | --- | ---: | --- |
| 1 | `run_1a0a341653e403c87a5` | 中断（1200秒） | pass | 0 | Reviewer未提出 |
| 2 | `run_1a0a353b7ffcf524231` | completed | pass | 1 | 保存成果物に監査・Deployment・Business qualityの混在語 |
| 3 | `run_1a0a35c3d8f1fb20656` | 中断（1200秒） | fail | 1 | 要約欠落と翻訳ドリフト |
| 4 | `run_1a0a36e936737c8cbea` | 中断（1200秒） | fail | 0 | Business qualityの禁止語 |
| 5 | `run_1a0a380dc8c8274e002` | partial | fail | 0 | 必須フィールド欠落 |
| 6 | `run_1a0a38cb58e032057ec` | 中断（1200秒） | pass | 0 | Reviewer未提出 |
| 7 | `run_1a0a39f0fba2ee13ed1` | completed | pass | 1 | `デシフryption`、`キールドリル` などの混在語 |
| 8 | `run_1a0a3ae01a773f4b1cc` | 中断（1200秒） | fail | 0 | 中国語混入と必須語不足 |
| 9 | `run_1a0a3c0545535d84e71` | 中断（1200秒） | fail | 0 | Business qualityの引用不一致 |
| 10 | `run_1a0a3d2a47a2f7c33eb` | completed | pass | 1 | `シネティック`、`エGRESS`、`承約` などの混在語 |

`observed-rep02-readiness.json`、`observed-rep07-readiness.json`、`observed-rep10-readiness.json` は、Reviewerが通過させた実成果物をそのまま保存したもの。これらを修正後の配信契約で再検査し、翻訳ドリフトを検出する回帰テストを追加した。成果物を直接書き換えて成功扱いにはしていない。

この系列はL3、本番導入、顧客環境の受入を示さない。`access.json`、秘密鍵、Cookie、SQLite状態、モデル資格情報はリポジトリに含めていない。
