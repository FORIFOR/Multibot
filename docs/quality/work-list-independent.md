# 作業一覧の独立検証

2026-09-19、independent-product-verificationを適用。別の一時Chromeプロファイルで8796の実作業を読み取り検証した。**検証した範囲に不具合なし**。実装変更・新規依頼・停止・再開・指示送信・モデル呼出はなし。ブラウザのHTTP要求はGETのみ。

環境: macOS、Chrome153、1440×1000 / 390×844。受入はdocs/quality/work-list.md。初見で作業一覧から「Jevについて調査してPDFでまとめて」を選び、当該作業の会話を開いた。会話直前にも依頼名があるため対象を見失わず、一覧へのリンクで戻れた。コードは初見一覧表示後に読んだ。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| WL1 | API状態と4フィルター件数照合 | 実状態の正確な分類 | interrupted6/cancelled1、全て7。他3分類0。完了への変換なし | PASS | verification.json / 1440-list.png | 実8796 |
| WL2 | 実作業行にfocus→Enter | 当該会話へ移動 | run_1a0b9570af7d0142694へ移動、work-conversationにfocus、依頼名一致 | PASS | verification.json / 1440-entered-conversation.png | 1440px・キーボード |
| WL3 | 一覧リンク／ブラウザ戻る | 選択フィルター復元 | filter=allとaria-current=pageを維持、ロード後7件 | PASS | verification.json / error-recovery.json | 実allフィルター |
| WL4 | 390pxで一覧→会話、画像目視 | 可読性と横幅 | 長い日本語は折返し、横あふれ0、一覧への戻りリンクあり | PASS | 390-list-loaded.png / 390-conversation.png | 390px |
| WL5 | 独立ブラウザのみoffline→一覧poll失敗→online→再読み込み | 失敗を明示し再試行可能 | role=alertで古い可能性を表示、再試行で7件復帰、警告消去 | PASS | 390-error.png / error-recovery.json | 実ネットワーク遮断、偽レスポンスなし |
| WL6 | API会話とUI照合 | 実会話数一致 | 対象runは0件、UIも0件 | PASS | verification.json | 空の実会話、本文一致試験ではない |
| WL7 | 状態分類コードレビュー | 指定状態を指定分類へ | created/queued/planning/running→active、approval_required/blocked→attention、completedのみcompleted | PASS | frontend/src/pages/WorkList.tsx | 静的レビューに限る |
| WL8 | 非all分類の実行行・復帰 | 実作業から各フィルターへ戻る | 対応実データが0件のため未実施 | BLOCKED | verification.json stateCounts | 実データ不足 |

証拠は `artifacts/product-quality/work-list-independent/`。一覧・会話の1440/390画像、390の読み込み後と通信エラー画像を実際に開いて確認した。フィルターはリンクでキーボード操作可能、行をEnterで開いた直後は会話領域に可視フォーカスが付く。

進行中・承認待ち・blocked・completed・failed・partialの実状態表示はデータに存在せず未検証。非allフィルターから実行行へ入る経路も同理由で未実測。状態を人工的に作ってPASSにしていない。空の各フィルターは0件表示と空状態を確認した。自動更新は5秒pollによる実切断の検出で確認したが、サーバーの作業状態を変化させた動的分類試験は行っていない。

戻り直後のverification.jsonでは件数が一時「—」だが、一覧再取得中の表示であり、読み込み完了後は7件。エラー中は既存行を保持し警告で古い可能性を示す。

実会話本文は対象作業に存在しないため本文一致は未検証（0件一致に限定）。人間評価・OS日本語IMEはBLOCKEDを維持。既存の入力・成果物経路は今回変更箇所の静的確認のみで、依頼送信や採用操作による再試験はしていない。
