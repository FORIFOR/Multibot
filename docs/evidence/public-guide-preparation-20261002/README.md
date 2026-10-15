# 新しい実資料ガイド系列の準備と起動前拒否

2026-10-02 JST。固定commit `4fc43b4472c67776d2df3bdfdd972f41db45fac1` のfresh checkoutで `public-guide-qwen35-fixed-20261002` をprepareし、実operator・SQLite・loopback APIによる `start:false` のpreflightを実施した。**新しい生成10回はまだ開始していない。**

## 確認された状態

独立した読み取り確認で、DBはrun 1件（`created` / real）、永続receipt 1件、同じoperatorに紐づく受付台帳1件だった。元preflightキーのscopeと、元依頼を `start:false` にした本文の正規化hashがreceiptと一致し、保存応答は202・同じrun_id・createdだった。tasks / messages / artifacts / execution_jobs / queued・leased / modelイベントはすべて0件。受付試験は日次受付枠には計上されるが、生成試行や成果件数には数えない。

系列は `prepared` / `model_execution_started=false`、`attempts.json=[]` のまま。固定checkoutはcleanで、code/runtime/input fingerprint、元profile、先行v62 fingerprintが一致した。原DBのWAL/SHMを含む参照ファイルのbytesは不変。DB照会には私有領域へ複製したDBとWALを用い、原DBに接続して変更していない。確認時に対象workflow/supervisorプロセスはなく、元loopback portは閉じていた。共通global lock、新旧workflow lock、サービスlockを排他・非待機で取得でき、確認後に解放した（[read-only-inspection.json](read-only-inspection.json)）。

## supervisorの1回目の拒否

私有supervisorのsession `20261001T172737Z-293a8fc37fe24111bae6d105bb1597e3` は、2026-10-01 17:27:38 UTC（10月2日02:27:38 JST）に資源条件で起動前拒否となった。実測した回収可能メモリ推定値は **6.217 GiB**、そのsupervisorで設定した運用上の開始閾値は **8.142 GiB** だった。メモリ圧力はnormal、空きdiskは10 GiB超で、同じdigestのモデルは常駐していなかった（[resource-policy-observation.json](resource-policy-observation.json)）。

この推定値はmacOSのfree・inactive・speculative pagesの合計である。未常駐時の閾値は `max(8 GiB, model file bytes + 2 GiB)` という今回の私有supervisorの運用方針であり、ベンダーの最低要件や実機の起動限界ではない。条件確認はColima準備とworkflow子プロセスの起動より前にあり、今回の試行ではchild・Colima・推論を開始していない。自動再試行もない（[supervisor-refusal.json](supervisor-refusal.json)、[supervisor-cleanup.json](supervisor-cleanup.json)）。

したがって、この記録は**運用閾値による開始拒否**であり、実際のメモリ確保失敗、モデル起動不能、生成失敗、出力品質の不合格を測定した結果ではない。新系列の生成・意味審査・採用ZIPの補助検証は未実施で、`business_quality_accepted=false` / 人間受入未実施を維持する。preflightの成功も業務品質の合格ではない。

## 公開する証拠

[fingerprint-summary.json](fingerprint-summary.json) は固定情報とhashだけを掲載する。access設定はhashのみで、設定本文・鍵の値は含めない。[source-sha256.json](source-sha256.json) に原記録の出典hash、[sha256.json](sha256.json) に公開ファイルのhashを保存した。

公開JSON/READMEは実operator/admin鍵2値とのバイト一致とJWT等のパターン検査で該当0を確認した（[publication-check.json](publication-check.json)）。私有ログ、DB/WAL/SHM、設定、鍵、supervisor scriptは掲載していない。読み取り確認ではサービス・モデル・supervisorを新たに起動していない。
