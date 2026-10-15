# 文書のファイル検査とコマンド隔離の境界

2026-10-02（JST）。公開サービスPR27の継続作業。基点は `81f2ab4fc85b5983df8b8ace958c15f054a1f7e8`。文書の確認担当は `sandbox_run` を使用できず、`run_check(kind=command)` も拒否する一方、受付は `run_check` という名前だけでDockerを要求していた。

## 先に固定した契約

- `workflow=document` かつ `role=reviewer` の実効権限だけをファイル検査に限定する。別の担当者やteam経路のコマンド権限を同じ扱いにしない。
- 作成は選択した担当者、再開は保存した設定、分岐は既存の保存設定/現在設定の選択とoverride適用後の設定に対して判定する。受付のために保存済み設定や過去の成果物を書き換えない。
- 実コマンド実行時の `require_container` を維持する。Dockerが必要な権限ではホスト実行へ切り替えず拒否する。
- 管理readinessの既定値はworkflow不明として従来どおり保守的に扱う。文書を明示したreadinessは、文書で許可される実効権限を確認する。
- 実v62資料・実SQLite・実HTTP・実Gatewayと固定check workerで確認する。モデル応答やDocker状態を模擬しない。受付と実行、形式と意味品質は別判定にする。

受付とGatewayの権限判定を共有し、作成/分岐では判定時の設定を深いコピーとして保存まで引き継ぐ。再開は保存済み設定を確認する。判定後の管理設定変更で別の権限が保存される経路を防ぐ。**本番化・業務品質・人間受入・受賞水準は未達のまま。**

## 固定系列と資源

旧 `4fc43b4` の完成例なし系列と監督は変更しない。この境界変更を使う場合は別のコード固定点・系列・監督へ分ける。元の開始前拒否や未開始受付は保持する。

2026-10-01 20:31 UTCの読取確認では、固定モデルは未ロードでdigestは一致、旧比較STOPを保持、既存の関連lockは解放され、対象workflowプロセスは0。回収可能メモリ推定は4,767,694,848 bytes、既存の独自運用閾値は8,741,958,113 bytesで不足していた。推論・Colimaを起動せず、無関係なアプリやモデルを停止していない。これは実機のモデル起動失敗や品質の失敗を実証したものではない。[資源確認](resource-check.json)を参照。

## 前反復のCI

基点 `81f2ab4` の[CI 36918856490](https://github.com/FORIFOR/Multibot/actions/runs/36918856490)と[OIDC 36918856522](https://github.com/FORIFOR/Multibot/actions/runs/36918856522)は成功し、実行merge commitは `fb2843db24c10620bb69a26837d3e58d9ac77cbd`。保持済みartifactと対応する検証ソースのhash照合は[前反復のCI記録](baseline-ci-summary.json)に残した。今回の境界修正の検証結果とは区別する。


## 実装と実測

[変更前](baseline-rejection.json)は実非Docker環境で、文書のreadinessと実受付が503になった。変更後の[最終実測](boundary-final.json)は、実v62の入力・設定・原生成物を使った30 HTTP応答と79条件を確認した。実行設定だけを限定した境界試験で、架空業務や生成応答を使っていない。測定対象は基点HEADに未コミット修正を加えたソースであり、対象13ファイルのSHA256を記録している。

- 既定team readinessは503、文書指定は200/not_required、不明workflowは422。文書受付は202で同一キー照合は同じ受付へ戻る。
- document reviewerに許可されたファイル検査だけはDocker不要。他のrole、team経路、有効な非選択コマンド担当では503。選択/無効化後の実効設定を使用する。
- 再開では元の保存済み設定、分岐では既存規則どおりの保存/現在設定とoverrideを使用する。無効な選択/overrideの拒否・予約の境界も記録する。
- 本物の実行枠を全て取得してから受付し、8ジョブを実APIで取り消してから枠を解放した。queued→cancelled、モデル増加0、未処理0を確認した。これは推論開始・完了を試したものではない。
- 実Gatewayから固定check workerを起動し、元成果物のJSON schemaとrevision/SHAを確認した。document reviewerのcommand/sandbox呼出は拒否。他担当者の実コマンド実行点は非Dockerで拒否され、ホストコマンドは実行されていない。

別担当が独立して、実際の設定置換とSQLite保存を[別の私有DBで確認](configuration-independent.json)した。作成/分岐の設定を解決後に元v62設定へ置き換えても、保存設定は先に判定したSHAを保持した。元run全フィールドと原資料を保全し、実Gatewayも確認、追加モデル/ジョブ0。HTTPの競合タイミングを誘発した試験ではない。

別担当による[同じrunnerの独立再実行](boundary-independent.json)も79条件・30 HTTPを通過した。[実DBの独立照合](independent-verification.json)では、元3 run全フィールド・232 event prefix・5成果物bytes・原資料14 hashを確認した。既存モデルeventは75→75、8受付jobは全cancelled、queued/leased 0、実行ソース13 hash不変、所有サービス停止/port閉鎖。追加検証の件数を足して品質点数としない。

既存の[文書報告replay](report-replay.json)は実記録2件で通過。[実サービス回帰](service-regression.json)も実HTTP/SQLite/Chromeの6段階を通過、所有Chrome残留0。ただしこの実サービス試験後に予算上限の同時設定取得を追加したため、最終ソース全体の根拠は新境界試験と次のCIで区別する。

## 失敗と制約を保持

[初回](runner-failure-r1.json)は検証脚本のPath型誤り、[2回目](runner-failure-r2.json)は無効overrideに対する保守的503の期待値誤りで失敗した。製品の合格として数えない。[3回目](boundary-prior-r3.json)と最終回を別記録で保持している。[実在する不適合資料を指定した負例](invalid-source.json)は開始前にexit 1、HTTP 0、未到達のsource不変/モデル差分はnull。生のエラー/traceback/鍵/DBは私有領域に残し、公開はallowlistのsafe-reportに限定する。

新しい監督候補は固定したrunnerが読んだ実workflowと共通権限関数を使う。[監督差分の独立静的レビュー](supervisor-static-review.json)と[helper追加後のレビュー](supervisor-helper-review.json)を分けて保存した。メモリ/ディスク/STOP/同時実行lock/前系列終了/モデル同一性/所有資源cleanupの基準は変更しない。監督候補の存在や静的レビューを推論成功としない。

CIに同じ実HTTP/SQLite/Gateway検証を追加し、失敗時もsafe-reportだけを公開する。旧モック試験や必須チェック迂回は使わない。初見第三者・公開環境/TLS・実IdP/MFA/回復・可用性・運用責任・業務品質の受入は残る。今回の件数を品質採点や受賞認定へ換算しない。
