# 制作スタジオ — 受け入れ契約

対象: 添付の設計提案。主フローは実成果物を読む→対象の版/選択箇所を指定→修正指示を準備する→版の差分と確認記録を読む。

デザイン: 会話だけの画面、常時3列、成果物と会話の2領域を比較し、デスクトップは成果物を広く取る2領域を採用。チームは上部の小さい担当一覧、モバイルは成果物/会話を切り替える。同じコンポーネントを保持し、入力とスクロールを失わない。白い作業面と既存の絵文字を使う。

実装前条件（macOS Chrome、実記録、1440/390px、reduced motion）:
- 成果物と会話がデスクトップで並び、モバイルで切替可能。フォーカス・下書きが保持される。
- 会話の参照は指定revision/hashの成果物へ移動し、不明な参照を最新へ代替しない。
- テキスト成果物はブラウザー内のコピーを編集・復元・ダウンロード可能。サーバーの版を更新したと誤表示しない。保存不可時に成功と言わない。
- 選択箇所・パス・revision/hashを付けて修正指示を準備する。クリックだけで送信しない。既存指示を勝手に消さない。受付と修正完了を区別する。
- 既存diff APIで直前版との差分を表示し、確認は選択revision/hashの記録のみ。
- 実記録/API/ダウンロード内容と照合。build/typecheck/lint、キーボード、200%相当、狭幅、原文保持、変更送信なしを確認。

権限/契約: GET artifact/diffと既存instruction APIを使用。編集はlocalStorageのrun/id/revision/hash別下書きとファイル保存のみ。サーバーへ新revisionを発行する編集・自動再実行・共有・外部送信は追加しない。HTMLは既存sandbox preview、編集コピーをスクリプト実行しない。添付記載の他社機能は依頼の背景として扱い、新たな検証済み事実とは報告しない。

未達を隠さない: 画像/スライドの直接編集、指摘からページ内座標への自動ジャンプ、自動修正→再確認、実iPhone/日本語IME実機、人間初見比較は別途検証が必要。架空会話/成果物で代用しない。

## 実行結果

対象HEAD/未コミット差分のhashと環境は `artifacts/product-quality/creation-studio/revision.json`。Chromeバージョンは同ディレクトリ `verification.json`。参照は実記録 `run_1a09c8485503d406bf4` の隔離コピー（8798）。現在の実作業（8796）も初稿なしの配置を確認。新規モデル実行/外部送信なし。

| 項目 | 判定 | 観測/証拠 |
|---|---|---|
| 成果物/会話の2領域と初稿前の会話優先 | PASS | desktop.png/current-run.pngを開いて目視、位置/幅を実測 |
| 編集コピーの保存・reload復元・原文復元 | PASS | edited-copy.txtが編集文字列と完全一致、原本API本文/hash不変 |
| 選択箇所＋版/hashを修正指示へ | PASS | 指示入力と対象原文を照合、送信なし。独立検証で既存指示保持 |
| 版の差分表示 | PASS | 実r2→r3のAPI diffとUI全文一致 |
| 390/720幅の切替と入力保持 | PASS | verification.json、results-390.png/results-720.pngを目視、横溢れなし |
| キーボード/Chrome実200% | PASS | 独立検証報告。720px試験のみを実zoomの証拠にはしていない |
| 結果領域axe A/AA | PASS | 最初の試験で差分preのfocus欠落を検出→tabIndex修正→再試験で0件 |
| build/typecheck/lint | PASS | 下記exit0。lint警告あり（effectのstate更新等、新規部品の警告も含む） |
| 会話refsの実クリック・不正参照からの復帰 | BLOCKED | 対象実発言にrefsなし、静的実装確認のみ。親target解除を独立指摘後に修正 |
| storage保存失敗/ネットワーク切断からの復帰 | BLOCKED | エラー表示/retryコードは存在、障害実測は未実施 |
| 指示の実送信→修正版→再確認 | BLOCKED | 今回GETとローカル編集のみで確認。モデル再実行未実施 |
| 実iPhone/日本語IME実機/人間初見評価 | BLOCKED | 対象実機・評価者による試験なし |
| 画像/スライド直接編集・サーバー新revision保存・共有 | BLOCKED | 今回未実装。テキストコピーのローカル保存とは区別 |

実行コマンド（root）: `python3 artifacts/product-quality/run-command.py creation-studio-build-final pnpm --dir frontend build`、同wrapper `creation-studio-lint pnpm --dir frontend lint`。frontend cwd: `python3 ../artifacts/product-quality/run-command.py creation-studio-browser-final node scripts/creation-studio-check.mjs`。各exit0、ログは `artifacts/product-quality/`。初回browserのaxe失敗は `creation-studio-browser.log` に保存し、合格基準を変更していない。実行準備でcwdを誤ったMODULE_NOT_FOUNDも初回ログに残る。

独立検証: [creation-studio-independent.md](creation-studio-independent.md)。UIはローカル配信assetsへ反映。添付提案すべての完成・競合への優位を意味しない。

## 制作デスクへの再構成（2026-09-20）

ユーザーの「パッとしない」「修正して」に対応。上部の大きなカード/常時警告を整理し、担当を展開可能な絵文字ボタンにした。ニュートラル背景と深緑の操作色、単一の制作面に統一。指示欄を初期表示、詳細な進捗は下へ移動。再開の注意は実行前の開閉欄に移し、確認して再開ボタンを押すまで実行しない。

PASS: build/typecheck (`desk-build-final`)、lint (`desk-lint`、警告あり)、実成果物の保存/原文復元/差分/モバイル下書き保持/axe回帰 (`desk-regression`)、担当のEnter開閉、再開注意の開閉、GET以外0/例外0。コマンドは前節と同じwrapper、各exit0。画像を開いて目視。現在の実作業・1440pxで会話上端633px付近→359pxへ。初回390pxで担当の順序問題を検出しCSS修正。

証拠: `artifacts/product-quality/desk/`、対象revisionと未コミット差分hashは同ディレクトリrevision.json。独立検証は `desk-redesign-independent.md`。競合優位・人間初見評価、前節の未実装項目の判定は変更しない。

独立検証追加指摘: 390pxの再開説明が左端へ28pxはみ出す問題を修正。最終CSSで確認領域x12/幅366、画面内に収まることを実測（desk/resume-fixed.json、resume-390-fixed.png）。git diff --check exit0。
