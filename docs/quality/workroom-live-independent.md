# Workroom状態・会話の独立検証

2026-09-19、macOS Chrome153、1440×1000 / 390×844、8796の実ユーザーrun `run_1a0b9570af7d0142694`をGETのみで検証。新規依頼・指示送信・再開・中断操作・モデル呼出・実装変更なし。

初回コードレビューの2件（acceptedを確認済みと誤表示、SSE終了後の外部再開で接続復帰しない）は主担当が修正済み。前者は「作業を終了」の実表示、後者はpollでliveかつ非terminalならconnectするコードを確認。外部再開をこの検証のために実行してはいないため後者は静的確認に限る。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| L1 | 実run画面とAPI照合 | 実行中を完了と誤表示しない | running時は調査・作成が進行中、確認/終了未到達、0/3作業終了 | PASS | 1440-progress.png / 390-progress.png | 実run |
| L2 | 空チャットの実表示 | 実発言と作業eventを区別 | 0件と発言なしを表示、モデル応答受信は直近作業記録へ別表示 | PASS | 1440-conversation.png / 390-conversation.png | 実chat=[] |
| L3 | 追従ボタン停止/最新へ戻る | aria-liveを切替 | off→politeを確認 | PASS | live-verification.json補足・本報告 | チャット0件なのでスクロール保持は未検証 |
| L4 | 390px実画像を開く | 操作・状態を読める | clientWidth=scrollWidth=390、段階名は折返し、会話領域が表示 | PASS | 390の両画像 | 実Chrome |
| L5 | 実runが中断した後の再読込 | 中断を成功と誤表示しない | 調査・作成に作業中断、確認未到達。終了は記録あり（成功とは表示しない） | PASS | 1440-interrupted.png, live-verification.json | 実run自然遷移、再読込 |
| L6 | 原文表示経路のコードレビュー | 発言を改変しない | chat_view payload.text→m.text直接表示、pre-wrap。長文はdetailsだが省略なし | PASS | static-review.md | 静的確認のみ |
| L7 | 通信観測 | GETのみ | nonGet=[] | PASS | live-verification.json | 全操作 |

証拠は `artifacts/product-quality/workroom-live-independent/`。1440/390の4画像と中断後画像を実際に開いた。空チャットを実会話の原文一致試験と呼ばない。主担当が用意する実過去会話の隔離storeで長文・スクロール保持・原文一致を追加確認可能。

ローカルブラウザだけ一時offlineとしてreload失敗→online→gotoで復旧したが、これはSSE単独切断復帰の試験ではない。中断への変化も再読込で確認したため、SSE通知によるリアルタイム遷移の成功とは断定しない。実データを偽eventで補わず、未検証を維持する。人間評価・OS IMEはBLOCKED。

## 過去の実会話の独立追加確認

主担当が実記録 `docs/evidence/real-readiness-v2-2026-09-14/runs/01-run_1a09c8485503d406bf4` を取り込んだ隔離サーバー8798の同runをGETのみで確認。APIの会話は1件、reviewer→builderのfinding、seq61。DOMの`.message-text` textContentとAPI本文は全文完全一致。和文/英文/引用符/識別子を改変していない。1440と390のスクリーンショットを実際に開き、発言者・受信者・時刻・本文を確認。390pxの横あふれ0、nonGet=[]。

証拠: real-chat-verification.json、real-chat-1440.png、real-chat-390.png（上記証拠フォルダ内）。**原文保持と実会話表示は実ブラウザでもPASS**。短文1件のみのため、長文detailsや複数の新着受信中に過去のスクロール位置を保持する動作は未実測。主担当が別途実施したoffline/online自動復帰のPASSと、この独立検証で行ったreload復旧は区別する。
