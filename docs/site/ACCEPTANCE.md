# ACCEPTANCE.md — Agent Team サイト 受入

| 項目 | 基準 | 結果 |
| --- | --- | --- |
| 理解 | 3 秒で「依頼は一度、成果物と検証の経緯が残る」と分かる（H1 + 補足のみで） | 目視確認済み（スクリーンショット `variants/`） |
| 実成果物が最初に見える | 折り返し前に実データの成果物（research-final-r2.md）が見える | PC 1440px: 見える。モバイル 390px: コピー + CTA の直下 |
| 操作 | F-1 / F-2 / F-3 クリック → 該当箇所へ移動・強調・変更前/後表示 | headless Chrome で 3 件とも移動先の `data-fix` が一致（`scripts/site-check.mjs`） |
| 映像 | ポスターあり、自動再生なし、`demo_start` / `demo_complete` 発火 | `demo_start` は headless Chrome で確認。`demo_complete`（ended）はローカル確認サーバが Range 非対応で未確認だったため、公開後に GitHub Pages 上で再実行し 4 通りとも `demo_start` → `demo_complete` を確認 |
| モバイル | 390px で横スクロールなし、1 列、ボタン高さ 48px | 同スクリプトで `scrollWidth <= innerWidth`、H1 36px、ボタン 48px を EN/JA とも確認（初回は導入カードの `pre` で横溢れ → `min-width:0` で修正） |
| 信頼 | partial / failed の行に理由と証拠リンクがある | 実績表に記載 |
| 事業導線 | 「相談」フォームが非公開チャネルへ、送信成功時に`contact_submit`発火 | 確認 |
| OSS 導線 | GitHub リンクと uvx コマンド、`github_outbound` / `quickstart_open` 発火 | 確認 |
| Reachmade導線 | 製品サイトと親サイトの製品一覧が英語・日本語フッターから開ける | `multibot.reachmade.com` は GitHub Pages へリダイレクト、`reachmade.com/products/#agent-team` は HTTP 200 を確認（2026-09-15 JST） |
| 表記 | Agent Team / FORIFOR/Multibot / MIT がヘッダ・フッタ・OG にある | 確認 |
| CWV | LCP ≤ 2.5s、INP ≤ 200ms、CLS ≤ 0.1 | **未計測**（フィールドデータなし。Lighthouse のラボ値のみ参考に記録） |

## 計測イベント
`track(name, props)` は `window.dataLayer` に積み、`portfolio.js` の固定されたサイト収集エンドポイントへ、受信確認済みのイベントだけ公開ページから `fetch` で送る（DNT/GPC が有効な場合は送信しない）。2026-09-15 JST に GitHub Pages の許可オリジンから `demo_start`、`demo_complete`、`artifact_open`、`artifact_download`、`github_outbound`、`quickstart_open` を送信し、HTTP 204 を確認した。`record_finding`、`example_open`、`quickstart_copy`、`contact_submit` は現在の収集側が HTTP 400 `INVALID_INPUT` を返すため、ページ内 `dataLayer` のみに記録し、公開エンドポイントへは送信しない。集計を閲覧する管理画面や、投稿単位の流入を特定する機能は未確認である。`<meta name="analytics-endpoint">` は現行スクリプトの送信先設定には使用していないため、未設定のまま残している。
- demo_start / demo_complete（実行記録の再生）、record_finding（指摘クリック、固有操作）、artifact_open、artifact_download、github_outbound（`intent: repo | star`）、quickstart_open、contact_submit。

## 実行ログ（2026-09-13）
- `node frontend/scripts/site-check.mjs http://127.0.0.1:8799` → en/ja × pc/mobile の 4 通りで: JS エラー 0、横スクロールなし、H1 56/36px、本文 18px、ボタン 48px、成果物が折り返し前に表示、F-1/F-2/F-3 のジャンプ先 `data-fix` 一致かつ画面内、`record_finding`×3 → `demo_complete`、ポスターあり・自動再生なし、ブランド表記あり、相談フォームとGitHub/Quickstart CTAを確認。
- ヒーロー 3 案の比較画像: `variants/hero-a.png` `hero-b.png` `hero-c.png`（同一コピー・同一データ）。採用 A（`DESIGN.md`）。
- CWV: フィールドデータなしのため **未計測**。
- 公開後（commit `b550e0e`、GitHub Pages built、2026-09-15 JST）: `node frontend/scripts/site-check.mjs https://forifor.github.io/Multibot` → EN/JA × PC/mobile の4通りすべて JSエラー0、横スクロールなし、ジャンプ先一致、動画イベント発火を確認。収集側が400を返す未対応イベントは送信しないため、公開ページ操作時の計測エラーは0件。

## Portfolio inquiry correction, 2026-09-13
Private form delivery replaces public business Issues/DM-click completion. Only durable accepted inquiries count as lead submissions. Event storage is now configured, restricted to enum event/product/language with DNT/GPC respected. No arbitrary URLs or user content is sent. Existing earlier validation statements describe their original revision. Final portfolio validation is recorded separately.

## Portfolio acceptance — 2026-09-13

Native in-app-browser checks of all six sites: 1440×1000 English and 390×1000 Japanese; one main H1 and one inquiry form per page, no document horizontal overflow, no autoplay attributes, no broken completed image loads. This checks local authored pages, not field Core Web Vitals.

Distinct interactions verified: Launchloom keyboard arrow tabs, Japanese kit LP/posts, actual playback and pause on tab switch; Genie keyboard workflow selection, selected-video-only load and pause on change; AI Meeting real recorded audio playback and all three scenario panels; Oathra ambiguous reply stays incomplete, alternative time stays proposed, explicit confirmed reply satisfies all four evidence fields; AISecure selected observation exposes the actual synthetic evidence; Agent Team F-1/F-2/F-3 each highlight their matching revision block.

Private form validation rejects empty required input. Browser failure preserves entered text and restores the submit control. Five production synthetic inquiries (one per newly connected product) verified allowed-origin preflight, 201 only after Firestore persistence, matching useCase, idempotent retry and denied public GET; synthetic inquiry rows were removed. Existing AI Meeting intake tests remain covered. Targeted backend tests: 8 passing; broker typecheck passing. Source and sanitized evidence are in FORIFOR/AI-meeting scripts/verification/portfolio-intake-real.mts and docs/validation-assets/portfolio-intake.json.

Counts are aggregate event/product/language only. No form fields, audio, arbitrary URLs or visitor identifiers enter these counters. lead_submit means durable intake, not a click. DNT/GPC respected. No messages were sent to personal social accounts.

Field LCP/INP/CLS at the 75th percentile, star gains, qualified leads, human first-impression studies and a full assistive-technology audit are not measured by this round. No conversion or full accessibility certification is claimed. Full 200% browser text zoom was not measured; responsive layouts were checked at the widths above. Existing narrower historical checks remain labeled as their earlier revision.

## 2026-09-19 — キャラクター中心の新ホームページ
日英のホームページを [DESIGN.md](DESIGN.md) の新方針で書き直した。上の表と実行ログは旧ページ（実行記録ビューア、動画、F-1〜F-3 のジャンプ）に対するもので、当時の記録として残す。

- `node frontend/scripts/site-check.mjs http://127.0.0.1:8799`（ローカルの `python3 -m http.server`、headless Chrome）: 日英 × 1440 / 768 / 390 / 360px の8通りと、reduced-motion、JavaScript無効の各2通りで **失敗0**。H1は 64.8 / 43 / 36 / 36px、ボタンの最小高さ48px。
- 実行記録の変更前・変更後は `record.js` の記録原文を生成時に取り込んでいる。初稿では要約文を載せていたが、F-2 の要約が実際の修正内容と違っていたため、原文に差し替えた。
- 未確認: WebKit / Firefox での表示（キャラクターの拡大に CSS `zoom` を使用）、公開後の GitHub Pages 上での再実行、フォームの実送信、実利用者による理解度、CWV のフィールド値。動画（`media/*.mp4`）は新ページからは参照していない。
- 旧ページ用の `site.css`、`portfolio.css`、`workflow.css`、`launch.js` は新ページから参照していない（`record.js` は記録原文の出典として残す）。削除はしていない。
