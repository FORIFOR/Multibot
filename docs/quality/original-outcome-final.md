# 元の導入ガイド条件の再検証

2026-09-20。短い紹介文の別試験を、元の導入ガイドの合格と置き換えない。
元の `frontend/scripts/product-quality-text-delivery.mjs` の依頼文、400〜700字、3見出し、根拠の節名、HTTP202/採用ZIP/応答喪失時の再送条件を維持する。初回の失敗記録は歴史として保持し、この最終コードでの新規依頼を判定する。

入力: 最新の `docs/quality/integration.md` を実UIで添付。出力: guide.md。
実行: 元の8796の実疎通済みprofileを隔離8801にコピー。loopback Qwen3.5 9B、480秒、30モデル呼出、出力上限1800トークン、max_replans0。外部検索/送信なし。既に導入済みの任意文書フローを選択し、別担当による内容照合を必須とする。他のモデル検証が完了してから開始する。

| 条件 | 方法・期待 | 証拠 | 判定 |
|---|---|---|---|
| 依頼から完了 | 新規UI依頼1回、再開なしで480秒/30呼出内にcompleted | run/events、設定snapshot | FAIL：4回とも480秒で中断 |
| 形式 | 実UTF-8全文400〜700文字、指定3見出し | 保存file/schema結果 | FAIL：最終試行775字、公開成果なし |
| 正確性 | 原資料の再送/採用/状態の意味を変えず、節を示す | 独立照合 | FAIL：最終試行775字、公開成果なし |
| 保存 | 採用→reload→ブラウザーZIP、公開bytes/hash一致 | ZIP/manifest/selection | BLOCKED：元課題の完了未達 |

証拠: `artifacts/product-quality/original-outcome-final/`。実行コマンド・exitは `artifacts/product-quality/commands.jsonl`。

実行ID: `run_1a0bae859e4490091e4`。原資料の添付内容/hashを実受領記録で確認。初稿638字/hash340b7237993a922a8ad63e23e9755574f4ab0be71467cc842bb97e08c9715b30。形式はPASSだが、再送条件の省略、根拠節名欠落、制作指示の転載があり、独立本文判定FAIL。途中の人間からの修正指示は入れず、確認担当の自力検出・修正を検証中。

再試行2: `run_1a0baf335de6bdcd0d0`。確認担当の文書書換え権限を実行層で制限し、依頼条件の網羅性を別の審査項目にした。生成稿1161/1089字は上限700字を満たせず、480.89秒でinterrupted。公開成果なし、確認担当は未開始。判定FAIL。証拠はattempt-2/、独立報告original-outcome-independent.md。

再試行3: `run_1a0bafc2841b158aa41`。Ollama通常呼出へのtemperature0強制を除去し、導入済モデルのsampling設定を尊重。疎通probeのみ0を維持。元の予算・モデル・依頼・文字数条件は変更していない。実行中。

再試行3終端: 480.92秒でinterrupted、作成担当未完了/確認担当queued。公開r1は699文字/1253bytes、SHA256 ab990a952a02e8e471ed0c706550956eea6f4ba6e253591e325180ba41c52f17。形式PASSだが、Idempotency-Key省略で拒否という誤説明、selected/selectionの混同、新キー許可条件欠落、指定見出しの変更があり内容FAIL。別評価PID38925と本試験PID42215のOllama11434接続を同時観測したため、単独の処理時間比較には使わない。内容違反を競合理由で免責しない。

再試行4: `run_1a0bb046e9f4e2240b8`。単一文書フローのworkspace_writeに依頼者のminLength/maxLengthと出力pathを明示する修正後。任意schemaを移植せず、Coreの全文検査は維持。前回の実受領資料をそのまま再添付し、goal/inputs完全一致をsame-inputs.jsonで確認。静的・実記録テストはPASS、生成効果は実行結果で別判定。

再試行4終端: 480.926秒でinterrupted、last_seq27、artifacts=[]。実測1150→992→775→775字で上限700字を満たさず、確認担当は未開始。ブラウザーの初回成果待ちも510秒でtimeout/exit1。tool schemaに制約を提示しても、モデルの遵守は保証されないことを実測した。文書完成はFAIL、確認担当の最終モデル審査/採用ZIPは到達できずBLOCKED。全PASS/完成とはしない。証拠attempt-4/、completion-original-request-4.log。
