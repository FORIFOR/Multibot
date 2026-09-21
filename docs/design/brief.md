# Agent Team アプリ — デザインブリーフ

対象はアプリ（`frontend/src`）。公開サイトのブリーフは `docs/site/PRODUCT.md`。
2026-09-22 時点の内容。「承認」の欄に人の承認と書いていないものは、提案か、実装された現状の記録。

| 項目 | 内容 |
|---|---|
| 製品 / 画面 | Agent Team。お願いする画面（`/`）、作業の画面（`/runs/:id`、1枚）、はじめての案内（`/welcome`）、マイチーム（`/settings`） |
| 対象種別 | web-app（ローカルで動くWebアプリ。インストール後は `backend/agentteam/ui` の同梱版が表示される） |
| 対象ユーザー | 主: AIに仕事を任せたいが、確かめられない成果には署名しない開発者・技術リーダー。副: 調べる→作る→確かめる→直すを任せたい事業側の人。初心者を含む |
| 利用者が完了したい1つの仕事 | やってほしいことを一度書き、できたファイルと「何を確かめたか」を受け取って、使う版を選ぶ |
| 初見で分かってほしいこと | 話しかける相手はまとめ役の1人。作る係と確かめる係が分かれている。受け取るのは返事ではなくファイル |
| 最重要の操作と結果 | 入力欄に書く →「チームにお願いする」→ 作業の画面でチームの様子とできたものを同じページで見る →「この版を使う」 |
| 今回変えないもの | ユーザーが名前と絵文字を選べる担当表示。状態は実データからだけ決める。未完了・未確認をそのまま見せる。成果物の作成と内容確認は区別する |
| 想定する画面幅・言語・入力方法 | 390 / 768 / 1100 / 1440px。日本語が主、英語が副。マウス、キーボード、タッチ |
| 利用できる部品・トークン | `docs/design/tokens.md`。部品: `BotAvatar`、`Journey`、`Markdown`、`BotSettingsCard`、`CustomBotCreator` |
| 説明なしでも理解できる入口 | お願いする画面の入力欄と、編集できる依頼例。初回だけ「はじめての方へ」の案内 |
| この製品らしい表現1つ | 役割の違う担当を絵文字ボタンで示す。押すと担当内容と実際の状態が開く。初稿前は会話、成果物ができた後は成果物と会話が主役 |
| 今回採用しない表現と理由 | 台本の会話・架空の成功表示（事実でない）。推薦文・利用者数（実在しない）。他社マスコットの意匠（借り物になる）。内部用語（`run`、`revision`、`sha256`、生のJSON）を日常の画面に出すこと |
| 承認済み / 提案段階 | 利用者の指示: 選べる絵文字、短い説明、実際のチーム会話、成果物の編集、obsidianui.dev を参考にした見た目（2026-09-22、案Bは実装者の選択で、できあがりへの人の承認は未取得）。制作デスクの構成は利用者から「良い感じ」と評価済み。人間による初見操作の成功率は未測定 |

## 参照するもの
- ホームページの参照: voiceos.com（サイト同士で比較）。
- アプリの参照: wonder.next-standards.com の初回案内2画面（ワークスペース本体はサインインが必要で未確認）。
- 広告用のヒーローと操作画面を直接比べない。記録は `references/README.md`。

## 現在の見た目（2026-09-22 — Obsidian surface）

利用者の指示「obsidianui.dev を参考に」「アプリ全体・ライトのみ」「ボットは愛着が湧くように、ただし可愛すぎず、シンプルに」による。値の正本は `frontend/src/obsidian.css`（`tokens.md`）。

外枠は薄い灰色、その上に角丸の白い面が1枚。ナビは白いタブ。主要操作は1画面に1つの黒いボタンで、未確認のまま進む操作だけは琥珀色の枠で弱める。状態の色（良・注意・問題・進行）は意味として残し、飾りの色は使わない。担当は白いタイルに絵文字、下辺に役割色の細い線、名前は太字。常時の動きはなく、指したときに少し傾くだけ。

お願いする画面は中央1列: 見出し → まとめ役（名前と一言。依頼を書くと一言が変わる）→ 入力欄（資料・条件のチップ、おまかせ／自分で選ぶ、主ボタンを下端にまとめる）→ 依頼例 → 送信先の開示 → 履歴。作業の画面は制作デスクの構成のまま（大画面は成果物を左、会話を右。初稿前は会話を広く。スマートフォンは切り替え、下書きを保持）で、チームの行に「今回のチーム構成」「資料と前提」を並べて読み物の開始位置を上げた。

成果物のテキストコピーをブラウザー内で編集・保存できる。編集コピーはチームが公開した版とは別であり、確認済みの記録を引き継がない。選択箇所と版を添えて修正指示を準備できる。指示の受付は修正完了ではない。現在、指示は次に始まる担当作業へ渡される。完了した作業を自動で再実行する機能や、コピーをサーバーの新しい版として保存する機能は未実装。

### Simple bot characters — 2026-09-20
Use a small animal emoji and short nickname as the identity; keep expertise and permissions separate. My team offers editable Mame/まめ (🐣, curious), Pon/ぽん (🐻, easygoing), Mugi/むぎ (🐱, practical), Lulu/るる (🐧, thoughtful). These are identity presets, not a four-person team requirement. Selection updates only the local draft; explicit save uses the existing configuration contract. Existing names and run snapshots are preserved. No invented chat or claimed human affection measurement. AI recommendations are guided toward similarly simple identities, with locked identities preserved; effects on generated voices remain unverified.
