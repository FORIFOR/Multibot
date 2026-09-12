# 受け渡しメモ（Builder → Reviewer）

## 成果物
- `index.html` revision=1 / sha256=7d5fc3555b51e1d7ece4c00039f32bddeee50205c00ab89f4c63b9582e2316f9
- `posts.md` revision=1 / sha256=e10dd39b072d1fd10f3552a1da2a5d87f928871586e91641c3903624098d10a6

## Builder 側で実行した検証（run_check、workspace path 指定、上記 sha256 と同一内容）

| 対象 | kind | 引数 | 結果 |
| --- | --- | --- | --- |
| index.html | html_basic | — | pass（title あり / viewport true / links 9・empty_links 0 / scripts 0 / inline_handlers 0 / headings 17 / problems なし） |
| index.html | text_contains | Master, Researcher, Builder, Reviewer, ローカルファースト, オープンソース, 価格未定, 実行記録 | pass（missing なし） |
| index.html | text_not_contains | 月額, 円/月, 無料トライアル, 導入企業, http://, https:// | pass（found なし） |
| posts.md | markdown_basic | sections = 案1, 案2, 案3 | pass（headings: 案1 / 案2 / 案3 を検出、urls 0、problems なし） |
| posts.md | text_not_contains | 投稿済み, 公開済み, 配信しました, https:// | pass（found なし） |

## 文字数（sandbox_run / python3 で実測）
コードフェンス内の本文のみを抽出して len() で計測（改行なし1行本文）。

- 案1: 135 字
- 案2: 115 字
- 案3: 126 字

いずれも 140 字以内。ハッシュタグ・絵文字を含めた本文全体での計測値。

## 構成上の判断（前提に基づく）
- `<img>` は使用せず、実行記録のイメージ図は HTML + CSS のみで表現し、`role="img"` + `aria-label` で内容を説明。よって alt 未設定画像は存在しない（img 要素が 0）。
- 外部リンク・外部CDN・外部画像・追跡スクリプトなし。JavaScript は 0 個（scripts 0）。
- リンクは全てページ内アンカー（#roles, #flow, #record, #oss, #faq, #cta）。リンクテキストは全て非空。
- 見出しは h1 が 1 つ（ヒーロー見出し）、以下 h2 / h3。
- 配布URL・リポジトリURL の差し込み箇所は HTML コメントで TODO 明示（FAQ の OSS 項目、CTA 下部の注記）。
- 価格は「価格未定」のみで表現。金額・プラン名・トライアル・実績値・比較数値は記載していない。
- 実行記録のイメージ図には「説明用の例示で特定の実行結果ではない」旨の注記を付け、架空の実績と誤読されないようにした。

## 未検証・未確認事項
- ブラウザでの実描画・実機レスポンシブ表示（各ブレークポイントでの崩れ）は未確認。CSS は静的記述のみで、GUI 目視確認は実施していない。
- 日本語フォントスタックの実端末での適用結果は未確認。
- X（Twitter）側の実際の文字数カウント仕様（URL の t.co 換算、絵文字のサロゲートペア扱いなど）は未検証。上記は Python の len()（コードポイント数）による計測値。
- SNS 投稿・LP 公開・アップロードは一切行っていない。草案のみ。
- 製品の実挙動（ローカルファーストの動作範囲、ライセンス種別、対応OS）は提供テキストに記載がないため LP に書いておらず、検証もしていない。
