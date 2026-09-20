# 文書の言語条件と実モデル成果の独立確認

2026-09-20、AIによる独立補助評価。人間の評価ではない。期待値・モデル出力・アプリコードは変更しない。対象は追加された文書ワークフローの言語条件と、隔離された実Ollama実行の成果。

## 静的確認

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| DL01 | worker / document_plan の言語条件を読む | 元資料の引用・識別子を壊さず日本語本文を検証 | ユーザー明示言語優先、未指定時team言語。引用・固有名・コード保持。保存済み成果の言語を形式検査と別に確認、不明時unverifiedを指示 | PASS | backend/agentteam/runtime/worker.py:80, planner.py:253 | 静的確認 |
| DL02 | document_plan の入力前提を読む | 単一text成果と入力資料が必要 | RunInputs.document_inputs が単一text契約、実資料の存在、URL無しを検証。builder/reviewer分離も計画生成時に検証 | PASS | backend/agentteam/contracts.py:304, runtime/planner.py:242 | 静的確認 |
| DL03 | review / delivery の対象を照合 | 古い版や書き換えた契約で合格しない | 全criterionの判定必須、latest artifactのid/revision/hash集合一致を要求。verify_deliveryは永続化された依頼者契約で実bytesを検査 | PASS | runtime/tools.py:t_submit_review, runtime/delivery.py:verify_delivery | 静的確認 |

言語条件追加はプロンプトとモデル審査条件の改善であり、日本語品質を自動的に保証するものではない。実成果は公開後に別途照合する。

## 実モデル成果

実モデルを5回観測した。実行1〜4の内容・審査未達を保持し、実行5の最終成果と処理完遂はPASS。人間による初回利用評価、実スクリーンリーダー、実IME、実タッチ端末はこの担当の範囲ではBLOCKED。詳細は各実行節に記録する。

## 実行1・版1の独立観測

- run: `run_1a0babe269cb90ea9b7`（隔離実Ollama、8799）。入力は実資料 `docs/design/brief.md`。原依頼・契約は `artifacts/product-quality/document-language-independent/run-initial.json` にGET結果を保存。
- 成果: `intro.md` revision 1、1263 bytes、461 Unicode文字（見出し・空白・改行込み）、SHA256 `2c197a287d010eb475c60335e47082d6f573ac5adc1394da02f6fdd15d5e6f87`。公開メタデータとダウンロードbytesが一致。
- 以降の証拠ファイルは `artifacts/product-quality/document-language-independent/` 配下。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| DL04 | GETで公開版とrawを取得しhash/文字数照合 | 同じ公開版、300–600文字 | 461文字、1263bytes、hash一致 | PASS | intro-r1.md, independent-r1.json, artifact-r1-detail.json | 実モデル成果r1 |
| DL05 | 原依頼の4内容を全文と照合 | 対象者/依頼→ファイル受取/別担当/未完了未確認を説明 | 全4項目を説明。対象者は冒頭、流れは第2段落、別担当と開示は第3段落 | PASS | intro-r1.md, source-brief.md | 独立AI読解 |
| DL06 | 日本語文を読み中国語混在・不自然な切替を調べる | 日本語として理解可能 | 過去readiness.jsonにあった中国語混在を認めず、自然な紹介文 | PASS | intro-r1.md | 独立AI読解、単発 |
| DL07 | 原依頼「固有名詞以外に別言語を混ぜず」を別途厳密照合 | Agent Team等の固有名詞以外を日本語化 | Web / UI / AIという一般略語が残る。通常の日本語文として自然でも、固有名詞限定の明示条件からは外れる | FAIL | intro-r1.md, independent-r1.json | 原依頼を後から緩和しない |
| DL08 | 資料と各主張を対応づける | 架空の機能・評価を足さない | 4人、動作表現、細部が提案段階であることまで入力に対応。架空の評価追加なし | PASS | intro-r1.md, source-brief.md | 入力資料への忠実性 |
| DL09 | チーム内reviewerの指摘と原依頼を独立照合 | 本当に不足した内容のみfail、言語も検査 | reviewerは4内容の完全一致キーワード不足と3ステップ文言欠落を理由にaccuracy fail。しかし原依頼は説明を要求し、完全一致語句/3ステップを必須にしていない。r1には4内容が存在。さらにlanguage pass「日本語のみ」はDL07を見逃す | FAIL | chat-review-r1.json, artifact-r1-detail.json, 02-reviewing.png | モデル審査の偽陽性と見逃し |
| DL10 | 実作業中/審査中のUIを読む | 実状態と要修正を開示 | 作成→確認の担当遷移、引継ぎ会話、途中成果、未確認・要修正バッジを表示 | PASS | 01-running.png, 02-reviewing.png（双方を開いて目視済み） | Chrome1440×1000 |

DL08は現UIの最新紹介としての承認ではない。入力の旧デザインブリーフに「持ち上がって光る」が含まれ、そのまま成果へ反映された。資料の鮮度は親タスクが現実装と照合する。モデルに与えた資料の忠実な要約と、資料自体が現状に一致しているかは分ける。

成果や合格基準は本担当が書き換えていない。reviewerの指摘を機械的に正解とせず、原依頼・資料・公開版の3者で判断した。

実行1の最終観測状態は `cancelled`。intro.mdは版1のままで、作成タスクはreview_pending、確認タスクはinterrupted。作業全体完了・独立審査通過とは判定しない。`run-current.json` にGETで取得した状態を保存した。

## 追加修正の静的レビューと後片付け

- reviewer.mdの追加指示は、意味条件を完全一致キーワード検査に置き換えず本文の該当箇所で照合すること、依頼者の略語制限を資料中の用例だけで例外化しないことを明示する。今回の偽陽性・見逃しへの方針としてPASS。ただし次の実モデル実行での改善実証は未完了。
- `ToolGateway._pending_review_notice` と `t_read_messages` は、review_pendingの依存先を持つ確認担当の待機時間を0にして、依存先が修正を始めるには審査確定が必要であることを伝える。循環待ちを減らす方向は妥当。
- 静的にP2候補を親担当へ返した: noticeは`ctx.reviews`の提出済み対象を除外しておらず、submit_review→send_message後にも再度submit_reviewを促す。再提出では`communicated_to.discard(owner)`が行われるため、再提出と再送信を繰り返す誘導になりうる。提出済みを区別しfinish_taskへ誘導する修正を推奨。実際の再発を実モデルで観測したという主張ではない。
- 2回目の実行は親担当で503 insufficient storage space。500MiB admissionは保持。本担当が起動したChrome（port9338、PID22838、親node22834）へCDP Browser.closeを送り通常終了した。自分のプロファイル `/var/folders/qy/086ttpq57jsd36jnc1jffst00000gn/T/playwright_chromiumdev_profile-E3IkR4` はPlaywrightにより自動削除済み、両PIDの消滅も確認。他人のChrome・ユーザーファイルは変更していない。
- 後片付け後のdf Availableは433672KiB（約423.5MiB）。500MiB未満のままで、ここで実モデル完遂をPASSに変更しない。

## 実行2・版1の独立観測

ディスク空き容量が外部要因で回復し、親担当が正規の依頼を再実行した。500MiB admissionを緩和していない。run `run_1a0bac931320e5b2ac5` の原依頼と300–600文字契約は実行1と同じ。入力資料は現UIを反映した2026-09-20版（`source2-brief.md`）。意味条件の審査指示と依存待ち防止はロード済みだが、提出済みnoticeの追加分岐は今回サーバーに未ロードとの親担当申告。ファイル上では提出済み時に再提出を禁じfinish_taskへ誘導する分岐を静的確認した。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| DL11 | 公開版とrawをGET、文字数/hash照合 | 同じ公開版、300–600文字 | intro.md r1 / 518文字 / 1354bytes / SHA256 f108d58ae8b36bc79bb78a2b6b8fdaa9fcfd13415d6842860c5ec3df0eb04303一致 | PASS | run2-intro-r1.md, run2-independent-r1.json, run2-current.json | 実モデル成果r1 |
| DL12 | 必須4内容と最新資料の照合 | 4内容と現担当表示を説明 | 対象者、依頼から受取、作成確認別担当、未完了未確認を説明。絵文字ボタンの担当/状態も資料に対応 | PASS | run2-intro-r1.md, source2-brief.md | 独立AI読解 |
| DL13 | 固有名詞以外の別言語禁止を確認 | 一般略語も日本語化 | AI/Webが残存。Agent Teamは固有名詞として可 | FAIL | run2-intro-r1.md | 原依頼を維持 |
| DL14 | 資料の条件・例外を照合 | 編集コピー固有の制約を一般化しない | 最終段落は「確認済みの記録を引き継がない仕組み」と説明するが、資料の「編集コピーはチームが公開した版とは別」という適用条件を落としている。編集コピーへの限定を明示するか、この追加説明を省く必要 | FAIL | run2-intro-r1.md, source2-brief.md | 独立AI読解 |

成果と期待値は本担当が変更していない。実行2のチーム審査・最終状態は別途追記する。

実行2は `completed`、終了時刻 `2026-09-19T17:55:14.981Z`。intro.mdは版1のままで、builder/reviewer両タスクがaccepted。review対象のid/revision/hashは独立取得した公開版と一致した。従って、実行1で止まったモデル処理完遂と審査確定のフローは今回成立している。

一方、モデル審査はdocument_contract / document_language / document_accuracyをすべてpassとし、DL13とDL14を見逃した。モデルの「固有名詞以外の英語は含まれていない」は実本文のAI/Webに反する。また審査の文字数記載は526文字だが、実bytesのUTF-8復号文字数は518。両者とも300–600の範囲なので形式契約の合否は変わらないが、審査説明の精度には未達がある。`run2-artifact-r1-detail.json` / `run2-chat.json` / `run2-current.json` に実記録を保存。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| DL15 | 実run最終状態と審査参照をGET照合 | 審査待ちで停止せず、公開版に審査を結びつけ完遂 | completed、t1/t2 accepted、審査hashはr1に一致 | PASS | run2-current.json, run2-artifact-r1-detail.json | 実Ollama単発 |
| DL16 | モデル審査と独立判定を照合 | 明示制約/資料の適用条件を見落とさない | 全passだがDL13/14未達。文字数の説明も526と誤記 | FAIL | run2-chat.json, run2-artifact-r1-detail.json, run2-independent-r1.json | 審査品質 |

最終判定: **操作とモデル処理の完遂はPASS、依頼条件・内容審査品質はFAIL**。今回だけで言語品質や審査信頼性の未達解消とはしない。人間の評価や統計的な成功率は引き続き未測定。容量不足BLOCKEDは今回の実行成立により解消した経緯として保持する。

## 実行3・版1の独立観測

run `run_1a0bacfe61c70f1bc6b`。原条件と文字数契約を保持し、依頼に一般略語の言い換え例と編集コピーの適用範囲保持を明記した（`run3-initial.json`）。この条件明確化があるため、実行2と完全に同一プロンプトの反復試験とは扱わない。

- intro.md revision 1 / 430文字 / 1222bytes / SHA256 `b4b8683f031ee1075f1e463e0d921656e473382a15bb5c8dc0fc1fdec02a1df1`。GETで取得した実bytesと公開記録が一致。
- 対象ユーザー、依頼からファイルを受け取る流れ、作成確認別担当、未完了未確認の開示は含まれる。一般略語はなくLatin表記はAgent Teamのみ。編集コピーの制約を全成果物へ一般化する説明もなくなった。
- ただし「使い方は簡単です」「初心者にも使いやすい設計です」という未検証の評価を追加している。原資料は初心者を対象に含むが、人間の初見成功率は未測定と明示する。対象者や設計意図の説明と使いやすさの断定を区別し、原依頼の「架空の機能や評価を足さない」に照らしてaccuracy FAILを保持する。
- 観測結果: 形式/版結合/4内容/略語修正/適用条件修正はPASS、未測定の評価追加はFAIL。証拠は `run3-intro-r1.md` / `run3-independent-r1.json` / `source3-brief.md`。成果物自体は変更していない。

実行3はcompleted、intro.mdはr1のまま。審査の対象hashは正しいが全passとなり、未測定評価を見逃した。言語審査の根拠にある「具体的な UI 要素のみの記述」は本文に存在しない表現であり、正確な引用根拠とは言えない。`run3-artifact-r1-detail.json` と `run3-current.json` に保存。処理完遂PASS、成果の評価追加と審査精度FAILを保持する。

## 実行4

run `run_1a0bad481bdaa794239`。元の条件に加え、原資料に使いやすさの実測結果がないため「簡単・使いやすい」を断定せず実操作と結果だけを書くと明確化。`run4-initial.json` に原依頼を保存。前3回のFAILは取り消さない。

実行4版1は492文字、SHA256 `896a88649ea57d120216c21e07e21515cc65181eada0ad1a933347bcc923f07c`、公開版とbytes一致。4必須内容、一般略語の排除、絵文字担当表示、ブラウザー内コピー編集を含む。末尾には初見成功率未測定・使いやすさ実測なしを明示する。

しかし第2段落の「使い方は簡単です」は明示された禁止条件に直接反し、第3段落の「一目でわかります」も未測定評価。末尾の未測定説明で前段の断定を取り消したことにはならない。**版1の内容はFAIL**。証拠: `run4-intro-r1.md` / `run4-independent-r1.json`。reviewerはseq42の引継ぎで全条件通過と明言しているが、最終審査記録とrun最終状態は別途確認する。

実行4はcompleted、intro.mdはr1のまま、作成/確認タスクaccepted。正式審査も対象r1/hash一致で全passとした。accuracy根拠は「未測定事項は『未測定』と明記」であり、同じ成果にある「使い方は簡単です」の矛盾を見逃した。具体的な主張と原条件の対照という追加指示も十分には実行されていない。`run4-artifact-r1-detail.json` / `run4-current.json` に保存。**実処理完遂PASS、明示禁止条件と審査精度FAIL**。人間評価の未実施は変わらない。

## 実行5

run `run_1a0bad92ee9aa7923c3`。依頼文は実行4と同じ。納品契約に依頼者が明示した6文字列（AI / Web / UI / 簡単 / 使いやすい / 一目で）を全文リテラル禁止として追加し、JSON Schemaのnot/anyOf/patternで永続化したことをGETで確認。これは既存条件の具体化・強化であり、条件緩和ではない。ただし前回と同一条件の反復成功率として集計しない。

版1は369文字・1023bytes、SHA256 `c2299d2cd50f511e6e03c8f047c70ea924d4795111013f22e7486e215844de0c`。公開記録との一致を確認し、保存済みschemaを`backend/.venv/bin/python`のDraft202012Validatorで独立再検査してerrors=[]。初回にsystem python3ではjsonschemaがなくexit1だったため既存venvへ切り替え、追加インストールや期待値変更はしていない。

独立読解では、対象者（人工知能に作業を任せたい方）、依頼からファイル受取、作成/確認別担当、未完了/未確認開示の4内容を最小限含む。一般略語と未測定の使いやすさ評価はなく、編集コピーは公開版と別と明記し、初見操作の成功率未測定も維持する。版1の依頼条件はPASS。対象者の説明が開発者・技術リーダー等を省き一般的である点は具体性の改善余地であり、今回の必須条件違反とはしない。画面幅/入力手段は入力資料からの説明であり、本試験による実タッチ検証済みの主張ではない。

証拠: `run5-initial.json` / `run5-intro-r1.md` / `run5-independent-r1.json` / `source5-brief.md`。内容そのものは変更していない。審査・最終状態は以下に追記する。

実行5の最終状態はcompleted、intro.md r1のbytesは再取得しても不変。作成/確認タスクaccepted、正式審査のid/revision/SHA256は独立取得した最終版と一致。モデル審査は369文字と禁止6表現の不在を正しく記載し全pass、独立読解の納品判定も今回PASS。

ただし、モデル審査の「略語（人工知能、画面）」という分類は不正確で、各意味主張と原条件の具体的な引用対照はなお弱い。今回の成果に対する合否一致は、モデル審査全般の見逃し解消や統計的信頼性を示すものではない。過去4回の失敗はそのまま保持する。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| DL17 | 実保存契約と最終rawを独立再検査 | 300–600文字、禁止6表現なし | 369文字、schema errors=[]、公開hash一致、最終再取得bytes不変 | PASS | run5-initial.json, run5-independent-r1.json, run5-intro-r1.md | 実モデル最終r1 |
| DL18 | 本文と資料/原依頼を独立全文照合 | 4内容、言語制約、適用条件、未測定の保持 | 最小限の4内容を説明、Latinは製品名のみ、編集コピーを区別、未測定明記、使いやすさ評価なし | PASS | source5-brief.md, run5-intro-r1.md | 独立AI補助評価 |
| DL19 | 最終run/正式review/原文を照合 | 完遂し正しい公開版へ審査が結びつく | completed、t1/t2 accepted、r1/hash一致、合否も独立評価と一致 | PASS | run5-current.json, run5-artifact-r1-detail.json, run5-chat.json | 実Ollama単発 |
| DL20 | 審査説明の精度と一般化限界を確認 | 各主張と条件を具体的に照合 | 今回の合否は妥当だが、略語の分類誤りと引用対照不足は残る。汎用的な審査信頼性の改善はこの1回では実証できない | BLOCKED | run5-artifact-r1-detail.json、過去実行証拠 | 複数ケース/人間評価未実施 |

今回の最終結論: **実行5の成果と処理完遂はPASS**。明示禁止表現をCoreの永続契約にしたことでモデル判断に依存しない検査が成立し、独立読解も今回の内容を確認した。これを、人間の初心者評価、実IME/VoiceOver/実タッチ検証、汎用的なモデル審査精度のPASSへ読み替えない。

## 実行5の追加で判明した検査記録と実行6

親担当の採用・ZIP取得確認で、実行5には確認担当が`text_contains('369')`により文字数を確認しようとした失敗記録が残ると判明した。実行5の成果bytes自体の独立PASSは維持するが、不要な誤検査を含まない審査実行とは言えず、その失敗履歴を削除しない。

実行6 `run_1a0bae0e04b3806b7be` は同じ依頼文・納品条件。json_schema(text)結果がUnicode code point数とUTF-8 byte数を返す最終コードで再実行。Coreの`len(text)`/`len(data)`は形式契約の測定と整合し、run_check説明も文字数を本文検索で確かめないと明記している。

intro.md r1は343文字・985bytes、SHA256 `5ef969e6286a54f302b21154bcda8a6578158b1e9676073aca55b616e5ee4bd9`。独立取得・公開版・作成時チェックのhashが一致し、永続契約を再検査してerrors=[]。4必須内容を含み、対象者を開発者/事業側/初心者として説明。一般略語、未測定の使いやすさ評価、編集コピーの条件一般化はない。初稿前は会話、成果後は成果物と会話という説明も資料と一致。版1本文は独立PASS。

証拠: `run6-initial.json` / `run6-intro-r1.md` / `run6-independent-r1.json` / `run6-events.json`。チェックseq13のunicode_code_points=343 / utf8_bytes=985は独立実測と一致。最終審査と不要検査の有無は以下に記録する。

実行6は確認担当のjson_schema実行（seq35、343文字/985bytes/pass、公開r1/hash一致）までを独立に観測した。その後モデル呼出中に数分間進展がなく、親担当が検証runのみ取消した。本文と形式契約の独立PASSは維持するが、正式審査・処理完遂はPASSにしない。今回確認できた範囲では文字数のtext_contains誤検査は再発していないが、未完遂のため最終審査品質の解消とは言わない。

次は短いintroの成功で元課題を置換せず、元の400–700文字の導入ガイドを別記録 `docs/quality/original-outcome-independent.md` で評価する。
