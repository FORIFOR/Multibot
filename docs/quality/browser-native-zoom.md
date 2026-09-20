# Chrome標準200%ズームの独立検証

**PASS（既存成果物の閲覧・キーボード保存という検証範囲）**。Chrome自身の「ページのズーム」を200%に変更し、CSS zoomやdeviceScaleFactor指定による代替ではないことを実測した。OS日本語IMEはBLOCKEDのまま。全画面のアクセシビリティ準拠や人間評価を意味しない。

2026-09-19、macOS、インストール済みChrome 153.0.8010.53をPlaywrightからheadlessで起動。mkdtempで作成した独立一時プロファイルのみ使用し、通常プロファイル・システム設定は変更していない。対象は8796の既存実run `run_1a0b8f5c9511106dcd2`。GETと既存採用版のローカルZIP保存のみ。新規依頼・再開・修正指示保存は行っていない。実装変更なし。revisionの識別は証拠フォルダのrevision.json。

`chrome://settings/appearance` のShadow DOM内 `select#zoomLevel` を標準選択UI経由でvalue `2`（200%）に変更。設定画面画像にも「ページのズーム 200%」が表示される。終了後の一時プロファイルPreferencesは `partition.default_zoom_level.x=3.8017840169239308`（1.2のこの指数＝2）。deviceScaleFactorを指定せず、ページのCSSは変更していない。

| id | method | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| Z1 | Chrome Page zoom UI設定とDOM実測 | 本物の200%ページズーム | innerWidth 1440→720、innerHeight 1000→500、DPR 1→2、html/body CSS zoomは1、visualViewport.scaleは1のまま | PASS | metrics.json, chrome-settings-200.png, chrome-zoom-preference.json | 一時Chrome profile |
| Z2 | 拡大後の実画像を開く | 中断状態・採用・未確認・保存が判読可能 | 各表示を確認。clientWidth=scrollWidth=720、横あふれなし | PASS | 200-percent-top-settled.png, 200-percent-save-cdp.png, 200-percent-history-cdp.png | 1440×1000外寸、720×500 CSS viewport |
| Z3 | Tab15回→保存リンク→Enter | キーボードで採用版保存 | 保存リンクに到達、ZIP取得成功 | PASS | metrics.json keyTrace、run_1a0b8f5c9511106dcd2.artifacts.zip | 200% zoom |
| Z4 | ZIP実バイトとmanifest照合 | 選択版そのものを保存 | selection=adopted、revision=1、SHA-256完全一致 | PASS | saved-bytes.json | 実ファイル |
| Z5 | ブラウザ通信記録 | 実runへ変更を送らない | nonGetRequests=[] | PASS | metrics.json | アプリ通信 |
| IME | OSの日本語入力検証 | 実IME操作 | 主担当でSystemEvents UI elements enabled=false。今回もOS設定は変更せず実IME操作はしていない | BLOCKED | 主担当のOS権限調査を参照 | OS機能、DOMイベント代替なし |

証拠はすべて `artifacts/product-quality/browser-native-zoom/` 配下。再現コマンドはリポジトリ直下で `node artifacts/product-quality/browser-native-zoom/reproduce.cjs`。スクリプトはGETとローカルダウンロードのみで、別の一時プロファイルを作成する。

## 観察上の注意

最初の目視では中断説明と使用額の接触を疑ったが、DOM境界は20 CSS px離れており重なりを再現できなかった。表示欠陥という初期判断を撤回。密度の高い配置という主観に留める。

Playwright標準page.screenshotは実ズーム後のスクロール位置で大きな空白が入るキャプチャ不整合があった。アプリのレイアウト障害とは扱わず、CDP `Page.captureScreenshot({fromSurface:false,captureBeyondViewport:false})` でブラウザ描画面を取得し、結果と確認履歴を実際に開いて確認した。標準キャプチャの初回失敗画像も経緯として保持する。CDP画像下端の黒帯はブラウザ描画面外であり、アプリ内容の黒帯とは認定しない。

既存guide.mdの字数超過・誤った再送案内など、生成品質のFAILはこのズーム試験で解除しない。headless Chrome標準ズームの試験であり、人間によるOSショートカット操作・物理キーボード・実OS IME試験とは区別する。

再現スクリプトを独立した2つ目の一時プロファイルでも実行しexit 0。1440→720 / DPR1→2 / CSS zoom1 / nonGet0を再現した。人間ユーザーによる操作評価は未実施のためBLOCKEDを維持する。
