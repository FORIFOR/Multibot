# Real-source local-Qwen acceptance series v24

確認日時: 2026-09-15 JST。固定checkoutのcommit `f93105c`、実際のリポジトリ資料 `PRODUCTION_PLAN.md` と `docs/evidence/operations-2026-09-14/README.md`、ローカル Ollama の `agentteam-qwen35-9b-16k`、Docker 分離を使用した。Claude、クラウドLLM、架空データ、合成入力は使用していない。

同じ実資料を10回実行した。`status.json` は `completed_mechanical_trials` だが、実行スクリプトの `semantic_review` は全回 pending である。機械契約を通過した実成果物は3件（rep04、rep07、rep08）で、rep04とrep07はReviewer提出まで到達した。rep07の保存成果物には「ハードネード」「键轮换与」という実際の誤変換が残り、契約が見逃したため、現時点の受入成立数は0件とした。rep08は独立レビュー未提出である。rep01〜03、rep05、rep06、rep09、rep10は中断・部分完了・失敗または契約不合格だった。

| repetition | run | runtime result | mechanical contract | Reviewer submissions | post-run finding |
| --- | --- | --- | --- | ---: | --- |
| 1 | `run_1a0a3eabbad8b197dc6` | 中断（1200秒） | fail | 0 | 禁止語・アンカー不足 |
| 2 | `run_1a0a3fd0d9d4a9ec3c1` | 中断（1200秒） | fail | 0 | 禁止語・要約契約違反 |
| 3 | `run_1a0a40f5ea4c2cc3929` | approval_required | fail | 0 | readiness.json 不成立 |
| 4 | `run_1a0a41686033b59ec78` | completed | pass | 1 | 現行契約は通過、意味レビューは pending |
| 5 | `run_1a0a426d80913836312` | partial | fail | 0 | 禁止語・出典アンカー不足 |
| 6 | `run_1a0a431cb902199839d` | failed | pass（実行結果表示） | 0 | 成果物は失敗状態で受入不可 |
| 7 | `run_1a0a442ffed28b171fe` | completed | pass | 1 | 「ハードネード」「键轮换与」の誤変換を契約が見逃し |
| 8 | `run_1a0a45142a04d7d9fa2` | partial | pass（実行結果表示） | 0 | 独立レビュー未提出 |
| 9 | `run_1a0a463f87cb3adeb7d` | failed | fail | 0 | readiness.json 不成立 |
| 10 | `run_1a0a46d3b5c6fc545b1` | partial | fail | 0 | キーcloak等の誤変換と契約違反 |

`observed-rep04-readiness.json`、`observed-rep07-readiness.json`、`observed-rep08-readiness.json` は実行時に保存された成果物をそのまま固定したもの。rep07の誤変換を回帰テストに追加し、成果物を直接書き換えて成功扱いにはしていない。次の固定系列ではこの実測フラグメントを契約で拒否する。

この系列はL3、本番導入、顧客環境の受入を示さない。`access.json`、秘密鍵、Cookie、SQLite状態、モデル資格情報はリポジトリに含めていない。
