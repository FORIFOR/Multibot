# 並行ログイン検証の前提と原CI失敗の保全

初回接続エラーからの明示的な再読込を実装した `330c18c874fb34c13b5f75f404244f6d57ca63b4` のCI `36947671100` は失敗した。新しい初回復帰の実Chrome確認は通過したが、既存の並行ログイン確認が `response_loss_submit_both_forms` / `Error` で止まった。原safe診断にDOM/タイマーの時系列や生エラーはなく、具体原因は未確定。後続のpeer/結果読取/siteは実行されていない。同headのOIDC `36947671134` は成功した。原結果を別の成功で上書きしない。

実行mergeは `22fe57835280ec39bf32723168784b45c81d15f9`。PR headと区別し、source/runner/bundleを照合した結果を `ci-service-review.json` へ保存した。`ci-original/` は公開済みsafe artifactの原bytes、`ci-site-not-run.json` はsite未実行/該当artifactなしの記録である。`ci-original-summary.json` はこの失敗headの集約であり、後続変更の証明ではない。

## 観察と変更

旧scriptは2タブに同じ200ms後の目標時刻を渡すだけで、両方の実submit開始を同期していなかった。先にsubmitしたタブの通知で相手のformが消える可能性は静的に存在する。ただし追加した受動的診断の実実行1回と、片側の実Chrome CPUを6倍に減速した別条件1回はどちらも成功し、元CIの仮説は再現していない。`r1-*` / `r2-*` と `observation-summary.json` はこの2観察を区別する。受動的診断自体にも処理時間があり、原実行と同一条件とはしない。

最終scriptは実DOMDebuggerのsubmit停止点を使う。両方の本物のsubmit処理が5秒以内に停止点へ到達し、まだログイン要求が出ていないことを確認してから解除する。各タブの実HTTP200が1件ずつ届くことを必須とし、既存の3確認（通常並行、実2件目応答喪失、共有Cookieと旧主体の不一致による書込拒否）を残した。偽submitやAPI応答・通知の捏造/差替えは行わない。後段の共有Cookie確認では実発行キーによる実ログインで主体を切り替える。実際の `requestSubmit()` とReact処理を使い、実行スケジュールを制御した競合確認である。自然な利用タイミングの再現率、原CI原因の確定、製品の認証競合全体の解決を意味しない。

私有prototypeは1回だけ実行した。両roundのsubmit停止到達差は195ms/185msで、それぞれ両タブの実200、既存3項目、業務DB0、所有API/Chrome終了を確認した。prototypeは私有配置に合わせたimport/sourceパスで実行しており、そのSHAは `prototype-summary.json` にある。後段のadmin再ログインが最終roundの診断一覧へ1件混ざる問題を独立レビューで発見したため、原結果を保全したまま `observation-scope-addendum.json` に記録した。この制約は先の受動観察2回にも適用する。held応答とassertの実行は後段ログイン前なので、各タブ1件の実200確認とは区別できる。

repoへの採用時は相対パスへ戻し、round終了時に記録区間を閉じた。元3項目を弱めず、停止点解除・Debugger/Fetch終了・ブラウザー終了の失敗は非0終了へ伝播する。cleanup helper内の各CDP解除は3秒、ブラウザーcloseは15秒、wrapperの当該子プロセスは180秒上限。通常経路の `Fetch.disable` には個別期限がなく、wrapperの上限に依存する。catch内の私有失敗画像取得には個別期限がなく、固着した場合は外側の所有プロセス終了に依存する。生の画像・エラー・鍵・DBは公開allowlistへ含めない。

## 最終版の実HTTP・SQLite・Chrome確認

最終script SHA `89872cd7dca1ab9f6977b7df3e22cda5c1342966006ce4e99f0e3ae831e8159e` を別担当が静的確認後、exclusiveな新保存先でwrapper全7段階を1回実行した。約39.7秒でPASS。両roundとも各タブの実submit停止、ログインPOST、held HTTP200が1件ずつで、後段再ログインの診断混入はない。`final-suite-summary.json` と原 `final-suite-report.json` / `final-diagnostic.json` / `final-result.json` を保存する。

事後の独立37照合でcode229・原資料4・配布UI6ファイルが前後一致した。所有Chromeは5組57process、signal0/残留0。browser用APIはtask終了・lock解放・port閉鎖・lifespan失敗なし。先行admission/responses用2APIのportもこのローカル試行では事後に閉鎖を確認したが、wrapperの常設cleanup scopeは引き続きbrowser用APIのみである。response DBのmodelイベント20件は取り込んだ過去v18記録と全field一致、追加推論0。ブラウザーsuiteのrun2件は既存の同一依頼再送確認によるstart:false受付であり、suite全体を業務DB0とは記さない。

`node --check` とfrontend lintは終了0。既存警告（当該scriptのfinally内throwを含む）は残っている。今回の確認script改修による製品UI/bundleの変更はない。新GitHub CIの結果はPR27と次の記録を確認し、このローカル成功をGitHub成功の代替にしない。

## 判定の限界

ここで変更したのは確認scriptと診断であり、初回復帰の製品UIや配布bundleは変更していない。元のCI失敗は原因未確定のまま残す。成功件数を一般業務品質、受賞水準、公開TLS/SSO/MFA/回復、第三者自力利用、人間受入へ数えない。PR27はdraft、本番公開/L3は未達のまま。
