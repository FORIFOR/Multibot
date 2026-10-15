# 文書経路の最終報告の境界

2026-10-02 JST。v62の6回目で、readiness.jsonのレビュー後に追加されたモデル最終報告が、独立WORM保管とアラート配送について原資料の「未受入」を「未実装」と書いた。元の失敗・成果物・報告は保存し、修正後の文章に置き換えない。

## 変更

限定document経路では、依頼された成果物とそのレビュー記録を評価対象とし、終端処理で追加のモデル要約を生成しない。final-report.mdは既存の実行台帳・対象版の検査/レビュー・失敗・未解決の記録から生成する。JSONとreport.generatedにnarrative_policyと省略理由を残す。依頼した文書の生成やレビューを固定文で代替していない。team経路の任意モデル要約は維持する。

画面では過去の報告も含め、モデルによる要約・確認済みとの解釈・未解決点・次の提案を、記録された検査/レビューと別の欄に表示する。日本語/英語でAIの解釈であることを明記し、原文は保持する。

## 検証と制約

backend/scripts/check_document_report.pyが、v62の実1回目(completed)と6回目(failed)の記録を別SQLiteへ再構成し、実RunManager._make_reportを呼び出した。両方で追加モデル呼出0、provider生成0、元依頼成果物のbytes/SHA不変、元の完了/失敗状態不変、narrative=null、JSON/イベント/Markdownの方針一致を確認した。原6回目の誤った主張が保存されていることと、追加解釈なしの報告には新たに加わらないことも照合した。原系列の全参照ファイルは不変。別担当も新規SQLiteで独立再実行し2/2 PASS（independent-replay.json）。両回とも持越し後のモデル呼出残枠はあり、予算枯渇によって追加呼出が抑止された試験ではない。

これは実記録を使う実装回帰である。元run.jsonの最終使用量を引き継ぎ、taskはcheckpointのstatus/attemptを中心に復元するため、当時の実行状態の完全再現でも、モデル呼出削減量・業務品質改善の実測でもない。元10回の失敗は失敗のまま。team経路の新しい実LLM実行は行っていない。

frontend build/lintと配布UI一致を確認した。以下の実ブラウザー確認も実施した。この変更を含む新固定系列の実LLM検証は別途必要であり、一般公開・人間受入・L3達成を意味しない。

## 実ブラウザーでの表示境界

旧v62 rep6の実DBから対象run・task・message・event・artifact・approval・checkpointの行を別の私有SQLiteへ移し、2件の原成果物bytesを保持した。実AppServiceのloopback HTTP、実発行operator鍵とread権限、実Chrome（1440×1000）で日本語・英語を確認した。queued/leased jobは0で、推論・probeは実行していない。

- 初回r1は検証スクリプトがログイン先を `/api/auth/session` と誤記し、通信監査のassertで失敗した。実通信は既存実装の `/api/auth/login` へのPOST 1件のみだった。表示4項目は通過したが、r1全体はFAILとして保持した（[ui-r1-failure.json](ui-r1-failure.json)）。
- 製品を変更せず、検証側のURL前提を直したfresh r2で4/4 PASS。RunViewの検査・レビュー4行と旧AI解釈を分離し、Workroomの旧unresolvedに出自ラベルを表示した。旧summaryとverified 3件・unresolved 5件・next_steps 3件を保持し、誤主張を修正文に置き換えていない（[ui-r2-result.json](ui-r2-result.json)、[ui-browser-checks.json](ui-browser-checks.json)）。
- pageerror 0、追加modelイベント0、provider adapter生成経路の観測呼出0、待機job 0。原DBを含む参照7ファイルのhash、旧報告・成果物bytes、原イベントは不変。起動したAPIとChromeは停止し、port閉鎖と所有Chromeプロセス残存なしを確認した。

日本語: [検査・レビュー](ja-report-evidence.png) / [AI解釈](ja-report-interpretation.png) / [Workroomの確認事項](ja-workroom-notes.png)。英語: [検査・レビュー](en-report-evidence.png) / [AI解釈](en-report-interpretation.png) / [Workroomの確認事項](en-workroom-notes.png)。6画像はAIが実際に開いて見た。人間受入、他画面幅、旧文書の正しさ、新規依頼の完遂はこの確認の対象外。

[ui-source-manifest.json](ui-source-manifest.json)に出典・実装・画像のSHA-256を保存した。公開するJSON/画像について実発行鍵5値のバイト一致、JWT・秘密鍵・GitHub token・Authorization値のパターンを検査し、該当0を確認した（[ui-publication-check.json](ui-publication-check.json)）。私有ログ・DB・設定・鍵・検証スクリプトは掲載していない。この検査は一般的な秘密検出の完全性を保証するものではない。

## CI配置の実資料経路

リポジトリ内の保存v62資料を `--source` に指定したローカル実回帰も2/2 PASS（[ci-path-replay.json](ci-path-replay.json)）。CIが参照する配置でも同じ原資料から実SQLite再構成が動くことの確認であり、GitHubジョブの成功記録や業務品質合格ではない。追加モデル呼出は0で、上記の部分復元・最終使用量持越しの制約も変わらない。
