# 所有サービスの終了確認

ローカルでは最終 API ライフサイクル検証 **19/19 PASS**、既存サービス回帰 **全6段階 PASS（27.77秒）**。実発行鍵・実 AppService・実 SQLite・実 OS プロセスを使った。コンテナの実停止は次の GitHub OIDC 実行待ちであり、今回ローカルで VM・コンテナ・モデルは起動していない。業務品質・人間受入の合格ではない。

基準 HEAD は `a3258b52a3d8f6f2da0c14186b3491a2b5996f71`。変更後コードは [manifest.json](manifest.json) の3ファイル SHA で識別する。原 a325 の GitHub artifact、固定 checkout、原業務記録は変更していない。

## 変更した終了契約

- OIDC API は起動元 checkout と新規 DB を使い、実 PID・group・出生情報・確定した command SHA（Linux は start ticks も）を記録する。一致する所有プロセスのみを停止し、process 不在・group 空・port 閉鎖を確認する。macOS Python launcher の起動中の表現変更は、元の Popen と出生情報が一致する間に限り、ready 後の identity を確定して扱う。
- コンテナは当該起動の専用 label と immutable ID を照合して削除する。起動応答不明かつ ID 未観測なら、空の一覧だけで終了成功にしない。この経路の実測は GitHub 待ち。
- OIDC は終了確認後に safe cleanup report を always upload する。停止失敗を `|| true` で吸収しない。未開始は `NOT_STARTED`、未観測値は `null`。独立したリソースの後始末は一つの失敗で打ち切らない。
- `check_public_service.py` の観測対象は **browser_verification_api**。task 終了・service lock 解放・port 閉鎖に加え、実 Uvicorn の `shutdown_failed` / `error_occurred` を判定し、詳細ログは private file へ送る。内部の admission / responses API に同じ終了測定があるとは主張しない。

## 原失敗と修正後の証拠

|系列|原結果|観測と扱い|
|---|---|---|
|[r1](r1-start-import-failure.json)|FAIL|専用 venv に import path がなく API 起動失敗。残留なし。起動元 checkout/backend を明示した。|
|[r2](r2-identity-refusal.json)|FAIL|同 PID/group/birth のまま Python launcher の command 表現が変化し、安全側に停止拒否。原 owner / FAIL を保存した。出生情報と当該 root/port の完全な API 引数を照合して所有 API のみ TERM、[別記録](r2-owned-api-recovery.json)で process/group/port 終了を確認。|
|[r3](r3-initial-pass.json)|PASS、19条件|独立レビュー前の版。最終コードの根拠にはしない。|
|[r4](r4-lifespan-negative.json)|FAIL / exit 1|不適合な実 repo 文書を profile に渡し、実 startup/lifespan エラーを観測。23検査条件は満たしたが Uvicorn の SystemExit が asyncio 終了へ伝わり、系列全体の FAIL を維持。task/lock/port は終了、生 traceback は私有 API log のみ。|
|[r5](r5-api-lifecycle.json)|PASS、19条件|最終コード。正常終了、未開始、別 root にコピーした実所有記録の拒否、不適合資料での subprocess 起動失敗、in-process 呼出側失敗後の終了を確認。[実読取4 DB](r5-database-counts.json)の runs/jobs/model events は0（不適合 profile の起動失敗前に作成された DB を含む）。|
|[全6段階](six-stage.json)|PASS|追加した API 終了判定 PASS、lifespan flags は false。Chrome 4組計45 process の残留0・signal0。私有 console/API log の traceback・database locked・shutdown failed は0。|

不適合 profile は実 [integration.md](../../quality/integration.md) の無改変コピーであり、[照合結果](incompatible-source.json)に SHA を記録した。r4 は **startup** エラーで、実 `shutdown.failed` 自体への故障注入ではない。

## 独立レビューと限界

独立読取レビューで、Uvicorn は lifespan の終了失敗を記録しても serve task 自体は例外を返さない場合があると判明した。task/lock/port だけでは誤って PASS にできるため、lifespan flags を追加した。また、その生 traceback が CI console に出る問題を私有 FileHandler で閉じた。[同モデル AI による独立読取レビュー](independent-review.json)で最終3コード SHA と r5 の実記録を照合し、新たな blocker はないとの評価を受けた。独立担当の27件は読取検査であり、19件の実行を独立に追加実施したものではない。独立担当が照合した DB は3件で、実装担当の追加読取4件とは範囲を区別する。

- 実 Keycloak コンテナの削除・port 閉鎖は次の GitHub 実行で確認する。静的監査を実停止成功として数えない。
- 全6段階の admission DB には cancelled の技術検証用 job 1件が残る。responses DB の model event 20件は読み込んだ原記録であり、新推論ではない。browser DB は model/job とも0。
- ここにある JSON は allowlist に選んだ原レポートの無改変コピーと、本文を含まない照合メタデータだけ。manifest は各ファイルの SHA・サイズ・原記録名を保持する。
- 私有ログ、鍵、access 設定、DB、所有台帳、実 command 本文は公開しない。mock・provider 置換・架空業務データは使っていない。公開サービスの本番可用性や業務品質を認定するものではない。
