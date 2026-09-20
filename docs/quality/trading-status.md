# 株式アプリ検討チーム：現在の合格状況

2026-09-20 JST。第5回 `run_1a0bbbe514dcf34c2a8`（8805）は再開後にarchitecture.md / decisions.mdの第3版を公開したが、seq207で審査タスクの通信枠不足により停止し、seq212 partial / live=falseで終了した。第3版の内容は未達であり、正式レビューも未実施。第1版の不合格レビューを第3版の判定に流用しない。保存した最終報告にはこの混同があったため、今後の報告は版・SHA一致のレビュー台帳をモデルに渡し、Markdownにもモデル解釈とは別に表示する。実記録による回帰検証はPASSだが、モデル本文の混同が解消したかはまだ未検証。

新たな自動編成チームは8806で実行中。最新状況は [自動編成の検証](adaptive-team-status.md) を参照。

完了判定の修正は関連40件と境界1件、未公開草稿を見失わない復帰案内は25件PASS。通常8796にも反映し、設定保持・実画面を確認した。再開時にも既存版と未公開編集を案内する追加改善は関連30件PASS、静的独立確認PASS（この追加分のみ稼働サーバー未ロード）。実会話14件のAPI/DOM/reload一致を検証済み。以下の表は第4回の履歴。第5回の内容評価は [独立報告](trading-round5-independent.md) と `artifacts/product-quality/trading-team-round5/` を参照。

合格条件は [trading-team.md](trading-team.md) 冒頭のまま。これはAI補助ありのローカル検証であり、人間のユーザーテストではない。

対象は `run_1a0bb85dc7e671d12d4`（8804）。HEAD `69d484a4e67c7ee26fe04e4d1d285fc07166d370` と未コミット変更。実行開始時のコード識別は `artifacts/product-quality/trading-team-round4/revision.json`、後続修正の識別と未ロード範囲は同ディレクトリの各変更記録に保存している。macOS、実Chrome、Ollama 0.33.3、既存ローカル9Bモデルを使用。

| 条件 | 判定 | 観測した事実と残る作業 | 証拠 |
|---|---|---|---|
| 性格・話し方を編集、保存、再読込できる | PASS | 実UIと設定API、snapshotを照合。空欄は役割既定。 | conversation-voice-contract、trading-team-observe、main-ui-document-recovery-smoke の記録 |
| 4役が実際に送信し、UIと保存内容が一致する | PASS | 4役6件を実イベントと画面で照合しreloadを検査。後続メッセージは別途照合が必要。 | round4-four-bot-chat-ui.log、独立voices証拠 |
| 全員の話し方が設定に沿って明確に異なる | FAIL | master/reviewerは適合。researcher/builderは特徴が弱く、builderの会話が長い目次再掲。改善ヒントは未実モデル検証。 | trading-round4-independent.md |
| 指定の2文書が生成される | PASS | architecture.md r1、decisions.md r1の実公開bytes/hashを照合。生成と内容合格は別。 | round4の各r1.md/json |
| 本番までの設計が正確で具体的 | FAIL | 注文状態・取消競合、認可、ID対応と送信前永続化、3対象照合、Adapter契約、Live通過条件が不足。公式仕様と設計要求の誤分類も残る。 | 独立R4A/R4D評価、正式fail審査seq111 |
| 審査・会話を受けて修正版が作られる | FAIL | 初稿のfail審査は保存。初回reviewerは引継ぎ未完了で失敗し、masterのretry後も完了せず、60分で中断。r2は未成立。 | events seq111–146、final.json |
| 合格した最新版を実UIで採用し、再読込・ZIP照合する | FAIL | 内容合格の最新版がないため未到達。未確認の初稿を採用して代用しない。 | download/verify用スクリプトは準備済みだが、この条件の成功証拠は未取得 |
| 実口座への接続・発注 | NOT_APPLICABLE | 依頼は実装方法の検討。実行権限がなく、この検証で実施しない。 | 元の依頼・実行権限 |

## 次の検証

8805で第5回のprobe成功後、実UIから開始した。前回と同じ依頼、資料、4役の話し方、3600秒・120呼出上限を保持。Ollama互換APIへtemperature .6/top_p .95を明示する。第3/4回は未指定値が1.0へ上書きされており、この条件と同一ではない。

第4回は3600.348秒でinterrupted/live=false/seq146を確認し、終了時UIも照合した。新たなモデル処理はこの終了確認後に開始する。第5回の `preparation.json` / `preflight.json` は準備の証拠であり、成果物・会話品質・完了の証拠ではない。

最新の回帰試験は29件PASS（review-context-handoff-recovery、exit 0）。これは実記録・SQLite/gatewayでの復帰契約の確認。稼働中8804には未ロードであり、実モデルの成功を意味しない。
