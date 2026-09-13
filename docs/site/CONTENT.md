# CONTENT.md — Agent Team サイト コピー

## ヒーロー（日本語 / English）
- H1: 依頼は一度。成果物も、検証の経緯も。 / One request. The deliverable — and how it was checked.
- 補足: AIチームが作成・レビュー・修正を進め、誰が何を確かめたかまで、成果物と一緒に残します。 / An AI team drafts, reviews and revises the work, and keeps who checked what next to the deliverable.
- 主 CTA: 実際の作業記録を見る / See a real work record
- 副 CTA: GitHub で見る / View on GitHub

## 作業記録（実データ、2026-09-13、claude-opus-5）
- 依頼 21:13Z: 3 つの公開ページを取得し「主張・対象読者・ライセンス」を出典 URL 付きで比較する調査メモ。推測で埋めない。
- 初稿 21:16Z: researcher が `research.md` r1 を公開（sha256 e3420149…）。
- レビューの指摘 21:19Z: reviewer が検査 5 件（pass 3 / unverified 2）と指摘 F-1〜F-3 を提出し、researcher へ finding メッセージを送信。
- 修正箇所 21:29Z: researcher が `research-final-r2.md` r1 を公開（sha256 fbc33429…）。F-1〜F-3 を反映。
- 再検証 21:36Z: reviewer が F-1〜F-3 反映 pass / 出典付き pass / 推測混入なし pass / 原文照合 unverified。予算上限で終了し、実行は partial。

## 指摘（review.md r1 §3 から）
- F-1 根拠引用の欠落: 比較表 deer-flow「（backend / frontend 構成）」に原文引用がない。→ r2: 記述を削除し「未確認」と明記。
- F-2 関係性の未明示: `agentskills/agentskills` を「仕様ページ上部にリンクされている公式リポジトリ」とする根拠引用がない。→ r2: 再取得したヘッダのリンクラベルを引用し、リンク先 URL の同一性は未確認と限定。
- F-3 言い換え: deepagents の提供形態「CLI」は原文にない語。→ r2: 原文 "a pre-built coding agent in your terminal" に沿って修正し引用を併記。

## 実績（5 依頼、各 1 回、未編集）
- 完了 3（LP + 投稿案、Python CLI + unittest、4 ファイルの docs サイト）、部分完了 1（調査メモ、上記）、失敗 1（同じ調査メモの初回。スケジューラのデッドロックを露出し修正済み）。

## 導線
- OSS: `uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart`
- 事業相談: 「自社の作業フローを AI チーム化する相談」→ X の DM（非公開）。公開 Issues は不具合・提案のみ。

## 表記
- 製品名 Agent Team、リポジトリ FORIFOR/Multibot、ライセンス MIT を毎ページに表記。数字は実行記録の値のみ。約束する数字はなし。
