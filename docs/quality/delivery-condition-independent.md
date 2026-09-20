# 成果物条件の独立ブラウザ検証

今回の範囲で不具合は見つからなかった。実装変更なし。2026-09-19、macOS Chrome 153、独立一時プロファイル、127.0.0.1:8796で確認。人間評価・OS IMEはBLOCKEDを維持する。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| D1 | 実資料添付と条件入力後reload | 下書きを維持 | 実repo integration.md、依頼文、guide.md、400/700を復元。sessionStorage添付本文が実ファイル全文と一致 | PASS | verification.json | 独立Chrome / 390px |
| D2 | 最小文字数からTab、最大文字数へキーボード入力 | 順序とフォーカスを確認 | 最大文字数へ移動し700を入力、フォーカス枠表示 | PASS | 390-invalid.png, 200-condition-window.png | 390px / 200% |
| D3 | 最小400・最大300、ボタンへfocus→Enter | POSTより前に矛盾拒否 | role=alertで範囲修正要求、POST発生なし | PASS | verification.json | 390px / 200% |
| D4 | Chrome appearance Page zoom=2、reload、入力 | 本物の200%で条件を操作・復元 | innerWidth720 / DPR2 / CSS zoom1、条件700復元、Tab操作可、scrollWidth720 | PASS | verification.json, 200-condition-window.png | 1440 viewport / Chrome標準200% |
| D5 | リクエスト観測 | 新規依頼等を送信しない | nonGet=[]、安全用abortガードの発火も0 | PASS | verification.json | ブラウザ通信 |

証拠は `artifacts/product-quality/delivery-condition-independent/`。390-invalid.pngと200-condition-window.pngを実際に開き目視確認した。200-condition.pngは一時ウィンドウが390px起動時の大きさのままのキャプチャだったため、独立ウィンドウのみBrowser.setWindowBoundsで拡張して後者を撮り直した。アプリCSSは変更していない。

手順: Homeで「資料を添える・予算を決める」から実際のdocs/quality/integration.mdを添付。「成果物の条件を指定する」でguide.md、最小400、最大700を入力してreload。各入力と添付本文を照合。最大300へ変えて矛盾条件を作り、送信ボタンにfocusしてEnter。実装の送信前returnを事前確認し、さらにnon-GETをabortする安全ガードを設置したが発火しなかった。偽レスポンスや成功モックは使用していない。矛盾条件でのローカルvalidationのみ作動し、依頼自体は送信していない。最大700へ戻し、Chrome標準設定chrome://settings/appearanceのselect#zoomLevel=2で200%にした後reloadし同様に操作。セッション終了まで新規実行・再開・指示保存なし。

これはブラウザ下書きと送信前検証に限る。実際に条件付き依頼をモデルへ送信して完成品を得る検証は、主担当の別試験と区別する。
