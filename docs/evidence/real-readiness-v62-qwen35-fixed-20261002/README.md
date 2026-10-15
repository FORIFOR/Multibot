# 実ローカルLLM限定回帰 — v62

2026-10-02 JST。全10回の記録と固定資料を独立AI担当が意味照合した。**一般業務・人間受入は0/10、本番/L3は未達。** 元のstatus/attemptsが持つsemantic_review=pendingは収集当時の原記録として保存し、最終審査は[semantic-review-20261002.json](semantic-review-20261002.json)に別記した。

## 固定条件

- コード: 9eb798849cd8352ec645f6da2ed1e04d9729d63c（PR26の固定checkout）
- Ollama: agentteam-qwen35-9b-16k、0.33.3、digest c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866
- 同時LLM1件、クラウド切替なし。各回1200秒/40モデル呼出の既存v62条件。入力・設定・依頼/schema hashはfingerprint.json。
- リポジトリ実資料からのreadiness.json。ただし17の要約欄に完成例/constを入力で与えている。v61の「入力取得→入力検査」という例文の誤りを訂正した限定回帰であり、自由な文書作成の品質を試したものではない。

## 結果

| 判定 | 結果 |
| --- | --- |
| 記録済み試行 | 10/10 |
| 実行状態 | completed 4、failed 5、interrupted 1 |
| readiness.jsonの形式/配信契約 | 10/10 |
| 固定資料8引用と入力取得表現 | 10/10一致 |
| 17要約欄 | 全10件が提供完成例/constと一致 |
| モデルレビュー提出 | 10件、対象はreadiness.json r1 |
| 追加final-report.md | 9件。9回目は未生成 |
| 独立AIの事後意味照合 | 全10件完了。人間受入ではない |
| 一般業務/人間受入 | 0/10 |

全readiness.jsonのSHA-256は f88dc43c64d26af915ee7fba4713a9dfcc6a36b593f3998accaaffa1b514569e。同じ完成例から同じbytesが得られたことを一般業務の再現性と呼ばない。モデル呼出合計223、ツール呼出192、記録上のwall_seconds合計7408.16秒。

## 残った不具合と修正の分離

2/5/6/7/9/10回目はレビュー後の引継ぎで進めなくなった。reviewerの実行元t2と合法な関連先t1の混同を[別の実装修正と実SQLite回帰](../message-handoff-provenance-20261002/README.md)で確認した。9回目は最終的に1200秒で中断。旧結果の状態は修正後に付け替えていない。

6回目の追加最終報告は、WORM保管とアラート配送の「未受入」を「未実装」と断定した。2回目には実証されない自動メッセージ上限reset待機の提案があった。6/7/10回目には、日本語要約の対象をimplemented/remainingだけと説明し、トップのsummaryを落とす不正確な記述もある。この記述はモデルレビュー説明から最終報告にも再掲された。readinessのみを対象とするモデルレビュー後に生成された報告を、レビュー済みとは扱わない。[文書経路の最終報告の修正](../document-report-boundary-20261002/README.md)は後続コードであり、この元報告を消去・書換えしていない。

次の検証は完成回答を渡さない実integration.mdからのguide.md生成とし、コード/資料/設定/モデル/実依存を別系列で固定する。代表1業務10回でも一般業務全体や公開後の可用性を証明しない。

## 証拠保全

全10件のrun.json・events.jsonl・artifact inventoryと公開された全bytes、入力資料、依頼/schema、fingerprint、status/attempts、監督終了/Colima停止記録を原bytesでコピーした。各artifactはinventoryのevidence_fileから辿れる。SHA-256はsha256.json。元の実キーとのbyte照合と資格情報パターン検査に該当なし。鍵・access設定・DB・秘密を含み得る非公開ログは含めない。

全SQLite、workspace、元設定、ログは ~/.cache/agentteam-bench/real-readiness-v62-qwen35-fixed-20261002 に保持する。監督/ワークフロー終了、所有Colima停止(exit0)を確認。旧合成比較のSTOPと全結果は保持し、再開していない。
