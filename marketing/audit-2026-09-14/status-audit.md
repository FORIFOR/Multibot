# Agent Team / Multibot 公開・発信・成果 現状監査

- `project_id`: `multibot`
- 対象プロジェクト名: ユーザー指定がプレースホルダーだったため、現行リポジトリと公開ページに一致する **Agent Team（リポジトリ: FORIFOR/Multibot）** を対象とした。
- 調査基準日時: 2026-09-14 23:57 JST
- 調査範囲: リポジトリの現行 `main`、公開HTML/API、公開SNSページ、公開記事、公開GitHub PR・Release。読み取りだけを行い、投稿・返信・いいね・フォロー・登録・問い合わせ送信・設定変更・コード変更・デプロイは行っていない。
- 判定語: **確認済み**=公開ページ/APIで現在確認、**資料記載のみ**=リポジトリ内の運用記録だけ、**一部確認**=URLまたはアカウントは確認できるが本文・数値などが取れない、**未確認**=存在や接続を確認できない、**取得不可**=アクセス制限等で取得できない。空欄の数値は0ではない。

## 1. 現状の要約

現在、プロジェクトは [GitHubリポジトリ](https://github.com/FORIFOR/Multibot)、[GitHub Pages英語版](https://forifor.github.io/Multibot/)、[日本語版](https://forifor.github.io/Multibot/ja/)、[Zenn記事](https://zenn.dev/forifori/articles/agent-team-launch)、[dev.to記事](https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a)、[Xの `@forifori_dev`](https://x.com/forifori_dev)、[Facebookページ `foriforapps`](https://www.facebook.com/p/foriforapps-61593966556275/) で公開状態を確認できる。XのローンチスレッドとFacebookリールは、URLと発信元までは確認できたが、Xは一部投稿がログイン・年齢制限画面になり、反応数値を取得できなかった。TikTokは運用資料に投稿記録があるが、公開アカウント・投稿URLを確認できない。

発信は個人共用のX、Zenn、dev.to、GitHubアカウントと、複数の自作アプリを紹介するFacebookページから行われている。主な誘導先はGitHubとGitHub Pagesで、ページにはローカルOllama、Claude Code、OpenAI互換接続を使うQuickstart、実行記録、成果物、非公開相談フォームがある。Facebookリールには `utm_source=facebook&utm_medium=social&utm_campaign=real_workflow_20260914` が確認できるが、他の公開記事・X URLには同様のUTMを確認できない。

外部成果として公開APIで確認できるのは、GitHub **Star 1、Fork 0、公開Release 3件、Release添付ファイルのダウンロード合計4件**、Zenn記事 **いいね1・コメント0・ブックマーク0**、dev.to記事 **公開リアクション0・コメント1** である。これらはアカウント全体のフォロワーやページ全体の閲覧数ではなく、取得時点の公開値である。Xのフォロワーはアカウント全体で1、Facebookページは公開OG情報で「いいね1件・4人が話題」と表示されたが、いずれも本プロジェクトへの帰属値ではない。

GitHub Pagesの訪問者数・流入元・CTAクリック、X/Facebook/TikTokの表示回数・動画再生・保存、インストール人数・アクティブユーザー・継続利用、問い合わせ・商談・有料契約・売上は確認できない。サイトの現行JavaScriptにはイベント／問い合わせ送信先のコードがあるが、受信済みデータや管理画面の集計は取得できず、フォーム送信も実行していない。したがって、投稿からStar・利用・商談へつながったとは断定できない。

公開ページ自身が「顧客データでの有償PoC、本番SLA、SSO、組織分離は提供済みとしていない」と明記しており、現時点で確認できる状態は **紹介ページ、公開実行記録、OSSの自己ホスト導入案内、個別相談入口** である。有償PoCや本番導入の実績・提供可能性は確認できない。

## 2. プロジェクト基本情報

| 項目 | 目指している状態 | 現在確認できる状態 | 根拠 | 確認日時 |
| --- | --- | --- | --- | --- |
| 集計用固定識別子 | 6プロジェクト横断で一意に管理 | `multibot` を採用（リポジトリ名と衝突しない固定値） | `docs/site/PRODUCT.md` | 2026-09-14 23:57 JST |
| 正式な公開名称 | Agent Teamとして統一 | GitHub、サイト、記事で **Agent Team**。リポジトリ表記は **FORIFOR/Multibot** | [GitHub README](https://github.com/FORIFOR/Multibot)、`docs/site/PRODUCT.md` | 2026-09-14 23:57 JST |
| 旧名称・別名 | 旧名称があれば横断管理 | 旧名称は未確認。別名として `Multibot`、`FORIFOR/Multibot` を確認 | `README.md`、サイトOG・フッター | 2026-09-14 23:57 JST |
| リポジトリ | OSSコードと実行証拠を公開 | `https://github.com/FORIFOR/Multibot`、Public、MIT、main。Star 1、Fork 0 | [GitHub](https://github.com/FORIFOR/Multibot)、GitHub API `repos/FORIFOR/Multibot` | 2026-09-14 23:57 JST |
| 製品の一文 | AIチームが業務を最後まで自動完遂 | 「資料やコードの作成を、レビューまで任せる。AIチームが実メッセージで作成・レビュー・修正し、成果物と検証の経緯を残す」 | `docs/site/PRODUCT.md`、公開サイト | 2026-09-14 23:57 JST |
| 主な想定利用者 | 企業の業務担当、開発者、技術リーダー | 開発者・技術リーダーが主対象、自社の調査→作成→レビュー→修正をAIチーム化したい事業側が副対象 | `docs/site/PRODUCT.md`、サイト本文 | 2026-09-14 23:57 JST |
| 利用者に最も取ってほしい行動 | 問い合わせまたは導入・購入 | 公開ページ上の主CTAは「実例を見る」「自分の環境で使う」「GitHub/READMEを見る」「業務利用の相談」。Starを主CTAにした公開ページは確認できない | `docs/ja/index.html`、`docs/index.html` | 2026-09-14 23:57 JST |
| 現在利用できる状態 | サインアップしてクラウドで利用、または本番導入 | 紹介ページ、実行記録・動画閲覧、GitHubから自己ホスト導入案内、非公開相談フォーム。登録・決済・本番SLAは未検証／未提供表記 | 公開サイト、`README.md`、`docs/STATUS.md` | 2026-09-14 23:57 JST |

## 3. アカウント台帳

| project_id | 媒体 | アカウント表示名 | ハンドルまたは取得可能なアカウントID | プロフィールURL | 種別 | 共用している他のプロジェクト | 用途 | 運用担当 | 投稿方法 | 使用しているツール・実行場所 | 接続状態 | 公開済み投稿の有無 | 最終投稿日時 | 確認状態 | 根拠 | 確認日時 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| multibot | GitHub | horio | `FORIFOR` | https://github.com/FORIFOR | 個人共用 | 公開リポジトリ38件があるが、対応する他製品名の全量は未確認 | コード、README、Release、Issue/PR、実行証拠の公開 | 本人 | Git/local checkoutからのpushと推定。ただし今回の投稿手段は未確認 | Git、GitHub Actions、GitHub Pages | リポジトリ・公開ページ・Releaseは確認済み。管理者認証状態は未確認 | あり | 2026-09-14（commit/Pages更新） | 確認済み（一部運用手段は未確認） | [repo](https://github.com/FORIFOR/Multibot)、GitHub API users/FORIFOR / repos/FORIFOR/Multibot | 2026-09-14 23:57 JST |
| multibot | X | フォリフォリ｜AIと個人開発 | `@forifori_dev` | https://x.com/forifori_dev | 個人共用 | プロフィールはAIと個人開発全般。別プロジェクトの具体名は未確認 | ローンチスレッド、開発・実画面の発信 | 本人 | 不明。リポジトリに `marketing/post_x.py`（X API実装）はあるが、各投稿の実送信手段は未確認 | X公開ページ、リポジトリ内 `marketing/` | プロフィールと投稿URLは確認。現在のAPI接続／ログイン状態は未確認 | あり（URL確認、本文は一部取得不可） | 2026-09-13（運用資料記載） | 一部確認 | [profile](https://x.com/forifori_dev)、`marketing/POSTED.md`、各status URL | 2026-09-14 23:57 JST |
| multibot | Zenn | forifori | `forifori` | https://zenn.dev/forifori | 個人共用 | 同アカウントの他記事3件。別製品との紐付けは未確認 | 日本語の製品記事・開発記録 | 本人 | GitHub連携元の記載は資料にあるが、現在の連携認証は未確認 | Zenn公開ページ、資料記載のGitHub連携 | 記事ページ・著者プロフィールは確認。API／連携設定は未確認 | あり | 2026-09-14（本文更新） | 一部確認 | [profile](https://zenn.dev/forifori)、[article](https://zenn.dev/forifori/articles/agent-team-launch)、`marketing/ZENN-RESEARCH-2026-09-14.md` | 2026-09-14 23:57 JST |
| multibot | dev.to | horio | `forifor` | https://dev.to/forifor | 個人共用 | 同アカウントの他活動は今回未確認 | 英語の製品記事・GitHubへの導線 | 本人 | 不明（API／手動の区別は公開ページから判断不能） | dev.to公開ページ/API | 記事ページと公開APIは確認。編集権限・連携は未確認 | あり | 2026-09-13 JST相当 | 確認済み（投稿手段は未確認） | [profile](https://dev.to/forifor)、[API article](https://dev.to/api/articles/4639808) | 2026-09-14 23:57 JST |
| multibot | Facebook | foriforapps | Page ID `61593966556275` | https://www.facebook.com/p/foriforapps-61593966556275/ | 組織共用 | プロフィールに「Genieをはじめ、自作アプリ」とあり、他製品を含む共用ページ | 実演動画、開発記録、製品導線 | 本人／管理者は不明 | 資料はFacebook Studioからの投稿と記載。現在の投稿方法は未確認 | Facebook公開ページ、リール | ページとAgent Teamリールの公開状態を確認。管理画面・Insightsは未確認 | あり | 2026-09-14（資料記載および公開リール確認） | 一部確認 | [page](https://www.facebook.com/p/foriforapps-61593966556275/)、[reel](https://www.facebook.com/reel/1117648910591001/)、`marketing/POSTED.md` | 2026-09-14 23:57 JST |
| multibot | TikTok | 不明 | 不明 | 不明 | 未確認 | 不明 | short-ja.mp4の投稿と資料に記載 | 不明 | TikTok Studioと資料に記載 | 公開アカウントURL・投稿URLはリポジトリ／公開検索で確認できず | 未確認 | 資料上は2026-09-13早朝 | 資料記載のみ | `marketing/POSTED.md`（「審査中」「誰でも」設定の記載のみ） | 2026-09-14 23:57 JST |

X・Facebookのフォロワーやページ反応はプロジェクト専用値ではないため、6章でアカウント全体値として分離した。Hacker News、Reddit、Product Hunt、Qiita、YouTube、Instagram、LinkedInについては、現行公開ページ・README・運用資料から本プロジェクトの実アカウントを確認できなかった。運用資料にはShow HN／Reddit／Product Huntはアカウント未保有と記載されているが、存在を推測していない。

## 4. ホームページ・公開先台帳

| project_id | 公開先の種類 | 名称 | 正確なURL | 公開状態 | アクセスできるか | ページが伝えている価値 | 主要CTAの文言 | CTAの遷移先 | 利用開始までの手順 | 確認できたリンク切れや導線の問題 | 計測ツール | 計測の状態：コードのみ／設定済み／受信確認済み／未確認 | 確認状態 | 根拠 | 確認日時 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| multibot | 公式ホームページ・日本語 | Agent Team 日本語サイト | https://forifor.github.io/Multibot/ja/ | 公開 | HTTP 200、本文・動画・リンクを取得 | AIが作成・レビュー・修正し、成果物と検証経緯を残す | 実例を見る／自分の環境で使う／業務利用の相談 | ページ内実行記録、`#how-to`、非公開フォーム | READMEでOllama等を準備 → uvx quickstart → 接続probe → ローカルUI。導入は未実行 | 調査対象リンクはHTTP 200。フォーム送信・動画再生終了・受信は未実行 | `portfolio.js` の `window.dataLayer`、Cloud Runのevents/leads送信コード | コードあり。イベント／leadの受信確認なし | 確認済み（一部計測未確認） | `docs/ja/index.html`、`docs/portfolio.js`、`docs/site/ACCEPTANCE.md` | 2026-09-14 23:57 JST |
| multibot | 公式ホームページ・英語 | Agent Team English site | https://forifor.github.io/Multibot/ | 公開 | HTTP 200、本文・動画・リンクを取得 | 複数AIが作成とレビューを分担し、成果物と変更履歴を残す | See a real example／Use it in your environment／Discuss using it at work | ページ内実行記録、`#how-to`、非公開フォーム | READMEで接続準備 → uvx quickstart。導入・登録は未検証 | 調査対象リンクはHTTP 200。フォーム送信・解析受信は未確認 | 同上 | コードあり。受信確認なし | 確認済み（一部計測未確認） | `docs/index.html`、`docs/portfolio.js`、公開HTML | 2026-09-14 23:57 JST |
| multibot | 製品利用画面・デモ | 実行記録と32秒動画 | 各サイトの `#example`、`media/real-walkthrough-ja-silent.mp4` | 公開 | HTMLとMP4のHTTP 200を確認。ライブ製品はホストされていない | 依頼→成果物→指摘→修正→再検証の実データを見せる | 実例を見る／実行画面の動画を見る | ページ内 record.js、GitHub evidence | サイト閲覧だけで確認可能。ライブ実行はREADMEの自己ホスト手順 | 動画は補助資料で、実行の成否はリンク先記録に依存。自動再生なし | `demo_start`、`demo_complete`、`record_finding` | コードあり。今回のイベント受信は未確認 | 確認済み | `docs/record.js`、`docs/evidence/scenarios/research2/` | 2026-09-14 23:57 JST |
| multibot | GitHub | Agent Team / Multibot repository | https://github.com/FORIFOR/Multibot | 公開、MIT、main | HTTP 200 | OSSコード、README、設計、評価、実行証拠、制約を公開 | Website／Quickstart／Starボタン（GitHub標準） | GitHub Pages、README、サイト | cloneまたはuvx → backend依存関係 → AI接続設定 → `agentteam quickstart`。未実行 | Issue表示は0、PRは1。GitHub Insightsの訪問・cloneは未取得 | GitHub標準、Actions、Pages | 公開値は一部受信確認済み（Stars/Forks/Release asset）。Trafficは取得不可 | 確認済み | [repository](https://github.com/FORIFOR/Multibot)、GitHub API | 2026-09-14 23:57 JST |
| multibot | GitHubドキュメント・実行証拠 | Evidence / STATUS / README | https://github.com/FORIFOR/Multibot/tree/main/docs/evidence/scenarios/research2 | 公開 | HTTP 200 | 成功だけでなくpartial・未検証・失敗理由を追跡可能にする | イベント記録／最終報告／評価と制約 | raw/HTMLのGitHubファイル | リポジトリ閲覧のみ。実行にはローカル環境と接続が必要 | 取得対象リンクはHTTP 200。ドキュメントの古い計測説明と現行JSの送信先に差分あり | GitHubページ、サイトイベントコード | コード・資料の記載はあるが外部受信未確認 | 確認済み（一部記載差分） | `docs/evidence/scenarios/research2/`、`docs/site/ACCEPTANCE.md`、`docs/portfolio.js` | 2026-09-14 23:57 JST |
| multibot | 配布ページ・Release | GitHub Releases v0.1.0〜v0.2.1 | https://github.com/FORIFOR/Multibot/releases | 公開、3 releases | HTTP 200、API 200 | パッケージwheel、デモメディアなどを配布 | Releaseのダウンロード | GitHub Release assets | GitHubから対象assetを選択。製品インストール人数は不明 | Source archive／clone数はGitHub Traffic未取得 | GitHub Release asset counter | Release assetの公開ダウンロード数のみ確認済み。利用者数ではない | 確認済み | GitHub API `/repos/FORIFOR/Multibot/releases` | 2026-09-14 23:57 JST |
| multibot | 記事 | Zenn 日本語記事 | https://zenn.dev/forifori/articles/agent-team-launch | 公開 | HTTP 200、公開status、本文、著者を確認 | 実際のpartial実行、レビュー修正、費用、限界、試し方 | 記事内GitHubカード／リンク | GitHub | 記事閲覧→GitHubリンク。登録・Starへの帰属は未計測 | PVは公開HTML/APIで取得できず、記事いいね等のみ | Zenn公開反応 | いいね・コメント・ブックマークは確認。PV・流入・クリックは未確認 | 確認済み | Zenn `__NEXT_DATA__`（article id 650356） | 2026-09-14 23:57 JST |
| multibot | 記事 | dev.to English article | https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a | 公開 | HTTP 200、公開API 200 | 実モデルの作業、イベント記録、制約、導入手順 | Repo／Site + 59s intro | GitHub、GitHub Pages | 記事閲覧→Repo/Site。登録・Starへの帰属は未計測 | PVは公開APIに見当たらず、反応・コメントのみ | dev.to公開反応 | 公開リアクション・コメントは確認。PV・クリックは未確認 | 確認済み | dev.toページ、`https://dev.to/api/articles/4639808` | 2026-09-14 23:57 JST |
| multibot | SNS動画 | Facebook Agent Team reel | https://www.facebook.com/reel/1117648910591001/ | Publicと表示された公開リール | HTTP 200、OGタイトル・本文・リンクを取得 | 32秒で実モデル記録とpartial／未検証を説明 | サイト・GitHub・Starへの誘導（本文） | `https://forifor.github.io/Multibot/ja/?utm_source=facebook&utm_medium=social&utm_campaign=real_workflow_20260914`、GitHub | 動画閲覧→サイトまたはGitHub。クリック・再生・Starは未計測 | Facebook Insights未取得。公開OGに反応数値なし | Facebook公開ページ／Insights | 公開ページ・投稿本文は確認。Insightsと遷移受信は未確認 | 確認済み（一部計測未確認） | [reel](https://www.facebook.com/reel/1117648910591001/)、OG、`marketing/POSTED.md` | 2026-09-14 23:57 JST |
| multibot | 問い合わせ先 | 業務利用の相談フォーム | 英語 `#consult`／日本語 `#consult` | フォームUI公開。送信結果は未検証 | フォーム要素とCloud Run送信コードは取得 | 仕事の内容・確認条件を送り、適用範囲を相談 | 業務利用の相談／非公開で相談する | Cloud Run `api/site/leads`（公開コードに記載） | 入力→同意→送信の想定。今回送信していない | 受信・受付番号・返信・商談への遷移は未確認 | `portfolio.js` の `leads`、`contact_submit` | コードのみ／エンドポイントGETは403。受信確認なし | 一部確認 | `docs/portfolio.js`、`docs/index.html`、`docs/ja/index.html` | 2026-09-14 23:57 JST |
| multibot | 料金・購入 | 料金ページ／決済 | 該当URLなし | 未確認／公開なし | 該当ページを確認できず | MITソフトとAI接続費用の分離説明のみ | 料金・購入CTAなし | なし | 料金・決済導線は未確認 | 料金、購入、課金利用者を確認できない | なし | 未設定 | 未確認 | `README.md`、公開サイトの全リンク確認 | 2026-09-14 23:57 JST |

## 5. 発信履歴・運用状況

対象期間は公開開始から調査基準日まで（2026-09-12〜2026-09-14 JST）。30日未満のため、直近30日と公開開始以降は同じ範囲である。Xの日時・スレッド構成、TikTokの投稿状態、Facebook初回リールの記録は一部が `marketing/POSTED.md` の資料記載であり、公開HTMLで取得できる事実と分離した。

| project_id | 媒体 | 発信アカウント | 投稿IDまたは投稿URL | 公開日時 | 活動の種類 | 内容の要約 | 形式 | 使用言語 | 訴求している価値 | 読者に求める行動 | 誘導先URL | UTMなど追跡情報の有無 | 状態 | 取得できた反応数値 | 数値の取得日時 | 根拠 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| multibot | X | `@forifori_dev` | EN 6投稿: `2098800226199130220`〜`2098800281513570639` | 2026-09-13 00:45 JST（資料記載） | ローンチスレッド | 実メッセージ、revision単位の検証、Runtime制約、Claude/OpenAI互換/Ollama、実行証拠 | 文章＋動画/画像（資料記載） | 英語 | 監査できるAIチーム | GitHub Star、サイト閲覧 | GitHub、GitHub Pages | URL上のUTMなし | 公開済み（URLは確認、本文は一部取得不可） | 取得不可（X公開HTMLに本文・数値がない投稿あり） | 2026-09-14 23:57 JST | `marketing/POSTED.md`、X canonical URLs、`https://x.com/forifori_dev/status/2098800236382900538` 等 |
| multibot | X | `@forifori_dev` | JA 6投稿: `2098800307421716835`〜`2098800362719514927` | 2026-09-13 00:46 JST（資料記載） | ローンチスレッド | 実配送メッセージ、revision検証、Runtime制約、Ollama対応、限界開示 | 文章＋動画/画像（資料記載） | 日本語 | 依頼から成果物・経緯を残すOSS | GitHub Star、サイト閲覧 | GitHub、GitHub Pages | URL上のUTMなし | 公開済み（URLは確認、本文は一部取得不可） | 取得不可 | 2026-09-14 23:57 JST | `marketing/POSTED.md`、X canonical URLs、`https://x.com/forifori_dev/status/2098800317681049772` |
| multibot | X | `@forifori_dev` | `2098924627162792058` | 2026-09-13 09:00 JST（資料記載） | 追加告知 | 追加の短い動画／更新告知と推定されるが本文未取得 | 動画（資料記載） | 日本語 | 未確認 | 未確認 | 未確認 | 未確認 | URL公開は確認、本文・反応は取得不可 | 取得不可 | 2026-09-14 23:57 JST | `marketing/POSTED.md`、X canonical URL |
| multibot | X | `@forifori_dev` | `2098925143389343862` | 2026-09-13 09:02 JST（資料記載） | 追加告知 | 追加の短い動画／更新告知と推定されるが本文未取得 | 動画（資料記載） | 英語 | 未確認 | 未確認 | 未確認 | 未確認 | URL公開は確認、本文・反応は取得不可 | 取得不可 | 2026-09-14 23:57 JST | `marketing/POSTED.md`、X canonical URL |
| multibot | Zenn | `forifori` | https://zenn.dev/forifori/articles/agent-team-launch | 2026-09-13 00:45 JST | 記事公開・更新 | 「3件直っても未完了」だった実行、レビュー修正、未検証、費用、試し方 | 記事・画像・動画リンク | 日本語 | 成功だけでなくpartialと検証限界を見せる | GitHub閲覧／導入 | https://github.com/FORIFOR/Multibot | なし | 公開済み／2026-09-14本文更新 | いいね1、コメント0、ブックマーク0 | 2026-09-14 23:57 JST | Zenn公開HTML `__NEXT_DATA__`、`marketing/ZENN-RESEARCH-2026-09-14.md` |
| multibot | dev.to | `forifor` | https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a | 2026-09-13 00:44 JST（API UTCをJST換算） | 記事公開 | 実作業、実メッセージ、revision検証、実モデルrun、限界と導入手順 | 英語記事 | 英語 | “chatが台本ではなく仕事の記録” | Repo／Site閲覧 | GitHub、GitHub Pages | なし | 公開済み | 公開リアクション0、コメント1 | 2026-09-14 23:57 JST | dev.toページ、`https://dev.to/api/articles/4639808` |
| multibot | Facebook | `foriforapps` | https://www.facebook.com/reel/1117648910591001/ | 2026-09-14 JST（資料記載） | リール公開 | 3ページ比較→レビュー→修正→検証、partialと未検証を32秒で説明。本文にサイトUTMとGitHub | 操作デモ動画 | 日本語 | 監査可能な実モデル作業 | サイト閲覧、GitHub Star | 上記サイトUTM、GitHub | **あり（Facebook UTM）** | Public公開済み（OG本文確認） | 公開ページに反応・再生数なし | 2026-09-14 23:57 JST | Facebook OG/canonical、`marketing/POSTED.md` |
| multibot | Facebook | `foriforapps` | https://www.facebook.com/profile.php?id=61593966556275 | 2026-09-13早朝 JST（資料記載） | 初回リール投稿 | short-ja.mp4とGitHub/Zennリンクの投稿と資料に記載。個別投稿URL・公開状態は未特定 | 動画（資料記載） | 日本語 | 製品実演 | GitHub、Zenn | 資料記載のみ | 資料上は投稿済み | 取得不可 | 2026-09-14 23:57 JST | `marketing/POSTED.md`（公開個別URLなし）、Facebookページ |
| multibot | GitHub Release | `FORIFOR` | v0.2.1 / v0.2.0 / v0.1.0（[releases](https://github.com/FORIFOR/Multibot/releases)） | 2026-09-12〜13 JST | リリース告知・配布 | 実行証拠、再現性記録、Docker sandbox、one-command install等 | Release本文＋asset | 英語 | OSSの導入・再現性 | Release asset取得、リポジトリ閲覧 | GitHub | なし | 公開済み | asset download: v0.2.1 wheel 2、v0.1.0 demo.gif 1/demo.mp4 1、他0 | 2026-09-14 23:57 JST | GitHub Releases API |
| multibot | GitHub community | `FORIFOR` | https://github.com/caramaschiHG/awesome-ai-agents-2026/pull/572 | 2026-09-12（GitHub表示） | awesome-list PR | Multi-Agent Orchestration欄へのAgent Team追加。PRはOpen、レビューなし | PR本文 | 英語 | 第三者リストへの掲載 | PR merge・リスト掲載 | 受け入れ側repo | なし | 公開中／未マージ | レビューなし、採用未確認 | 2026-09-14 23:57 JST | [PR #572](https://github.com/caramaschiHG/awesome-ai-agents-2026/pull/572) |
| multibot | GitHub community | `FORIFOR` | https://github.com/Jenqyang/Awesome-AI-Agents/pull/487 | 2026-09-12（GitHub表示） | awesome-list PR | Multi-Agent Task Solver Projects欄へのAgent Team追加。PRはOpen、レビューなし | PR本文 | 英語 | 第三者リストへの掲載 | PR merge・リスト掲載 | 受け入れ側repo | なし | 公開中／未マージ | レビューなし、採用未確認 | 2026-09-14 23:57 JST | [PR #487](https://github.com/Jenqyang/Awesome-AI-Agents/pull/487) |

**運用状況の集計**

- 確認できた期間: 2026-09-12〜2026-09-14 JST。調査対象は公開開始以降で、30日分の過去履歴は存在しない。
- 公開活動数: X 14 URL（EN/JAローンチ各6＋追加2）、Zenn 1記事、dev.to 1記事、Facebook個別リール1件＋資料上の初回投稿1件、GitHub Release 3件、awesome-list PR 2件。Facebook初回とTikTokは個別公開URLの確認が不足しているため、外部公開件数としては「確認済み」と「資料記載」を分離する。
- 頻度: 2026-09-12〜13に集中。継続的な週次・月次投稿計画の実行は確認できない。`marketing/LAUNCH.md` は計画・下書きを含むが、全計画の実行証拠ではない。
- テーマ内訳: 製品紹介・実演・開発記録・失敗／制約開示・OSS導入が中心。比較記事、役立つ一般情報、顧客事例は確認できない。
- 返信・コミュニケーション: dev.toコメント1件は公開値として確認。Xの返信・Facebookコメント・GitHub外部Issue/PRレビューは、今回取得できた範囲ではプロジェクト成果として帰属できる数値なし。awesome-list PRは本人投稿のみでレビューなし。
- 成功・失敗: 公開に到達した記事、X URL、Facebookリール、Releaseは確認できる。一方、X本文・反応の一部、TikTok、サイト計測、問い合わせ受信は未確認。失敗数を0とはしていない。

## 6. 成果の実測値

「公開したもの」と「外部成果」を分ける。期間列が空欄の行は、過去時点の比較スナップショットがないためであり、0ではない。アカウント全体の値には明記した。現時点の累計・残高は調査基準日時点の公開値である。

| project_id | 対象種別：アカウント／投稿／サイト／リポジトリ／製品 | 対象IDまたはURL | 指標名 | 値 | 単位 | 対象期間の開始と終了 | 数値の取得日時 | データ取得元 | 確認状態 | 補足 |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot | GitHub Star | 1 | star | 現時点残高 | 2026-09-14 23:57 JST | GitHub公開ページ／REST API | 確認済み | 過去7日・30日の増加数は履歴未取得。プロジェクト帰属値 |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot | Fork | 0 | fork | 現時点残高 | 2026-09-14 23:57 JST | GitHub公開ページ／REST API | 確認済み | 0は公開値として確認。過去増減は未取得 |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot | 公開Issue | 0 | issue | 現時点残高 | 2026-09-14 23:57 JST | GitHub公開ページ | 確認済み | HTMLはIssues 0。REST `open_issues_count=1` はOpen PRを含むためIssue 0と分離 |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot | Open Pull Request | 1 | PR | 現時点残高 | 2026-09-14 23:57 JST | GitHub公開ページ／公開Issues API | 確認済み | 本リポジトリのPR #2。外部利用者のPRとは確認できない |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot/releases | 公開Release数 | 3 | release | 2026-09-12〜2026-09-13 | 2026-09-14 23:57 JST | GitHub Releases API | 確認済み | v0.1.0〜v0.2.1 |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot/releases/tag/v0.2.1 | Release asset download | 2 | download | 累計（asset単位） | 2026-09-14 23:57 JST | GitHub Releases API | 確認済み | `agentteam-0.2.1-py3-none-any.whl`。利用者数やインストール成功数ではない |
| multibot | リポジトリ | https://github.com/FORIFOR/Multibot/releases/tag/v0.1.0 | Release asset download | 2 | download | 累計（asset単位） | 2026-09-14 23:57 JST | GitHub Releases API | 確認済み | `demo.gif` 1、`demo.mp4` 1。intro assetsは0 |
| multibot | アカウント | https://github.com/FORIFOR | GitHub followers | 1 | follower | 現時点残高 | 2026-09-14 23:57 JST | GitHub Users API | 確認済み | アカウント全体。Multibot専用に帰属させない |
| multibot | アカウント | https://x.com/forifori_dev | X followers | 1 | follower | 現時点残高 | 2026-09-14 23:57 JST | X公開プロフィールHTML | 確認済み | アカウント全体。プロジェクト帰属不可 |
| multibot | アカウント | https://x.com/forifori_dev | X following | 24 | account | 現時点残高 | 2026-09-14 23:57 JST | X公開プロフィールHTML | 確認済み | アカウント全体 |
| multibot | アカウント | https://x.com/forifori_dev | X投稿数 | 41 | post | 現時点残高 | 2026-09-14 23:57 JST | X公開プロフィールHTML | 確認済み | アカウント全体 |
| multibot | アカウント | https://www.facebook.com/p/foriforapps-61593966556275/ | Facebookページいいね | 1 | like | 現時点残高 | 2026-09-14 23:57 JST | Facebook公開OG description | 確認済み | ページ全体。フォロワー数ではない |
| multibot | アカウント | https://www.facebook.com/p/foriforapps-61593966556275/ | Facebook「話題にしている人」表示 | 4 | people | 現時点表示 | 2026-09-14 23:57 JST | Facebook公開OG description | 確認済み | 定義・プロジェクト帰属は未確認 |
| multibot | 投稿 | https://zenn.dev/forifori/articles/agent-team-launch | Zennいいね | 1 | like | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | Zenn公開HTML `article.likedCount` | 確認済み | 記事単位 |
| multibot | 投稿 | https://zenn.dev/forifori/articles/agent-team-launch | Zennコメント | 0 | comment | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | Zenn公開HTML `commentsCount` | 確認済み | 記事単位。0は公開値 |
| multibot | 投稿 | https://zenn.dev/forifori/articles/agent-team-launch | Zennブックマーク | 0 | bookmark | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | Zenn公開HTML `bookmarkedCount` | 確認済み | 記事単位。0は公開値 |
| multibot | 投稿 | https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a | dev.to public reactions | 0 | reaction | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | dev.to API article 4639808 | 確認済み | 記事単位。0は公開値 |
| multibot | 投稿 | https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a | dev.to comments | 1 | comment | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | dev.to API article 4639808 | 確認済み | 記事単位 |
| multibot | 投稿 | https://x.com/forifori_dev/status/2098800226199130220 | X reactions / views |  | count | 公開2026-09-13〜現時点 | 2026-09-14 23:57 JST | X公開HTML | 取得不可 | ログイン・年齢制限表示で数値が取得できない。空欄は0ではない |
| multibot | 投稿 | https://www.facebook.com/reel/1117648910591001/ | Facebook views/reactions/comments/shares |  | count | 公開2026-09-14〜現時点 | 2026-09-14 23:57 JST | Facebook公開OG／ページ | 未取得 | 公開本文は取れたがInsights数値は未取得。空欄は0ではない |
| multibot | サイト | https://forifor.github.io/Multibot/ja/ | ページ訪問者・セッション |  | visitor/session | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | GitHub Pages公開HTML、ローカルJS確認 | 未取得 | GA等の受信済み集計を確認できない。コードのイベント送信先だけでは数値にならない |
| multibot | サイト | https://forifor.github.io/Multibot/ja/ | CTAクリック（GitHub、Quickstart、相談） |  | click | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | `docs/portfolio.js`、Cloud Run endpoint | 未確認 | `dataLayer`と送信コードはあるが受信データ・クリック数を取得できない |
| multibot | サイト | https://forifor.github.io/Multibot/ja/ | 相談受信・問い合わせ |  | lead | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | `portfolio.js`、Cloud Run endpoint | 未取得 | フォーム送信をしていない。管理画面・受信集計にアクセスしていない |
| multibot | 製品 | https://github.com/FORIFOR/Multibot | 実際の試用人数・登録者・アクティブユーザー |  | user | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | 公開repo、サイト、Release | 未取得 | サインアップ基盤・利用者台帳は公開されていない |
| multibot | 製品 | https://github.com/FORIFOR/Multibot | 外部Issue/PR/フィードバック |  | item | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | GitHub公開ページ | 未取得 | Open PRは1件だが、リポジトリ所有者のPRで外部利用者成果とは確認できない |
| multibot | 製品 | https://github.com/FORIFOR/Multibot | 公開実行の定価換算コスト | 6.07 | USD/run | 2026-09-13の公開実例 | 2026-09-14 23:57 JST | `docs/site/PRODUCT.md`、README | 確認済み | 内部実行の記録。売上・制作費・顧客費用ではない |
| multibot | 製品 | https://github.com/FORIFOR/Multibot | 売上・有料利用者・契約 |  | JPY/user/contract | 直近7日／直近30日／累計 | 2026-09-14 23:57 JST | 公開ページ・repo | 未取得 | 料金・決済・顧客台帳を確認できない |

**期間比較について**: 昨日までの直近7日間・30日間の増減は、過去スナップショットまたは所有者Analyticsがないため、Star・フォロワー・記事反応を推測していない。公開開始日が2026-09-12であり、公開開始以降の実績と調査時点の残高だけを示した。

**内部アクセスの除外**: GitHub公開値、記事公開値、SNS公開値は、内部アクセスを除外した集計かを確認できない。サイト・フォーム・製品利用の数値は受信データ自体を取得できていないため、内部アクセスを除外できていないのではなく **未取得** とした。

## 7. 発信から成果までの導線

| 段階 | 存在するか | 利用可能か | 計測されているか | 実測値 | 根拠・状態 |
| --- | --- | --- | --- | --- | --- |
| X/Zenn/dev.to/Facebook → サイト／GitHub | あり | 公開URLはアクセス可能 | FacebookだけUTMを確認。X/Zenn/dev.toはUTMなし。クリック受信は未確認 | X・記事・Facebook本文のURL存在。クリック数は空欄 | 各公開ページ、`marketing/POSTED.md`。投稿が存在してもクリック・Starへの因果は未確認 |
| GitHub Pages → 実行記録・成果物 | あり | HTML、GitHub evidence、動画はアクセス可能 | `record_finding`等のコードあり。受信集計は未確認 | 公開実行記録1件、リンクHTTP 200 | `docs/record.js`、`docs/evidence/scenarios/research2/`。一例を成功率とみなしていない |
| GitHub Pages → Quickstart／自己ホスト | あり | README・uvxコマンド公開。導入操作は未実行 | `quickstart_open`／`quickstart_copy`コードあり。受信未確認 | Release asset download 4件のみ。インストール人数は空欄 | `docs/index.html`、`README.md`、GitHub Releases。asset downloadをユーザー利用数にしない |
| GitHub Pages → 非公開相談 | あり | フォームUIと送信コードあり。送信・受付は未実行 | `contact_submit`コードあり。Cloud Run受信・受付番号は未確認 | lead数は空欄 | `docs/portfolio.js`。エンドポイントGETは403、書込みは行っていない |
| 試用 → 継続利用 | 判定不能 | サインアップ・利用者台帳なし | 計測設定・受信データなし | 空欄 | OSS自己ホスト利用を外部から識別できない |
| 試用／相談 → 有償PoC／本番導入 | 公開ページは「未提供・未確認」と表示 | 顧客データPoC、SLA、SSO、組織分離は未提供表記 | 計測なし | 有償利用者・契約・売上は空欄 | 公開サイトのreadiness表記、`docs/STATUS.md`。提供実績を推測しない |

現状の分類は次のとおりである。

- **公開している**: GitHub、Pages、Zenn、dev.to、X URL、Facebookリール、awesome-list PR。
- **発信しているが、見られたか測れていない**: X、Zenn、dev.to、Facebookの多くの表示・再生・クリック。
- **見られていることを一部確認できる**: 公開記事の反応値、GitHub Star/Fork/Release assetの公開カウンタ。
- **クリック・利用・継続・事業成果**: 帰属可能なデータがなく判断不能。
- **未公開／未確認**: TikTokの公開投稿URL、料金・決済、サインアップ、利用者・顧客導入。

## 8. 未確認事項と取得方法

| 未確認事項 | 現在の状態 | 最小限の取得方法（読み取り） | 今回実行しなかった理由 |
| --- | --- | --- | --- |
| GitHub Pagesの訪問者、流入、CTAクリック | 受信済み集計を取得できない | Cloud Runのイベント管理画面または匿名集計exportを所有者権限で閲覧。期間をJSTで指定 | 管理画面アクセス権がなく、フォームやリンク操作も禁止されているため |
| 問い合わせ受信数、受付番号、商談化 | 未取得 | `api/site/leads` の管理者向け集計または保存DBの匿名集計を閲覧 | 送信・問い合わせ・顧客情報へのアクセスは行わない指示のため |
| Xの各投稿の表示、いいね、返信、再投稿、保存、リンククリック | URLは確認、一部本文・数値は取得不可 | `@forifori_dev` のX Analyticsを所有者が読み取りexport | Xはログイン／年齢制限画面で公開数値を取得できず、操作禁止のため |
| Facebookのリール再生・反応・リーチ・リンククリック | 投稿本文と公開状態は確認、Insights未取得 | `foriforapps` Page Insightsを所有者が読み取りexport | 管理画面権限がなく、公開OGには数値が出ないため |
| TikTokアカウント、投稿URL、審査結果、再生数 | `marketing/POSTED.md`の資料記載のみ | TikTok Studioの投稿一覧で公開URL・公開範囲・審査結果・期間別指標を読み取り | アカウントID/URLが資料にない。アカウント推測やログイン操作を行っていない |
| Zenn・dev.toのPV、流入、GitHubクリック | 記事反応のみ公開。PVは未取得 | 各サービスの著者ダッシュボードで記事別PV・流入を読み取り | 公開HTML/APIにPVがなく、管理画面権限がないため |
| GitHubのStar増加、clone、unique visitor、traffic referrer | Star/Fork/Release asset現時点値のみ | Repository Insights/Trafficを所有者が読み取り、取得時点を記録 | unauthenticated APIがTrafficを401で拒否。トークンをレポートに含めないため |
| 自己ホストのインストール人数、試用、アクティブ、継続 | 未取得 | 任意利用者を追跡しない前提で、公開任意アンケートではなく既存の配布／サポート記録を匿名集計 | 新規登録・問い合わせ・外部ユーザー追跡を行わない指示のため |
| 有償PoC、契約、売上、費用 | 未取得 | 会計・CRM・請求のプロジェクト別集計を読み取り、共有アカウント費用と分離 | 顧客／会計データへのアクセス権がない。根拠なく0にしないため |
| サイト計測コードと資料の不一致 | 現行JSはCloud Run送信先あり、`docs/site/ACCEPTANCE.md`はendpoint未設定と記載 | 現行デプロイの受信ログと、公開commitの対応版を所有者が照合 | コード変更やデプロイを行わず、事実差分だけを記録するため |

## 9. 優先して解消すべき問題、最大3件

1. **成果を帰属できる計測が不足している。** FacebookにはUTMがあるが、サイトイベント・lead受信、GitHubクリック、X/Zenn/dev.to流入の集計を確認できない。現状は「投稿した」「公開ページがある」までは確認できるが、「その投稿でStarや相談が増えた」とは言えない。
2. **媒体・アカウントの台帳が分断され、公開状態の確認粒度が揃っていない。** Xは投稿URLだけで本文・反応が取れないものがあり、TikTokは資料記載のみ、Facebook初回投稿も個別URLがない。共有アカウント全体値と本プロジェクトの値を混同しやすい。
3. **導入後の成果が公開導線から観測できない。** GitHub自己ホスト導入案内と相談フォームはあるが、インストール、継続利用、顧客データPoC、本番契約の実測は未取得である。公開ページ自身もL2/L3を未提供としているため、現段階の外部成果はOSS・記事・公開反応の範囲に限定して報告する必要がある。

---

### 監査に使用した主な根拠

- [GitHub repository](https://github.com/FORIFOR/Multibot)
- [GitHub Releases](https://github.com/FORIFOR/Multibot/releases)
- [GitHub Pages English](https://forifor.github.io/Multibot/)
- [GitHub Pages Japanese](https://forifor.github.io/Multibot/ja/)
- [Zenn article](https://zenn.dev/forifori/articles/agent-team-launch)
- [dev.to article](https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a)
- [X profile](https://x.com/forifori_dev)
- [Facebook page](https://www.facebook.com/p/foriforapps-61593966556275/)
- [Facebook reel](https://www.facebook.com/reel/1117648910591001/)
- [awesome-ai-agents-2026 PR #572](https://github.com/caramaschiHG/awesome-ai-agents-2026/pull/572)
- [Awesome-AI-Agents PR #487](https://github.com/Jenqyang/Awesome-AI-Agents/pull/487)
- ローカル根拠: `README.md`, `docs/index.html`, `docs/ja/index.html`, `docs/portfolio.js`, `docs/site/PRODUCT.md`, `docs/site/ACCEPTANCE.md`, `docs/STATUS.md`, `marketing/POSTED.md`, `marketing/LAUNCH.md`.
