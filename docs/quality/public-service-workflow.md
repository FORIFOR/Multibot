# 完成例を渡さない実資料ガイド10回検証

`backend/scripts/public_service_workflow.py` は実 `integration.md` から `guide.md` を作る既存課題を、実SQLite・loopback HTTP・実発行operator鍵で10回逐次実行する評価用runnerです。未実施の業務品質を合格にせず、`semantic_review=pending` / `business_quality_accepted=false` を常に残します。公開ホスティング、OIDC、実ブラウザー、人間受入、他業務への一般化はこのrunnerの検証対象外です。

## 固定する条件

- cleanなコミット、原資料全文、依頼文、納品schema、実効prompt/tool/設定、Ollamaモデルdigest/versionを保存・照合します。実Pythonのversion・実行ファイル・環境prefix・installed distributionの名前/version一覧もfingerprintへ保存し、起動時と各回に比較します。同じlock/commitでも実依存が違えば別系列が必要です。各回は独立した新規依頼で、途中の人手修正・再開を行いません。内部の修正は上限2回です。
- 出力は日本語 `guide.md`、指定3見出し、400〜700 Unicode文字（空白・改行・Markdown込み）。入力は実資料と依頼だけです。schemaはstring型と文字数だけで、完成文、`const`、過去成果物、`x-repair-summary-examples` は渡しません。
- 元導入ガイド比較の480秒／30モデル呼出／1800出力token、1 worker、replan 0を使用します。Ollamaは既存の `127.0.0.1:11434/v1` のみ、fallbackなしです。過去の実成功probeの記録を再利用しますが、その記録が現在の能力を再証明したとは扱いません。probe APIは呼びません。
- document経路の最終実行報告は、成果物・レビュー対象版・実行状態の記録だけから生成します。v62で確認された、レビュー後の追加LLM要約が原資料にない主張を加える経路を除きました。依頼した文書の生成とモデルレビューは継続します。この変更も新固定系列の条件であり、旧系列との同一条件比較や業務品質改善の実証とは扱いません。
- Web検索ツール・sandbox shellは提供しません。builderにはcommandを実行できる `run_check` も提供しません。reviewerの `run_check` はdocument workflowの既存gatewayでcommandを拒否します。現行secure admissionはreviewerの `run_check` にもDocker条件を課すため、本実行には既存Docker隔離の準備が必要です。
- 受付試験は `start:false` で実runとreceiptを作成します。モデル呼出・成果物生成・実行待ちjobがないことを確認し、10回の生成試行には数えません。operatorの日次受付枠には計上されます。

## 準備と安全な受付試験

Python >=3.12と既存backend依存を使用し、リポジトリルートから実行します。以下の変数は実在する私有領域を指してください。`SERIES` は未作成の新規ディレクトリにします。prepareはOllamaのversion/tagsをGETしますが、モデル推論やprobeは実行しません。

```sh
python backend/scripts/public_service_workflow.py prepare --root "$SERIES" --profile "$REAL_PROBED_PROFILE" --prior-series "$V62_SERIES"
python backend/scripts/public_service_workflow.py preflight --root "$SERIES"
```

未コミットコードの実受付検証に限りprepareへ `--validation-only` を付けられます。そのrootからのモデル実行は恒久的に禁止され、後で本実行に転用できません。コード固定後は別のfresh rootを準備します。鍵はroot内の `security/admin.key` / `operator.key` に0600で保存し、出力にはその参照だけを残します。rootと生の管理者記録は私有資料として扱います。

## v62終了後の明示実行

```sh
python backend/scripts/public_service_workflow.py run --root "$SERIES" --allow-model-execution
```

runはv62の固定fingerprint、`completed_mechanical_trials` / 全10件のresult、`workflow.lock` 解放を確認してから新しい実サービスを起動します。実行中はv62のロックを読み取り専用で共有取得し、そのrunnerの再起動を防ぎます。未完了v62・異なるモデル・変更されたコード/設定では拒否します。起動先portを他プロセスが使っていた場合も拒否し、他サービスは停止しません。このガードは他の独立Ollama利用者までは排除しないため、単独負荷や性能比較を保証しません。

送信前にrep・キーを永続化します。再度runコマンドを明示実行した場合、既知runは状態照会、送信結果不明でも永続receiptがある場合だけ同じキー・同じ本文で再照合します。サービス再起動時に未実行queuedの元受付が初めて実行されることはあります。中断済みの推論は自動再開せず、その状態を記録します。receiptがなければ手動照合待ちで止まり、別キーを作りません。runが終端状態になってもworkerのlease解放が遅れる場合があるため、実queueの空きを最大60秒待ってから次の受付へ進みます。非202、未知状態、タイムアウト、`STOP` ファイルでも停止し、失敗記録を保持します。STOPはサービス起動前と次のrep開始前に確認するため、進行中推論の即時取消ではありません。

## 証拠と独立審査

`fingerprint.json` / `attempts.json`、各sessionのHTTP応答bytes・status、operator/adminそれぞれの全ページイベント、全公開revisionのbytes/hash、最新版ZIP、model reviewを保存します。再開時にも過去sessionは上書きしません。SQLiteとrun workspaceもrootに残るため、公開前の作業記録はそこから追跡できます。未知応答ではサービスを停止するため、実際の中断状態は再照会が必要な場合があります。

各resultはruntime完遂、保存bytesの形式検査、model review件数、独立意味審査待ちを分離します。ZIPは最新版の保存経路確認であり、採用操作や人間の承認は行いません。モデルreviewの原記録は `model-reviews.json` に保存しますが、件数やpassを業務合格へ変換しません。

別担当は固定入力と10件すべての最終公開bytesを照合し、202＝受付、通常ZIPと `selection=adopted` の違い、未選択409、応答喪失時の同一キー・本文保持と状態確認、前の結果を解決した後の意図的な新操作だけ新キー、根拠節名、3見出しを確認します。「409なら無条件に新キー」「採用＝品質合格」「外部作用もexactly-once」「資料にない省略時の拒否」は不合格です。形式・完遂・意味を別判定し、欠落や過剰主張には原文と成果物箇所を添えます。同モデルの別担当を含むAI審査は人間受入ではありません。完成例ありのv61/v62や短い紹介文の成功で、この課題の失敗を置き換えません。

全10件終了後には別工程として、実operatorで未選択時の409を確認し、保存したい対象revisionを明示して採用し、`selection=adopted` のZIPとそのrevisionの公開bytes/SHA-256を照合してください。成果物が存在しないrunは到達不能として残します。生成開始後のrunnerコードを変更せず、外部の補助操作と別証拠で実施できます。これは保存経路の操作検証です。AIが採用を操作しても、人間受入や業務品質合格として記録しません。

## 全10件終了後の補助検証（実HTTPは未実行）

`backend/scripts/verify_public_service_exports.py` はこの別工程専用です。**新系列をprepareする前にこの補助scriptもコミットして固定**し、10件の生成と同じPython環境で使用します。既存runnerや原 `attempts.json` / `status.json` / result / 保存済みHTTP・ZIPは書き換えません。`POSTFLIGHT_PREPARE` と `POSTFLIGHT_VERIFY` は新旧系列・checkoutの外にある、それぞれ未作成の私有ディレクトリを指します。

```sh
python backend/scripts/verify_public_service_exports.py prepare --root "$SERIES" --session-root "$POSTFLIGHT_PREPARE"
python backend/scripts/verify_public_service_exports.py verify --root "$SERIES" --session-root "$POSTFLIGHT_VERIFY"
```

`prepare` は開始条件を検査するだけで、HTTPサービス・モデル・Docker/Colimaを起動しません。`verify` は同じ条件を再検査してから、固定originのloopback APIだけを起動します。新系列の `completed_trials` / 全10result、旧系列の `completed_mechanical_trials` / 全10result、変更のないcode/runtime/input fingerprint、元operatorの私有鍵、実DBの終端状態・全receipt・全artifact bytes・元イベントを照合します。新旧supervisor共通の親 `.production-llm.lock` を排他取得し、旧 `workflow.lock` を共有、新 `workflow.lock` を排他取得して終了まで保持します。新旧系列は同じbenchmark親ディレクトリに置き、既存lockを利用します。旧supervisorのcleanupを含め、いずれかがlockを保持中なら拒否します。このlockは協調しない別のOllama利用者を制御するものではありません。

全DBでqueued/leased jobまたはqueued/running/planning runがあれば、実サービスの起動前に拒否します。プロセスlockを取得した実AppServiceの初期化直前にも読み取り検査を行い、検査から起動までに状態が変わった場合の復旧実行を防ぎます。受付台帳の期限切れ削除も不変比較の対象なので、起動から5分以内に期限を迎える行があれば拒否します。長時間経過した系列では台帳を手動変更して通さず、別の限定検証を検討してください。各操作後とサービス終了後にrun/task/message/receipt/受付台帳/job/artifact/config/access、採用以外の全イベント、modelイベント数、元記録のhashが不変であることを確認します。監査記録・認証管理情報と明示した採用イベントの追加は不変条件の対象外です。

各回の永続receiptに対し元Idempotency-Keyと正規化済み元本文のhashが一致することを先に確認し、`request.json` の同じ本文と元キーを実 `POST /api/runs` へ送ります。202・元run_id・元operator向けreceipt応答との一致、および受付件数・job・modelイベント・run状態が増減しないことを確認します。これは**記録済み受付に対する新たな同キー再照合**です。元の生成受付で実際に応答喪失を発生させた試験ではなく、新しいキー、変更した本文、resume、再推論は使用しません。

その後、未採用ZIPの409を確認し、元記録の `guide.md` の特定最新revisionだけを `expected_selected_revision=0` で採用します。採用ZIPのmanifest全体、revision、全entryの集合（重複・余分・欠落を拒否）、全entryのbytes/SHA-256を照合します。本文は元の公開revision、final reportは元のlatest ZIP、eventsは元operatorイベント列に今回の採用イベント1件を加えた実HTTP出力を基準にします。manifestはその選択から構成した期待値と照合します。`guide.md` が公開されていない回は `unreachable_no_published_guide` のまま残し、別成果物で置き換えません。

実採用はDBに選択イベントを追記します。既に採用済みの回があれば、未選択409の前提を復元せず起動前に拒否します。途中失敗や応答不明でも自動再送・採用の取消・元記録の修復を行いません。新しい私有sessionの `report.json`、`original-records.sha256.json`、HTTP応答bytesと `execution.private.log` を読み、既に行われた操作を先に確認してください。既存session-rootも上書きしません。consoleには定形statusだけを出し、本文・キー・raw例外を出しません。session全体には私有資料が含まれるため公開しません。

採用操作はAIが実operator権限で行う保存経路の検証です。既存APIイベントの `actor_kind=human` は操作主体の人間性を証明せず、この補助reportでは `adoption_actor` を明示して `human_acceptance=not_performed` / `business_quality_accepted=false` を維持します。`status=completed` は全補助操作の記録完了であり、到達不能の回や未審査の意味品質を合格にしません。`additional_model_calls=0` は成功時に全modelイベントとDB不変を確認した範囲の値です。上記の実HTTP検証は次の10件が終わるまで未実施です。

2026-10-02には既存の実 `public-guide-runner-preflight-20261002-r5`（validation-only）を対象に、fresh私有sessionで `prepare` の早期拒否だけを実行しました。固定コードとの差異で拒否され、exit 1・定形console・空stderr・未起動・元系列の全ファイルhash不変を確認しました。この確認は後段の全10件・lock・receipt・ZIP検証を実行した証拠ではありません。新規サービス・モデル呼出は0です。
