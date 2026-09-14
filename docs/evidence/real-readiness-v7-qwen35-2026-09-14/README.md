# 実資料ワークフロー証跡 v7（qwen3.5 / 2026-09-14）

Builder/Reviewerの短い修正ループを含む固定checkout `879886a2836904890ef06a482b588c912cde6382` で、実際のローカルOllamaモデル `agentteam-qwen35-9b-16k` を使った10回目標の系列を開始した。能力プローブは `tool_calling=true`、`json_schema=true` で通過した。

初回計画はReviewer依存条件を満たさず拒否され、Masterが再生成した計画を受理した。Builderは初版から4つのrevisionを実際に公開した。r1では禁止語を含み、r2〜r4では禁止語を除去できたが、監査領域の必須語「監査者」「カーソル」が不足し、機械検査がすべて不合格にした。Reviewerは未実行のまま、実行を強行せず停止した。

## 実測

| 項目 | 結果 |
| --- | --- |
| run | `run_1a09e2c8e6e8728c32a` |
| モデル | `agentteam-qwen35-9b-16k` |
| モデルdigest | `c1b119d707b9016f93889584506a196e67ecc37db2ccb625c6df61111c0b7866` |
| probe | tool calling / JSON Schema ともに pass |
| 公開revision | r1〜r4（すべて契約不合格） |
| revision SHA-256 | r1 `870c273b25c396a391df60ba63b4a6e19af1e2215863a79212de3c64c0045fa2`、r2 `c0bb7b06ff2b7738286222d9fece998d4ad08950875442b1ec18aae4ec93ea3e`、r3 `59367526f39e85fbae945980090142dc7c3e54e3bdb10c8026e4c9151e4ce1d3`、r4 `900697fcd6c52bde376106c7afec7278d1cf4a7b4373569517719965edec1461` |
| 終了状態 | `stopped`（Builder中断、Reviewer未実行） |

10回の反復条件は1回目の途中で停止したため、L1の再現受入数には算入しない。生成契約を緩めず、必須語を明示するBuilder指示を追加した次の固定checkoutで再試験する。L2、L3も未達である。

## 収録ファイル

- `fingerprint.json`、`probe.json`、`goal.txt`、`delivery-requirements.json`、`status.json`: 固定条件と停止状態
- `01-run_1a09e2c8e6e8728c32a/`: 50件のイベント、実行メタデータ、r1〜r4の全アーティファクト、workspace最終状態
