# ログイン中の別タブ離脱からの復帰

2026-10-02 JST。ログイン中のタブが完了通知を送らず閉じられると、他タブが「接続を確認しています…」から戻らない不具合を実Chromeで再現した。peerごとに20秒の待機期限を追加し、期限後は資料・主体を消去したログイン画面へ戻す。Cookieから無言で利用者を復帰させない。

## 実測と保存した失敗

実アプリが発行したadmin/operator鍵、実HTTP、実SQLite、実資料 `docs/PRODUCTION_PLAN.md` の添付を使った。CDPで実際のログインHTTP 200応答を保留し、本文・status・認証結果を差し替えていない。モデル・模擬プロバイダーは使っていない。

| 記録 | 観測・制約 |
| --- | --- |
| original-r1 | close後21.6秒の接続中を再現。ただしreloadも停止するという試験側の期待が不成立となり全体FAILED。書き換えず保持 |
| original-r2 | close後21.5秒、実完了通知なしで接続中。reloadは実完了通知を受け78msでログイン画面へ戻った |
| fixed-r1 | close/reloadとも完了通知が届きPASS。期限による復帰の証拠には数えない |
| fixed-r2 | close時に送信元JavaScriptを停止してから閉じ、完了通知喪失を確実にした。20,049msで空ログイン画面へ復帰。reloadは実通知で復帰 |
| fixed-r3 | 同じ障害注入で20,099msの復帰。観測側ブラウザー時計も20,101ms進行し、観測側自体の停止ではないことを確認 |

fixed-r2/r3は、復帰後に実operator鍵で明示的に再ログインし、ログイン応答と `/api/auth/me` の主体・role一致、旧goal・貼付文・添付なしまで確認した。既存の並行ログイン3項目・主体分離7項目もPASS。全5環境の停止後SQLiteでrun/job/model.calledは0、所有Chrome残留0、専用listener終了を確認した。

製品の期限は20秒で、ログイン・ログアウトの15秒通信期限より長い。他peerの待機と自タブのログアウトは解除しない。同じpeerの新しい通知は古いtimerを取り消し、完了通知とunmountもtimerを解放する。ブラウザー自体が停止・抑制された時間に画面が描画される保証や、20秒のSLAではない。

試験の元の観測上限21.5秒はclick前起算で、製品timerの通知受信からの20秒とは起点が異なる。CIのスケジューリング余裕を確保するため最終scriptは30秒まで観測する。製品期限・15秒未満の期限解除拒否・完了通知なし・実測時刻・明示再ログインの条件は維持する。

## 最終版の独立確認

実装を編集しない別担当がfresh環境で実HTTP/SQLite/Chromeの全6段階を実行した。21.5秒観測版のindependent-r1は全6段階PASS・前後hash一致。その後、観測上限だけを30秒へ変更した最終script（SHA256 `4abe3473ff5401014cbe6d9cc95fa3baecd0b741aab8df055f9ac0a249b2be7d`）のindependent-r2も全6段階PASS。closeは完了通知なしで20,128ms後に復帰し、observer時計は20,131ms進行。reloadは実完了通知で78ms後に復帰した。双方とも明示operator再ログイン後の主体/role一致と空の依頼画面を確認した。

最終独立確認では前後10ソース/UIファイルhash不変、runnerの7検証ファイルhash一致。既存の実受付確認で作った2件のrunはpeer試験の前後で2件のまま、job/model.calledは0。4ブラウザー処理の所有Chrome残留0・専用listener閉鎖。private実鍵7値/秘密形式との照合は0件。build・配布UI一致・構文・Ruff・diff確認は通過、frontend lintには既存のauthVersion cleanup警告が残る。これらを人間受入や一般品質とは数えない。

## 証拠の範囲

原アプリは `85630f1` の認証コード/配布UI。修正後AuthGateのSHA256は `743b1bb57b5552a7ea7e15be18674db2fc0ee52fb7e2a0fb6e48a89f02678fe8`。`scope-manifest.json` と各reportに差分前後のhashがある。過去の試験scriptはhashのみで全文snapshotを保存していないため、過去各版を完全再実行できる記録とは主張しない。最終scriptはリポジトリに保存する。

`safe-evidence-review.json` は実鍵10値との照合・秘密形式検査を記録する。公開は安全な結果JSONと、目視で鍵が空と確認した画面だけ。鍵、DB、設定、原ログ、失敗時の生error/画像はprivate保存先に保持する。ここにコピーした証拠の生バイトhashは `sha256.json`。

この不具合は先のGitHub並行ログイン試験失敗の原因と同一だとは特定していない。公開TLS/実IdP登録/MFA、第三者の自力利用、一般業務品質、人間受入、L3の達成を意味しない。
