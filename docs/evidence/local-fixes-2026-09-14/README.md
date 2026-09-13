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
- **レビュー後の状態**: failが0でもunverified/blockedが残ればpartialとして保存。未検証をacceptedにしません。
- **小型モデルへの説明**: `finish_task` のverifiedは文字列配列でありreview結果のオブジェクトではないこと、Reviewerのrun_checkは制作担当のworkspaceではなくartifactのid/revisionを指定することを明記。
- **長時間試験**: 接続probeで変化するメタデータを確定してから設定fingerprintを保存。`STOP`ファイルで実行中の1件を完了させてから停止できます。

## 回帰テストのデータ

新しいダミー応答は追加せず、既存の実行記録を使っています。

- `pilot-team.json`: 旧doc-email予備試験の実計画。
- `research-team.json` / `research-single.json`: 修正前の実計画と限定したイベント。取得ページの本文は省略。teamのPython課題は実行途中に取得した診断スナップショットで、最終状態はbaseline-results.jsonを参照。
- `unverified-review.json`: 公開済みresearch2実行のレビューイベントseq 50と計画。実DBとSchedulerへ再生し、未検証がpartialとして保存されることを確認。

修正後の実モデル予備試験と、本試験300件（50課題×3回×2方式）は別に保存します。未完了や不合格を合格数へ算入せず、代表業務の同一条件10回やL2/L3の達成もこの試験で代替しません。
