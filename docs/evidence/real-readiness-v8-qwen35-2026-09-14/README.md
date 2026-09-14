# 実資料ワークフロー証跡 v8（qwen3.5 / 2026-09-14）

必須語をBuilder指示へ明示した固定checkout `1e84e98f3cb2a7544e31db54e5077e6fb40a9a8b` で、実際のローカルOllamaモデル `agentteam-qwen35-9b-16k` を使う10回目標の系列を開始した。能力プローブは `tool_calling=true`、`json_schema=true` で通過した。

初回計画は受理された。Builderは初版 `readiness.json` を公開したが、Data領域に英語の `stale`、監査領域に禁止される「アクター監査」が混入し、強化契約が不合格にした。修正呼出しは同じ長い契約説明を繰り返して `max_tokens` に達し、ツール呼出しなしの状態を繰り返した。Runtimeは不合格成果物を自動成功へ変換せず、Builderをpartial、Reviewerをcancelledとして停止した。

## 実測

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e3b8bfb36ff125e` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| probe | tool calling / JSON Schema ともに pass |
| 公開revision | r1（契約不合格） |
| r1 SHA-256 | `be23007e57cafb36e6f45a5c912bf8e62c48ad0fcd837a04ffd5b721c63f89b1` |
| 終了状態 | `stopped`（Builder partial、Reviewer cancelled） |

1回目の途中で停止したため、10回のL1反復条件には算入しない。L2、L3も未達である。英語語彙と日本語訳の契約を矛盾なく扱えるよう、次系列では入力の要約と修正フィードバックを短くする変更を検討する。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`、`status.json`: 固定条件と停止状態
- `01-run_1a09e3b8bfb36ff125e/`: 43件のイベント、実行メタデータ、初版アーティファクト、workspace状態
