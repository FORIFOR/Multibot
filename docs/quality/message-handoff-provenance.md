# 関連タスクと送信元タスクの通信契約

`send_message.task_id` は話題となる関連タスクで、通信予算と受信フィルターの単位でもある。省略すると現在のタスクを使う。別の既存タスクを指定して配送できる契約は維持する。

`Message.source_task_id` と `message.sent.payload.source_task_id` は、Runtime が実行中の所有タスクセッションから記録する送信元。モデル入力には追加せず、モデルによる指定は拒否する。タスク所有者としての実行以外は `null`。イベント外枠の `task_id` と既存のチャット・タイムラインの `task_id` は関連タスクのまま。イベント JSON の新フィールドは省略・`null` とも許容する。

配送成功後、送信元タスクの `handoff` / `finding` / `decision` をそのセッションの送信済み宛先に数える。関連タスクが別でも同じ。必須宛先へ届いていなければ完了できず、レビュー提出は対象の作成担当への送信済み状態を消去する。レビュー提出前の送信で提出後の引き継ぎを代用できない。セッションを跨ぐ自動的な完了条件の復元・レビュー合格への変更はしない。

予算の上限・予約・会計は変更しない。成功配送は従来どおり関連タスクへ 1 件を計上し、送信元タスクへ重複計上しない。既存予算に拒否された配送は引き継ぎに数えない。`communication_budget_version=1` では関連タスクが現在のタスクと異なる場合の `own_session=false` と予約制約も維持する。今回の v62 / public guide の `document_plan` は同 version 未設定の経路であり、この回帰で version 1 の実行全体を再検証したとは扱わない。

既存 SQLite には nullable 列を追加する。旧 Message JSON はフィールド欠落を `None` として読み、保存済みイベント・メッセージに送信元を推測して補完しない。コンテキスト縮約は新しい送信元を使って関連タスクへの配送も残し、送信元のない旧記録では従来の関連タスクによる表示を維持する。この表示から必須引き継ぎを自動充足させない。

## 実記録からの回帰確認

`backend/scripts/check_message_handoff.py` は固定 v62 (`9eb798849cd8352ec645f6da2ed1e04d9729d63c`) の保全された `run.json` / `events.jsonl` / `artifacts.json` / 実成果物 bytes を入力にする。成功した rep 1・3・4 の task_id 省略と、合法配送後に必須引き継ぎ不足となった rep 2・5・6・7 の関連 task_id 明示を再利用する。既存の業務本文・引数・成果物を作り替えない。

```sh
PYTHONDONTWRITEBYTECODE=1 /path/to/venv/bin/python backend/scripts/check_message_handoff.py \
  --source-series /path/to/real-readiness-v62-qwen35-fixed-20261002 \
  --root /path/to/new-private-replay-evidence
```

実装リポジトリに元 commit の Git object と、上記の私有保全資料が必要。入力がなければ代用記録は作らない。公開 CI への原記録取り込みはこの変更に含まない。生の設定や会話を含むため、出力は新しい私有ディレクトリにのみ保存し、そのまま公開しない。

実 SQLite・EventStore・MessageBus・ToolGateway を使用する。タスク状態は元 checkpoint と開始イベントから復元し、元の最終 Run 記録と履歴 usage は保持する。通信数はその時点の実配送から復元する。各ケースの実操作・新規イベントは再生証拠として別 SQLite と `replay-events.jsonl` に保存する。元履歴・元成果物・元の成功/失敗判定は変更しない。

確認する境界は次のとおり。

- 元のレビュー・配送・finish 引数で引き継ぎが充足し、関連タスクだけへ 1 件を計上する。
- レビュー前の送信ではレビューを代用できず、レビュー提出後は新しい配送が必要。
- Master への配送だけでは必須の Builder 宛先が欠けたままになる。
- rep 2 の実際の予算上限到達時点を復元すると、同じ要求が拒否され、配送も引き継ぎも増えない。
- 実際の無効な宛先と、送信元フィールドを追加した不正なツール要求が拒否される。
- 元 commit の旧 SQLite schema と実 Message が新 schema に移行し、送信元は未確定のまま。新配送の送信元は DB 再接続後も残る。
- 旧・新イベントの JSON Schema、HTTP のイベント投影、Message JSON 往復、既存チャット・タイムライン投影とコンテキスト縮約を確認する。

`result.json` は元資料の SHA-256、コード SHA-256、旧 schema の commit / SHA、実行結果を保存し、終了前に入力 SHA を再確認する。プロバイダーを生成せず、新規モデルイベント・model call 加算がないことを検査する。サービス起動・LLM 呼び出し・モックはない。再生された元モデルのレビュー本文は業務品質の合格根拠にはせず、`business_quality_accepted=false` / `business_quality_review=not_performed` を保存する。修正後の実モデルによる新規一連実行、version 1 の実モデル動作、人間の受入は別工程。
