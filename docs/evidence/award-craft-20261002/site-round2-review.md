# 公開サイト round 2 独立レビュー

実Chrome 154.0.8037.58/headless、JA/EN、1440×1000・390×844。主タスクは「製品が何をしてくれ、AI出力をどう確かめられ、現時点でどう利用開始できるか理解する」。実装担当とは別AIの画像・操作レビュー。人間の受入/賞の認定ではない。

主タスク PASS、重大な新規欠陥は見つからなかった。資料→作成/確認→自分で版を選ぶ、保存原文と未確認/未完了、セルフホスト試用と公開サービス準備中の説明がつながっている。提供済みsignupや成果品質の保証を創作した表現は、この範囲では見当たらない。

| id | method | expected | observed | status | evidence |
|---|---|---|---|---|---|
| small-image | JA/EN実ページを390幅に変更し画像を目視 | 読める小画面素材 | pictureが390×844の実mobile素材へ切替、348px表示で依頼/送信先/見積り上限/CTAが読める | PASS | ja-app-390.png, en-app-390.png, observation.json |
| full-size | 原寸リンクを実クリック | 対応画像を別タブで表示 | JA desktop1440×900、JA/EN mobile390×844の画像タブへ到達 | PASS | desktop-detail.json, observation.json |
| mobile-nav | 初期画面目視 | 主要節へ移動できる | 実際の修正/使い方/導入/言語/GitHubを表示 | PASS | ja-hero-390.png, en-hero-390.png |
| finding-id | desktopでF-2を実選択して目視 | IDを1行で読む | F-1/2/3の不自然な折返しを解消 | PASS | ja-proof-f2-1440.png |
| english-context | ENでF-2を実選択 | 原文と説明を区別し変更意図を理解 | 日本語原文を保持し、その上に短い英語の変更説明 | PASS | en-proof-f2-390.png |
| nojs-contact | JavaScript無効の実Chromeでフォーム表示 | 送れない状態を明示 | JavaScript必須の説明とdisabled送信ボタン、入力送信はしていない | PASS | ja-contact-nojs-390.png, observation.json |

前回指摘の主要部分（縮小画像、nav欠落、F-ID改行、英文の意味説明）は解消。重要な提供状況・記録条件の注記も以前より読める。font-sizeの機械auditは別担当の結果と区別する。

## 残差

- P2: 英語mobileの画像captionで末文と原寸リンクが「fields.Open full-size screenshot」と間隔なく連結していた（en-app-390.png）。別行または間隔で整えることを実装担当へ報告した。画像を読む/開く操作は成立する。
- 次のアプリpolish候補: native file inputの「選択されていません」と保存済み添付チップが並ぶ。添付自体の成立とは別に、追加選択と現在の添付が区別できるラベルがあると迷いを減らせる。今回の公開ページの主タスクを止める欠陥とは扱わない。

公開予定の実アプリ4PNGは全て目視し、機密鍵/個人メール/顧客情報が見えないことを確認。内容は未送信の実integration.md由来依頼・技術アカウント・loopback送信先・見積り上限。app-final-independent-review.json（同証拠親dir）に7画像のSHAと限定した判定を保存済み。

制約: 画像内の依頼は未送信、生成品質は検証していない。フォーム入力・問い合わせ送信・LLM・モック/架空データなし。実Chromeの各所有context/browserはfinallyで閉鎖。外部人間評価・Awwwards/Webby/FWAの審査・スクリーンリーダー・全サイトWCAG適合・実利用者性能はこのレビューの対象外。200%画像の目視は別記録で、こちらが再操作したズーム測定とはしない。
