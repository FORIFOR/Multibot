# 公開サイトと初回依頼画面の品質改善

2026-10-02。Awwwards / Webby Awards / FWAで受賞を狙える完成度を目標に、実装→実画面→別担当の批評→修正を反復した記録。[品質基準](../../design/AWARD_QUALITY.md)は公式基準を参照するが、自分の点数で受賞水準や完成サービスを認定しない。**一般公開・L3・業務品質・人間受入は未達のまま。**

基点は `32acf39072c4e43a15ea0ca9ae1ff476ec0d11bb`。ローカルの実測はその上の未コミット差分で行ったため、基点SHAだけを評価対象とみなさず、各JSONのソースSHAと公開manifestを照合する。保存時刻はUTC、作業日はJST。全試験で新しいLLM呼出しは0件。

## 変更と反復

既存の紙色・墨色・赤い主操作・形キャラクターを維持し、公開サイトとアプリの表現を揃えた。公開サイトの主導線は、実際の指摘を選んで保存原文の前後を読み、未確認事項を知り、利用開始方法へ進む流れ。スクロールで本文を隠す演出や動画の自動再生に依存しない。初回依頼は資料添付と貼付を常時見せ、依頼欄のラベル・送信先・見積り上限・主操作を近づけた。

| 回 | 観測した欠点 | 修正／判定 |
| --- | --- | --- |
| 変更前 | クラウド利用時にもPC内だけと読める説明、実アプリと異なる画像、小画面の細かい動画、スクロール演出で本文が見えない時間 | データ送信条件を正確に記述し、実Chromeの現在の画面へ交換。本文は最初から可読にした |
| site round 1 | 画像が小さい、携帯幅で主要nav不足、F-ID折返し、重要注記が小さい、英語の原文説明不足 | 小画面専用の実画像・原寸リンク・nav・文字・英語の変更説明を追加。機械検査109 PASS / 22 FAILは**検査側の誤検出**で、旧結果を残し検査を修正した |
| site round 2 | 178 PASS / 5 FAIL。英語390幅と拡大条件でGitHubリンクが実際にはみ出す。同じ原因の5条件。英語captionとリンクも連結 | headerの折返しと間隔を修正、原寸リンクを別行へ。独立画像レビューの「重大欠陥なし」は横幅測定の代用にならなかったことも記録 |
| site round 3 | 18条件 / 183 PASS / 0 FAIL / 0 UNVERIFIED | 前回のはみ出し・captionを解消。追加静的レビューで検査runnerの終了処理に期限がない箇所を発見し、検査自体も修正 |
| site round 4（最終） | 18条件 / 185 PASS / 0 FAIL / 0 UNVERIFIED、ソース不変 | 終了処理を含む最終runnerで全条件再確認。追加2項目は全条件完了と所有Chrome終了の確認で、製品品質の点数増加ではない |
| app | 同じ実資料を添付すると1440×900で依頼ボタン下端が1035.25pxにある | 820.89pxへ移動。ボタンを隠して収めず、既存の入力保持・主体分離を維持。320/390/768/1440と実Chrome200%を確認 |

最終回の機械結果は [site-final-audit.json](site-final-audit.json)、画像・独立批評は [site-final-review.md](site-final-review.md)、検査runnerの原本は [site-final-runner.mjs](site-final-runner.mjs) に保存した。独立画面確認はround 3で行い、サイトbytesを変えず検査runnerだけを改善したround 4と照合している。機械検査は表示・操作を確認するもので、デザインの受賞可否を決める点数ではない。

## 証拠を読む

- [変更前の公開サイト](site-baseline-ja-1440.png)／[独立レビュー](site-baseline-review.md)
- [最終公開サイト 大画面](site-final-ja-1440.png)／[日本語390幅](site-final-ja-390.png)／[英語390幅](site-final-en-390.png)／[日本語全体](site-final-ja-full.png)
- [round 1 原結果](site-round1-audit.json)／[検査側誤検出の説明](site-round1-review-note.json)／[独立レビュー](site-round1-review.md)
- [round 2 原結果](site-round2-audit.json)／[実overflow画像](site-round2-en-390-overflow.png)／[独立レビュー](site-round2-review.md)
- [round 3 原結果](site-round3-audit.json)
- [実Chrome異常停止時の失敗記録](site-browser-interrupted.json)／[終了確認](site-browser-interrupted-cleanup.json)
- [アプリ変更前](app-before-1440.png)／[同じ実資料での変更後](app-after-1440.png)
- [アプリの実操作・200%・限界](app-review-summary.json)／[実ブラウザー測定](app-browser-checks.json)／[独立画像確認](app-independent-review.json)
- [実Chrome200% 上部](app-browser-200-top.png)／[依頼操作](app-browser-200-action.png)
- [実サービス統合](service-integration.json)／[実HTTP・SQLite受付](service-admission.json)／[応答境界](service-responses.json)

公開用アプリ4画像は [export manifest](app-export-manifest.json) の実キャプチャを加工せずコピーした。実 `docs/quality/integration.md` を添付した未送信の依頼であり、架空の完成成果物ではない。携帯幅の画像は入力と操作までスクロールした実viewport。技術operator、実loopback送信先、見積り上限を表示し、顧客や公開環境を装っていない。

公開サイトの修正例は保存済み `docs/evidence/scenarios/research2` の行とセルを生成時に抽出する。原文・SHA・未検証範囲を表示する。**過去のClaude Codeによる記録であり、現在のローカルQwen品質や本番受入の証明には使わない。** 旧合成50課題の比較値はこのサイトの品質証明から除いた。原記録は保持している。

## 検査条件

公開サイト: 実Chrome、JA/EN、1440/768/390/320、720pxリフロー、CSS zoom2と全computed font×2の追加ストレス、JSなし、reduced motion。実Tab/Enter/Spaceによる2導線、保存原文3組の選択、FAQ、実clipboardの公開コマンドSHAを確認。問い合わせは入力・送信しない。no-JSはフォームをdisabledにし、受付できない旨を表示する。ソース変更／配信bytes混在は計測無効。

アプリ: 実uvicorn・新規SQLite・実発行operator鍵・実資料・ビルド済UI。資料追加/削除/再読込/破棄/言語切替、実package.jsonの拡張子拒否、空依頼の無効化を確認。実ブラウザー200%は専用profileのzoomを設定し、outer1440 / inner720 / DPR2 / CSS zoom1を確認した。通常スクリーンショットが空白になった試行は採用せず、実ブラウザーのCDP captureから保存した。サイトのCSS拡大検査とは区別する。

サイトaxeの10回の走査は自動違反0。未確定として残った装飾矢印2箇所は、別担当が実computed色と透明な祖先をたどった背景を取得し、通常日英・英語文字×2で追加確認した。CTAの矢印/主ラベル5.33:1、下部の矢印/補助ラベル6.08:1。[計算・観測](site-final-contrast.json)と画像の独立確認を残す。これは該当箇所への補足であり、全面WCAG適合や実読み上げの受入ではない。

実サービスの既存境界も最終UI bundleで再確認した。実HTTP/SQLite受付8、応答境界9、Chrome主体分離・再読込再送・並行ログイン・peerタブ離脱の全6段階が通過。終了後は所有Chrome残留0、検証API停止。TypeScript/build・配布bundle一致は通過、lintは終了0だが既存警告あり。

CIは実HTTP/SQLite/Chromeの既存jobに公開ページ生成整合と実ブラウザー検査を追加した。模擬providerや合成業務データは使わず、失敗時の画像・JSON・runnerだけをartifactに残す。認証鍵・DB・privateログはアップロード対象外。CI合格と業務品質を混同しない。

検査runnerにはレスポンス取得と終了処理の期限を設けた。終了失敗を記録しても最終JSON保存へ進み、残る場合は所有Chromeだけを止める。実Chromeを最初のページ取得後に強制終了する別試験は1/18条件・5 FAIL・終了1を保存し、専用profile削除・所有process group残留0を確認した。**これは正常なサイト確認の成功件数に足さない。** 異常を検出して証拠を残す経路の確認であり、OS全体停止でも必ず保存できるという保証ではない。

## 未達・次の反復

- 初回資料欄のnative未選択表示と添付済み一覧の役割を明確にする。選択値の偽装はしない。
- 作業一覧から終了済み成果物へ戻る動線、本文→確認→採用→保存の優先度を実記録で撮影して改善する。静的候補を実画面で確かめる前に達成扱いにしない。
- ログイン、実行中、問題発生、再接続、結果・保存画面にも同じ反復を適用する。
- 物理モバイル、ソフトキーボード、日本語IME、スクリーンリーダー、初見の第三者、実公開配信の性能は未受入。axe違反0はWCAG全面適合ではない。
- localhost性能は条件を記した単発ラボ値。変更前の自動性能測定はなく、速度改善率・field p75・INPを創作しない。
- 完成例なし実資料業務の10回、公開先/TLS/実IdP自己登録、費用と運用責任、負荷・復旧・独立セキュリティ審査は別途未達。AIによる独立レビューを人間受入と呼ばない。

private原保存先: `~/.cache/agentteam-bench/award-craft-20261002` と `~/.cache/agentteam-bench/app-first-request-craft-20261002`。失敗・不適切な計測・途中画像も原保存先に保持する。ここへは名前を指定した公開可能な証拠だけをコピーする。
