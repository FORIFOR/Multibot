# 開発エージェントに渡す実装指示

この仕様のAgent Teamを新規実装する。台本のBot会話やダミー成功表示を作って完成扱いにしない。
先に現リポジトリ、開発規約、既存設定、テストを読み、既存のユーザー変更を保持する。
実装対象のリポジトリが未指定の場合、勝手に既存製品を改変・公開せず新しいローカル作業領域を使う。
GitHubへの変更が許可された場合は1タスク1ブランチ、早期Draft PR、コミット単位で進める。

## P0: 一つの依頼から実成果物まで
A. Contracts: agent config、team plan、task、message、event、artifact manifest、approval、run snapshot。
B. Event Store: run単位seq、UTC、transactional outbox、SQLite WAL、再接続cursor、PII/secret redaction。
C. Provider Adapter: 接続先とmodelをagent単位で設定。native/compatの違いをdriverで吸収。
D. Worker: 独立state、mailbox、task scope、sandbox。実tool callingを使う。
E. Master: 成果物からDAGを生成。schema、循環、権限、予算をRuntimeが検査。
F. Delivery: send_messageを本当に宛先mailboxに配送し、同時にevent化。
G. Artifacts: atomic publish、version/hash、入力snapshot、実review対象との対応付け。
H. UI: 一行依頼、実行中状態、成果物プレビュー、thread chat、時系列、設定。
I. Final: MasterまたはReporterが証拠から短く報告。不明/未検証は残す。
J. Acceptance: 実LLMを呼び出すスモーク、実ファイルと検証、trace照合。

## P1: 公開に必要な堅牢性
停止・cancel・checkpoint resume、二重実行防止、budget reservation、競合制御。
権限拡大と外部書込のapproval、スキル固定、設定revision、user_locked prompt。
Replay、JSONL/Markdown export、機密を除いた共有、同一総予算single-agent比較。
初回接続診断、エラー時に設定画面へ戻れる導線、実model attribution。

## P2: 評価後の拡張
保存済み成功パターンのTeam Recipe化、受託・開発チーム向けhosted実行。
スマホ通知、動画生成、外部Botプロトコル、第三者Skill registry。
これらでP0を遅らせない。既存OSSの全機能を詰め合わせない。

## Backend API契約案
POST /api/runs: goal、artifact_inputs、任意のbudget/mode。実行条件未充足なら開始せず構造化した不足を返す。
GET /api/runs/{run_id}: 状態、task、artifact、usage、blocked理由。
GET /api/runs/{run_id}/events?after_seq=N: durable event cursor。
GET /api/runs/{run_id}/stream?after_seq=N: SSE。event idをcursorとし再配送はidで除重。
POST /api/runs/{run_id}/cancel: cancellation tokenを発行。外部操作の確定状態を別途記録。
POST /api/runs/{run_id}/resume: checkpoint指定。曖昧な外部side effectは要照合。
POST /api/runs/{run_id}/fork: 元run/checkpoint/設定revisionを保存。
POST /api/approvals/{approval_id}/resolve: approve/reject/edit。対象操作hash、期限、nonceを検証。
PATCH /api/agents/{agent_id}: expected_revisionを使う楽観的排他。role promptのロックを尊重。
GET /api/agents/{agent_id}/effective-config: 秘密を除く実効設定。
POST /api/connections/{connection_id}/probe: 実model疎通と必要能力を検査。小額の実呼出を事前表示。
GET /api/artifacts/{artifact_id}/versions/{revision}: authorized content、hash、出典、検証。

## Botに公開するツール契約案
create_task / update_taskはMaster専用。権限拡大は行えない。
send_message(to, task_id, purpose, text, artifact_refs, reply_to)で実配送する。
read_messagesは自分のtaskに関連する受信分のみ。
read_artifactは認可済みimmutable revisionのみ。
publish_artifactは自分のwrite scope内からatomicに公開する。
run_checkは登録済み検証かsandbox内コマンド。対象revisionと実出力をRuntimeが固定する。
request_approvalは実行予定の対象・内容・費用を示す。Bot自身が承認する経路は設けない。
report_blockerは停止理由と次に必要な情報を返す。
ツール名は仕様上の提案。既存APIがこれらを実装していると主張しない。

## 設定とUX
初回は1接続・1modelで開始できる。Botカードの詳細で個別上書きを可能にする。
新規BotのシステムプロンプトはMasterが初期候補を作る。外部権限とキーは生成できない。
手動変更は保存・diff・元に戻す・user_locked切替を用意する。
実行中の会話を中断しない設定変更は次のrunから反映する。
未検証のプロバイダーやplaceholderのmodelでボタンを有効にしない。

## 完了の報告
変更ファイル、実行したコマンド、実APIモデル・usage、成果物、成功/失敗の具体的根拠を報告する。
APIキーや実行環境がなく実API確認できなかった場合は「未検証」を明示して残す。
APIがない場合にfake providerへ切り替え、実LLMが動いたように見せない。
評価のための決定論的単体テストは可。ただしそれを実LLMの統合試験の代わりにしない。
