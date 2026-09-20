# 作業一覧から会話を開く

受け入れ条件（実装前）: `/runs` に全て・進行中・確認待ち・完了の4フィルターと件数を表示。created/queued/planning/runningを進行中、approval_required/blockedを確認待ち、completedだけを完了とする。中断/失敗/取消/部分完了は全てで正確な状態を表示し、完了へ変換しない。各実作業の行から当該runの会話に移動し、一覧へ戻ると選択フィルターが復元される。既存の依頼入力/成果物閲覧は維持。読取のみの自動更新、取得失敗の明示と再試行。実記録で390/1440px、キーボード、ブラウザ戻る、API本文一致を確認する。新規モデル実行や偽のデータは使わない。

UI方針: 既存の色/丸みを保った一覧行。4列カンバンより長い日本語の依頼を読みやすくし、スマホでも同じ切替を使う。別の会話モーダルを増やさず既存Workroomへ入る。

## 検証結果

環境: macOS、Chrome 153.0.8010.53、1440/768/390px、reduced motion設定。8796の実作業7件（中断6・取消1）、8798の隔離した実過去記録1件を使用。対象HEADと今回のファイルハッシュは `artifacts/product-quality/work-list/revision.json`。API変更なし。既存APIの直近50件の範囲を画面に明記。

| 条件 | 判定 | 観測・証拠 |
|---|---|---|
| build/typecheck | PASS | `work-list-compact-build.log`、tsc + Vite exit 0 |
| lint | PASS | `work-list-lint.log` exit 0、既存警告あり |
| 4分類と件数・空状態 | PASS | 実一覧と件数一致。進行中/確認待ち/完了は0件。`work-list/browser.json` |
| 作業選択→会話→一覧、戻る、reload | PASS | URLフィルター保持、会話へスクロールとフォーカス、キーボードEnterで操作 |
| 会話原文 | PASS | 過去の実発言1件をAPIとDOM全文比較。新規発言は生成していない |
| 通信断と復帰 | PASS | ブラウザofflineで警告、onlineで自動更新復帰 |
| 狭幅・自動a11y | PASS | 1440/768/390横溢れ0、一覧をaxe WCAG A/AA検査で違反0、実画像を目視 |
| 作業への副作用 | PASS | ページ例外0、GET以外の通信0。実行/停止/送信/採用はしない |
| 非空の進行中/確認待ち/完了一覧と非allからの復帰 | BLOCKED | 対象の実状態が現サーバーに存在しない。分類分岐は静的確認のみ |
| OS IME・200%拡大・実ユーザー理解 | BLOCKED | 今回未実施。自動検査の成功で代用しない |

独立担当による検証は [work-list-independent.md](work-list-independent.md)。最終調整で長い依頼を一覧3行・会話直前2行へ抑え、会話を押し下げないようにした。全文は既存の依頼詳細から開ける。結果の品質や既存未達項目を本UI試験によって合格に変更していない。

コマンド（repo root）:
```sh
python3 artifacts/product-quality/run-command.py work-list-compact-build pnpm --dir frontend build
python3 artifacts/product-quality/run-command.py work-list-lint pnpm --dir frontend lint
# cwd: frontend
python3 ../artifacts/product-quality/run-command.py work-list-final-browser node scripts/work-list-check.mjs
```

最終実行はいずれもexit 0。ログは `artifacts/product-quality/`、画像とJSONは `artifacts/product-quality/work-list/`。初回ハーネスのパス誤りは `work-list-browser.log` に残し、パスを修正して同じ条件で再実行した。
