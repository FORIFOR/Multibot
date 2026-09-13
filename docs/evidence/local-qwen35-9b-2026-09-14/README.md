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
