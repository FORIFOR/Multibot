# ローカルLLMでの team / single 再比較 — 2026-09-18

Claudeの週次上限で79ペアが未完了のままだった比較（[readiness-2026-09-14](../readiness-2026-09-14/README.md)）を、クラウドの利用枠を使わずにローカルで取り直した記録です。**小さな試験で、一般的な品質優位は示しません。**

## 条件
- モデル: `agentteam-qwen35-9b-16k`（Ollama、ループバックのみ、`ollama_thinking: false`）。team / single とも同一モデル。
- コード: commit `71d97d3`（隔離チェックアウト）。設定と指紋は [campaign-fingerprint.json](campaign-fingerprint.json)、[team-agents.yaml](team-agents.yaml)、[single-agents.yaml](single-agents.yaml)。
- 課題: 既存50課題のうち、入力が実在の公開ページである research 5件と、隠しテストで採点する code 5件。合成の業務メモやCSVを入力にする40課題は使っていません。
- 反復: 各1回。先攻は課題ごとに交互。1並列。
- 壁時計上限: 両方式とも1800秒（既存の `local_benchmark_campaign.py` は600秒固定。旧系列ではteamだけが600秒で打ち切られていたため、同条件で延長）。実行手順は [driver.py](driver.py)。
- 採点: 既存の自動採点（正規表現・ファイル存在・隠しテスト）。人間による独立評価ではありません。research系の正規表現は語の有無を見るもので、内容の正確さは保証しません。

## 結果（[team](team-results.jsonl) / [single](single-results.jsonl)）

| | team | single |
| --- | ---: | ---: |
| completed | 5 | 9 |
| partial / interrupted / failed | 4 / 1 / 0 | 0 / 0 / 1 |
| 自動採点で正解 | 5/10 | 6/10 |
| うち research | 0/5 | 3/5 |
| うち code | 5/5 | 3/5 |
| completedだが不正解 | 2 | 3 |
| 合計所要時間 | 164分 | 37分 |

- code: singleは `code-wc-plus` でファイルを出せずfailed、`code-slugify` は隠しテスト不合格のままcompleted。teamは5件とも正解の成果物を出しましたが、うち2件はReviewerがツールを呼ばずにターンを終え続け、独立レビュー未提出のためpartialになりました（成果物は正解）。
- research: teamは1件が1800秒で時間切れ、2件は最終成果物のファイルが出ずpartial、2件はReviewerがpassを出したが採点不合格でした（`research-changelog` は必須の `Fixed` と `Security` が抜けたまま通過）。`research-uv` にはDNS解決失敗の記録があり、同じURLをsingleは取得できています。原因は切り分けていません。
- teamはsingleの約4.4倍の時間を使いました。

## 2026-09-19 の追試（[結果](followup-2026-09-19-team-results.jsonl)）
作業ツリー（main `e052c46` + 未コミットの変更）で、partialだった `code-wc-plus` と `code-slugify` をteamで1回ずつ再実行し、両方とも completed・正解・レビュー提出（2/2、3/3）になりました。この変更には、ツールを呼ばずに終わったターンへの促しを役割ごとに具体化する修正が含まれますが、**この2回ではReviewerが最初からツールを呼んでおり、促し自体は一度も発火していません。** したがって、この改善を修正の効果とは判定しません。同じ課題でも実行ごとに挙動が変わることの記録です。

## 限界
反復1回・10課題で、差は偶然の範囲に入り得ます。9Bのローカルモデルの結果で、より大きなモデルへ外挿できません。イベント全量のSQLiteは容量のためリポジトリに含めていません。
