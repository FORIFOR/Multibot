# 作業状態・チーム会話の改善

対象: e344859 + 保持した既存変更。実ユーザーのrun_1a0b9570af7d0142694は読み取りのみ。実行の停止・再開・指示送信を検証のために行わない。

合格条件（実装前固定）: 実run/task/eventに基づく受付→計画→作成→確認→終了の現在地を表示。中断・承認待ち・未確認を完了に変換しない。会話は実message.sentだけを本文改変なく表示し、作業イベントとは区別。SSEと可視時pollで更新し、切断を表示。読んでいる位置を勝手に動かさず、最新追従へ戻れる。作業中の1440px初期表示で進行と会話欄が見つかる。390px、キーボード、reduced motion、既存成果物操作が維持される。

構成: 既存キャラクターと3ステップナビは保持。状態遷移帯を追加し、左に担当、右に会話・成果物。添付情報と指示フォームは開閉できる補助領域へ。状態は進捗率や残時間へ推定変換しない。会話のない計画中も実処理の更新記録を別枠で見せる。修正前画像: artifacts/product-quality/workroom-live/before.png。

## 最終検証（2026-09-19）

対象revision: `e3448595e13aceb1b4ad5a6fbd92154e4de1a9ac` + 未コミット変更。今回のsource/assetsのSHA-256は `artifacts/product-quality/workroom-live/revision.json`。環境: macOS、実Chrome 153.0.8010.53、1440/768/390px。8796の実依頼と、8798に隔離取り込みした過去の実記録を使用。モック・偽の発言・モデル追加実行なし。過去記録の中断/不合格を成功へ変更していない。

| 条件 | 測定方法・期待結果 | 判定・観測 | 証拠 |
|---|---|---|---|
| 型と本番配信 | tsc + Vite、同梱assets一致 | PASS、exit 0 | workroom-final-build.log、revision.json |
| 静的検査 | oxlint、エラーなし | PASS、exit 0。警告は残る | workroom-final-lint.log |
| 状態遷移 | APIと実画面照合、現在地/中断/未到達を区別 | PASS、5段階・実履歴を表示。作業終了件数を品質確認済みと呼ばない | browser-check.json、独立検証 |
| 会話の正確さ | 過去の実発言1件をAPI本文とDOM全文照合 | PASS、sender/recipient/本文/時刻を表示。現行依頼は会話0件と明示 | browser-check.json、review-1440.png |
| 通信断から復帰 | ブラウザoffline→online、再読み込みなし | PASS、取得失敗の表示後、自動復帰 | workroom-final-browser.log、workroom-live-check.mjs |
| レイアウト・操作 | 1440/768/390px、追従停止/Enterで復帰、reduced motion設定 | PASS、横溢れなし・aria-live off→polite・pageerror 0・更新操作0 | browser-check.json、各画像 |
| 新設部分のアクセシビリティ | progress/conversationをaxe WCAG A/AA検査 | PASS、1440/390で違反0。全製品の適合性を保証しない | a11y.json、workroom-a11y-fixed-context.log |
| 複数新着・長文を読む位置の維持 | 実際の新着受信中に追従停止/長文展開を観測 | BLOCKED、保有する実発言は短文1件。処理は実装済みだが実測未達 | TeamConversation.tsx、独立検証 |
| 外部再開後のSSE再接続 | 別の操作で実runを再開して観測 | BLOCKED、稼働中のユーザー依頼を検証のため変更しない。pollから再接続する分岐は静的確認 | Workroom.tsx、独立検証 |
| 日本語OS IME・200%拡大・実ユーザー理解 | OS操作と実ユーザー評価 | BLOCKED、この追加検証では未実施。自動検査で代用しない | 未実施 |
| ネイティブOS UI | 今回対象はWeb UI | NOT_APPLICABLE | — |

ログは `artifacts/product-quality/`、JSON/画像はその `workroom-live/` 以下。独立検証: [workroom-live-independent.md](workroom-live-independent.md)。比較は同じ実タスクの変更前 `before.png` と変更後画像に限定し、他社製品より優れるという評価はしていない。モデルの成果物品質に関する既存未達条件は今回のUI改善によってPASSにはならない。

実行コマンド（repo root、browserのみfrontend cwd）:

```sh
python3 artifacts/product-quality/run-command.py workroom-final-build pnpm --dir frontend build
python3 artifacts/product-quality/run-command.py workroom-final-lint pnpm --dir frontend lint
# cwd: frontend
python3 ../artifacts/product-quality/run-command.py workroom-final-browser node scripts/workroom-live-check.mjs
python3 ../artifacts/product-quality/run-command.py workroom-a11y-fixed-context node scripts/workroom-a11y-check.mjs
```

すべてexit 0。初回検証ハーネスのcwd誤り/Chrome context終了による失敗ログも保持し、スクリプトを修正して同じ期待値で再検証した。実依頼へ指示送信・停止・再開を行わず、既存成果物の採用状態も変更していない。

## 進行中の応答待ち表示（追加受け入れ条件）

ユーザー要求: チャットの応答待ちと同様に、会話のない間にも処理継続が見えること。実runのcreated/queued/planning/runningを対象に、接続とliveが確認できた場合のみ動く3点と段階の文言・実担当を表示。承認待ち・終了・中断は処理中にしない。通信断/状態取得失敗は動きを止め状態確認中へ。会話件数や本文には追加しない。reduced motionと既存の動き停止を尊重。390/1440pxの実run、切断・復帰、既存の実中断runで検証し、新しいモデル呼び出しは行わない。

追加検証結果（2026-09-19、macOS / Chrome 153.0.8010.53）:

- PASS: 実run `run_1a0b982c5bc72cef6bb` のplanning/liveをAPIで照合。実際に3点のCSS animationが動作し、390/1440pxで横溢れなし。動き停止・reduced motionではanimation:none。
- PASS: ブラウザofflineで状態確認表示と静止、onlineで処理中へ復帰。実中断run `run_1a0b9570af7d0142694` では処理中表示なし。取得失敗も接続確認として扱う。
- PASS: build（tsc/Vite）とlintはexit 0。lintの既存警告は残る。追加部分のaxe A/AAは違反0、pageerror0、GET以外0。新規依頼・停止・再開などの副作用なし。
- BLOCKED: 同じ実行のplanning→running→approval/completed全遷移は未観測。担当表示/承認待ちの分岐は静的確認のみ。実ユーザー評価、OS IME、200%拡大は今回未実施。

実行コマンド: repo rootで `python3 artifacts/product-quality/run-command.py conversation-processing-final-build pnpm --dir frontend build` と `python3 artifacts/product-quality/run-command.py conversation-processing-lint pnpm --dir frontend lint`。frontend cwdで `python3 ../artifacts/product-quality/run-command.py conversation-processing-final-browser node scripts/conversation-processing-check.mjs`。ログは同名の `artifacts/product-quality/*.log`。画像・観測JSON・対象revisionとSHA-256は `artifacts/product-quality/conversation-processing/`。表示の動きは実行状態のフィードバックであり、架空の発言・思考過程・進捗率を生成していない。


## 簡素化（ユーザー指定）

受け入れ条件: 会話原文・現在状態・操作と費用/承認/再開に必要な注意は保持。通常表示から会話の説明文と空状態の長文を削除。進行状況、処理の詳細、作業記録、各担当の作業内容、資料と前提を標準detailsで開閉可能にする。折りたたみはユーザーが求めた情報量の削減であり、実記録の削除ではない。390/1440pxで折りたたみのキーボード操作と実会話の原文一致を検証する。


簡素化の検証: PASS（自己レビュー）、macOS Chrome153、390/1440px。実中断runと隔離した過去の実会話1件で、標準detailsの初期閉状態/Enter開閉、原文完全一致、横溢れ0、会話領域axe違反0、pageerror0、GET以外0を確認。画像を実際に開いて目視。build/typecheck `simple-chat-final-build.log`、lint `simple-chat-lint.log`（警告あり）、ブラウザ `simple-chat-browser.log` はexit 0。ブラウザコマンドはfrontend cwdで `node scripts/simple-chat-check.mjs`。証拠: `artifacts/product-quality/simple-chat/`。今回実runは自然中断済みのため、短縮後の処理中表示の実動作はBLOCKED（状態判定とanimationは変更なし）。人間評価/OS IME/200%拡大は未実施。既存試験の進行状況取得は、今回の折りたたみ仕様に合わせて開いてから従来の検証を行うよう更新した。


## 経過時間

会話ヘッダーに経過 mm:ss（1時間以上 h:mm:ss）を追加。開始から終了までの時計時間で、承認待ち/中断時間を含む。liveかつ非終了の場合だけ毎秒更新。終了記録がない停止runは最後の実eventまでを「記録時点」と表示。開始未記録は —。読み上げを毎秒繰り返さない。

PASS（自己検証）: macOS Chrome、実runningで9808→9810秒、実interruptedで479→479秒。実API started_at/finished_atと照合、390px横溢れなし、画像目視。build/typecheck exit0: `elapsed-build.log`。frontend cwd `node scripts/elapsed-check.mjs` exit0: `elapsed-browser.log`。証拠 `artifacts/product-quality/elapsed/`。未開始と終了時刻欠落の実ケースはBLOCKED（未観測）。新規モデル実行なし。
