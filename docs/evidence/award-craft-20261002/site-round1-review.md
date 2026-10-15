# 公開サイト round 1 独立レビュー

実Chrome 154.0.8037.58/headless、JA/EN、1440×1000・390×844。baselineと同じ初見タスクで閲覧。ページ原文・HTML hash は observation.json、操作は interactions.json、色と安定後の観測は contrast-and-settle.json に保存。実装担当とは別AIの評価で、人間受入・賞の認定ではない。過去の製品文脈は持っている。

主タスクは PASS。冒頭から「資料→作成/確認→使う版を自分で選ぶ」、実記録の指摘/変更前後/原文リンク、現在はセルフホスト試用・公開登録サービスは準備中、と理解できる。以前のPC内だけという断定、初期動画スピナー、白紙のreveal依存は解消した。

## 実確認

| id | method | expected | observed | status | evidence |
|---|---|---|---|---|---|
| purpose | 初期実画面目視 | 役割と成果物が分かる | 説明/2CTA/提供状態が両幅の初画面内 | PASS | ja-1440.png, ja-390.png, en-1440.png |
| real-record | 実ボタンF-2/F-3をクリック | 対応する原文に切替 | 保存原文・aria-pressedが切替 | PASS | interactions.json, ja-proof-f2-settled-1440.png |
| no-js | JavaScript無効の実Chrome | 全原文が読める | F-1/F-2/F-3と前後原文を表示、390pxの横overflowなし | PASS | interactions.json, ja-proof-nojs-390.png |
| start | 実ナビの導入をクリック | 開始条件に到達 | 1800ms時点で節上端44px、uv/AI接続/費用条件を表示 | PASS | contrast-and-settle.json, ja-start-settled-1440.png |
| contrast | 実computed色と背景の計算 | 対象小文字4.5:1以上 | proof内の最小4.64:1、安定後opacity1 | PASS | contrast-and-settle.json |
| mobile-figure | 実アプリ画像を読もうとする | 主な入力UIが読める | 1280px実画像を約348pxへ縮小、本文が読めない | FAIL | ja-app-390.png |

contrastはproof内のsolid色の組合せのみで全面WCAG判定ではない。切替直後の薄いsnapshotは不具合の根拠から除外し、安定後画像も保存した。app画像の初回naturalWidth0は遅延読み込みで、実際にスクロールすると1280幅の画像を読み込んだため、破損とは判定しない。

## 修正候補（大きな操作ブロッカーなし）

- P2: 小画面のアプリ画面が細かく読めない。新しい素材へ替えるだけでなく、実画像を拡大できるリンク/表示か、実モバイル画面を使用する。本文説明は既に読める。
- P2: desktopのF-1/F-2/F-3が「F-／1」の2行になる。IDをnowrapと必要幅で揃える（ja-proof-f2-settled-1440.png）。
- P2: mobile headerはEN/GitHubのみで、実記録・使い方・導入の移動が消える。ヒーローの2CTAは使えるが、読み進めた場所から移動しにくい。簡潔なセクション導線を残す。
- P2: 390幅で提供状態11px、実記録のモデル限定10pxと小さい。重要な制約は本文に準じた読みやすいサイズへ。
- suggestion: 英語ページの主な実記録は日本語原文だけなので、変更の意味を短い英語の説明で補う。原文と説明の区別を残す。
- suggestion: mobileではF-2/F-3の説明文が隠れ、見出しだけになる。誤りの理由を一文読めると原文比較を理解しやすい。

ヒーローは大きいが、対象2幅では主説明・CTA・提供状態を初画面から追えたため、サイズだけを欠陥とは判定しない。暖かい紙色・太い見出し・罫線・実記録の組合せは以前より製品固有の一貫性がある、という美的所見。

未検証: 実インストール、外部問い合わせ送信、生成品質、200% native zoom、スクリーンリーダー、全ページのWCAG適合、実利用者性能、外部賞の水準・競合優位。フォーム入力/送信、LLM、架空データはなし。所有Chromeは各操作のfinallyで閉鎖。
