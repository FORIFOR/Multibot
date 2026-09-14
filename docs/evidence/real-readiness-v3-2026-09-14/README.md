# 実資料 readiness 系列 v3 — 2026-09-14

この系列は、Claudeやクラウドモデルを使わず、固定したローカル Ollama モデル `agentteam-qwen35-9b-16k`（digest `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866`、Ollama `0.33.3`）で、リポジトリ内の実資料 `PRODUCTION_PLAN.md` と運用検証記録だけを入力にした。架空の業務データや合成レコードは追加していない。

実行1〜3を同じ固定checkout（`68af523ca97566815169b25b167e25518edf2850`）と同じ入力ハッシュで実施した。実行3の途中で、旧系列のReviewerが不正なJSON Schemaを手書きし、さらに日本語文字の存在だけで語崩れを見逃していたため、STOPを記録して系列を停止した。停止は成功扱いではなく、実行3のDBレコード・イベント・成果物を保存している。

## 結果

| 実行 | 実行状態 | 公開された最新版 | 旧ランタイム判定 | 現行契約の再監査 |
| --- | --- | --- | --- | --- |
| 1 | completed | `readiness.json` r1, SHA-256 `398bc994756ebbec357da0c910c9d56d85986131deecc64f126d73c9027dbb44` | Schema pass / Reviewer pass | **fail** — `アイデムpotent`、`リカスケル`などの語崩れ |
| 2 | completed | `readiness.json` r2, SHA-256 `3297dd3cac126e219e59a4218af1cad8f18bf612b4d43db6365c6bda603d52db` | Schema pass / Reviewer pass | **fail** — `アバター`、`パーラン`、`イデム`などの語崩れ |
| 3 | interrupted | `readiness.json` r1, SHA-256 `4a49f10cc01c02d56b31e54b3e345da8bb906fd9e296777a326316756df7673a` | Reviewer作業中に停止 | **fail** — `アバター`、`イデム`、`アドバザリ`などの語崩れ |

現行ブランチでは、実際に観測した誤変換をSchemaの禁止語として追加し、Executionには`idempotent`/「冪等」、Dataには`age`を要求した。`remaining`が原文英語を日本語の前後に隠してコピーすることも拒否する。証跡収集側も同じ契約Schemaを再実行するため、旧ランタイムの機械的な合格をそのまま採用しない。

ReviewerがSchemaを再生成する必要はない。公開成果物を`run_check(kind=json_schema, artifact_id=..., revision=...)`で指定すると、保存済みの依頼者契約Schemaをそのまま使う。モデルが不正Schemaを明示的に渡した場合は`blocked`であり、合格根拠にならない。

## 証跡ファイル

- `fingerprint.json` — commit、入力、設定、Schema、モデルdigestの固定値
- `attempts.json` — 旧ランタイムが保存した各実行の状態
- `runs/01-*`、`runs/02-*` — 完了2実行の`run.json`、全イベント、全artifact revision
- `runs/03-*` — STOP時点の実行、Reviewerの作業、未完了状態を含む保存記録
- `goal.txt`、`delivery-requirements.json`、`probe.json` — 実行契約とローカルモデルprobe

この系列はL3達成の証明ではない。品質評価に必要な実資料の反復で、旧Reviewerの見落としとローカルモデルの日本語品質問題を再現・固定した結果である。次の系列は、現行mainの依頼者Schema・自動終了検査・Reviewerの直接契約検査を使う。
