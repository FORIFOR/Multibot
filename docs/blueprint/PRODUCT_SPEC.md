# Product Specification

## 1. 製品の約束
「依頼は一度。AIチームが作り、確かめ、成果物と経緯を残す。」
英語の説明案: An open-source AI team that ships real work—with a conversation you can follow.
名称は未決定。Agent Teamは作業上の仮称であり商標・ドメインの確認はしていない。

最初の対象はソフトウェア開発者、個人開発者、小規模チーム。
最初の訴求は「製品URLまたは説明 → 調査メモ・紹介LP・README草案・SNS投稿草案」。
公開・投稿・送信は別の承認済み操作。動画生成、24時間クラウドPC、大規模マーケットプレイスは初期版から外す。
汎用基盤だが公開デモはこの1用途に集中する。

## 2. 体験
初回だけプロバイダー接続と予算上限・外部操作の許可範囲を設定する。
通常画面は依頼入力欄、添付・URL、開始ボタン。Bot数・モデル・プロンプトの初期設定を強制しない。
初期は全Botが同一接続・モデルを継承してもよい。ユーザーは任意のBotだけ上書きできる。
接続先と使用可能ツールを確認後、Masterが成果物・完了条件・役割・依存関係を生成する。
既知情報は再質問しない。推定で前進できる点はAssumptionsとして記録し、未確認の事実とは分ける。
取り返しのつかない判断、認証不足、予算超過、公開・送信だけを必要時に確認する。

デスクトップは「チーム状態 / 成果物プレビュー / チャット・経緯」を基本とする。
成果物を主役に置き、右側で実際のBotメッセージと実行カードを確認できる。
モバイルは成果物を先頭に置き、経緯とチャットはタブで切り替える。
完了時は成果物、検証、未解決・承認待ち、コスト・時間、経緯への導線を表示する。

## 3. Botを会話の演出にしない
Botごとにagent_id、設定revision、独立した会話state、受信箱、task、tool scope、作業領域を持つ。
同じLLMでもこれらが分離されていれば独立実行になる。逆にモデルが異なるだけでは協働とはいえない。
Masterは計画・割当・例外判断・最終集約。実際のタスク起動と予算・権限・状態変更は決定論的なRuntimeが行う。
Workerは各タスクの成果物を作る。Reviewerは指定revisionを検査し、機械的な検証と根拠付き評価を返す。
Reporterは初期では無効。Masterの最後の一回の応答で報告を兼務し、独立Reporterは設定で有効にできる。

## 4. 実行モデル
依頼を成果物と依存関係の有向非巡回グラフ(DAG)に変換する。
一つのtaskには一人のowner、入力成果物revision、成果物契約、受入条件、予算、期限、書込範囲を持たせる。
循環、不明なowner、不明なtool、権限逸脱、重複書込先は開始前に拒否する。
単純な依頼は単一WorkerまたはMaster自身で終了可能。協働が必要な依頼だけ複数Botを起動する。
独立した調査とコピー制作などは並列、調査完了を必要とする実装は依存関係を満たしてから起動する。
peerメッセージは依頼・質問・回答・引継ぎ・指摘・判断のみ。相槌や受領確認だけではモデルを起動しない。

通常状態: queued → ready → running → review_pending → accepted。
追加状態: blocked / approval_required / interrupted / failed / cancelled / partial。
修正は元の履歴を上書きせず、新しいattempt・成果物revisionを作る。
意味的な進捗は成果物変更、検証追加、未解決解消で測り、発話量で測らない。
同一問題で上限回数修正しても改善がなければpartial/blockedへ移行し、根拠と残作業を渡す。

## 5. 保存と通信
append-only Event Storeを実行記録の正本にする。
チャット表示・時系列・報告はそのprojectionだが、LLM報告文は別の派生物であり正本の代わりにしない。
最低限: event_id、run_id、単調なseq、UTCの記録時刻、actor、task_id、causation_id、event type。
並列処理は同じ時刻でもよい。seqで保存順を示し、因果関係はcausation_id / task dependencyで辿る。
Botが時刻や自分の権限を指定しても採用しない。Runtimeが確定する。
画面の時刻はユーザーのタイムゾーンに変換する。

inter_agent_messageは実際に宛先の受信箱へ配送する。ログだけに会話を後付けしない。
宛先、目的、task、関連message、artifact revisionを持つメッセージを型付きツールで送る。
APIモデルの非公開の思考過程を取得・表示できる前提にはしない。
ユーザーに見せるのは実際の通信、短い判断要旨、ツール結果、変更差分、根拠。

ログ保存とLLMへの再入力は分離する。
Workerに渡すのは担当task、必要な短い前提、指定された成果物revision、宛先の受信メッセージのみ。
全文は必要時の検索対象として保持し、全Botに毎回配送しない。
大きなツール出力は容量上限・秘密情報マスクを適用して保存し、短い説明と参照だけを渡す。

## 6. 成果物管理
作業領域は run / agent / attempt ごとに分離。
受渡しはArtifact Storeに公開されたimmutable revisionを参照する。
artifact_id、revision、SHA-256、media type、作成task、作成agent、出典、検証event参照を記録する。
共有ファイルを全Botが同時上書きする設計は避ける。
コードはタスク別Git worktree / branchを使い、mergeは担当Runtime操作で行う。
branchやフォルダはセキュリティ隔離ではない。実行は別sandbox・権限制御を必要とする。
検証は必ず実際のartifact revisionに紐付け、改変後に古い検証結果を流用しない。

## 7. 初期ガードレール案
Worker同時実行上限3、task上限12、taskあたりpeerメッセージ6、修正上限2回。
モデル呼出上限30、tool呼出上限50、runのwall-clock上限600秒を初期候補とする。
これらは提案値であり、品質・費用の実測後に調整する。
Master呼出は計画、依存task完了・例外、最終集約に限定。定期ポーリングにLLMを使わない。
全体履歴の長文化、同一URL再検索、同一artifact再要約、無制限レビューを避ける。
キャッシュはartifact revision、tool入力、model・prompt revision、出典の鮮度、権限境界をキーに含める。
秘密情報や異なるユーザーの内容が共通キャッシュから漏れないよう分離する。

予算は実使用額＋実行中呼出の最大見積額予約で判定し、超過見込みの新規呼出を止める。
price不明のクラウドモデルはコスト0扱いにしない。価格設定またはプロバイダー側上限確認まで停止する。
ツール・画像・音声料金も会計対象。UI推計はプロバイダーの最終請求額と完全一致する保証ではない。
単一Bot・同一総予算の比較を実施し、並列化のメリットがないtaskは単一Botへ戻す。

## 8. モデル・プロンプト設定
connection、model、editable role promptをBotごとに変更可能。
Providerのdriverはnative APIと互換APIを区別。base URLだけでAPI差異を吸収しようとしない。
モデル選択時に実疎通、structured output / tool calling / visionなど必要能力を検証する。
設定モデルと実応答モデル、connection、prompt hash、skill hash、fallback理由を別々に記録する。
モデルが自己申告したモデル名は実行経路の証拠にしない。プロバイダー応答とクライアント経路から記録する。
providerがmodel名を返さない場合はunknownとして表示し、推測で埋めない。

prompt = platform policy + approved role prompt + task contract + 必要なSkill/context。
role promptはユーザーが編集でき、user_lockedならMasterは上書きしない。
Masterによる自動生成もreview済みテンプレート・Skill・tool registry内に限定する。
権限境界はpromptの文言ではなくRuntimeで強制する。
変更はrevisionを作成し、進行中runに無断適用せず次回runから適用する。
緊急切替はcheckpointで止め、新しい設定snapshotとfork runを作る。
fallback先へのデータ送信はあらかじめ許可されたconnectionだけに限定する。

## 9. SkillとSNSからの改善
SNS → 候補 → 一次資料 → ライセンス・内容審査 → hash固定 → 評価 → 採用、の順。
SNSの人気、GitHub star数、プロンプトの長さを品質の代理指標として扱わない。
外部投稿は学習対象ではなく非信頼の資料。system promptへ直接挿入しない。
初回は同梱Skillのメタデータのみを読み、該当Skillの本文を必要時だけ展開する。
Masterに外部Skillのインストール、ネットワーク権限拡大、APIキー参照、予算増額は許可しない。
自動改善はcandidate promptを作るところまで。評価済みstableを無条件に上書きしない。
最低3件の問題を見つけるなど指摘数を強制する文言は採用しない。
外部ソースの特定のscriptが存在する前提で呼ぶ指示もコピーしない。
新プロンプトと旧プロンプトを同じtask、budget、モデル、成果物検証条件で比較する。
ユーザーのプロジェクト実データを外部評価サービスへ送る場合は別途同意が必要。

## 10. 再生と再実行
Replayは保存済みイベント・成果物revisionの再生で、モデル再呼出をしない。
Resumeは最後の確定checkpointから未完了の仕事だけを続行する。
Forkは任意checkpointから条件・モデル・指示を変えた新runを作る。
LLMを再呼出して同一結果になる保証はしない。
外部書込はoperation_id / idempotency key / 実行先の状態照会で二重実行を防ぐ。
応答喪失で成功か不明な外部書込を再送しない。reconcileまたは承認要求にする。
共有Replayは初期OFF。明示的に選んだ成果物とマスク後の履歴だけを共有する。

## 11. 技術構成
UI: React + TypeScript / Vite。API: Python + FastAPI。
各WorkerのLLM loop / filesystem / context管理: Deep Agentsを薄いadapter越しに利用。
checkpointやgraph実行: LangGraph。製品固有のtask、通信、成果物、権限は小さい独立モジュール。
SQLite WAL + ローカルArtifact Store + SSEを初期構成にする。
LangSmithや有料クラウドを必須にせず、tracingの外部送信は初期OFF。
PythonとUIの型はJSON Schema / OpenAPIから生成してズレを防ぐ。
既存harnessのdelegationと独自schedulerを二重起動しない。子生成は一つの管理層に統合する。
Deep Agentsの同期subagentだけで中途の双方向チャットが実現するとは扱わない。
独立session・mailboxを持つworker管理、または適合するasync APIをadapter内で検証する。
DBやフレームワークのstateは隠蔽し、AgentRunner/ProviderAdapter/EventStore/ArtifactStore/Sandbox/PolicyEngineを契約として分離する。

## 12. 初回公開基準
実APIを呼ぶ3Bot協働runが複数回成功し、別Botの成果物を参照した実際の受渡しを確認できる。
実ファイルが開き、検証結果は実コマンド・実操作・対象revisionに紐付く。
Bot間会話は実際のLLM応答を配送したもの。台本、ダミーの成果物、固定成功ログは禁止。
停止・再開・失敗・API制限・ユーザー編集・同時書込競合・秘密情報マスクを試験する。
デモの時間短縮編集は明示し、実行コスト・モデル・成功例選別の有無を公開する。
スター数の保証はしない。初回成果物完成率、介入数、費用、再利用、継続利用を主指標にする。
