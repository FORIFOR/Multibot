# 作業画面の読込みを、待ち続けずにやり直せるようにする

2026-10-02 JST。作業の詳細・会話・イベントを取得する3本のGETのうち1本が返り切らないと、画面内の再読込も定期更新も動かなくなる経路を修正した。通信の読取失敗と業務の失敗を分け、既に読めた内容と未送信入力を保つ。一般公開・業務品質・人間受入・受賞水準の認定ではない。

## 修正前の実観察

基準は `6ada2a36e7c8269e07e3a063b0319f67a1ce2534`。実v62の保存記録を別SQLiteへ原bytesで取り込み、実AppService、発行キー、Chromeを使用した。[原観察](before-observation.json)と[ブラウザー原記録](before-browser.json)を保持する。

日本語390幅で、interruptedのrep9の実詳細GETが返した200応答をCDPのResponse段階で保留した。[有効な再読込ボタンへTabで移動してEnter](before-held-focused.png)しても、詳細・会話・イベントの要求は各1件から増えず、17.502秒と[35秒時点](before-held-at35s.png)でも読込表示のままだった。応答の保留を解除すると元の状態と原成果物へ戻った。画面や応答を捏造した試験ではない。

英語768幅の実通信遮断では既存の警告・Refreshからの回復と未送信文の保持を確認した。ただし詳細URLだけを指定した遮断が実際には会話・イベントにも及び、原診断の4件が分類漏れだった。警告画像はスクロール位置のため上部の警告を写していない。[範囲の補足](before-scope-addendum.json)と[独立批評](before-critique.json)を原記録に追加し、detail単独遮断や警告の画像証明へ読み替えない。

## 読取だけを有限にする

`Workroom` の3 GETを共通のAbortControllerで管理し、本文を含む読取に15秒の期限を設けた。画面の再読込や共有refreshを使う明示操作後の読取は、前の読取を終了して新しい一組を送る。通常のpoll/SSEの更新通知は従来どおり一組へまとめる。一つが失敗した時は残りも終了し、画面から離れる時も終了する。

古い組の成功・エラー・終了処理は新しい組の結果、イベント位置、読取中状態を上書きできない。失敗時は「最新の状態を取得できない」と示し、作業statusや既表示本文・会話・入力を変更しない。3 GET以外の成果物本文取得、主体header/generation照合、AuthGate、SSE、更新操作の同一キーと30秒期限は変更していない。[静的な独立レビュー](static-review.json)と[ビルド/配布一致](build-checks.json)を保存した。

15秒はこの読取の製品側の待機期限で、ブラウザー停止や背景のtimer抑制まで含むwall-clock SLAではない。CDP Response段階の保留はヘッダー到達前の観察であり、ストリーム本文の途中だけが停止した場合の実証ではない。本文にもsignalが届くことはコードレビューの範囲として分ける。

## 修正後の独立確認

[独立r2の原結果](independent-r2-safe-report.json)では、次の4経路を確認した。秒数は保留開始からの単発観測で、一般的な通信性能の保証ではない。

| 条件 | 観測 |
| --- | --- |
| 日本語390、初回詳細GET保留中 | Tab/Enterで旧読取を終了し、新しい3 GETを送信。保留開始175ms後に元の成果物へ復帰 |
| 日本語320、初回詳細GETの期限 | 期限前は読込中、15,020msで読取エラー。自然なTab/Enterを経て15,142msで復帰 |
| 英語768、既表示のpoll保留 | 15,312msで最新状態未確認の警告。表示済みの状態・会話と未送信入力を保持し、Refresh後15,573msで原成果物へ復帰 |
| 英語、実Chrome200% | outer1440 / inner720×456 / DPR2 / CSS zoom 1。focusと操作が見え、自然なTab/Enterで保留開始654ms後に復帰 |

実装担当と別担当が、[日本語320の期限とfocus](ja320-deadline-deadline-focus.png)、[英語768の警告と既表示内容](en768-loaded-deadline-deadline-warning-focused.png)、[実200%](en-native200-manual-focused-retry.png)、[日本語390の元の未完了成果物への復帰](ja390-manual-recovered.png)を目視した。[実装担当の画像記録](root-visual-review.json)と[独立担当の批評](independent-r2-independent-review.json)を分けて保存する。

r2全体は追加の画面移動試験で停止したため **FAILのまま保持**する。「作業一覧」のselectorがブランドと一覧の2リンクに一致し、クリック前に検証側が拒否した。製品で移動不能と実証したものではない。合格した4経路を再試行せず、[別のr3](independent-r3-safe-report.json)で画面移動だけを補完した。実一覧リンクから別のrep2を開き、旧rep9の200応答の解放を試みても、rep2のrun ID・failed・last_seq 80・全成果物tupleと表示先は保たれた。旧要求は実際に取消済みで、CDPのInvalidInterceptionIdとERR_ABORTEDを照合した。旧成功本文がReactへ到達した上で捨てられたという実行証明ではなく、そのguardは静的レビューの範囲に残す。[範囲付き結果](independent-acceptance-summary.json)は原r2を成功へ書き換えていない。

r2/r3とも原資料・業務記録・配布UI・対象コードが前後不変、追加model/job 0。所有Chromeはそれぞれ42件/11件を追跡して残留0、APIのtask/lock/port/lifespan終了を確認した。[さらに別担当の最終批評](independent-final-critique.json)でも実画像8枚・原manifest・54ソースを照合し、今回の範囲で新しい阻害事項はなかった。保留中の実主体切替は今回未実施。

同じ製品差分で[既存の実認証・受付7段階](local-service-regression.json)も一度実行し、[独立照合](auth-regression-review.json)を保存した。58所有Chromeプロセスの残留0、browser用APIの終了を確認した。検証対象8fileのhashと現buildを関連付けた確認であり、このsuite単体には製品の配信bytesの直接採取がない。過去v18から取り込んだmodel記録20件を新しい推論や全DBが空であることと混同しない。新しい読取保留試験とは別の回帰確認である。

## 実通信の回帰確認をCIへ追加する

`check_workroom_recovery.py` / `workroom-load-recovery.mjs` を専用のCI段階へ追加した。[最終ローカルr2](local-recovery-r2.json)は5ケースを75.83秒で確認した。初回の期限前再読込に加え、詳細・会話・イベントを個別に保留した期限、既表示内容があるpollの一組を保留した回復を扱う。12秒時点の通常待機、初回3条件で15.323〜15.329秒・既表示pollで15.449秒のエラー観測、明示操作からの新しい実GET、旧要求の取消、原bytesと入力の保持を確認した。45項目の通過はこの通信境界の結果で、品質点ではない。

初回の[原r1](local-recovery-r1-failed.json)は5番目の準備で停止した。実goalは11,406文字で、検証脚本が置いた4,000文字の下書き候補上限に合わなかった。製品の入力制限の失敗ではない。既に通過した4ケースと未実施8項目を保持し、固定規則で実goalの先頭1,024 Unicode code pointsを抜粋する脚本へ修正した。全文と抜粋のSHA・長さを記録し、架空文を作らず、送信もしていない。原r1と別rootのr2を混ぜない。

[実在する不適合なdocs/qualityを参照した負例](local-recovery-invalid-source.json)は開始前にexit 1となり、API/Chrome未開始、未観測値はnullのまま保存した。最終r2はコード56file・原資料14file・配布UI6file不変、業務不変、追加model/job 0、所有Chrome21件の残留0とAPIのtask/lock/port/lifespan終了、runtime error 0を確認した。CIへは固定項目のsafe JSONだけを収録し、秘密・DB・HTTP原文・生エラー・ログは送らない。

## 継続する未達

[前版6ada2a3のCI](prior-ci-6ada2a3/summary.json)と[service](prior-ci-6ada2a3/service-review.json)・[OIDC](prior-ci-6ada2a3/oidc-review.json)・[site](prior-ci-6ada2a3/site-review.json)の独立照合は過去結果として保存する。今回の変更の証明ではない。サイトのaxeには矢印とCSS拡大条件のtextareaのcontrast incompleteが残り、全面WCAG適合とはしない。

v62は全件が終了した保存記録で、現在のlive進行やモデル待ちの証拠ではない。task行を再構成しない取込の制約、成果物本文だけの通信停止、読み上げ、Safari/iPhone、仮想キーボード、初見の第三者、実公開環境の受入は残る。

完成例なし10回の固定983系列は準備済み・推論未開始のまま。[今回の資源確認](resource-gate.json)でもメモリ推定6,097,715,200 bytesが固定8,741,958,113 bytesに、空きディスク9.46 GiBが10 GiB超に届かなかった。基準を変えず、無関係な資源を停止せず、モデル/VMを起動していない。物理的な実行不能や業務品質不合格を実証したものではない。公開先、登録、費用/運用責任、業務品質などの未達を引き続き解消する。
