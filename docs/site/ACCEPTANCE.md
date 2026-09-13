# ACCEPTANCE.md — Agent Team サイト 受入

| 項目 | 基準 | 結果 |
| --- | --- | --- |
| 理解 | 3 秒で「依頼は一度、成果物と検証の経緯が残る」と分かる（H1 + 補足のみで） | 目視確認済み（スクリーンショット `variants/`） |
| 実成果物が最初に見える | 折り返し前に実データの成果物（research-final-r2.md）が見える | PC 1440px: 見える。モバイル 390px: コピー + CTA の直下 |
| 操作 | F-1 / F-2 / F-3 クリック → 該当箇所へ移動・強調・変更前/後表示 | headless Chrome で 3 件とも移動先の `data-fix` が一致（`scripts/site-check.mjs`） |
| 映像 | ポスターあり、自動再生なし、`demo_start` / `demo_complete` 発火 | `demo_start` は headless Chrome で確認。`demo_complete`（ended）はローカル確認サーバが Range 非対応でシークできず未確認 → 公開後に GitHub Pages で確認（下記「公開後の確認」） |
| モバイル | 390px で横スクロールなし、1 列、ボタン高さ 48px | 同スクリプトで `scrollWidth <= innerWidth`、H1 36px、ボタン 48px を EN/JA とも確認（初回は導入カードの `pre` で横溢れ → `min-width:0` で修正） |
| 信頼 | partial / failed の行に理由と証拠リンクがある | 実績表に記載 |
| 事業導線 | 「相談」CTA が非公開チャネルへ、`lead_submit` 発火 | 確認 |
| OSS 導線 | GitHub リンクと uvx コマンド、`github_outbound` / `quickstart_open` 発火 | 確認 |
| 表記 | Agent Team / FORIFOR/Multibot / MIT がヘッダ・フッタ・OG にある | 確認 |
| CWV | LCP ≤ 2.5s、INP ≤ 200ms、CLS ≤ 0.1 | **未計測**（フィールドデータなし。Lighthouse のラボ値のみ参考に記録） |

## 計測イベント
`track(name, props)` が `window.dataLayer` に積み、`<meta name="analytics-endpoint">` が設定されていれば `sendBeacon` で送る。**現在 endpoint は未設定**（送信先なし。ページ内の `window.dataLayer` で確認可能）。
- demo_start / demo_complete（実行記録の再生）、record_finding（指摘クリック、固有操作）、artifact_open、artifact_download、github_outbound（`intent: repo | star`）、quickstart_open、lead_submit。

## 実行ログ（2026-09-13）
- `node frontend/scripts/site-check.mjs http://127.0.0.1:8799` → en/ja × pc/mobile の 4 通りで: JS エラー 0、横スクロールなし、H1 56/36px、本文 18px、ボタン 48px、成果物が折り返し前に表示、F-1/F-2/F-3 のジャンプ先 `data-fix` 一致かつ画面内、`record_finding`×3 → `demo_complete`、ポスターあり・自動再生なし、ブランド表記あり、相談 CTA の href が X の DM。
- ヒーロー 3 案の比較画像: `variants/hero-a.png` `hero-b.png` `hero-c.png`（同一コピー・同一データ）。採用 A（`DESIGN.md`）。
- CWV: フィールドデータなしのため **未計測**。
