# 話し方設定の独立確認

AIによる独立補助評価。実設定と実ブラウザーをread-onlyで確認し、アプリコード・設定・実行中runは変更していない。実メッセージ/成果物の品質は生成後の別判定とし、既存の導入ガイドFAILを置き換えない。

環境: macOS / Chrome153.0.8010.53 / Playwright channel chrome / 1440×1000と390×844。隔離URL8802、対象run `run_1a0bb14eded265c29b5`。証拠は `artifacts/product-quality/trading-team/independent/`。ブラウザーはGET以外をabortするrouteを設定し、試験後に通常終了した。非GET要求は0件。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| TV01 | 実UI設定→reload→API値照合 | 永続設定が表示される | builderの明示設定と他担当の空欄が全員一致、reload前後完全一致 | PASS | settings-readonly.json, cross-check.json | 実Chrome/GET |
| TV02 | 空欄の見え方とeffective値を照合 | 空欄は役割既定、変更は次runに反映 | 役割別の異なる既定文をplaceholder表示、説明は「空欄なら役割に合った話し方。次の依頼の会話から反映」 | PASS | settings-1440.png, settings-390.png, settings-readonly.json | 実画面を開いて目視済み |
| TV03 | API/effective/run snapshotを照合 | 開始時の話し方を固定 | 有効4担当のspeech_style・system_prompt_sha256・toolsがsnapshotと一致。無効reporterはrunに含まれない | PASS | cross-check.json | 実run/GET |
| TV04 | loader/worker/planner/voiceを静的に読む | 役割指示と話し方を分離 | speech_styleは別field、role prompt/hashを変えず実プロンプト組立時に別sectionとして付加。成果の言語/文体・事実/権限/完了条件を変えないと明示 | PASS | backend/agentteam/config/voice.py, loader.py, runtime/worker.py, planner.py | 静的確認 |
| TV05 | API/工具権限/競合処理を静的確認 | 話し方が権限を増やさない | tools解決はCORE_TOOLS+agent.toolsの既存処理でstyle非参照。PATCHは既存revisionチェックと認可経路を使用し、styleのみ更新可能 | PASS | api/app.py:patch_agent, security/server.py:authorize, config/loader.py:effective_agent | 静的確認、認証アカウント実試験は未実施 |
| TV06 | 390pxのラベル/説明/幅確認 | 入力の意味を見失わず操作領域が収まる | ラベル・説明紐付けあり、maxLength600、document.scrollWidth=390。詳細プロンプトは別開閉領域 | PASS | settings-390.png, settings-readonly.json | モバイルviewport、実タッチではない |
| TV07 | 独立担当による保存/リセット/再起動/競合試験 | 実保存から再取得まで独立実行 | 本担当はread-onlyのためPATCHしない。親担当browser-observation.jsonのvoicePersisted=trueとAPI試験コードは確認したが、本担当の保存実行PASSとはしない | BLOCKED | ../browser-observation.json, backend/tests/test_conversation_voice.py | 権限範囲による分離 |
| TV08 | 実発言の違い・応答・成果物を確認 | 名前/絵文字だけでなく実会話と成果が成立 | この設定確認時点では判定対象外。設定が異なることだけでモデルの話し方実現を断定しない | BLOCKED | docs/quality/trading-team.mdの固定条件 | 生成後に別評価 |

静的レビューで修正必須の不具合は発見していない。保存済み設定の表示とsnapshotは確認できたが、自然言語の話し方設定がモデルに必ず守られるとは保証しない。性格を理由とした権限逸脱は、プロンプトだけでなく既存実行層の工具/ポリシー制約が引き続き防ぐ構造である。

親担当のAPI試験は実AppService/SQLiteで保存、古いrevisionの409、601文字の422、役割prompt/tools不変、snapshot固定、再起動後の保持、空欄リセットを検査するコードだった。スタブによる生成会話を使っていない。ただし本担当では再実行していないため、実行結果は親担当の証拠に帰属する。

## 途中成果 requirements_summary.md revision 1

対象は同じrunが公開した途中成果。最終architecture.md/decisions.mdの判定とは分離する。GET取得したrun.inputs.filesの原資料を正として全文照合し、実モデルへの指示・フィードバックは送っていない。原文の修正もしていない。独立AI評価であり、人間評価ではない。

証拠: `independent/requirements-run.json`、`independent/source-trading.md`、`independent/requirements-r1.md`。raw本文SHA-256は `2a139f0cd92402d330beb03d22fcf261a3224be552fd2390ee90e70fe2d26b78`（API記録と一致）。以下の行番号はこの保存原文を指す。

| id | 手順・期待 | 観測 | 判定 |
|---|---|---|---|
| TR01 | 入力の本番までの段階・移行条件を保持 | 14/140行が検討をPaperまでに限定。120–124行はLive分岐の基礎までで、本番接続に進む条件がない | FAIL / P1 |
| TR02 | pending_cancelを外部確認なしに取消済みへしない | 56行では取消未完了と理解する一方、63行で再接続失敗時にローカル処理で完了させる。外部の成立結果を確かめる条件がなく矛盾 | FAIL / P1 |
| TR03 | client IDと証券側IDの発行責任を分ける | 44行が「両方のIDを生成」とする。証券側IDはサービス発行。45行の省略時自動生成は資料と整合するが、応答不明時に照会へ使える相関IDを事前永続化する設計が不足 | FAIL / P1 |
| TR04 | 取消と約定の競合を扱う | 62行は取消対新規発注の内部FIFOに置換し、取消待ち中の部分/全約定や取消拒否の処理を示していない | FAIL / P1 |
| TR05 | 応答喪失・再接続時に口座/注文/約定を再照合 | 85行の応答なし→照会は適切。ただし78行は全注文情報だけで、口座と約定照合、結果不明を保つ条件、解消前の再発注抑止が不足 | FAIL / P2（適切な照会方針は部分充足） |
| TR06 | Paper制約の公式記述を正確に維持 | 72行のNBBOを模擬しない可能性は原資料にない。数量制限を照合しないことと価格照合の有無を混同。129行には数量制約が残るが72行を解消しない | FAIL / P2 |
| TR07 | 公式仕様・設計提案・未確認を区別 | 20行に区別方針はあるが、FIFO、MFA/KMS/TLS等の追加案の根拠区分が本文で曖昧。93行は価格利用権限をPaper/Liveと表現し、環境区分とデータ契約を混同する | FAIL / P2 |
| TR08 | 秘密情報/未決事項/古い価格を明示 | サーバーで秘密鍵管理、古い価格をリアルタイムと表示しない、対象市場・証券会社・法令未確認を記述 | PASS（当該部分のみ） |
| TR09 | 実装・実発注の実施を装わない | 実装順序として将来形で記述し、接続/実発注成功の証拠を捏造していない | PASS（成果物本文の主張のみ） |

2026-09-20に公式ページも再読した。証券側注文IDはシステム発行であり、利用者指定IDと区別される。[Orders at Alpaca](https://docs.alpaca.markets/us/docs/orders-at-alpaca)。取消待ち、取消処理済み、取消拒否は区別される。[Websocket Streaming](https://docs.alpaca.markets/us/docs/websocket-streaming)。PaperはNBBO価格による約定模擬を行う一方、注文数量を実際のNBBO数量と照合しないため、両者を混同できない。[Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading)。外部の実口座・取引APIは呼び出していない。

途中成果の独立判定は **FAIL（修正が必要）**。特にTR02の記述をそのまま実装すると、まだ約定し得る注文を取消完了と扱う。この結果だけで未公開の最終成果や審査の結論を断定しない。会話・最終成果・人間利用評価は引き続き別判定とする。

## まとめ役の初期引継ぎ経路（追加コードの静的確認）

`runtime/communication.py`、`tools.py`、`orchestrator.py`と関連試験をread-onlyで確認した。この追加コードは観測中の8802プロセスには未ロードのため、そこで公開済みの会話を追加コードの実動証拠として扱わない。

- PASS（静的）: 初期計画の永続化後に通常teamだけで実行し、document/single経路は対象外。既存AgentRunnerを用い、固定文面の会話を自動挿入する実装ではない。
- PASS（静的）: `send_message`/`finish_task`/`report_blocker`とmaster既存許可の積集合だけを工具にする。ToolGatewayの許可確認を通るので成果の書込み・公開などをこのsessionに追加しない。
- PASS（静的）: 宛先の有効性、実在task.ownerとの一致、handoff/decision用途を送信境界で検査する。全担当への永続messageがなければfinishを拒否し、同担当への再送を拒否する。
- PASS（静的）: 再開時はDBの送信者/用途/task/担当の一致を再確認する。memoryフラグやfinishの自己申告だけで完了にしない。
- BLOCKED（独立実動未試験）: 新版のモデル発言、障害途中からの再開、各担当の返信と話し方は本担当では実行していない。試験コードが実記録のtask.objectiveを直接gatewayへ渡す保存・再開試験は、永続化の検証にはなるが、実モデルがその会話を生成した証拠にはならない。

今回の静的範囲では修正必須の権限増加や固定文の虚偽会話挿入は発見していない。永続送信の存在は内容の充足を保証しないため、実モデルの会話内容と成果品質の独立判定は別途必要である。

## architecture.md 公開前草稿の独立確認（補助あり）

2026-09-20 04:31 JST、同一runのseq44/live=true時点。公開一覧にはrequirements_summary.md r1だけが存在したため、`workspaces/t2/architecture.md`は**公開前草稿**として採取した。revision番号は付けない。親担当からseq28で検証補助指示が送られたことを実run.latest_instructionで確認した。無支援初回成功やモデルの自力発見とは評価しない。本担当はGETとファイル読取だけで、本文変更・指示送信・新規実行・他のサーバーへの操作をしていない。

草稿は10,936 bytes、SHA-256 `647fd10a9371edb64aabe790bab20b53bd88d1401bd098dc450f75b8d7a73ed0`。証拠は `independent/architecture-draft.md`、`architecture-draft-evidence.json`、`architecture-run.json`、`architecture-run-after.json`。添付原資料を `architecture-source.md` に保存し、SHA-256 `043daf3a1b08c3d6e0413ebc320d83219ff2cf3d8af7d3f60b301950351a7a9c`。行番号は保存草稿に対応する。原要求・原資料との全文照合で判定した。

| id | method / expected | observed | status | evidence / environment |
|---|---|---|---|---|
| TA01 | 外部確認なしの取消完了を禁止する | 51/106/134行に不明を保持して照会、ローカル完了しないと明示。先行資料の危険な記述を改善した | PASS（当該条件） | 草稿§2/4.4/5.2、隔離実run/静的本文 |
| TA02 | 再接続時に口座・注文・約定を照合する | 135行に3対象を明示。先行資料の注文のみから改善した。ただし照合不一致時の判断・更新順序は未具体化 | PASS（3対象の明示） | 草稿§5.2 |
| TA03 | 証券側IDとアプリ側IDの責任を一貫して分ける | 91行は証券側生成とするが「省略可能」がサービスIDへ移動し、93行は両方生成可能・サーバーで統一と残す。省略可能なのは要求のclient_order_idであり、証券側IDをアプリが統一生成する意味なら誤り。区分追加だけで曖昧さは解消していない | FAIL / P1 | 草稿§4.3、添付「注文の識別と照会」 |
| TA04 | 取消要求中の部分/全約定との競合を具体化する | 114行が依然「取消発注と新規発注」のFIFO/time-based。取消より先に約定した場合の残量・終端状態・取消拒否などの判断がない | FAIL / P1 | 草稿§4.5 |
| TA05 | 応答不明時に任意HTTP再送の安全性を保証しない | 141行の照会方針は適切だが、49/79行が内部トークンだけで結果不明時の安全な再送を保証する表現。接続先の重複排除契約、送信前ID永続化、照会で解消しない間の再送禁止などの条件がなく、原資料の注意を保持していない | FAIL / P1 | 草稿§2/4.1/5.3、添付「任意のHTTP再送」の注意 |
| TA06 | 本番までの段階と通過条件を具体的に示す | §7にPaper状態同期試験→キー/コード承認という条件を追加した点は改善。一方7行はPaper検証までと限定したまま。市場/利用資格/実注文権限/配信契約など未決事項を本番前に解消する段階がなく、鍵と分岐の承認だけで進める条件は不足 | FAIL / P1（部分改善） | 草稿§1/7、原要求と添付末尾 |
| TA07 | PaperのNBBO数量制約を正しく保持する | 125行でNBBOを模擬しない可能性を根拠なしに残す。「一部API/市場」に一般化しただけで、添付の数量不照合という制約の説明が消えている | FAIL / P2 | 草稿§5.1、添付Paper/Live |
| TA08 | 価格の利用権限と環境区分を分離する | 47/149行で権限=Paper/Liveと混同が継続。85行に権限ラベルを別途置く文はあるが、全体で一貫しない | FAIL / P2 | 草稿§2/4.2/6.1 |
| TA09 | Core/Adapter/UIの契約、認可、具体的な検証条件を示す | 層の図と概略責務は追加したがCoreはAPI/Serverと一体で操作契約/戻り値/不明状態の型がない。認証方式の列挙はあるが利用者がその口座へ発注できる認可条件がない。状態列挙に留まり、遷移・試験結果の合格条件も不足 | FAIL / P2 | 草稿§2/3/4/7 |
| TA10 | 公式仕様・提案・未確認を区別し、未実施を装わない | §7を設計提案と明示し、実接続成功を称していない点は適切。署名、MFA/WAF等の追加要素の根拠区分は曖昧で、未決の認証方式を固定したようにも読める | FAIL / P2（未実施の開示は維持） | 草稿§1/3/7 |
| TA11 | 公開された最新版・decisions.md・実版に対する審査を確認 | 再GETでもseq44、architectureは未公開。最終成果・decisions・その版への審査をこの草稿確認では判定できない | BLOCKED | architecture-run-after.json |

草稿の内容判定は **FAIL（改善2点を確認、主要な未達は継続）**。特にTA05は不明時の照会と無条件に見える再送保証が同居しているため、単語が追加されたことを意味上の修正完了とは扱わない。最終公開版が変われば別hashで再照合する。これは実取引の安全性試験や人間の使いやすさ評価ではない。
