# チーム通信の確認と修正

確認時、ユーザーrunのchat APIは空配列。send_message/read_messages、message.sent/read、質問による相手の起動は存在したが、通信なしでfinish_task/auto_finishできた。受信フィルターは自分の所有タスクだけで、他担当タスクIDの引継ぎが対象から外れていた。

修正: 同runの自分宛てメッセージを全件受信。タスク担当は下流の別担当へhandoff/finding/decisionを送るまでfinish不可。Reviewerは依存元の作成者へ返す。下流なしでは依存元へ報告。新しいpublishで送信済み状態を消去、submit_reviewでも該当作成者向け状態を消去。セッション単位の送信であり、再実行は再度報告。通常終了/auto_finish両方で同じ条件を使用。replyはanswer送信が必要。空本文拒否。メッセージ内容の真偽を機械判定したとは言わない。

制約: 計画段階のMasterはtaskセッションではなく、必須送信の対象外。単独実行、別担当との依存関係がない仕事、出番のないBotは会話を強制しない。通信能力のない設定やメッセージ予算不足では完了を許可しない。入力チェック/成果物チェックは緩めていない。会話を増やすための偽発言は作らない。

PASS: macOS、Python backend/.venv、実SQLiteと保存済み実記録を使用した関連13テスト。引継ぎ未送信を拒否、auto_finishも拒否、実保存済みresult本文の配送、別task担当のInboxへの到達とread記録、送信後完了、別attemptの再送要件を確認。テスト用provider/モックなし、モデル呼出なし。

コマンド: `python3 artifacts/product-quality/run-command.py peer-communication-tests backend/.venv/bin/python -m pytest backend/tests/test_peer_communication.py backend/tests/test_text_delivery.py backend/tests/test_product_contract.py -q`。exit0、13 passed。ログ artifacts/product-quality/peer-communication-tests.log。

BLOCKED: 実モデルが新要件に従う完全フローの再検証と8796への適用。既存ユーザーrunがrunning/liveのため再起動せず、過去の会話を補完せず、実行中の設定も変更していない。ローカルソースの修正と稼働サーバーへの適用を区別する。

独立レビューで指摘された通信権限/残メッセージ枠の不足を、schedulerのAgentRunner開始前に検出するよう修正。communication_configurationでblockedとしMasterの再試行も抑止。実設定からsend_messageを外したテストでモデル呼出件数が増えないことを検証。実履歴の既存23callsを0と誤期待した初回テストは失敗ログを保持し、前後差0（新規呼出なし）を検査するよう修正。最終 `peer-communication-verified-tests.log` exit0、13 passed。独立報告はこの最終修正前の指摘を記録している。
