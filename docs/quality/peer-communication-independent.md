# 通信ゲートの独立コードレビュー

2026-09-20。対象: communication.py / context.py / worker.py / tools.py（backend/agentteam/runtime）、関連scheduler/mailbox/config。実装変更なし、モデル呼出なし。**新たな致命的問題は未発見。P2の早期検出不足1件**。

## 指摘

P2: 必須送信相手があるのにsend_messageを許可していない設定でもモデル処理に入る。communication_targetsはenabledな依存相手を返し、finish/auto_finishはその全宛先への送信を要求する。一方、config.loaderのCORE_TOOLSはread_skill/finish_task/read_input_fileだけで、scheduler._run_taskはagent.toolsをそのままSessionContextへ渡す。ToolGateway.callは許可外send_messageを拒否する。モデルにとって解消不能な条件を実行後に知らせるため、無益な再試行・予算消費になりうる。

既知の制約として「通信能力なし/予算不足では完了しない」と明示されており、このfail-closedを欠陥とはしない。改善は計画確定後・最初のモデル呼出前に、必要な送信権限と必要宛先数に対するpeer枠を確認して明示blockedとすること。権限を自動追加したりゲートを黙って回避しない。

## 確認

- finish_task / auto_finishは同じcommunication_targetsとセッションのcommunicated_toを参照。
- publish成功後に全宛先をクリア、submit_review成功時に該当作成者の宛先を無効化。更新前の送信だけでは完了できない。
- 送信済みとするのは同task_idかつhandoff/finding/decisionの配送成功後。
- 受信taskfilter=NoneでもMessageBusはrun_id/to_agent_idで範囲を限定し、他run/他宛先へ拡張しない。
- replyのfinishにはanswer配送が必要。本文内容の真偽・有用性をこのゲートが保証するわけではない。
- Master計画、single、別担当の依存がない仕事は対象外。独立仕事に偽の発言を追加しない。

13件の実SQLite/実記録テスト成功は主担当の実行報告。今回はそのテストとコードを読み、独立でモデル実行やテスト再実行はしていない。稼働8796には未反映であり、稼働中runの動作を修正後の成功証拠とはしない。実モデルの全フロー検証は未実施。
