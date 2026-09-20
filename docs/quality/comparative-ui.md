# 競合を参考にした操作品質の改善

2026-09-20、ユーザー指定のVoiceOS / OpenClawを公式公開情報で調査。
- https://www.voiceos.com/features/agent : アクション前の宛先/内容確認、背景での長い作業、タスク履歴を公開デモで説明。
- https://docs.openclaw.ai/web/control-ui : 会話の優先読み込み、遅いロード/失敗/Retry、接続とサブエージェントの状態を説明。

上記は公式説明/公開デモの観測であり、契約済みアプリを同タスクで操作した測定ではない。UIの装飾や他社アセットをコピーせず、作業/話者/成果物revisionを結ぶ本製品固有の操作へ適用。

実装前の合格条件:
1. 取得済み実作業一覧を依頼文で検索でき、状態フィルターと組み合わせ可能。検索に外部送信なし。0件からクリアで復帰。
2. 実会話を話者/宛先のBotで絞り込み、本文をそのまま検索。0件から解除できる。絞り込み中は自動追従停止で読書位置を保つ。
3. artifact_refsがある発言から参照した正確な版を1リンクで開ける。新しい版へ勝手に置き換えない。
4. 390/1440px、キーボード、API原文一致、GET以外0、コンソール例外0。

比較判定: 競合の同条件試験・実ユーザー初見評価・成果物生成の安定完了が揃うまで「VoiceOS/OpenClawを超えた」はBLOCKED。ローカル改善のPASSと混同しない。以前からのモデル品質/稼働サーバーへの通信修正適用の課題は別に残る。


## 結果

測定環境: macOS / Chrome153、1440/390px、reduced motion。実ユーザーrunの一覧と過去の実発言1件を使用し、モックの会話なし。候補がない場合の検索入力には本repoの実文書見出しを使用。

| 条件 | 判定 | 証拠 |
|---|---|---|
| 作業検索→reload保持→クリア | PASS | comparative-ui/browser.json、0外部検索送信 |
| 実会話の本文/担当フィルターと0件復帰 | PASS | 原文完全一致、解除で同じ実発言を表示 |
| フィルター中の自動追従停止 | PASS | aria-live offを確認。新着複数件の実受信は未実施 |
| 横溢れ/例外/変更送信 | PASS | 1440/390横溢れ0、pageerror0、GET以外0 |
| 会話領域axe A/AA | PASS | 違反0。全製品の適合宣言ではない |
| build/typecheck/lint | PASS | buildとlint exit0。lintの既存警告あり |
| artifact_refsリンクの実クリック | BLOCKED | 配信中の実発言にrefsなし。正確なrevision URL生成は静的確認、リンク追加だけで実測扱いしない |
| 競合より優れていること | BLOCKED | 実アプリの同条件比較・実ユーザー評価未実施 |

実行コマンド: repo root `python3 artifacts/product-quality/run-command.py comparative-ui-final-build pnpm --dir frontend build` と同wrapper `comparative-ui-lint pnpm --dir frontend lint`。frontend cwd `python3 ../artifacts/product-quality/run-command.py comparative-ui-browser node scripts/comparative-ui-check.mjs`。すべてexit0。

公開参考ページをChromeで開き画像を目視した。VoiceOSはLP先頭の大見出し/デモ動画、OpenClawは文書のナビと説明。これを実アプリのUI操作試験や同じ状態での美的比較と呼ばない。参考画像/取得結果と実装後画像は `artifacts/product-quality/comparative-ui/`、第三者画像を製品へ同梱していない。

最終確認: `comparative-ui-reviewed-build`（build/typecheck）、`comparative-ui-reviewed-browser`（上記browserコマンド）、`git diff --check` はexit 0。配信assetsへ最終ビルドを反映。artifactRawUrlのpath各要素を防御的にURLエンコードした（生成IDでの不具合再現はない）。対象HEADと未コミット実装・配信assetsのSHA256は `artifacts/product-quality/comparative-ui/revision.json` に記録。
