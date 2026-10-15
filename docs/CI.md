# 実資料・実サービスによる継続確認

2026-10-02に自動CIを切り替えた。ユーザーのモック・ダミーデータ原則禁止に従い、通常のpush/PRで模擬API・fake-provider・架空業務資料を使う試験を起動しない。CIの成功は一般公開・業務品質・L3の受入を意味しない。

## 自動実行する範囲

`.github/workflows/ci.yml` はmainへのpushとPRで次を実行する。

- 固定依存関係の脆弱性監査（既存ジョブを維持）。
- Pythonの静的確認、フロントエンドbuild/lint、配布済みUIとビルドの一致。
- 保存した実v62の1回目/6回目を別SQLiteへ再構成し、文書経路の最終報告で追加モデル呼出・追加解釈がなく、元の状態と成果物が変わらないことの回帰確認。完全な過去runtime再現や新たな業務品質評価ではない。
- `backend/scripts/check_public_service.py` による実HTTP・SQLiteの受付上限/再送/応答権限境界、実Chromeでのログイン・別タブ・下書き破棄・通信切断・並行ログイン。API 2段階とChrome 5段階の計7段階。
- `backend/scripts/check_database_concurrency.py` による実資料・実APIの並行読取と監査保存。共有接続の読取cursorと別接続の利用枠transactionが重なる競合を、実SQLiteと実HTTPで確認する。負荷容量や可用性の受入ではない。
- `backend/scripts/check_document_sandbox.py` による文書ファイル検査の受付とコマンド隔離の確認。実資料・実HTTP/SQLite・実Gatewayを使い、推論は実行枠を保持して待機させる。コマンド権限が残る設定では拒否する。公開artifactはallowlistの `safe-report.json` だけとし、私有ログ・鍵・DBは含めない。
- `backend/scripts/check_result_reading.py` と実Chromeによる、保存した実v62の完了/失敗/中断の成果物画面。operator/viewerの320/390幅で、結果優先・本文見出し・nativeチーム開閉・定期更新/会話往復・未完了警告・戻り先・横overflowを確認する。小画面の常設ナビゲーション、メニューの開閉、Escape後のfocus、外側クリック後に隠れた操作へfocusを残さないことも実画面で確認する。元資料と業務状態不変、追加モデル/キュー0、所有サービス/ブラウザー終了を照合し、`safe-report.json` のみ公開する。採用/ZIPや一般業務品質の受入をこの読取り回帰へ含めない。

入力はこのリポジトリの資料と実資料からの保存済みv18/v61/v62記録。実際に鍵を発行し、loopbackでAPIを起動する。受付/応答/ブラウザーでDBを分離する。既存の受付/応答試験の新規要求は `start:false`、キュー直接検証はサービス停止中に行い再起動前に取り消す。文書の隔離境界試験は実行枠を全て取得した状態で `start:true` を受付し、queuedを実APIでcancelledにしてから枠を解放する。LLMを起動せず、応答を代替しない。保存された過去のprobeは受付の前提記録としてのみ用い、CI上のモデル疎通を確認したとは扱わない。

`auth-initial-recovery.mjs` は初回のJA390 `/api/auth/status` とEN768 `/api/auth/me` をChrome CDPで実際に遮断する。接続エラー時はログイン欄や作業画面を見せず、明示的な再読込操作を出すこと、遮断中の再読込は再び失敗状態になること、遮断解除後のTab/Enterによる再読込で空のログイン画面へ戻ることを実APIで確認する。その後、実発行operatorキーでログインし主体を照合する。API応答の差替えは行わない。業務DB件数と原資料/実装SHAの前後一致、明示ログイン以外のwriteなしを確認し、固定項目の `browser/initial-recovery.json` だけを公開する。5秒の自動復帰観察を超える可用性、SSO、認証済み利用中の接続失敗は対象外。子プロセスの上限は120秒で、既存の所有Chrome追跡・終了確認を使う。

初回Chrome起動前に失敗した場合は、開始時刻・単調時計での経過ms・15秒のPlaywright期限・外側wrapperの実remaining/期限発火をsafe結果へ記録する。既知のtimeout/target closed/実行file不在/特定sandbox拒否文は固定booleanだけとし、生例外・command line・pathは公開しない。すべてfalseなら原因は未分類のまま。起動成功は後続の認証検証成功と別であり、15秒の延長・自動再試行は行わない。元CIの原因がこの追加で遡って分かるわけではない。

`check_workroom_recovery.py` と `workroom-load-recovery.mjs` は実v62のrun/events/成果物を別SQLiteへ正確に取り込み、実発行operator/viewerキーとChromeを使う。detail/chat/eventsの実HTTP200をCDPのResponse段階で保留し、3種それぞれの初回読込期限、期限前の手動再読込、表示済み下書きがある定期更新中の再読込の計5条件を確認する。期限試験は保留12秒時点の状態維持を必須とし、製品の15秒期限に対して観測上限22秒を置く。初回手動操作は最初のGET要求から2秒以内にTab/Enterし、旧応答を解除する前に新3GETの実200を3秒以内に確認する。この余裕はCIの操作観測用で、性能保証ではない。旧応答の解除前後に原成果物のSHA、実APIのrun ID/status/last_seq、URL、表示と下書きの維持を照合する。取消済み応答が解放できない場合は同じnetwork IDの実取消イベントと既知のCDPエラーの両方を必須とし、旧bytesがReactへ到達したとは主張しない。模擬応答・業務変更・追加モデル/キューは使わず、元資料/実装/配布UIの不変と所有API/Chrome終了を確認する。本文だけが途中で止まる通信や自然発生率の再現ではない。ブラウザー160秒・子170秒・wrapper既定210秒と個別終了期限を設定し、CI外側は5分。公開は固定項目の `safe-report.json` のみで、未到達は未確認、失敗は非0とし、鍵/HTTP原文/DB/ログを含めない。

`check_artifact_recovery.py` と `artifact-load-recovery.mjs` は、同じ実v62取込と実発行キーで、成果物の初回pending手動再読込・実200保留の期限・artifact URLだけの実通信遮断後の復帰・表示済み同一版の再取得の4条件を確認する。応答を差し替えず、CDPのResponse保留とNetwork.setBlockedURLsを使う。未取得/失敗を記録の不存在と表示せず、採用を無効にすること、自然なTab/Enterで新GETを発行すること、原本文SHAと実checks/reviewsの表示を確認する。本文復帰後、次の操作前にretry自身のfocusとviewport/sticky見出しに対する実可視性も測り、検証側はfocus/scrollを補正しない。表示済みケースでは原成果物先頭1024 Unicode code pointsだけを編集コピーへ未送信入力し、pending・期限後・再取得後の本文と下書き保持を照合する。元資料・業務記録・実装・配布UI不変と追加モデル/ジョブ0、明示ログイン以外のwrite0を必須とする。元資料に真の空確認記録はないため「成功した空配列」の表示は未実測として残す。製品15秒に対して12秒の待機継続と22秒以内のエラーを観測し、ブラウザー160秒・子170秒・wrapper210秒・CI外側5分を区別する。期限付きの所有API/Chrome終了と失敗/null保持を継承し、公開するのはallowlistの `safe-report.json` のみ。原文・HTTP応答・鍵・DB・ログは私有に保つ。

`auth-parallel-login.mjs` は、両タブの本物のsubmit処理へDOMDebuggerで停止点を置き、両方の到達と解除前のログイン送信0を確認してから再開する。同時刻のタイマーだけでは両submit開始を保証できなかったため、競合を確認する前提を明示した。各タブの実HTTP200を1件ずつ必須とし、応答順序の制御・2件目の実応答喪失・共有Cookie変更後の旧主体による書込拒否という既存3項目を維持する。応答bytesや通知を差し替えず、5秒以内に両submitが到達しなければ失敗する。自然な同時利用の再現率・負荷試験ではない。原CI `36947671100` のタイマー段階の失敗原因は未確定のまま保存する。診断は時刻、固定phase/error名、DOMの存在/件数、各タブの到達・解除結果だけを保持し、鍵・本文・生のDebuggerフレームを含めない。各roundが終わったら記録区間を閉じ、後段の再ログインを混ぜない。所有Debugger/Fetch解除とブラウザー終了の失敗も非0へ伝播する。子プロセス上限180秒と外側の所有プロセス終了確認を維持する。

秘密キー・セッション・DB・設定・非公開ログをartifactに含めず、個別に列挙した結果JSONと、キー入力欄消去後の画面だけを保持する。Playwrightの生エラーには入力値を含む可能性があるため、生エラー入りの失敗JSON/画像やログはuploadしない。失敗時は生エラーを含まない `report.json` と初回接続回帰の `initial-recovery.json` の状態・実施項目・未確認値を保持し、別の成功で上書きしない。生の失敗記録はローカル検証ではprivate rootへ保持するが、CIではrunner終了時に消える。

ローカル再現は依存関係、Chrome、Node、sqlite3、最新配布UIを用意して、次を実行する。指定する保存先は新規ディレクトリに限る。

```sh
backend/.venv/bin/python backend/scripts/check_public_service.py --root /tmp/multibot-public-service
```

## 保持した旧試験と未移管の範囲

旧ciは `legacy-fixtures.yml`、旧current-ui/workroomは各ファイルの `workflow_dispatch` に移した。履歴とスクリプトは削除せず、今回は手動実行もしない。手動経路があること自体を例外承認とは扱わない。例外が必要なら、根幹機能のブロッカー、最小の対象、使用箇所と撤去計画を具体化し、ユーザーの指示を優先する。

旧secure-container/OIDCも、`provision_secure_smoke.py` 経由で旧架空会議メモのrunとemailを読み込んでいたため自動移管しない。実モデル生成済みでも、元資料が架空であれば実資料受入へ数えない。実IdP自体の存在や既存証拠は取り消さず、対象の限界を保持する。

別の `public-oidc.yml` は専用の実Keycloak・API・Chromeを使い、実発行トークンの署名検証、JWKS取得/キャッシュ/鍵切替、IdP停止中の期限切れ、権限・トークン失効を確認する。登録するのは検証専用の実技術アカウントで、氏名・メールアドレス・架空業務資料を与えない。OAuth2 Proxyや公開TLSを経由する本番ブラウザーログインではなく、実code/PKCEフローで得たトークンをAPIへ渡す限定的な回帰確認である。ローカルのLLM試験へ影響しないよう、この確認スクリプトは使い捨てGitHub Actions環境のみで動作する。公開する証拠は `provenance.json`、秘密情報を含まない `report.json`、`cleanup-report.json`、起動前後に失敗した場合の `start-api-failure.json` / `start-container-failure.json` の明示的allowlistに限る。所有記録、鍵、DB、コマンド、生のエラーやログは公開しない。

旧pytest全件・fixture状態網羅・JA/ENの模擬UI・WebKit・Docker/seatbelt・age・実IdP/コンテナの全回帰範囲は新自動CIと同等ではない。必要な範囲を実資料・実サービスの検証へ移す作業が残る。特にSSOの登録/本人確認/回復、公開TLS、負荷/復元、実LLMの業務品質は別途受入が必要。

既存のbranch protection/required checksは変更しない。名前を変えた旧チェックが必須なら未達のまま扱い、空ジョブやskipで合格にしない。PR27初回の `[skip ci]` は旧模擬試験を起動しないための一時措置で、切替後は新CIを実行して結果を確認する。

## 検証サービスの終了確認

`cleanup_public_oidc.py` はAPIのPID・出生情報・実引数のhashと専用process group、Keycloakのimmutable container IDと実発行UUIDラベルを私有ファイルへ保存する。記録と一致する対象だけを停止し、API process/group/portと所有container残数/portを確認する。不一致や期限超過は失敗を返す。終了stepは常に実行し、失敗を `|| true` で吸収せず、続くalways-uploadでsafe結果を保持する。依存関係の導入前失敗でもstdlibだけで未起動を記録できる。使い捨てGitHub環境での資源終了確認であり、本番の停止・復旧受入ではない。

`check_public_service.py` の `api_cleanup.scope=browser_verification_api` は、このwrapperが所有するブラウザー検証用APIの終了・lifespan失敗・process lock解放・port閉鎖を確認する。先行するadmission/responses用の別APIや、他workflowのサービス終了まで一括で確認したとは扱わない。過去artifactに終了観測がなかった範囲は、後続の成功で遡及的に補完しない。
