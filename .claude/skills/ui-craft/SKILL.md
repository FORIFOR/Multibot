---
name: ui-craft
description: 指定された画面を設計・実装・実画面検証・独立レビューまで進める品質ワークフロー。
argument-hint: "<対象画面・主目的・制約>"
disable-model-invocation: true
---
# UI craft
対象: $ARGUMENTS

## 0. Read and bound
CLAUDE.md、docs/design/{brief,acceptance,tokens}.md、既存の画面・部品を読む。公開サイトが対象なら docs/site/{PRODUCT,DESIGN,ACCEPTANCE}.md を読む。
未記入項目はリポジトリとユーザーの要望から埋め、推定だと明示する。
設計済みブランドを勝手に変更しない。ユーザーの未コミット変更を壊さない。
検証コマンドは CLAUDE.md の Commands を使う（frontend は pnpm）。
参照URLのHTMLしか読めない場合は視覚確認とは扱わない。

## 1. Establish the design target
新規の主要画面、または明示されたリデザインでは、1画面だけを使い構成の異なる2〜3案を試作する。
色替えを別案と数えない。小修正や承認済み案の展開では案出しを省略する。
既存のfrontend-designを明示的に使う。未導入なら不足を報告する。勝手にプラグインを増やさない。
Impeccableを使う場合は機能を選択し、複数の美的方針を無差別に重ねない。
比較して1案を選び、選定理由と捨てた案の理由を短く残す。自動選択の場合は承認済みと書かない。

## 2. Activate optional evidence gate
ui-quality.config.jsonがconfigured:trueで導入済みの場合に限り、作業開始前に実行:
`node scripts/ui-quality.mjs begin "${CLAUDE_SESSION_ID}"`
設定は既存のテストへ接続する。不足テストをecho等の常時成功コマンドで代用しない。
このローカルゲートは外観の良さを自動証明しない。

## 3. Implement a vertical slice
最重要の入口→操作→結果まで、1つの短い体験を実装する。
全体を作り込む前にこの体験を品質見本にする。実際の日本語とデータ長を使用する。
状態・入力値の上限・エラーからの復帰・必要なアクセシビリティを同時に実装する。
モックは明示的なfixture/demo環境だけに閉じ込める。

## 4. Drive the application
実際にアプリを起動し、Playwright CLI / MCP / Chrome連携など利用可能なブラウザ手段で主操作を行う。
起動方法が特殊ならプロジェクト用run skill等に記録する。起動不能ならBLOCKEDを記録する。
対象がネイティブなら別途その実アプリを確認する。Web表示だけで全体PASSとしない。
台本のテストサーバを起動し `node frontend/scripts/ui-capture.mjs` で artifacts/ui/ に規定サイズの画像を保存し、画像として開いて見る。実データでの見え方は実行記録のコピーを別ポートで開いて確認する（動作中のストアを直接開かない）。
スクロール、hover、focus、通常motion、reduced-motion、エラー復帰を対象範囲に応じて確認する。

## 5. Independent review and bounded repair
ui-reviewerへ、brief、acceptance、参照画像、実装後画像、再現手順だけを先に渡す。
実装者の「優れている」等の評価や点数は渡さない。
同一モデルの別コンテキストにも相関した見落としは残る。利用者テストの代替とはしない。
P0/P1から直し、再撮影して再レビュー。最大3回で止め、残る問題を報告する。
局所的な見栄えより、操作を妨げる問題の修正を優先する。

## 6. Record and verify
画像とレビューに出典を付けてartifacts/ui/へ保存する。
ゲート有効時: `node scripts/ui-quality.mjs inspect` で最新ソース指紋と画像ハッシュを得る。
レビュー結果をdocs/design/report-template.mdの形式でartifacts/ui/review.jsonへ保存する。
ゲート有効時: `node scripts/ui-quality.mjs check "${CLAUDE_SESSION_ID}"` を実行する。
このcheckが画像を再生成して内容が変わった場合、必ず新画像を見て再レビューする。
テスト失敗・未レビューを合格に書き換えて通してはならない。

## 7. Hand back
変更概要、実画面への入口、最新スクリーンショット、実行テストと結果、未達・未確認を報告する。
「VoiceOSを超えた」は、比較対象・同条件の観察・利用者評価の証拠がない限り主張しない。
未達時は完了でなく部分実装と明記する。承認なしにpush/deployしない。
