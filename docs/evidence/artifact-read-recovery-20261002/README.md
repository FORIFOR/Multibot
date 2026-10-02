# 成果物本文の取得をやり直せるようにする

2026-10-02 JST。成果物の取得が止まった場合に画面から再取得できないことと、未取得の確認記録を「記録なし」と表示することを、実通信と画面で確認した。本文と確認記録の読取に期限と明示的な再取得を加える。これは通信回復の改善であり、原文の業務品質・人間受入・一般公開・受賞水準の認定ではない。

## 修正前の実観察

基準は `a32b136749b1e17100f3228c753a31b0810b4df7`。実v62の保存済みrun・event・artifactを別SQLiteへ原bytesで取り込み、実AppService、実発行キー、Chromeを使った。元資料にないtaskを不完全に再構成していない。全runは終了済みで、現に生成中の業務を再現する試験ではない。

[日本語390幅](before-ja390-held-at35s.png)では成果物の実200応答をCDPのResponse段階で保留すると、35,004ms後も本文が読込中で、再取得ボタンはなかった。自然な会話タブ操作から実seq24の同一ファイル参照を選び直しても本文GETは1件のまま。作業の詳細・会話・イベントは各8件の200応答があり、この別経路の保留だった。

事前の実応答にはchecks 3件とreviews 1件がある。それでも[取得中に展開した確認記録](before-ja390-pending-record.png)は「記録はありません」と表示し、[英語768幅の単体通信遮断](before-en768-failed-record.png)では概要・展開記録の両方が記録なしと断定した。英語の既存Refreshは遮断中に再失敗し、解除後には原本文へ復帰できた。

[観察の原記録](before-observation.json)、[ブラウザー記録](before-browser.json)、[独立批評](before-independent-critique.json)を保持する。観察の完遂PASSと製品のP2二件を区別する。警告の検査selectorが存在しなかったため、そのfalseを製品警告欠落とは数えない。[補足](before-scope-addendum.json)は原記録を変更せず、実画像に未完了警告があることを確認している。

## 読取と記録の不在を区別する

成果物GETにAbortSignalを渡し、取得開始ごとに15秒の期限を設けた。明示的な再取得は旧要求を取り消して新要求を送る。画面・版の変更時も旧要求とtimerを終了し、旧要求は新しい表示状態を上書きしない。受信・表示するデータはrun、artifact、revision、SHAの一致を確認する。

「本文と確認を再読み込み」を本文後の確認概要に常設した。取得中・失敗・成功で同じボタンを保ち、本文前に操作を増やさない。取得中と失敗時は、概要と展開記録の双方で未取得／取得不能を示す。成功した応答が空のときだけ、記録がないと表示する。この分岐は静的レビューで確認し、原資料に実在しない空の確認記録を作って実測済みとはしていない。

同じ版の本文とローカル編集コピーは再取得中も保持する。ただし確認の取得中・失敗中は、新たな採用をボタンと処理側で拒否する。既に選んだ版と採用ZIPは取り消さない。読取操作から採用POSTや生成を実行しない。元本文を編集して合格に変える機能ではない。

[契約レビュー](contract-review.json)と[実装の静的レビュー](static-review.json)を別に保存した。共有APIの認証主体・generation・更新操作の同一キーと30秒期限、AuthGate、採用競合の比較、コピー編集、親の3 GETとSSEは維持する。

## 実画面を見て、もう一度修正する

最初の修正[r1は全体FAIL](r1-safe-report.json)として保持する。本文再取得と誤った「記録なし」は解消したが、初回復帰で本文が伸び、同じDOMに残ったretryのfocusが画面の下へ外れた。[日本語390](r1-ja390-manual-restored-focus-outside.png)ではy1141.56–1185.56pxでviewport高844pxの外だった。日本語320と英語768も同じ欠点があった。既表示本文の実200%とviewerは別条件で通過しており、この成功で初回の失敗を相殺しない。[独立批評](r1-independent-review.json)と[実装担当の目視](root-r1-visual-review.json)を保存した。

r2では本文取得の成功後、まだretry自身にfocusがあり、実矩形がviewportや重なるstickyメニューの外にある場合だけ位置を補正する。別の要素へfocusを移す処理は加えない。[r2の静的差分レビュー](r2-static-review.json)を保存する。

[r2の独立実操作](r2-safe-report.json)では次の条件を確認した。速度保証や品質得点ではなく、同一実資料を使った単発の読取境界の観測である。

| 条件 | 実観測 |
| --- | --- |
| JA390、初回の実200保留→Tab/Enter | 保留開始368ms後に原本文へ復帰。retryの同一DOMと可視focusを維持 |
| JA320、初回の実200を保留したまま | 15,036msで取得不能、15,217msで再取得成功。失敗中は採用不可 |
| EN768、成果物GETだけを実遮断 | 取得不能を表示し、解除後の再取得で466ms時点に原本文へ復帰 |
| EN実Chrome200%、既表示の同版を再取得 | 15,013msで期限、15,439msで復帰。原本文・編集コピー・未送信文を保持 |
| EN390、実viewer | 再取得できるが、採用操作は表示しない |
| JA390、保留中に別の操作へShift+Tab | 実応答解放後もfocusとscroll225→225を維持 |

[320幅](r2-ja320-deadline-recovered-focus.png)、[英語768幅](r2-en768-transport-recovered-focus.png)、[実200%](r2-en-native200-loaded-recovered-focus.png)を実装担当が目視し、折り返し・操作の順・focus輪郭・記録と注意書きを確認した。[目視記録](root-r2-visual-review.json)と[さらに別担当の証拠・画像批評](browser-after-r2-evidence-critique.json)は分ける。独立操作の編集コピーは実artifact先頭640 JS unit、未送信文は実資料先頭900 unitで、入力した抜粋のSHAを照合した。全文を編集入力して保持したという証明ではない。実200%はouter1440/inner720/DPR2/CSS zoom 1で、サイトのCSS拡大stressとは違う。

最後の別操作へ移った対照では、その別操作自体は本文増高でy609→1141pxへ移り画面外になった。今回の補正は復帰後retryの範囲であり、全focus要素を可視に保ったとはしない。320幅で期限後にTabした時のfocus輪郭が画面端に接する余白の制約も残す。これは残る操作上の制約で、受賞水準に達したという判定はしない。

同じ最終製品で[既存の3 GET回復5ケース](parent-read-regression.json)も一度実行し、PASSを保存した。[別担当の照合](parent-read-regression-review.json)でcode56/source14/dist6が現製品と一致し、所有Chrome21件残留0を確認した。新しい成果物取得の証拠と、作業詳細・会話・イベント取得の回帰結果を分ける。追加model/jobは0。元資料・業務・配布UIは不変で、所有APIの終了を確認した。

## 実通信の回帰をCIへ加える

`check_artifact_recovery.py` / `artifact-load-recovery.mjs` を、実資料・実HTTP・実SQLite・実Chromeで動く専用段階として追加する。初回保留中の手動操作、期限、Network.setBlockedURLsによる成果物URLだけの遮断、既表示同版の本文と編集コピーの保持を扱う。CIへは固定項目のsafe JSONだけを収録し、鍵・DB・HTTP本文・生エラー・画像を送らない。

[原ローカルr1](local-ci-r1-failed.json)は全体FAILのまま保持する。3ケース30項目と遮断ケースの準備2項目は通過したが、実Playwrightの通信エラー文字列 `inspector` が検査側の想定と一致しなかった。旧検査はCDPの失敗詳細をその想定で絞っていたため、元Networkイベントの値は保存されていない。別担当の遮断はFetch.failRequestで、同じ方式・原値の証明に混ぜない。

また、検査側のPromise.raceで待機期限が来てもfalse判定のループが残り、子プロセスは親の170秒期限で終了した。所有19processの追跡・1 signal・残留0、APIのtask/port/lifespan終了を確認した。製品の15秒期限の失敗とは区別する。新脚本ではループ自体に期限を設け、正確なartifact URL・phase・実CDP blockedReasonを照合する。元の未保存情報を推測で補わない。[原r1の診断補足](ci-r1-failure-addendum.json)と当時の[ブラウザー脚本](ci-r1-browser-source.mjs)・[wrapper](ci-r1-runner-source.py)も保持する。

[別rootの最終r2](local-ci-r2.json)は一度の実行を35.26秒で終了し、4ケース40項目を通過した。初回手動はGETから81msでEnter、新たな実200は操作後29〜33ms、二つの期限観測は保留後14.989/15.025秒だった。取得開始と応答保留の時点差を含むため、秒数をSLAに換算しない。遮断は実CDPのexact artifact / blocked_initial / blockedReason inspectorの1件を保存して照合し、元r1の不明なイベントへ後付けしない。[修正した検査の静的レビュー](ci-r2-static-review.json)も別に保存する。

最終r2はcode56/source14/dist6と業務記録が前後不変、追加model/job0、所有20processの残留0・signal0、API/lifespan/port終了を確認した。CI用の編集コピーは原成果物先頭1,024 Unicode code pointsを使用し、独立実画面試験の640 JS unitとは別条件である。[事後の独立照合](ci-r2-independent-review.json)でもソース・HTTP・コピー・版・終了記録を照合した。実本文・確認行・版・focusの照合を、自由な文書生成の品質へ一般化しない。

[実在する不適合資料を指定した負例](local-ci-invalid-source.json)は開始前にexit1となった。空のDB schemaは作成されるが、API/Chromeは起動せず、未観測値はnull・40項目は未確認である。

## 検証の範囲

15秒はブラウザーのtimerによる取得期限で、背景停止も含むwall-clock SLAではない。Response段階の保留は本文ストリーム途中だけの停止の証明ではない。HTML iframeのraw要求、別タブ表示、差分、ZIPは別経路で、この成果物メタデータ・text・checks GETの変更では扱わない。

採用保存失敗時の従来のRefreshは親runの採用状態を再取得する操作ではなく、この変更で採用通信喪失を解決したとはしない。同一参照の再選択自体は従来どおりで、今回追加した明示操作で再取得する。連続したliveイベントによる再取得・複数版・本文保留中の主体切替・Safari・読み上げ・第三者の自力利用は別の未確認条件である。[abort境界の静的補足](abort-resolution-edge-addendum.json)も、再現していない条件を実欠陥と混同しない。

[前版a32bのCI](prior-ci-a32b136/summary.json)は過去の証拠として保持し、新変更の証明へ混ぜない。[今回の資源確認](resource-gate.json)ではメモリ推定5,881,364,480 bytesが8,741,958,113 bytesに、ディスク9.378 GiBが10 GiB超に届かなかった。固定983系列は準備済み・推論0を保持し、閾値変更、無関係サービス停止、モデル/VM起動を行っていない。独自開始基準の未達であり、物理的な推論不能や業務品質の失敗を実証したものではない。

[本体checkoutの照合](main-checkout-final-verification.json)では1,338件の元内容・status・head不変を確認した。初稿は元からmissingの3tracked pathを除外して誤ってFAILにしたため、その[原誤判定](main-checkout-verification.json)を残し、元kindも含む比較へ訂正した。本体を復元・改変して一致させたものではない。

[全検証サービス終了後の資源観測](resource-final-gate.json)は2026-10-02 03:08 UTCで、メモリ推定5,494,112,256 bytes・disk9,912,070,144 bytesと、二つの開始基準を引き続き満たさなかった。[独立最終照合](resource-final-independent-review.json)では5locks解放、固定3checkout・実runtime/metadata・元資料・mainの保全、両準備系列の生成0を確認。初稿でv62の正規化fingerprintへ生JSONと事後設定を誤比較した記録は私有rootにFAILのまま残し、元の構築方式に沿う別の照合で訂正した。新しい推論・VM・サービスを起動して通したものではない。
