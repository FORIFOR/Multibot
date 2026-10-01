# 実サービスのCI移行と、完成例を与えない試験の準備

2026-10-02 JST。一般公開・本番受入・業務品質は未達のまま。実HTTP/SQLite/Chromeの回帰確認を自動CIへ移し、次の実LLM試験を始める前の安全な受付確認を行った。今回は新たなモデル推論を行っていない。

## CIの実測

CI実装は `fea6fa39cd7a254795fe9ad5d3ba42aec5dc918b`。ローカル統合は `local-report.json`、GitHub初回実行は [36889372543](https://github.com/FORIFOR/Multibot/actions/runs/36889372543) と `github-initial-*.json` に保持する。GitHubはPRのmerge commit `825c254f8a796d8400450121aefccd0ebab1c7e9` を実行した。

- 実HTTP/SQLite受付8項目、実資料の保存記録を使う応答境界9項目、実Chrome主体分離7項目、応答喪失と再読込後の再送、並行ログイン3項目を通過。利用者別の鍵を実発行し、専用DBとloopback APIを使用した。
- GitHubのbackend静的確認、frontend build/lint・配布UI一致、public-serviceはsuccess。**初回CI全体はfailure**。依存監査がPyJWT 2.14.0の既知脆弱性を検出した。フロント依存監査はその時点では未実行。
- 生のPlaywright失敗には入力値が含まれる可能性があるため、uploadは安全な結果JSONとキー消去後の画面の明示リストに限定した。鍵・DB・設定・生ログ・失敗画像は含めない。
- Nodeだけの強制終了では独立したChromeプロセス群が残り得るため、観測した親子関係とPID開始時刻を再確認して終了する。実Chromeを停止状態に置いた5秒timeout試験で残留0を確認した（`browser-timeout-cleanup.json`）。通常の3ブラウザー試験でも残留0。無関係なサービスは停止していない。

修正後 `1b932e9da8bb26e77fabd693022562981ba80fcc` の [GitHub実行36890627114](https://github.com/FORIFOR/Multibot/actions/runs/36890627114) は4ジョブすべてsuccess。実行対象のPR merge commitは `8e39fa177ad4828f0c511c4f00b61a9869d3545b`。`github-fixed-*.json` に実サービスPASSと監査原記録（runtime46依存、frontend production4依存、ともに既知脆弱性0件）を保持する。

旧模擬試験は履歴を保持して手動workflowへ移した。旧pytest、模擬UI、Docker/seatbelt、暗号化、実IdPの回帰範囲を新CIで網羅したとは扱わない。必須チェックを変更・迂回していない。範囲と限界は [CI方針](../../CI.md) を参照。

## 依存監査の修正

[PyJWT公式advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v) に従い、配布条件を `>=2.15,<3`、lockを2.15.0と公式配布hashへ更新した。旧実行環境を変更せず、専用venvへhash付きで導入し、依存整合性を確認した。修正後のローカル監査は46依存で既知脆弱性0件。同venvの実HTTP/SQLite/Chromeも通過した（`dependency-fix.json`、`pyjwt215-local-report.json`）。これは監査時点の既知情報であり、未発見の脆弱性がないという保証ではない。

公式に記録された問題は特定の署名検証前payload解析での未処理例外である。このアプリで認証回避やプロセス停止が実証されたとは主張しない。2.15.0のJWKS取得/キャッシュ変更について、以下の限定的な実IdP回帰を行った。アクセスキー試験をSSOの代替とは扱わない。専用 `public-oidc.yml` を追加したが、初回 [36892758365](https://github.com/FORIFOR/Multibot/actions/runs/36892758365) は検証用キーのアカウント名に予約接頭辞を使ったため、IdP/API起動前の準備で失敗した（`oidc-initial-failure.json`）。一般の技術アカウント名へ修正し、実キー発行とprivate保存・非GitHub環境の拒否を確認した（`oidc-account-verification.json`）。この準備確認はSSO成功を意味しない。 再実行 [36893451047](https://github.com/FORIFOR/Multibot/actions/runs/36893451047) は実Keycloak/PKCEのトークン取得後、初回APIが401で失敗した（`oidc-first-token-failure.json`）。[Keycloak公式変更](https://github.com/keycloak/keycloak/blob/main/docs/documentation/upgrading/topics/changes/changes-25_0_0.adoc) に照らし、`profile` だけだったclient scopeへ `sub` を提供する `basic` を追加した。元のトークンは公開・保持していないため、元401の原因をsub欠落と断定しない。次の実行ではclaimの存在と期待値との一致だけを保存し、JWTやclaim値を公開しない。稼働中v62のcheckout・依存・モデルは変更していない。

修正後 `bbe75b1` の [実行36894250724](https://github.com/FORIFOR/Multibot/actions/runs/36894250724) は13項目PASS（実行merge commit `71795593b7296712dc52d265a727f5ffc7dda234`）。実Keycloak・PKCEの発行トークンで、初回JWKS取得1回、既知鍵3回検証で追加取得0、実署名鍵の切替で追加取得1回を観測した。切替後API完了は初回API開始から1.881秒で、60秒TTL失効による再取得と区別できる。実IdP停止中はcache内200、実61秒後は503で拒否し、復旧後200。実トークンの30秒失効、ID token/未所属者の拒否、operatorのadmin権限拒否、logout失効も確認した。実資料のstart:false受付/同一キー再送は1件、SQLite job/model eventは0。キー・JWT・コード・個人情報を公開しない。`oidc-fixed-report.json` と `oidc-fixed-provenance.json` を参照。

引継ぎ修正を含む `8257cd1` の [CI 36894570667](https://github.com/FORIFOR/Multibot/actions/runs/36894570667) も4ジョブsuccess、[OIDC 36894570643](https://github.com/FORIFOR/Multibot/actions/runs/36894570643) も13項目PASS（merge commit `1b8539f775b00792608128623be786d9729ab59f`）。後者の原記録は `oidc-handoff-head-*.json` に別保存し、先の成功・失敗を上書きしない。

この検証はloopbackの一時KeycloakとAPIの署名検証経路である。OAuth2 Proxy、本番TLS、MFA、自己登録・アカウント回復、公開環境での運用、第三者自力利用の受入は含まない。

## 次の業務品質試験の準備

`backend/scripts/public_service_workflow.py` と [再現手順](../../quality/public-service-workflow.md) を追加した。入力は実 `docs/quality/integration.md` 全文で、完成回答・過去成果物・固定回答のconstは渡さない。原資料に残っていた「再読込でキーを失う」という旧説明を、現行実装と実ブラウザー証拠に合わせて訂正した。目標はguide.md、3見出し、400〜700字、同条件10回。元の480秒・30呼出・1800出力tokenを維持する。

実operatorによる `start:false` を同一キーで2回送信し、run・receipt・受付台帳は各1件、実行job・model.called・成果物は0件だった。未完了の実v62を参照する起動ガードが新サービス/モデル開始前に拒否した。`guide-preflight-database.json` と `guide-preflight-manifest.json` はvalidation-only r4の記録。その後、cleanな `1b932e9` と専用PyJWT2.15.0環境を使うvalidation-only r5でも同じ受付/ガードと件数を確認した（`guide-preflight-pyjwt215.json`）。10回の生成、非空/採用ZIP、実行中のlease遅延、意味品質を検証した記録ではない。

独立担当の読み取りレビューで、終端状態後のqueue解放待ち、最新版ZIP一覧の完全照合、資料の再読込説明を補強した。形式・完遂・モデルレビュー・独立意味審査・人間受入は別判定を保持する。v62終了後に全結果を保存して意味照合し、資源を確認してから、新しいcleanな固定コード/実Python依存/モデル/資料/設定で本試験を開始する。事後の採用ZIP操作も人間受入とは記録しない。

採用ZIPと同一キーの記録済み受付の照合用に `verify_public_service_exports.py` を準備した。既存validation-only r5へのprepareはコード固定不一致でサービス開始前に拒否し、元記録が不変だった（`guide-postflight-early-refusal.json`）。全10件終了後の実HTTP採用・ZIP照合は未実施。この拒否結果で後段の起動条件や保存経路を合格としない。

## 保持場所

公開JSONの生バイトのhashは `sha256.json`。鍵・SQLite・生ログを含む完全記録は `~/.cache/agentteam-bench/` の `public-service-ci-20261002-r2`、`public-service-ci-gh-36889372543`、`public-service-cleanup-20261002-r1`、`public-service-dependency-audit-20261002-r1`、`public-service-pyjwt215-integration-20261002-r1`、`public-guide-runner-preflight-20261002-r4` に保持する。以前の失敗/r1〜r3も削除・上書きしていない。
