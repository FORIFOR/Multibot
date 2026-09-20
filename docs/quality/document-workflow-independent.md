# 文書ワークフロー設定の独立検証

2026-09-19、macOS Chrome 153、独立一時プロファイル、8796の更新済みUIで確認。**今回の検証範囲で不具合なし**。依頼送信、新規モデル実行、実装変更は行っていない。以前の証拠は上書きしていない。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| W1 | 最大文字数からTab、Space | checkboxへ移動して切替可能 | 正しいラベルのcheckboxにフォーカスしchecked=true | PASS | verification.json / 390-workflow.png | 390px |
| W2 | 実repo integration.md添付、guide.md/400/700/checkbox指定→reload | 選択保持 | checked=trueが復元 | PASS | verification.json | 390px |
| W3 | Chrome標準Page zoom 200%→reload→Tab/Space | 本物のズームで復元・操作 | innerWidth720、DPR2、CSS zoom1、checkbox復元。SpaceでOFF/ONできる | PASS | verification.json / 200-workflow-full.png | 1440 viewport・200% |
| W4 | 下書きを破棄→reload | checkbox・入力・資料を破棄 | checked=false、goal/file空、files=[]、min/max空、documentWorkflow=false | PASS | verification.json | 200% |
| W5 | 説明文目視とHome.tsxレビュー | 選択前に処理と条件が明確 | 作成担当→別確認担当、計画生成省略、資料/ファイル名必須、URL調査は通常経路という説明をcheckbox直後に表示 | PASS | 両画像、frontend/src/pages/Home.tsx | 実表示＋静的レビュー |
| W6 | 通信観測 | 送信なし | nonGet=[] | PASS | verification.json | 全操作 |

証拠は `artifacts/product-quality/document-workflow-independent/`。両画像を実際に開いて確認。フォーム項目・checkbox・説明は390pxでも200%でも読め、200%のscrollWidth=innerWidth=720。説明は機能選択に必要な動作差を具体的に示す。ファイル内容の正確性は別途確認が必要という既存注記も維持。

下書き保存useEffectの依存と保存対象にdocumentWorkflowが含まれ、初期状態はdraft.documentWorkflow===true。破棄はstateをfalseへ戻し、添付等も消去。送信前の静的条件は資料・ファイル名必須、URL入力ありを拒否し、選択時にのみworkflow=documentを渡す。今回、この送信経路やバックエンド処理は実行していないため成功判定の対象外。

人間ユーザー評価とOS日本語IMEはBLOCKEDを維持。このAI独立ブラウザ検証を代替の人間評価とはしない。

初回200-workflow.pngは390px起動ウィンドウ由来のキャプチャ幅制約で右側が切れたため、1440pxで起動した別の一時Chromeの本物200%ズームで200-workflow-full.pngを再取得し実画像を確認した。前者はキャプチャ不整合の経緯として保持。後者は説明とcheckboxの表示確認、復元・破棄の数値証拠は最初のセッションのverification.json。
