# 制作スタジオ独立検証

2026-09-20、independent-product-verificationを適用。macOS / Chrome153、独立一時プロファイル、reduced motion。対象8798実記録コピーrun_1a09c8485503d406bf4。基準HEAD 18763d8a7c02ce3ec28bcd6725334efaf81bd7e6と未コミット配信UI。実装を読まず画面探索後、Workroom/ArtifactWorkbenchを静的確認した。別AIセッションの検証であり人間初見評価ではない。

## 指摘

- P2（実画面）: 1440pxで担当一覧が左の約480pxだけに配置され右が空白。成果物と会話の作業面がページy約965pxから始まり、1000px高の初期画面では内容がほぼ見えない。「上部の小さい担当一覧」という設計に対し主役を押し下げている。`1440-initial.png` を開いて確認。横一列等へコンパクト化する修正を依頼済み。
- P2（静的）: hash不一致時の「成果物一覧へ」はselectionだけを解除してartifactTargetを残す。既定の成果物が同一id/revisionなら不一致判定が続き戻れない。親targetも解除する必要がある。実会話refs=[]なので実ブラウザ再現はBLOCKED。欠陥候補と実測済みを区別する。

## 実測

証拠: `artifacts/product-quality/creation-studio-independent/`。

| ID | 方法・期待 | 観測 | 判定 | 証拠 |
|---|---|---|---|---|
| S1 | 成果物を閲覧、原文APIと照合 | readiness.json版3の編集初期値とraw本文が完全一致 | PASS | verification.json |
| S2 | 実際の誤字「鍵轮换手続き」を「鍵ローテーション手続き」へ編集、reload復元、ダウンロード | 復元値・保存バイトが編集値と完全一致。サーバー版変更を示さず手元下書きと明記 | PASS | verification.json、readiness.json |
| S3 | 選択箇所から修正準備、既存指示を保持 | path/版3/SHA256/編集コピーの選択箇所を挿入。2回目準備でも既存の修正要求を保持。送信なし | PASS | verification.json |
| S4 | 実版2→3差分 | UI本文がGET diff APIのdiffと完全一致 | PASS | verification.json |
| S5 | 390px会話→成果物→会話切替 | コピー編集値・指示値保持。textarea.scrollTop 130→130。横溢れ0 | PASS | verification.json、390-workbench.png |
| S6 | 原文に戻す | 編集欄がraw本文と一致 | PASS | verification.json |
| S7 | 実200%・キーボード | Chrome appearance Page zoom=200%。innerWidth720/DPR2/CSSzoom1。横溢れ0。Enter成果物切替後focus=room-results、Enter編集開始成功 | PASS | zoom.json、native-200-cdp.png |
| S8 | 副作用・例外監視 | GET以外0、pageerror0。非GET阻止ガード発動なし | PASS | verification.json |
| S9 | 参照から正確なrevision/hashへ移動 | 実会話にrefsなし。照合分岐は静的確認のみ | BLOCKED（実測） | 対象データ制約 |
| S10 | localStorage保存不可時の表示 | catchで保存不可を出す静的実装を確認、実容量不足等は発生させていない | BLOCKED（実測） | ArtifactWorkbench.tsx |

画像は実際に開いて目視した。native-200.pngはPlaywright標準スクリーンショットが背景だけを取得したため表示評価に使わず、同時のCDP fromSurface=falseによるnative-200-cdp.pngを使用した。

本検証はローカル編集・ファイル保存のみ。API書込み、再開、モデル呼出、修正指示の保存送信はしない独立検証の範囲。送信受付・修正完了・採用変更・不明参照からの復帰・実IME/読み上げ・人間評価は未実施。build/typecheck/lintは主担当の実行結果と独立実行を混同しない。実データの既存生成品質FAILはこのUI検証で解消扱いにしない。

## build-2 再確認

担当一覧が全幅の横並びに修正されたことを実画面 `1440-fixed-loaded.png` で確認。成果物/会話の開始はy849.6px、幅855/503px。初期の片側だけの空白は解消（P2クローズ）。ヘッダー・状態説明を含めて作業面までの距離はまだ長いが、追加の好みと機能障害を混同しない。

hash不一致から戻る操作にclearTargetが追加され、親targetとselectionの両方を解除する静的修正を確認（静的指摘クローズ、実参照操作はデータ不足のためBLOCKED維持）。diffのpre tabIndex=0も配信実DOMで確認。4000字超過時の送信制止と読み込み再試行は静的確認のみ。最終GET以外0/pageerror0は `final-monitor.json`。1440-fixed.pngは読込途中の画像で、完成画面判定には使用しない。

## build-final 配置再確認

最新配信の `index-DiIA65oV.js` / `index-Cj9daTtF.css` を新しい独立ブラウザーで読み込み、1440/390pxの画像を開いて目視した。`1440-build-final.png`、`390-build-final.png`、`build-final-visual.json` が最終対象証拠。確認事項・資料が作業面の後へ移動し、1440pxの作業面開始はy695.6px（build-2の849.6pxから154px上へ）、390pxはy587.0px。成果物ヘッダー・操作の圧縮後も文字とボタンは読め、重なり・横溢れはない。横溢れは両幅0。モバイルで会話→成果物をEnterで切り替え、表示とfocus=room-resultsを確認（build-final-switch.json）。GET以外0/pageerror0。

今回の差分は配置のため、編集ファイル保存等の全機能を再実行したとは主張しない。初稿前の会話優先配置は、この実記録に成果物が存在するため独立実測していない。既存のBLOCKED項目は維持。追加の主要問題なし。
