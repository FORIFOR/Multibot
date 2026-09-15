# Real-source local-Qwen acceptance series v25

確認日時: 2026-09-15 JST。固定checkoutのcommit `52e702f`、実際のリポジトリ資料、ローカル Ollama の `agentteam-qwen35-9b-16k`、Docker 分離を使用した。Claude、クラウドLLM、架空データ、合成入力は使用していない。

同じ実資料を10回実行した。`status.json` は `completed_mechanical_trials` だが、`semantic_review` は全回 pending であり、受入成立数は0件である。第4回は一時的に機械契約を通過したが、後続の実生成物にはトークン失効を「リバイス」とする誤訳が残った。第1〜3、5〜10回は要約不足、英語原文コピー、必須行欠落、JSON不成立、または契約不合格だった。

| repetition | run | runtime result | mechanical contract | Reviewer submissions | post-run finding |
| --- | --- | --- | --- | ---: | --- |
| 1 | `run_1a0a48cdc46d9571d5a` | 中断（1200秒） | fail | 0 | 要約不足、アーティファクト要件不足、混在語 |
| 2 | `run_1a0a49f3591bf987650` | 中断（1200秒） | fail | 0 | 英語の残務コピーと必須語不足 |
| 3 | `run_1a0a4b1881e9033618a` | partial | fail | 0 | 禁止語・引用契約違反 |
| 4 | `run_1a0a4bfb0e4b06d04e1` | 中断（1200秒） | fail（アンカー不足） | 0 | 「リバイス」など、失効の誤訳を含む保存成果物 |
| 5 | `run_1a0a4d207c462790272` | partial | fail | 0 | readiness.json 不成立 |
| 6 | `run_1a0a4d91a4301b8c396` | 中断（1200秒） | fail | 0 | Business quality 行欠落・英語化 |
| 7 | `run_1a0a4eb6d06cf1300eb` | 中断（1200秒） | fail | 0 | シグナルキールドリル、カーソル、アドバイザリ用語の不一致 |
| 8 | `run_1a0a4fdbd3be5c443d5` | failed | fail | 0 | readiness.json 不成立 |
| 9 | `run_1a0a4ff340580324d12` | 中断（1200秒） | fail | 0 | 了承約などの誤変換 |
| 10 | `run_1a0a51188dbfa62178b` | failed | fail | 0 | readiness.json 不成立 |

`observed-rep04-readiness.json` は第4回で保存された実成果物をそのまま固定したもの。次の固定系列では、実測した「リバイス」等を契約境界で拒否し、生成物を直接書き換えて成功扱いにはしない。

この系列はL3、本番導入、顧客環境の受入を示さない。`access.json`、秘密鍵、Cookie、SQLite状態、モデル資格情報はリポジトリに含めていない。
