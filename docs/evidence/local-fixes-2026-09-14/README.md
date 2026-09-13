# ローカルLLMの実行結果から行った修正

2026-09-14。モデルはインストール済みQwen2.5 7Bの16K構成を継続使用。推論はOllamaのループバック接続のみで、Claudeへの切替はありません。

## 修正の根拠

旧比較試験は4件で停止しました。最後の実行が終わるのを待って停止し、結果は削除していません。

| 課題 | team | single |
| --- | --- | --- |
| research-3repos | completed / 自動採点合格。ただし独立レビュー0件 | failed / 成果物なし |
| research-py313 | partial / 自動採点不合格 | failed / 成果物なし |

[全4件の結果](baseline-results.json)。この4件や予備試験だけでteamの品質優位は主張しません。

## 修正内容

- **独立レビュー**: 新規の標準設定とローカルteam設定は `defaults.require_independent_review: true`。Master/Reporterが制作を兼任する計画、最後の成果物にレビューがない計画を拒否。途中の計画変更でレビューが抜けてもrunをcompletedにしません。既存設定でこのキーがない場合は従来どおり任意レビューなので、必要に応じて明示的に有効化します。single比較設定はレビューなしを維持します。
- **連続無操作の判定**: モデルがツールを使ったら「ツールを使わず応答を終えた回数」をリセット。以前は離れた3回が累積し、作業を再開していても打ち切っていました。
- **ツール引数**: 実際に発生した `workspace_write` のcontent欠落などをJSON Schemaで検証。KeyErrorではなく、誤った引数の位置と型を返します。拒否・未発見はログでも `ok: false` にします。
- **成果物の所有権**: 修正途中の予備試験で、Reviewerが制作担当の `email.md` を別revisionとして上書きした実例を確認。公開パスは制作タスクに所属させ、別タスクからの上書きを拒否します。途中で追加するReviewerにも依存先を必須にします。
- **レビュー後の状態**: failが0でもunverified/blockedが残ればpartialとして保存。未検証をacceptedにしません。
- **小型モデルへの説明**: `finish_task` のverifiedは文字列配列でありreview結果のオブジェクトではないこと、Reviewerのrun_checkは制作担当のworkspaceではなくartifactのid/revisionを指定することを明記。
- **長時間試験**: 接続probeで変化するメタデータを確定してから設定fingerprintを保存。`STOP`ファイルで実行中の1件を完了させてから停止できます。

## 回帰テストのデータ

新しいダミー応答は追加せず、既存の実行記録を使っています。

- `pilot-team.json`: 旧doc-email予備試験の実計画。
- `research-team.json` / `research-single.json`: 修正前の実計画と限定したイベント。取得ページの本文は省略。teamのPython課題は実行途中に取得した診断スナップショットで、最終状態はbaseline-results.jsonを参照。
- `unverified-review.json`: 公開済みresearch2実行のレビューイベントseq 50と計画。実DBとSchedulerへ再生し、未検証がpartialとして保存されることを確認。

修正後の実モデル予備試験と、本試験300件（50課題×3回×2方式）は別に保存します。未完了や不合格を合格数へ算入せず、代表業務の同一条件10回やL2/L3の達成もこの試験で代替しません。

## 修正途中の予備試験

`doc-email` は366秒でpartialとなりました。自動採点は5/5ですが、Reviewerの終了引数エラーと成果物上書きが発生したため成功実績には数えません。[結果](intermediate-result.json)と[該当操作の実記録](intermediate-pilot.json)を保存し、所有権の回帰テストに使用しています。この実行には後から加えた引数説明・所有権修正は含まれません。

## 固定版f5de45fでの再検証

[実モデル2件の結果](fixed-qwen25-results.json):

| 課題・方式 | Runtime状態 | 自動採点 | 残った問題 |
| --- | --- | --- | --- |
| doc-email / team | partial | 0/5 | Builderが入力の理解を理由にblockerを報告。独立レビュー未提出の理由をrunへ記録 |
| research-py313 / single | completed | 3/5 | 途中打切りを越えて保存したが、出典URLとJITの記載が欠落 |

7Bモデルでの業務完了はまだ安定していません。Runtimeのcompletedは品質採点の合格と別であり、後者の不合格も記録しています。修正だけで品質改善が証明されたとは主張しません。

追加で[Qwen3.5 9Bの別試験](../local-qwen35-9b-2026-09-14/README.md)を準備しています。短い接続probeで推論出力だけが上限に達する実例に対応し、Ollama接続に `ollama_thinking: false` を指定可能にしました。未指定は従来どおりサーバー既定です。推論本文を証拠として公開せず、回答・終了理由・トークン数だけを記録します。
