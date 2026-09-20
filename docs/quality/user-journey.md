# 利用者の操作順による検証 — 2026-09-20

これは実ブラウザーを操作したAIによる利用想定テスト。人間のユーザビリティ調査ではない。独立担当は正解ルート/実装を読む前に目的から探索した。

環境: macOS、Chrome、1440/390/720px、reduced motion。既存の実記録を8798、同記録の別コピーを8799（/tmp/multibot-user-journey-20260920）で使用。8796の既存作業は再開/変更せず、8799のみで修正指示を受付。モック会話・APIレスポンス差替えなし。通信障害はブラウザーをofflineにし、容量不足は実repoの既存記録で実ストレージを埋めて再現。

判定条件: 入力/保存内容が一致する、失敗時に成功と言わず入力が残る、復帰できる、受付が完了扱いにならない、二重クリックで今回の指示が1件だけ記録される。モデルによる新規成果物生成の成功は別条件。

| id | 操作・期待 | 観測 | 判定・証拠 |
|---|---|---|---|
| U1 | 新規依頼へREADMEを添付しreload。入力と資料が残る | 本文と実READMEの全bytes一致 | PASS new-request.json/png |
| U2 | 作業を探し、状態/担当/実会話を読む | 独立探索で到達、途中成果と停止状態を認識 | 独立報告参照 |
| U3 | 成果物を編集し保存。原本は不変 | 保存ファイル全内容一致、reload復元、原文復元、API hash不変 | PASS user-journey-artifacts.log |
| U4 | 対象範囲/版を指定し修正指示を準備 | 選択本文とSHA256一致、mobile切替保持 | PASS 同上 |
| U5 | 成果物読込中に切断し復帰 | エラー表示→online→明示retryで同じ版を再読込 | PASS recovery.json |
| U6 | 指示送信をofflineで失敗させる | 入力が全文残る、失敗を表示 | PASS recovery.json |
| U7 | online復帰し指示を連打→reload | 指示1件だけ受付、最新指示に全文一致。作業はinterruptedのまま、model_calls不変 | PASS recovery.json/saved-instruction.png |
| U8 | ブラウザーの保存容量不足 | 保存不可を明示、編集コピーをdownloadして全文回収 | PASS recovery.json/quota-recovered.txt |
| U9 | 新規依頼の下書き容量不足→設定へ往復 | 最新入力を保持 | PASS draft-quota.json/user-journey-draft.log |
| U10 | 停止中に指示を保存しても経過時間は停止時点のまま | 初回140時間へ伸びる不具合を検出。停止イベント優先へ修正→再検証で15分を保持 | FAIL→修正後PASS user-journey-recovery-fixed.log |
| U11 | モバイル/キーボード/限定axe | 表示と下書き保持、結果領域axe0 | PASS artifactsログと独立報告 |
| U12 | 新規依頼→モデル生成→再確認→完了 | 隔離import profileの疎通確認がnot_runで開始無効。実モデル疎通/生成は今回未実施 | BLOCKED。過去成果物の閲覧試験で代用しない |
| U13 | 新規生成品質、人間初見、実IME/実iPhone | 今回の評価対象として未実施 | BLOCKED |

過去の実成果物に多言語混在がある。過去の確認通過や今回の操作PASSを生成内容の正しさと解釈しない。

実行: root `python3 artifacts/product-quality/run-command.py user-journey-fixed-build pnpm --dir frontend build`、同wrapper `user-journey-lint pnpm --dir frontend lint`。frontend cwd: wrapper `user-journey-artifacts node scripts/creation-studio-check.mjs`、`user-journey-draft node scripts/product-quality-draft.mjs`、`user-journey-recovery-fixed node scripts/user-journey-recovery.mjs`。すべてexit0、lint警告あり。git diff --check exit0。commands.jsonlに時刻/コマンド/exitを記録。

証拠ルート: artifacts/product-quality/。今回の詳細はuser-journey/、対象revisionと未コミット差分hashは同revision.json。成果物回帰の画像/内容はcreation-studio/。独立報告: [user-journey-independent.md](user-journey-independent.md)。
