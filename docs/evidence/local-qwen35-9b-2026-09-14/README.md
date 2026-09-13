# Qwen3.5 9B — 追加のローカル試験

2026-09-14。Qwen2.5 7Bで作業の中断と成果物の不足が残ったため、別候補として追加した実モデルです。旧7B系列、Claude系列の結果とは混ぜません。

- [Ollama公式のqwen3.5:9b](https://ollama.com/library/qwen3.5:9b)から取得。Q4_K_M、取得サイズ約6.6GB。モデル詳細・digestは[model-metadata.json](model-metadata.json)。
- `agentteam-qwen35-9b-16k` にnum_ctx=16384のみを指定。生成パラメータは元モデルの既定を継承。
- 接続の `ollama_thinking: false` は、[OllamaのOpenAI互換API](https://docs.ollama.com/api/openai-compatibility)の `reasoning_effort: none` として送信。
- 同じMacで同時実行1件。team/singleの予算・時間・課題条件は共通。推論はループバックOllamaのみ。公開Web資料の取得はネット接続を使います。

## 接続確認で見つかった問題

128トークンのJSON probeでは、既定の推論出力が上限を使い切り、回答が空になりました。推論を無効にすると6出力トークンでJSONを返しました。[実際のHTTP応答の比較](json-probe-comparison.json)。推論の本文は保存していません。

接続probeはツール呼び出しとJSON出力の双方を実モデルで確認します。これは業務品質の合格ではありません。次にファイル生成・独立レビューを含む予備試験を行い、その結果から採用するかを判断します。

修正後の[接続probe](provider-probe.json)はtool calling / JSON schemaとも合格。回帰テスト72件とfrontend buildも通過しました。設定画面のOllama接続で推論モードを選択でき、設定の保存・再読込を確認しています。

## 同じ構成を起動する

リポジトリ直下から、未使用のデータディレクトリへ設定をコピーします。既に起動したデータディレクトリではSQLite内の設定が優先されるため、既存設定の変更は画面から行ってください。

```bash
ollama pull qwen3.5:9b
ollama create agentteam-qwen35-9b-16k -f docs/config/Modelfile.qwen35-9b
mkdir -p data-local-qwen35
cp docs/config/local-qwen35-9b-team.yaml data-local-qwen35/agents.yaml
backend/.venv/bin/agentteam quickstart --data-dir ./data-local-qwen35
```

これは評価用の設定です。接続確認の成功だけで、本番品質や業務完了を保証するものではありません。実行中に見つかった問題と追加修正は[修正記録](../local-fixes-2026-09-14/README.md)へ残します。

## 初回予備試験（ac8837c、追加修正前）

| 方式・課題 | Runtime | 自動採点 | 時間 | 原文・出典の確認 |
| --- | --- | --- | ---: | --- |
| team / doc-email | completed | 5/5 | 332秒 | 不合格。未知の納期、添付書類への言及、日本語誤記をReviewerが見逃した |
| single / research-py313 | completed | 5/5 | 188秒 | 不合格。補足リンク2件を実HTTP確認すると404 |

[team結果](initial-team-result.json) / [single結果](initial-single-result.json) / [メールの確認](initial-team-quality-audit.json) / [リンクの確認](initial-single-quality-audit.json)。方式間の比較値ではなく、不具合探索の異なる2課題です。自動採点に通っても、人に渡せる品質とは限らないため、この2件を「業務品質合格」とは扱いません。

添付入力・レビュー重複・完了表示を修正したcommit `00bc20fb6e224435349e7be19db7293404e39092`でメール課題を再実行しました。[結果](attachment-fix-team-result.json)は600秒でinterrupted。自動採点5/5でも宛先の取り違えとレビューの過剰判定が残り、業務品質合格にはしていません。上記の原文・出典確認はCodexによる確認であり、人間の評価ではありません。

## 推論有効の予備試験（aaef3eb）

元の依頼の宛先・目的を保持する指示を補ったcommit `aaef3ebfe6715061228898eaf2710e3ffa9ef00f`で実施。モデルと16K設定は同じです。[結果](thinking-team-result.json)は600秒でinterrupted、自動採点5/5、Reviewer呼び出し・レビュー提出0件。計画生成だけで328.8秒かかりました。

[成果物の確認](thinking-team-quality-audit.json)では、A社へのメールなのに宛名が「各位」でA社を第三者として扱う点と、見積に不要な社内情報の混入が残りました。業務品質合格ではありません。時間切れを成功表示しない動作は確認できましたが、理由の欠落と終了イベントの重複が見つかり、[追加修正](../local-fixes-2026-09-14/README.md#時間切れの理由と終了イベント)しました。全76件の回帰テストが通過しています。

## 比較に使う構成

推論有効は今回の600秒枠ではレビューまで到達せず、品質改善の証拠も得られませんでした。そのため、広範囲の比較では推論無効・9B・16K・同時実行1件を使用します。これは本番推奨ではなく、このMac上で実用上の限界も測定するための評価構成です。

50課題×3回×2方式の300件は、修正版 `57f7fe5` を固定した別系列として2026-09-14 03:31 JSTに開始しました。[開始時の状態とfingerprint](campaign-start.json)。開始記録時点では0/300件完了であり、比較結果は未確定です。時間上限600秒、名目予算$6、同じモデル・課題・設定を固定し、失敗と途中成果物も保持します。ローカル推論API料金は$0ですが、電力・端末代は計測していません。基本採点の合格は原文との一致や業務品質の合格とは区別します。旧系列・推論有効系列とは集計を混ぜません。自動フォローは有効で、正常進行中の定例通知は行いません。
