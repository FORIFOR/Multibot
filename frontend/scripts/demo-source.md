# Agent Team 製品説明

Agent Team は、自分のパソコンの中だけで動く AI チームです。
ひとつの依頼を受け取ると、まとめ役が作業を分け、作る担当がファイルを作り、別の確認担当がその版を検査します。
利用者は、できたファイルと「どの版を何で確かめたか」の記録を受け取り、使う版を自分で選びます。

## 対応モデル
- Claude Code
- OpenAI 互換 API
- ローカルの Ollama

## インストール
- uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart の1コマンド

## 方針
- 外部にデータを自動送信しません
- 確認が取れていない項目は「未確認」と表示し、通過とは区別します
- 予算の上限を依頼ごとに設定できます
