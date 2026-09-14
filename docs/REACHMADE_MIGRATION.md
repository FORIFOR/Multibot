# Reachmade Lab 連携・移行記録

この文書は、Multibot を Reachmade Lab の製品群として案内するための現状記録です。ドメイン移管、DNS変更、ホスティング変更をこのリポジトリから実行した記録ではありません。

## 2026-09-15 JST に確認した公開先

| 役割 | URL | 確認結果 |
| --- | --- | --- |
| 親サイト | https://reachmade.com/ | HTTP 200。`Reachmade Lab` の日本語トップページを取得。 |
| 親サイトの製品一覧 | https://reachmade.com/products/#agent-team | HTTP 200。Agent Team の説明と GitHub・デモへの導線を確認。 |
| Multibot の製品サイト | https://multibot.reachmade.com/ | HTTP 200。`https://forifor.github.io/Multibot/` へリダイレクト後、英語ページを取得。 |
| Multibot 日本語サイト | https://forifor.github.io/Multibot/ja/ | HTTP 200。実行記録、導入手順、問い合わせ導線を取得。 |
| リポジトリ | https://github.com/FORIFOR/Multibot | 公開リポジトリ。製品コード、実行記録、評価資料を確認。 |

同じ確認で、次のサブドメインも応答することを確認しました。各製品の配信元やリポジトリをこのプロジェクトから変更したわけではありません。

- `https://genie.reachmade.com/`
- `https://ai-meeting.reachmade.com/`
- `https://oathra.reachmade.com/`
- `https://aisecure.reachmade.com/`
- `https://multibot.reachmade.com/`
- `https://launchloom.reachmade.com/`

## このリポジトリで反映したこと

- 英語・日本語サイトのフッターに、Multibot 製品サイトと Reachmade Lab の製品一覧へのリンクを追加。
- サイトのコンテンツ仕様に、親ブランドと製品サイトの関係を追記。
- 既存の GitHub Pages URL を canonical として維持。`multibot.reachmade.com` が現在リダイレクトである状態で canonical を先に変更しない。

## まだ確認できていないこと

- `reachmade.com` のDNS・Cloudflare・ホスティング設定を変更できる権限。
- サブドメインごとの配信プロジェクト、デプロイ元リポジトリ、所有者。
- GitHub Pages をカスタムドメインで直接配信するか、現在のリダイレクトを維持するか。
- 6製品を同じドメイン配下へ移す場合のログイン、保存データ、API、計測への影響。

## 次の移行判断

1. Reachmade のDNS・ホスティング管理元を確認する。
2. 各サブドメインの配信元と旧URL→新URLの対応表を確定する。
3. 製品ごとに新URLを公開・動作確認してから、README・SNS・広告のリンクを更新する。
4. 新URLが安定して配信されるまで、現在の GitHub Pages とリダイレクトを残す。

外部サービスへのログイン、DNS変更、公開設定変更、投稿、デプロイはこの記録作成時点では行っていません。
