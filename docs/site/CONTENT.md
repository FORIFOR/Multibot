# CONTENT.md — Agent Team site copy

## Hero (日本語 / English)
- H1: 資料やコードの作成を、レビューまで任せる。 / Let the drafting run through review.
- 説明: 複数のAIが、作成とレビューを分担して進めます。実ファイルを添付でき、実行中の指示を次のタスクへ引き継ぎます。できたファイルと一緒に、修正した箇所や、確認できなかった点を残します。 / Multiple AI agents split drafting and review. Attach real files and pass directions into the next task while the work is running. The files they make, the changes they apply and the things they could not verify stay together.
- 主CTA: 実例を見る / See a real example
- 副CTA: 自分の環境で使う / Use it in your environment
- 条件: オープンソース（MIT）。実行には対応するAI接続が必要です。 / Open source (MIT). A compatible AI connection is required.

## 実例
- 依頼、成果物、指摘、修正、再検証を、同じ実行記録で表示する。
- `docs/record.js` の内容は、`docs/evidence/scenarios/research2/` に保存された実行記録から転記したもの。架空の会話や成功ログは掲載しない。
- 初期表示ではF-1を選択状態にし、クリックで成果物の該当箇所へ移動する。選択時の枠の変化以外に自動再生や常時アニメーションは行わない。
- 現行の代表例は指摘3件を修正済みだが、原文の逐一照合が未完了で実行全体はpartial。未確認を成功と表示しない。
- 動画は実行画面の補助資料としてdetails内に置き、音声を除去した`real-walkthrough-ja-silent.mp4`と字幕を使用する。自動再生しない。

## 任せられる作業
- 小さなツールを作る → コード、テスト、README（`scenarios/code`）。
- ドキュメントサイトを作る → 作成したページと確認項目（`scenarios/long`）。
- 公開資料を比較する → 比較メモ、参照元、修正内容、未確認事項（`scenarios/research2`）。
- 個別の実行例を用途全体の成功率として説明しない。失敗・部分完了・未確認も理由とともに残す。

## 使い方
- 自分の環境で実行する。Ollamaなどのローカル接続、Claude Code、OpenAI互換接続に対応する。
- MITライセンスとAI接続の契約・利用料を分けて説明する。
- ローカル接続では入力は自分の環境に留まり、クラウドモデルを選ぶ場合は選択したプロバイダへ送信されることを明記する。
- 依頼にはtxt・md・csvの実ファイルを添付できる。実行中の人間の指示は`instruction.received`イベントとして保存し、次のタスクセッションへ引き継ぐ。既存の計画を自動で書き換えるとは表示しない。
- `uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart` を表示し、コピーは導入完了と扱わない。

## 業務利用の相談
- 見出し: 自社の仕事で使えるか、相談する。 / Discuss whether it fits your work.
- 任せたい作業と確認が必要な条件を入力する非公開フォームを一か所に置く。
- 問い合わせ本文をAI入力やアクセス解析へ送らない。送信成功時だけ`contact_submit`を計測する。
- 顧客データの有償PoC、本番SLA、SSO、組織分離は提供済みと表示しない。

## 表記
- 製品名Agent Team、リポジトリFORIFOR/Multibot、MITをヘッダーとフッターに併記する。
- Reachmade Labの製品であることと、製品サイト（`multibot.reachmade.com`）・親サイトの製品一覧（`reachmade.com/products/#agent-team`）へのリンクをフッターに置く。製品サイトの配信元やアプリ本体の移管を意味しない。
- 成果物、イベント記録、評価方法、制約へのリンクを用意する。スター数・成長率・ベンチマークの約束はしない。
