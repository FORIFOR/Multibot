# Site round 3 — 独立 UI 再確認

2026-10-01 UTC、実 HTTP `127.0.0.1:8897` と実 Chrome 154.0.8037.58。実装を変更せず、英語 390×844・320×844、日本語 390×844 で画像、DOM の位置、Tab/Enter 操作を確認した。LLM 実行、フォーム送信、架空入力はなし。所有 Chrome は終了済み。

## 前回所見の補足

round 2 の独立目視・表示要素の存在確認では、英語 390px の GitHub 右端超過を見落とした。別担当の機械検証で右端 416px > viewport 390px が検出された。前回の「重大な残差なし」はその範囲を測定した合格を意味しない。前回証拠は変更せず、本記録で不足を補う。

## 再確認結果

- 英語 390px・320px、日本語 390px の document.scrollWidth はそれぞれ 390/320/390px。すべてのヘッダーリンクで左右端が viewport 内に収まり、文字欠けなし。GitHub は狭い幅で折り返され、320px でも隠れない。対象の overflow P2 は解消した。
- 実 Tab で本文スキップ→ブランド→各ナビ→言語→GitHub の順に到達。各対象に 3px のフォーカス枠があり、GitHub 枠を実画像でも確認した。
- 英語 390px の画像説明と原寸リンクは別行。実 Tab でリンクに到達し、Enter で別タブが開いた。実モバイル画像は naturalWidth 390px で読み込まれた。
- 最初の caption 撮影は移動開始から 500ms で、smooth scroll の途中にリンクが下端へ切れていた。元画像を保持した上で別の実操作を記録。500ms 後は top877.5/bottom921.5、追加 1.5 秒後は top411.5/bottom455.5（viewport 高さ844px）となり、説明・リンク・枠が完全に見えた。途中撮影を恒常的な欠けとして判定していない。

参照画像: `en-390-github-focus.png`、`en-320-github-focus.png`、`ja-390-github-focus.png`、`en-390-caption-focus-settled.png`。測定値は `observation.json` と `caption-focus-settled.json`、判定集計は `verification.json`。

## 制約と残る所見

英語 390px では GitHub が単独行になるが、操作や読解の障害は今回の範囲では見つからなかった。スクロール中のフォーカス可視化には待ち時間がある。全ブラウザー、支援技術、全ページの適合判定ではない。AI による独立レビューであり、人間の受入、業務出力品質、Awwwards/Webby/FWA の評価や受賞相当を証明しない。前回の 4 枚の実アプリ画像、原寸リンク、no-JS、内容理解の確認は round 2 証拠を参照し、今回実行した範囲と混同しない。

## axe incomplete の装飾矢印 2 個の追加確認

別担当の round 3 axe が incomplete とした `.btn[href$="#proof"] > span[aria-hidden=true]` と `.hero-footer > span[aria-hidden=true]` を、実 Chrome の computed style と実画像で確認した。条件は JA/EN 通常 1440×1000、および EN 720×1000 で各 HTML 要素の取得済み font-size を 2 倍にする追加ストレス（機械検証と同じ方式。ブラウザーのネイティブズームではない）。

| 対象 | 文字色 | 実背景 | コントラスト比 | 主ラベル |
| --- | --- | --- | --- | --- |
| CTA の ↓ | `rgb(255,255,255)` | 親 `a.btn` の `rgb(189,65,28)` | 5.334484696897243:1 | 「実際の修正を見る」/「Explore a real revision」も同色・同背景・同比 |
| hero-footer の ↓ | `rgb(101,94,84)` | `body` の `rgb(251,249,245)` | 6.084080917348682:1 | 「OPEN SOURCE · MIT」「FILES + REVIEWS + HISTORY」も同色・同背景・同比 |

矢印自身の背景はいずれも transparent。CTA は親ボタンまで、footer は span→div.hero-footer→section.hero.wrap→main→body まで透明背景をたどった。全対象と祖先の opacity は 1、背景画像/フィルターなし、mix-blend-mode は normal。透明背景を白として即断せず、実背景を使った。通常と文字 2 倍でこの色と比率は不変。

計算は sRGB の各チャネルを 255 で割り、0.04045 以下は /12.92、それ以外は ((c+0.055)/1.055)^2.4 で線形化。相対輝度 0.2126R+0.7152G+0.0722B から (明るい側+0.05)/(暗い側+0.05) を算出した。主ラベルは丸め前でも通常文字 4.5:1 を上回る。[W3C の SC 1.4.3 解説](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) を参照。

実画像 6 枚を目視し、CTA の主ラベルと矢印は識別可能。footer の矢印は通常 10px で小さく、主ラベルも補助表示として小さいが、欠けや背景への埋没は確認しなかった。EN 720px の文字 2 倍では footer は 18px（基準 9px×2）、CTA は 28px となり、両方識別可能だった。`aria-hidden=true` は装飾矢印の属性であり、それだけで主ラベルの可読性や適合を免除した判断ではない。主ラベルを別に採取・計算した。

この追加確認ではコード修正を要する実問題なし。axe の自動判定 0 件や incomplete の限定レビューを、全サイトの WCAG 適合、全条件での視認性、人間の受入と解釈しない。証拠は `contrast-arrows.json` と `contrast-{ja-normal,en-normal,en-text2}-{proof-arrow,footer-arrow}.png`。ブラウザーのみ終了済み、サイトソースは変更していない。
