# UI仕上げの独立検証

2026-09-20、macOS Chrome153、一時独立プロファイル、1440/390px。8796の実run `run_1a0b982c5bc72cef6bb` と8798の実過去run `run_1a09c8485503d406bf4` をGETのみで確認。依頼・実行・採用・停止・再開・指示送信なし。実装変更なし。

**P2: 会話/成果物へのナビはスクロールだけで、キーボードフォーカスを移動しない。** `Workroom.select()`でscrollIntoView後も元buttonがactiveElementのまま。Enterで成果物へ移動して次Tabを押すと、成果物内ではなく進行状況へ進む。会話も同様。受入の「キーボードで会話/成果物へ移動」を満たすため対象領域へfocus({preventScroll:true})し、room-resultsにもtabIndex=-1を付与することを主担当へ依頼。

確認済み: 白い依頼ヘッダーに依頼名1回、3ステップなし、一覧へ戻る1箇所、会話/成果物ページ内ナビ、静かな担当一覧。390pxの上部ナビは1行、再開リスク文・使用額・記録時点・絵文字が表示される。確認事項は折り畳まれるが展開導線あり。390px横あふれ0。過去実会話1件のDOM本文とAPI本文は完全一致。実データの状態を完了へ変換していない。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| U1 | 1440/390画像を開く | 重複低減・必須情報保持 | 上記表示を目視確認、横あふれ0 | PASS | 1440-current-top.png, 390-current-top.png, 390-current-chat.png | 実Chrome |
| U2 | navをfocus→Enter→Tab | 対象へフォーカス移動 | 元nav buttonに残り次Tabが進行状況へ | FAIL | focus-failure.json, verification.json | 実キーボードイベント |
| U3 | 過去実会話とAPI照合 | 原文保持 | 全文一致、件数1 | PASS | verification.json, 1440-past-chat.png, 390-past-body.png | 隔離実記録 |
| U4 | 通信観測 | 閲覧のみ | nonGet=[] | PASS | verification.json | 両サーバー |

証拠は `artifacts/product-quality/ui-refinement-independent/`。初回に旧名称「チームのやりとり」でwaitしてタイムアウトしたが、新名称「チームの会話」に合わせ実DOMを探索して続行。アプリの取得失敗ではない。保存・採用状態を変更する試験はしていない。人間評価・OS IMEはBLOCKED維持。

## 修正後の独立再検証

主担当がselectでtarget.focus({preventScroll:true})、room-resultsにtabIndex=-1を追加し配信後、同じ実過去runをreloadして再確認。Enter後activeElement.idは成果物=`room-results`、会話=`work-conversation`。成果物から次Tabは「最新のファイルをまとめて取得」へ移動した。**U2は修正後PASS**。初回FAILと再現証拠は保持し、focus-fixed.jsonを追加。今回指摘の未修正項目は残っていない。
