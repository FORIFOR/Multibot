# 実資料ワークフロー証跡 v6（qwen3.5 / 2026-09-14）

強化した依頼者契約を固定したcheckout `ae9d409dfea0b6c5cc7c982f5842183efffb9b87` で、実際のローカルOllamaモデル `agentteam-qwen35-9b-16k` を使った系列を開始した。能力プローブは `tool_calling=true`、`json_schema=true` で通過した。

1回目のBuilder実行では、初版が英語の原文を `remaining` にコピーしたため機械検査が不合格になった。Builderがworkspace上の修正版を作り、同じ契約を手動評価では満たしたが、修正版を公開する前のmodel callが `max_tokens` で停止し、Ollama接続が長時間継続した。実行を強行せず、キャンペーンを停止した。Reviewerは未実行で、L1の反復受入数には算入しない。

## 実測

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e1c3c4b734f3807` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| probe | tool calling / JSON Schema ともに pass |
| 公開revision | r1（契約不合格） |
| 公開r1 SHA-256 | `ef53836505a60e52f225f0a1f8b74b07a9e502452f3ffb73f6a0d531fc414999` |
| 終了状態 | `stopped`（Builder中断、Reviewer未実行） |

`workspace-readiness.json` は修正候補を含むが、Reviewerによる独立受入と再公開の事実がないため成功扱いにしない。L1の10回再現、L2、L3は未達である。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`、`status.json`: 固定条件と停止状態
- `01-run_1a09e1c3c4b734f3807/`: 全イベント、実行メタデータ、公開r1、workspace候補

この停止で得た失敗（英語原文コピー、公開前の長時間model call）は次のv7/v8のBuilder修正ループ改善に反映した。
