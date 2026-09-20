# 元の導入ガイド依頼の独立評価

短い紹介文の成功を元の導入ガイドの達成に置き換えない。実資料integration.mdのみから400–700文字のguide.mdを作る元依頼を、実Ollama・元profileの1800 output tokens / 480秒 / 30 model calls / sandbox_run無しで評価する。人間ではなく独立AI補助評価であり、コード・成果物・期待値を変更しない。

対象run: `run_1a0bae859e4490091e4`、隔離サーバー8801。証拠は `artifacts/product-quality/original-outcome-independent/`。

## 版1

guide.md r1: 638 Unicode文字、1228bytes、SHA256 `340b7237993a922a8ad63e23e9755574f4ab0be71467cc842bb97e08c9715b30`。公開記録と取得bytesが一致。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| OR01 | 公開メタデータとraw、文字数を照合 | 400–700文字で同じ公開版 | 638文字、hash一致 | PASS | guide-r1.md, current.json | 実モデルr1 |
| OR02 | HTTP202説明を原資料Wire contractと比較 | 受付と完了を区別 | acceptedであり完了でないと明記 | PASS | guide-r1.md, source-integration.md | 独立読解 |
| OR03 | 採用ZIPをWire contractと比較 | selection=adopted、未選択409を保持 | 両方を明記 | PASS | 同上 | 独立読解 |
| OR04 | 応答喪失/新キーをRetry, failure and compatibilityと比較 | 同じキーと本文保持、状態確認、前結果を解決した意図的な新操作のみ新キー | 「Idempotency-Keyを使い再送」だけで条件を落とし、無条件再送に読める。新キー条件は「変更しないでください」という依頼文のコピーで説明になっていない | FAIL | 同上 | 独立読解 |
| OR05 | 省略挙動と参照節名を原依頼に照合 | 説明する省略挙動を変えず、根拠節名を示す | 省略挙動の説明をせず「変更しないでください」をコピー。原資料の根拠節名がない | FAIL | 同上 | 独立読解 |
| OR06 | 開発者向けガイドとして読む | 読者向けの実行可能な説明 | 「外部検索・送信を行わず」「文字数400–700字（実測値で検証）」など制作担当への指示が混入 | FAIL | guide-r1.md | 独立読解 |

現時点の版1は形式PASS・内容FAIL。reviewerの照合・修正と最終状態を以下に追記する。

## 最終結果

元profileの480秒上限に達し、runは`interrupted`、理由`wall-clock limit reached`（last_seq34）。作成タスクはreview_pending、確認タスクはinterrupted。正式審査は提出されず、guide.mdは版1のまま。初回成功を守るため、途中に人間や独立確認担当からモデルへの修正指示を追加していない。

保存済み契約をDraft202012Validatorで独立再検査しerrors=[]、638文字/1228bytesを再確認した。形式契約通過を内容充足や処理完遂へ読み替えない。独立に指摘した再送条件・新キー/省略条件・節名・制作指示転載の問題は未修正。

**元の導入ガイドの初回成功はFAIL、内容はFAIL、処理完遂と正式審査は未達**。短いintro.mdで得られた成功はこの結論を置き換えない。証拠: `current.json` / `events.json` / `chat.json` / `artifact-r1-detail.json` / `independent.json`。人間による評価は引き続き未実施。

## 元課題・2回目

run `run_1a0baf335de6bdcd0d0`、同じ8801/原依頼/400–700文字/1800出力/480秒/30calls条件。証拠は `artifacts/product-quality/original-outcome-independent-2/`。途中に独立担当からモデルへの指示は加えない。

静的確認では、document+reviewerだけのallowed_tools集合をspecsと実call双方に適用し、成果書込/公開/sandboxを除外。run_check(command)もDENIED。一般teamの工具集合は維持する。確認担当に下書き作成指示を送らず、公開版の検査と実測値参照に分離した。document_requestは原依頼の各内容・原資料節名を実本文で満たすことを求め、制作指示の転載を充足と扱わない。修正方針は静的PASSだが、実モデルの成功を代用しない。

中間観測: 下書き1161文字（check seq10/13）、次に1089文字（seq16）をCoreがmaxLength700によりfailとした。具体的な削減必要数と実測値が返され、成果未公開。文字数条件を緩和していない。最終状態と本文は以下に追記する。

### 2回目の最終結果

480秒上限で`interrupted`、理由`wall-clock limit reached`、last_seq26。公開artifactsは空、作成タスクinterrupted、確認タスクqueuedで未実行。下書きはseq10/13で1161文字、seq16/19/22で1089文字の形式fail。700文字以下へ収められず、guide.mdの公開・受領・正式審査には到達しなかった。

**元の依頼の納品と処理完遂はFAIL**。Coreが不適合な下書きを文字数検査でfailにしたことは確認できるが、それはユーザー目的の達成ではない。確認担当の工具分離・document_request追加は実行経路へ到達しなかったため、今回の実モデル試験では有効性を検証できない（BLOCKED）。原資料との意味照合は公開成果が存在しないため最終判定対象なし。失敗記録と初回の内容FAILは保持する。

最終証拠: `original-outcome-independent-2/current.json` / `events.json` / `chat.json`。アプリや成果物を本担当は変更していない。

## 元課題・3回目

run `run_1a0bafc2841b158aa41`。通常のOllama呼出をtemperature0強制からインストール済モデル既定値へ変更、probeのみ0を維持。モデル/依頼/400–700字/480秒/30calls/1800出力は維持。今回受領した`run.inputs.files`を正とし、終了後に本文を独立評価した。

環境注意: 実行中に別作業でHEADが69d484aへ進み、同じOllama11434へ別のproduction_workflow（PID38925）と検証サーバー（PID42215）の両方が接続していたとの親担当lsof観測。処理時間は競合ありであり、単独速度の評価に使わない。他プロセスに介入していない。本文違反を競合で免責しない。

下書き904→854→754→737→730→699文字へ修正し、形式条件を満たすguide.md r1を公開。699文字/1253bytes/SHA256 `ab990a952a02e8e471ed0c706550956eea6f4ba6e253591e325180ba41c52f17` を終了後GETで取得、公開記録と一致した。runはinterrupted/wall-clock limit reached、作成タスクinterrupted、確認タスクqueued。正式審査なし。

内容FAIL:

- 「Idempotency-Keyを省略すると同一要求が拒否される」は今回の入力資料にない挙動。省略についての原資料記述を別フィールドから転用してはならない。
- 「ZIPにselectedがない」と記すが実パラメータはselection=adopted。省略時が最新ファイルという説明も正確に保持していない。
- 「ブラウザリロードでセッション失われる」は、資料の「request keysはリロードを跨いで永続化しない」をセッション全体へ誤一般化している。下書き/添付のtab-scoped sessionStorage説明とも区別していない。
- 新キーを使える「前の結果を解決した後の意図的な新操作」の条件が欠ける。
- 指定見出し「最初の手順」を「初めての手順」に変更している。

202受理のみ/採用ZIPのURL/5xx・timeout時の状態確認など一部は合っているが、導入者の再送動作を変える誤説明があるため、形式PASSで全体を合格にしない。証拠: `original-outcome-independent-3/guide-r1.md` / `source-integration.md` / `current.json` / `events.json`。

実行中に追加されたworkspace_writeへのminLength/maxLength schemaヒントは、このrunの旧プロセスへ未ロード。生成効果は未検証。deepcopy/文書単一textのみ/保存後Core検査維持を静的確認した。全workspace_writeへ同じ境界が付くため補助ファイル利用時の範囲には注意が必要、と親担当へ返した。

## 元課題・4回目

run `run_1a0bb046e9f4e2240b8`。tool content schema min/maxとpath enumを実行前から反映したコード。入力資料はrun3が受領したbytesと完全一致、原依頼・モデル・予算・文字数を維持。証拠`original-outcome-independent-4/initial.json` / `source-integration.md`。最終結果を以下に追記する。

### 4回目の最終結果と総合判定

runはinterrupted、理由wall-clock limit reached、last_seq27。公開artifactsは空、作成担当interrupted、確認担当queued。下書きはcheck seq14=1150文字、seq17=992文字、seq20/23=775文字で、すべてmaxLength700違反。最終状態・全イベント・会話を8801から独立にGET取得して保存した。

実行前に文字数をtool schemaへ提示し、path enumで最終文書へ書込先を限定しても、この実モデル実行では上限内の文書公開へ到達しなかった。Core検査を回避・緩和せず、不適合をfailとして残した点は確認できる。確認担当は未開始のため、正式審査や意味条件の改善効果はこのrunからは判定できない。公開原文が存在しないため、最終本文の意味を合格とはしない。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| OR07 | 元課題4回目の終端run/全eventを独立GET | 400–700字の公開guideと正式審査を受領 | 480秒上限でinterrupted、artifacts=[]、775文字failが最終検査 | FAIL | original-outcome-independent-4/current.json, events.json | 実Ollama、競合あり |
| OR08 | 文書reviewer分離/document_requestの実効果を確認 | 原文照合し不備を返せる | reviewer queuedで未実行、効果判定不可 | BLOCKED | 同上 | 審査未到達 |
| OR09 | 単独性能/OS IME/実端末/人間評価 | 該当環境での実測 | 未実施。モデルの他ジョブ競合あり、人間の成功率を測定していない | BLOCKED | 本試験範囲 | 独立AI補助評価 |

**総合結論: 元の400–700文字導入ガイドの初回成功は未達。** 4回の失敗は保持する。短い紹介文で達成できた納品・保存操作、形式拒否機構、静的レビュー、関連テストの成功を、元の依頼達成に読み替えない。実データ・成果bytes・期待値は本担当が変更していない。
