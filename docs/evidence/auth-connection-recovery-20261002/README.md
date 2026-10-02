# 接続失敗から、その画面で再読込できるようにする

2026-10-02 JST。認証状態の取得に失敗した画面へ、明示的な「再読込して接続を確認」を追加した。接続が確認できるまでは、アクセスキー欄・SSOリンク・作業画面を表示しない。ブラウザーの再読込機能を知らなくても次の操作を選べるようにする改善であり、公開サービス・業務品質・人間受入・受賞水準の認定ではない。

## 観察から変更へ

[変更前の実観察](../auth-initial-recovery-observation-20261002/README.md)では、初回の `/api/auth/status` または `/api/auth/me` の通信遮断後、再読込を促す文と無効なログインボタンが同居していた。遮断解除から5秒待っても状態は変わらず、ブラウザーの再読込を行うとログインできた。原画像・原失敗は同記録に保持している。

`AuthGate` の状態取得失敗を独立した表示にした。操作は利用者による `window.location.reload()` だけで、認証処理の自動再試行は追加していない。取得時の version を保持し、別タブの認証変更・ログアウト・peer待機で無効になった古いボタンは、Reactの再描画前でも同期条件で拒否する。取得開始・セッション終了・明示ログインで失敗状態を解除する。既存の15秒の要求期限、20秒のpeer期限、主体分離、明示的な再ログインを維持する。

対象コードは初回取得だけでなく、認証済みタブが再表示されたときの状態取得にも共通である。後者の実通信失敗からの復帰は今回未実証で、初回の成功をそのまま一般化しない。

## 実画面と独立操作

実AppService・私有SQLite・実発行キー・Chrome 154.0.8037.93を使用。CDP `Network.setBlockedURLs` で要求を実際に遮断し、API応答や画面を差し替えていない。[独立r2の原結果](independent-r2.json)で次を確認した。

| 条件 | 観測 |
| --- | --- |
| 日本語390×844、status遮断 | 再読込をTab/Enterで操作。遮断中は再失敗、解除後は空の有効なログイン画面へ復帰 |
| 英語768×844、me遮断 | 同じ明示操作から実status 200 / me 401を確認 |
| 日本語320×844、status遮断 | 文と操作が横に切れず、自然なTab/Enterで復帰 |
| 日本語、Chrome実200%、me遮断 | outer幅1440 / inner720×412 / DPR2 / CSS zoom 1。操作とfocusが見え、Tab/Enterで復帰 |
| 通常の未認証、実発行後に失効したキー | me 401 / login 401では接続再読込ボタンを出さず、ログイン経路を維持 |
| 既存のpeer離脱試験 | 完了通知なしのタブ閉鎖で20,087ms後、再読込通知ありで77ms後に明示ログインへ。接続再読込ボタンは0件 |

4条件すべてで実operatorのlogin 200と主体・権限一致、空のHomeを確認した。peer試験でも明示ログイン後に空のHomeを確認。AIが操作した試験であり、第三者本人の利用実証ではない。通常401やpeer期限を通信失敗の画面へまとめていない。

- [日本語390の失敗画面とfocus](ja390-status-failed-focused.png) → [明示再読込後の空のログイン画面](ja390-status-signin.png)
- [日本語320](ja320-status-failed-focused.png)、[英語768](en768-me-failed-focused.png)、[実200%](ja-native200-me-failed-focused.png)
- [実装と配布UIの固定SHA](build-manifest-r1.json)、[静的独立レビュー](static-review.json)、[build/lint](build-checks-r1.json)
- [実画面を操作した別担当の批評](browser-independent-review.json)
- [さらに別担当による画像・証拠の批評](browser-evidence-critique.json)と[ローカルCI候補の照合](ci-candidate-evidence-review.json)

実装担当も代表画像を目視した。ブランドと説明・主操作が一画面で読み取れ、focus輪郭や主要操作の見切れはなかった。元の接続失敗時の無効なキー入力フォームが消え、次の行動を一つに絞れた。入力済みキーや業務文書を含む画像は公開していない。

## 失敗と未確認を残す

[独立r1](independent-r1-failed.json)は日本語390の初回回復・実失効キー401・実operator200まで進んだ後、追加した「認証済みタブの再表示」の前提確認で停止した。別タブを前面へ移しても対象タブの `visibilityState=hidden` を10秒以内に得られず、その段階のstatus/me再取得も通信遮断も実行されなかった。試験準備の未成立であり、製品の認証済み復帰失敗と断定しない。原FAIL・画像・私有ログを保全したまま、新しいr2へ初回4条件と既存peer試験を分離した。製品の条件を緩めて通過させていない。

原記録・製品source・配信bundleは各試験中不変。r2のrun/job/model event/artifactは前後すべて0。所有Chromeは本試験33件・peer15件の追跡で残留0、所有APIのtask終了・lock解放・port閉鎖・lifespan終了失敗なしを確認した。旧v62の成果物・採用・キューを操作していない。

読み上げ、実Safari/iPhone、仮想キーボード、SSO、登録・回復、本番障害、認証済みタブ再表示時の下書き復帰、古いDOMボタンを同一イベントループで操作する競合の実行再現は未確認。最後の競合については[静的レビュー](static-review.json)による境界確認のみ。一般的な可用性やセキュリティ受入とは扱わない。

## 継続確認へ組み込む

`auth-initial-recovery.mjs` を既存の実サービス回帰へ追加した。[ローカルの新段階](local-initial-recovery.json)は日英2条件で実遮断、遮断中の再読込、解除後5秒の明示操作待ち、Tab/Enterでの復帰、実発行operatorの認証を確認した。出力は固定の項目名・件数・hash・判定に限り、画面・API本文・秘密・生エラーをCIへ出さない。

[7段階の実結果](local-service-report.json)では既存の受付・権限・主体分離・同じ依頼の再送・並行ログイン・peer期限も通過。5組57件の所有Chrome残留0。API終了観測は `browser_verification_api` の範囲で、admission/responses用APIの全排出まで同じ観測を行ったとは称しない。推論0であり、モデルの品質試験を代替しない。

[保存結果の照合](local-final-verification.json)では、既存admissionのcancelled 1件とresponsesへ取り込んだ過去model記録20件を、新規の推論と区別した。[実在する不適合ファイル参照の負例](negative-reference-verification.json)はChrome/API作業前にexit 1となり、[原FAIL](negative-reference-result.json)の未観測値をnullで保持する。製品の認証エラーを捏造した試験ではない。

新しい初回回復段階のDB件数0と、全段階終了後のDBは分ける。後続の既存再送試験によりbrowser用DBにはrun 2件が保存される。全suiteのDBを空だったとは記さない。

[前版c6e2940のGitHub結果](prior-ci-c6e2940/summary.json)も原結果を変更せず収録した。CI36943859645 / OIDC36943859613は前版の証拠で、この新しい接続回復操作の証明ではない。サイトのaxeには矢印に加えてJA/ENのCSS拡大stressのtextareaもincompleteで、今回の原artifactに色・背景比の測定はない。実アプリのChrome200%や全面WCAG適合へ読み替えない。

実LLMの完成例なし10回は固定983系列のまま未開始。今回の読取ではメモリ推定6,063,996,928 < 8,741,958,113 bytes、空きdisk9.569GiBで独自の10GiB超基準も未達だった。無関係な資源を止めたり基準を変更して開始していない。これは物理的な推論不能や業務品質不合格の実証ではない。公開環境・自己登録・費用/運用責任・業務品質・初見第三者利用の受入を引き続き必要とする。
