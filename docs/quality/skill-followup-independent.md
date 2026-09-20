# 独立検証: Skill導入後の復旧操作

判定: **中断中の修正指示保存と再読込はPASS。生成品質A2はFAILを維持**。再開・新規モデル生成は行っていないため、実際に修正された成果物の品質は未検証。別AIセッションによる検証であり、人間の初見評価ではない。実装変更なし。

2026-09-19 JST、macOS 26.6.2 arm64、Chrome 153.0.8010.53、実HTTPサーバー127.0.0.1:8796、実SQLite、既存実モデルrun `run_1a0b8f5c9511106dcd2` を使用。commit `aad83ddf682606fc024b29b5855273472d345db8`＋既存未コミット変更。差分hashは `artifacts/product-quality/skill-followup-independent/pass-b-revision.json`。Pass Aではコード・操作ガイド未読、Pass Bで実装と契約を確認。依存物DL・モデルDL・アカウント準備を含む初期導入試験は対象外。

## 実操作と証拠

Pass Aはトップの履歴→中断依頼→guide.md→版と確認記録→採用版ZIP保存と進めた。版1が既に採用済みのため選択を維持。「未確認」と「採用済み」、依頼全体の未完了を区別できた。ZIP内manifestのselection=adopted / revision=1を読み、成果物SHA-256完全一致を確認。新規採用操作そのものは未検証。トップの過去依頼は1440×1000の初期画面下にありスクロールが必要だった。初見経路と各判定は `artifacts/product-quality/skill-followup-independent/pass-a-report.md`。

Pass Bはguide.mdの実際の1225字という超過と、409/410なら新しいキーが必要という誤りを指摘する修正要求を入力。integration.mdに従い、応答不明時は同一キー・本文を保持し状態照会、前の結果を解決して意図的に新しい操作を行うときのみ新しいキーを使うよう依頼した。Tabで「修正指示を保存」にフォーカスしEnterで保存。HTTP 202 / state=received、event seq=39。reload後「最後に保存した指示を見る」を開き、全文が入力と一致した。保存文面はJSON証拠に含む。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| F2-browser | 入力、Tab/Enter保存、reload、履歴展開、API前後比較 | 再開前に保存され実行を開始しない | UI/APIの指示本文一致。status/usage/plan/tasks/artifacts/artifact_selection完全不変。モデル呼出8→8。追加eventはinstruction.receivedのみ | PASS | pass-b-verification.json | 実ブラウザ・実サーバー |
| F2-handoff | 実装読解と実イベントのworker prompt組立テスト | 次のtask sessionに記録を渡す | build_task_messageがreceivedイベントを含む。実保存テストも一致 | PASS | pass-b-pytest.log, backend/agentteam/runtime/worker.py | 実SQLite・既存実run記録。モデルは未実行 |
| F3 | 実発行資格情報のAPI試験 | viewer禁止、完了/no-plan拒否 | viewer 403、completed/no-plan 409 | PASS | pass-b-pytest.log | ローカル隔離test db |
| F4-storage | queue / resume準備試験、差分読解 | 現在理由を消し履歴保持 | queue理由/終了時刻を除去、task準備理由を除去、元event同一 | PASS | pass-b-pytest.log | 実SQLite、既存実runを読込。実モデル再開は未実行 |
| F4-live | 実モデル再開 | UI・成果物まで一貫して回復 | 保存のみを測る今回の独立検証範囲として主担当が再開しないよう指定したため未実行（ユーザー権限不足・追加承認待ちではない） | BLOCKED | 本報告 | 実run中断状態を維持 |
| F5-visual | 1440/390スクリーンショットを実際に開く | 保存と実行を区別し狭幅で読める | 「修正指示を保存」、再開後の次作業に渡す説明、適用完了ではない注記あり。390px横幅超過なし | PASS | 05-correction-desktop.png, 06-correction-mobile.png | 1440×1000 / 390×844 |
| F5-build | npm run build | types/build成功 | tscとvite成功、exit 0 | PASS | pass-b-build.log | ローカルfrontend |
| F5-lint | npm run lint | lint実行結果を確認 | exit 0、13 warnings（React hooks等）。警告ゼロとは主張しない | PASS | pass-b-lint.log | ローカルfrontend |
| A2 | 既存成果物と依頼・integration.md照合 | 400〜700字、安全な再送説明 | 1225字・409/410で新規キーを促す誤りが残る | FAIL | Pass A保存ZIP内artifacts/guide.md | 未確認版1 |

証拠パスは特記なき限り `artifacts/product-quality/skill-followup-independent/` 配下。独立実行コマンドは `backend/.venv/bin/python -m pytest backend/tests/test_product_contract.py -q`（6 passed, exit 0）、frontendで `npm run build`（exit 0）、`npm run lint`（exit 0）。ログ全文を保存。テストはモック・ダミープロバイダーを用いず既存実run記録・実資料・実SQLiteを使用。主担当が報告した17件の全件再実行とは区別する。

## 判断の限界と残課題

画面は保存と実行を明確に分けており、保存機能について追加の必須修正は見つからなかった。長い保存指示はデスクトップ左列で縦に伸びるが全文を読め、390pxでも折り返される。入力欄から保存までのキーボード操作を確認したが、全画面の読み上げ、IME、200%拡大、reduced motion、人間の初見評価、競合比較は未検証。Web製品のためネイティブ検証はNOT_APPLICABLE。

保存は次の作業への指示で、既存の完了作業・計画の自動やり直しではない。今回の指示も「次に開始する確認作業で旧版の不合格を記録し、修正が必要と明示」と含めた。修正版の実生成・検証までは到達しておらず、品質FAILを解除できない。指示は実runに保存済みで、主担当は再開前にこの保存内容を考慮できる。新規実行・外部送信・モデル呼出は行わず、画面操作で唯一のPOSTはinstructionsだった。

再現コマンド: リポジトリ直下で `node artifacts/product-quality/skill-followup-independent/reproduce.cjs`。保存済み指示を読み直し、本文・状態不変・モデル呼出増分0を再検証してexit 0。実保存に用いた文面は同フォルダのcorrection.txt。スクリプトは既に同文が保存済みなら再送しない。未保存状態でUI保存を再現する場合のみ`--save`を指定し、新規依頼・再開は行わない。
