# 実モデルによる新規文書作成の完了条件

2026-09-20、未達の言語品質と生成完遂を対象。過去記録の書換えやモック成功を使わない。

環境: macOS、Chrome、loopback Ollama agentteam-qwen35-9b-16k、isolated data /tmp/multibot-completion-20260920、API8799。元profileのweb_search/web_fetch/request_approvalを外し、外部送信なし。ローカル実疎通は組込みping/schemaの最小プローブを使う（接続確認のみで成果物品質の証拠にはしない）。

主タスク: 実repo docs/design/brief.mdから初心者向けの日本語紹介文intro.mdを300〜600文字で作成。対象ユーザー、依頼→ファイル受取、作成/確認の別担当、未完了/未確認の開示を含める。

期待: UIで依頼→実モデル→作成と独立review→completed。intro.mdが実納品契約を通過し、その版/hashにdocument_languageとdocument_accuracyの確認記録がある。別担当が実本文を原資料と照合し、意図しない多言語混在なし。実bot会話と成果物の受渡しが残る。ブラウザーから採用/ZIP保存し中身hash一致。失敗した試行も記録し、期待値は緩めない。

言語チェックはモデルreviewであり、全出力の機械的な言語保証ではない。漢字を中国語とみなす誤った正規表現は使わない。引用/識別子/コードは原文保持。人間の初見評価・実iPhone/IME実機は別途BLOCKED。

## 改善と実測

- worker共通言語規則とdocument_language独立審査条件を追加。引用と本文、個別の外国語制限を区別。
- reviewerの「意味を満たす説明」を不要な完全一致キーワード検査で落とす誤判定を実モデルで観測。reviewer指示を修正。
- reviewerがreview_pendingの作成担当へ指摘後に30秒ずつ返信待ちし、作成担当が再開できない状態を観測。gatewayは当該待機を即時の受信確認に変え、判定提出/完了へ誘導。提出済み判定は再提出させずfinish_taskへ誘導。
- デザインブリーフの旧UI説明を現行へ更新。過去の入力/成果物は書き換えていない。
- 保存領域不足の503を日本語の復帰案内へ変更。500MiBの開始条件は維持。

実行1: `run_1a0babe269cb90ea9b7`、UIで疎通確認→資料添付→条件指定→新規依頼。実ローカルモデルがintro.md r1を生成、461文字/hash 2c197a287d010eb475c60335e47082d6f573ac5adc1394da02f6fdd15d5e6f87。独立確認で4内容と自然な日本語はPASS、固有名詞以外日本語という個別条件に対するWeb/UI略語はFAIL。実reviewerも不要な完全一致語句を要求する誤判定/言語見逃しがあり、完成とは扱わずユーザーの既存作業と別のこの試験runのみ停止。モデルが作った実会話は保存。

途中で実ディスク空き約418〜423MiBとなり、開始が503で拒否された。ユーザーファイル削除や開始基準変更はしていない。その後約8.6GiBに回復し再試行が実際に開始した。日本語案内の確認scriptは503を期待したが正常開始したためタイムアウトし、案内表示の実証には使えない。

実行2: `run_1a0bac931320e5b2ac5`、completed。r1は518文字/hash f108d58ae8b36bc79bb78a2b6b8fdaa9fcfd13415d6842860c5ec3df0eb04303。処理完遂と審査の版結合はPASS。ただし独立確認でAI/Webの言語条件違反、編集コピー限定の条件脱落を確認。モデル審査は両方を見逃しているため内容/審査はFAIL。途中の修正指示は次タスク向けで、すでに開始した審査には反映されていない。追加指示受付を修正完了として扱わない。

実行3: `run_1a0bacfe61c70f1bc6b`、実UIで開始。同じ条件に略語の具体的な言い換えと編集コピー限定条件を明記。受入条件は緩めていない。reviewerへ本文の短い引用と原条件の対照、略語の個別確認を指示。処理はcompleted。430文字/hash b4b8683f031ee1075f1e463e0d921656e473382a15bb5c8dc0fc1fdec02a1df1。言語とコピーの適用範囲は改善したが、「使い方は簡単」「初心者にも使いやすい」という未測定評価が残り、独立判定はFAIL。モデル審査は見逃した。

実行4: `run_1a0bad481bdaa794239`。作成/審査の共通指示に「設計意図と評価結果を区別し、根拠のない宣伝表現を足さない」を追加。同じ条件に未測定評価の禁止を明記して実UIから開始。前3回のFAILは保持。実行4もcompletedだが、「使い方は簡単です」「一目でわかります」の未測定評価が残り独立判定FAIL。ユーザーの継続指示に基づき3回の目安を超えて検証。

実行5: `run_1a0bad92ee9aa7923c3`。依頼者が任意の禁止表現を標準JSON Schemaで指定できるようUIを追加。AI/Web/UI/簡単/使いやすい/一目でを実UIで入力し、reload保持とサーバー保存契約を確認。元の意味条件は継続。369文字/1023bytes/hash c2299d2cd50f511e6e03c8f047c70ea924d4795111013f22e7486e215844de0cでcompleted。独立本文判定PASS、採用・reload保持・ブラウザーZIPと公開bytes一致もPASS。ただしreviewerが文字数をtext_contains("369")で検査する誤りを起こし、追加チェックの失敗記録とUI警告が残った。記録は消さない。

実行6: `run_1a0bae0e04b3806b7be`。textのjson_schema結果に保存内容のunicode_code_points/utf8_bytes実測を追加し、文字列検索は文字数検査ではないとtool説明を明確化。同じ入力・条件で最終コードを実行。343文字/985bytesの初稿は独立本文と実json_schema検査がPASS。確認担当のmodel呼出で4分以上追加記録がなく、この検証runだけ取消。本文PASSを処理完遂PASSとはしない。標準JSONモードの既存結果は変更しない。実行5の実ZIPも最終コードで再検査し369/1023とPASSを確認。

| 項目 | 判定 | 証拠 |
|---|---|---|
| 実接続・新規依頼・生成・実bot会話 | PASS | completion-probe-visible.log / completion-request.log / attempt-1/events.json、chat.json |
| 言語・全文条件・正しいreview・完了・保存の一貫成功 | FAIL | 実行5は本文/保存PASSだが不要なチェック失敗が残る。実行6は審査応答待ちを取消。元の導入ガイド条件はoriginal-outcome-final.mdで別途検証 |
| 実記録でreview待機の非ブロック化 | PASS | completion-final-contract-tests.log、8 passed、exit0 |
| 型検査/build | PASS | completion-storage-build.log、exit0 |
| 実容量不足時の日本語案内・入力保持・開始なし | PASS | 450MiBの検証専用APFS疎ディスク上に実サーバー8800を起動。実503/UI復帰案内/入力保持/実run0件を確認。completion-storage-volume-browser.log、storage-volume-result.json。実PCの空き容量は圧迫せず、試験用volume/imageは終了後除去 |
| 人間初見評価/実IME・実iPhone | BLOCKED | 人間/実機による実施が必要、AIの成功で代用しない |

実行コマンドは artifacts/product-quality/commands.jsonl。対象HEADと未コミット差分hashは completion/revision.json。`python3 artifacts/product-quality/run-command.py completion-final-contract-tests backend/.venv/bin/python -m pytest backend/tests/test_peer_communication.py backend/tests/test_text_delivery.py -q`、buildはwrapper `completion-storage-build pnpm --dir frontend build`。ブラウザーscriptsはfrontend cwdの同wrapperでnode実行。

途中のコマンド失敗: package __main__なしの起動指定、試験scriptのcwd誤り、接続設定detailsを開かずボタンを待ったタイムアウト。これらは試験操作の誤りでありプロダクトの合否と区別。修正前のログも保持。独立報告: document-language-independent.md。

追加検証: completion-measured-count-tests 9 passed、completion-schema-compatibility 3 passed（過去JSON納品、実別プロセスの正規表現上限、実private listenerへのschema参照拒否）。frontendのliteral schema 2 passed、1440/390条件欄keyboard/reload/axe0/横overflowなし。build/typecheck exit0。lint exit0、既存effect関連の警告あり。

元の400〜700字の導入ガイド課題はこの300〜600字の紹介文試験で置き換えない。[元条件の最終検証](original-outcome-final.md)で、元の依頼文と480秒/30呼出/出力1800トークンの条件を維持する。

最終追試: completion-adapter-runtime-testsは実記録/実ファイルを使う9件PASS、exit0。completion-final-python-compileもexit0。通常UI8796は稼働中の作業がないことを確認して新コードで再起動し、依頼画面と既存runの表示、pageerror0を確認。証拠refreshed-user-ui.json/png（画像も目視確認）。Ollamaの通常sampling設定はモデル側を尊重し、probeのみtemperature0。

文書toolへの文字数条件提示（公開契約の追加/緩和ではなく生成ヒント）も実装。出力pathを単一の依頼先に限定して提示し、他の作業で共有TOOL_SPECSを書き換えない。completion-advertised-contract-testsは9件、path提示を追加した後のcompletion-document-tool-path-testsは関連6件、どちらもexit0。実モデルの内容・完遂評価はoriginal-outcome-final.mdを参照。
