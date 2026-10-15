# 資料の追加から成果物の確認・採用・保存へ

2026-10-02（JST）。[継続する品質目標](../../design/AWARD_QUALITY.md)に沿った、公開サービスPR27の次の反復。基点は `01b11f0bacd5a5a1c37af5ebd9cf724b3fe6efff`、実測対象には未コミット変更を含む。[最終ソースと配信bundle](round2-source.json)、[公開画像manifest](public-capture-manifest.json)、各記録のSHAを照合する。基点コミットだけを実測対象としない。

**一般公開・受賞水準・業務品質・人間受入は未達のまま。** 保存済みv62の実記録を新しい私有SQLiteへコピーしてUIを検証した。元の状態・失敗・誤ったAI解釈・成果物を成功文へ変更していない。元系列の全記録とSQLiteは不変、新しいモデル呼出と実行jobは0。資料追加では実 `docs/quality/integration.md` と実発行operator鍵を使用し、依頼は送信していない。

## 実画面で見つけ、直した点

| 観測 | 変更と再確認 |
| --- | --- |
| 保存済み添付の横にnative inputの「選択されていません」が出る | 「資料を追加」と「依頼に添付済み」を分離。実input、キーボードフォーカス、同じ資料の再選択、保持・削除を維持 |
| 一覧は完了・失敗・中断でも会話画面を強制する | `from` を保ったまま強制viewを外す。実completed/failed/interruptedで成果物が初期表示され、会話切替と元の絞り込みへ戻れることを1440/390、最終英語320/390/1440で確認 |
| 本文を読む前に採用・ZIP・編集が集中し、版番号は閉じた詳細内 | ファイル名・現在版・採用状態→本文→対象版の確認記録→採用→採用ZIPの順に整理。最新の全ファイルZIPとコピー編集は説明付きの別操作へ |
| 確認記録をTab→Enterで開いても元ボタンにfocusが残り、次のTabが採用 | 展開した記録のsummaryへfocusを移す。独立した実Chrome操作で、summary・可視枠・その後の保存リンクまで確認 |
| 初版で単一ファイル名が選択ボタンと本文見出しに重複 | 別担当の画像批評を受け、選択ボタンは複数ファイル時だけにした。最終画面で名前・版・採用状態を常設したまま重複を解消 |

[変更前1440](before-results-1440.png)、[初版1440](round1-results-1440.png)、[最終の本文](final-reader-1440.png)、[390幅の採用版保存](final-save-390.png)、[英語390](final-save-en390.png)、[320幅の記録focus](final-check-focus-320.png)、[実Chrome200%](result-native-200-save.png)。変更前390 fullPageは切替後のsticky headerが途中へ写る撮影制約を含み、原画像を保持した。これを製品の重なり不具合と数えない。

## 実採用とZIP

[実操作](round1-adoption.json)、[全entry・bytes・SHA照合](round1-zip-verification.json)、[受付/権限](admission-and-readonly.json)、[最終UIの独立採用](independent-final-adoption.json)を保全。

- 未採用ZIPは409、実UIで特定r1を採用すると202、reloadで選択が残る。古い `expected_selected_revision=0` は409で選択を変えない。
- viewerの採用操作は表示されず、実APIも403。閲覧用説明を表示する。
- `selection=adopted` のZIP全entry集合、manifest、成果物・final-report・eventsのbytes/SHAを照合。通常ZIPは各最新版であり採用版とは別。ブラウザーの実downloadファイルを保存して照合した。
- 検証者はAI。APIの `actor_kind=human` や採用操作を人間の受入と扱わない。画面の保存リンクは取得開始の操作であり、利用者の端末保存完了を自動認定しない。

## 失敗・未確認も残す

[初回focus判定の原失敗](round1-focus-early-failure.json)は、実UIのrequestAnimationFrameより前に検査が読んだもの。採用送信前に停止した。次の試行では実focusを待って採用を1回だけ行い、選択の巻戻しや推論の再実行はしない。[検証まとめ](workroom-verification-summary.json)でこの経緯を区別した。

添付の[原round](attachment-original-round.json)はOSファイル選択取消の待機がtimeoutでFAILED。ツールが所有する別Chromeウィンドウに接続できず、無関係なChromeを操作せずに終了した。**実OS取消は未操作・未検証**。合成cancelや空の偽選択で埋めない。追加・同一実ファイル再選択・reload・削除・日英・幅・200%は別途通過として[部分検証のまとめ](attachment-verification-summary.json)へ残した。

v62の利用者向け成果物は各runで単一ファイル・r1だけ。複数ファイル切替、複数revisionの新select、成果物なしの終端状態は今回未検証で、状態や版を捏造しない。実Safari/iPhone・読み上げ・初見の第三者・公開配信の性能・自由な業務の正しさも未確認。

## 独立確認と範囲

[独立before](independent-baseline-actions.json)と[最終の実操作](independent-final-interaction.json)で、JA1440/390/320・EN390の読む/記録/採用版保存/最新版取得の区別、横幅、実Tab/Enterとfocusを確認。Homeは別担当が実画像とdiffを確認した（独立したOS選択操作ではない）。[最終英語の遷移](final-en-navigation.json)も320/390/1440で確認した。新たな重大な指摘がないという今回のAI批評であり、受賞審査や人間受入の代わりではない。

[実Chrome200%](result-native-200.json)はouter1440、inner720、DPR2、CSS zoom1。表示中runの前後hashは一致し、ログイン以外のwriteは0。画像拡大やCSS zoom試験と区別する。

最終combined UIで[既存の実HTTP/SQLite/Chrome 6段階](service-integration.json)も通過。主体分離・同じ依頼の再送・並行ログイン・peer離脱の境界は維持。TypeScript/build、配布UI一致は通過、lintはexit0・既存警告あり。チェック件数は業務品質の点数ではない。

公開サイトの4枚は同じ最終bundleから撮り直した実画像。携帯画像は未送信の依頼欄へスクロールしたviewport。旧4枚と最初の寄り過ぎたframingも私有領域に保持し、最終採用だけを[manifest](public-capture-manifest.json)へ明記。画像の修整や架空の成果物は使用していない。

独立レビューの全文は [独立評価](independent-review.md)、原成果物とZIPの照合は [照合結果](independent-final-verification.json) を参照。残るP3として、320/390幅では依頼情報とチーム表示が長く、本文開始が最初のviewportより下にある。

**別途見つかったサービスエラー:** 成果物検証用APIの終了時に、監査保存の `sqlite3.OperationalError: database is locked` を観測した。UI操作通過を全HTTP無エラーと読み替えない。回収ログはtool出力が切詰められており、全原文・全例外件数は不明。[原観測](database-original-observation.json)と[監査記録との時刻照合](original-lock-summary.json)を保持。別の実SQLiteへ原データをコピーし、通常のread/usage/auditを32並行で呼ぶと監査5件で `SQLITE_BUSY` (code 5) を[再現](database-r1-summary.json)した。`BUSY_SNAPSHOT` (517) と断定しない。共有接続のexecute→fetch→closeを専用lockで直列化し、取得したcursorを閉じる修正後は同じrunner・入力の20組640呼出でエラー0となった（[修正後](database-r2-summary.json)）。直接connを操作してguardを迂回する故意の負例は引き続き失敗し、失敗を消していない。元HTTPログは欠けているため同一原因の完全な証明とはしない。他プロセスの長期write lock、execute待ち中の取消まで全面解決したという主張もしない。修正後に[実サービス6段階](service-after-db-fix.json)も再通過し、モデル0・所有Chrome残留0。

原記録、private鍵、DB、browser profile、回収できたlog、取得ZIPは `~/.cache/agentteam-bench/{workroom,attachment}-craft-20261002` に保持。公開はこのディレクトリの名前指定ファイルだけ。所有検証サービス/Chromeは終了、LLM/Colimaは起動しない。[終了・原記録不変](cleanup.json)と[公開ファイルmanifest](manifest.json)を参照。元の一般公開・実業務・第三者自力利用の受入条件は [PUBLIC_SERVICE.md](../../PUBLIC_SERVICE.md) に残る。

補助証拠: [実記録の取込](record-import.json)／[原系列の不変](final-invariants.json)／[受付](service-admission.json)／[応答](service-responses.json)／[公開候補scan](safe-scan.json)。添付画面は [1440](attachment-1440.png)、[320](attachment-320.png)、[実200%](attachment-native-200.png)、[キーボードfocus](attachment-keyboard.png)。

監査保存の修正後は、新しい `check_database_concurrency.py` で実repoのv62 rep1/2/9を別DBへ取り込み、実発行鍵でログインした[並行HTTPの最終確認](database-http-final.json)を追加した。480 HTTPはすべて200、各応答のauthorized/response監査が揃い、別SQLiteの640通常呼出もエラー0。元資料/業務状態不変、追加model/job0、時刻付き全private logと終了を照合した。これは容量/SLAの受入ではない。検査runnerの報告形式を補強した前2回もprivateに保持し、最終script SHA一致の回だけを採用した。[対象外の実資料を渡す負例](database-invalid-source.json)は開始前FAIL/exit1、480/640予定に対して実施0を記録し、未測定を成功にしない。[失敗報告の安全な保存](failure-reporting-summary.json)も確認。CIへはallowlistの `safe-report.json` だけを保存する。

実装を書いていない担当も別private rootで[2組の実HTTP/SQLite](database-independent-http.json)を独立再実行。HTTP48・direct64・監査欠落0を確認し、さらに元資料14ファイル/成果物5件、3 run・232 eventと[個別照合](database-independent-verification.json)した。20組の試験と合算せず、模擬応答や推論の再実行は使用していない。
