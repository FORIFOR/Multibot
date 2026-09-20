# 作業画面構成刷新の独立検証

2026-09-20。independent-product-verification適用。実装担当とは別AIセッション、macOS Chrome153の独立一時プロファイル、reduced motion。コード改変なし、GETのみ。実記録8798/run_1a09c8485503d406bf4（成果物あり）と8796/run_1a0b982c5bc72cef6bb（成果物なし、中断）を使用。人間初見評価ではない。

対象最終アセット: index-hs8FG2m0.js / index-BweE_Ysc.css。証拠 `artifacts/product-quality/desk-redesign-independent/`。

## 指摘

P2: 390pxで「続きを進める」をEnterで開くと、説明ポップアップのx=-28px、width280px、right252px。左28pxが画面外になり、再実行リスク説明と「確認して再開」の先頭が欠ける。`390-resume-final.png`を開いて確認。右寄せ絶対配置をモバイルで画面内に収める必要がある。説明を開いただけで再開実行はしていない。通常のdocument.scrollWidthだけでは左側のはみ出しを検出しない。

## 結果

| ID | 方法・期待 | 観測 | 判定 | 証拠 |
|---|---|---|---|---|
| D1 | 実画面1440px目視 | 上部カードがなくなり、絵文字担当チップ、成果物/会話の単一作業面。過去実記録の会話y422.7px、現runは359.4px | PASS | history/current-1440-final.png、visual.json |
| D2 | 実画面390px目視 | 担当が会話より前。過去記録の担当y416.2/会話y507.2、現run386.2/529.2。通常画面横溢れ0 | PASS | history/current-390-final.png、visual.json |
| D3 | 成果物なし実runを閲覧 | 1440で会話1列、成果物0と表示。指示入力欄が初期展開 | PASS | current-1440-final.png |
| D4 | 担当summaryへfocus、Enter開閉 | つくる係の作業内容が開く、再Enterで閉じる。フォーカス表示明確 | PASS | keyboard.json、390-chip-final.png |
| D5 | 再開summaryへfocus、Enter | 説明と確認実行ボタンが現れ、実行されない。ただし左側が欠ける | FAIL | keyboard.json、390-resume-final.png |
| D6 | scoped axe WCAG2A/AA/2.1AA | .desk-workroomで両run×両幅4条件、違反0 | PASS（検査範囲限定） | visual.json |
| D7 | request/pageerror監視 | GET以外0、pageerror0。非GET中止ガード発動なし | PASS | visual.json、keyboard.json |

6枚の最終画像を実際に開いて、通常画面・担当詳細・再開説明を目視した。初回の検証スクリプトは狭幅で非表示の会話を待ってタイムアウトし、検証側の条件を会話選択URLに直して再実行。製品不具合として数えていない。history-1440.pngは旧試行、末尾-final.pngが今回判定対象。

再開、送信、採用、モデル呼出、API書込みは検証範囲外。成果物編集の回帰は本追加検証では再実行していない。実OS IME、読み上げ、人間評価はBLOCKED。axe0を完全アクセシビリティ準拠と扱わない。競合優位や既存生成品質FAILの解消を主張しない。

## P2修正の独立再確認

最終配信は `index-lPs3EOuA.js` / `index-9aCFrJz3.css`。390pxで同じEnter操作を再実行し、説明領域x12/right378となり左右12pxを確保。`390-resume-fixed.png`を開き、説明全文と「確認して再開」が欠けずに見えることを目視した。P2およびD5は修正後PASS。修正前のFAIL証拠は保持。説明を開いた状態のscoped axe0、GET以外0/pageerror0（resume-fixed.json）。実行ボタンは押していない。追加の主要問題なし。
