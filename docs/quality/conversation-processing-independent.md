# 会話欄の処理中表示：独立検証

2026-09-19、実run `run_1a0b982c5bc72cef6bb`（開始・終了時ともplanning/live=true）、macOS Chrome153、一時独立プロファイル。**今回の確認範囲で問題なし**。実行操作なし、HTTPはGETのみ。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| C1 | 実画面＋450ms間隔のcomputed style | 計画中の説明・3点の実動作 | 進め方を考えている表示、3点のopacity/transformが変化 | PASS | initial.png, verification.json | 実planning/live |
| C2 | reducedMotion=reduce | アニメ停止 | 全点animation:none、transform:none | PASS | verification.json | Chromeメディア設定 |
| C3 | UI「動きを止める」 | アニメ停止 | 全点animation:none。再開操作後は通常へ | PASS | verification.json | UI内の動き停止のみ |
| C4 | 独立ブラウザoffline→online | 切断中に動かず再接続で復帰 | 再接続中・状態照会、data-processing=waiting、全点animation:none。onlineでlive/active復帰 | PASS | verification.json | 実通信遮断、6秒/4秒観測 |
| C5 | 1440/390画像を開く | 判読でき横あふれなし | 両画像を目視、390横あふれ0。発言ログ外で生成量ではないと説明 | PASS | initial.png, 390-processing.png | 実Chrome |

証拠: `artifacts/product-quality/conversation-processing-independent/`。ConversationActivityはactiveかつconnection=liveかつrun.liveかつ承認なしでのみis-processingを付与。終了ではnull、承認待ちではアニメclassなしというコードを確認。ただし承認待ち・終了の実状態はこのrunで発生せず、実画面での検証はBLOCKED（静的確認のみ）。planning以外の実担当表示も今回は未実測。CSS zoom等や模擬イベントは使用していない。

GET以外0件。UIの「動きを止める」は装飾停止ボタンであり、作業の停止/再開・指示送信は行っていない。人間評価・OS日本語IMEはBLOCKEDを維持。
