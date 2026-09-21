# トークンの正本（アプリ）

2026-09-19 時点の現状の記録。新しいデザインの指定ではない。

| 分類 | 現在の正本 | 値・備考 |
|---|---|---|
| Color | `frontend/src/quiet-cinema.css` の `:root` | 背景 `#f7f8ff`、文字 `#202124` / `#4f5665` / `#737b8c`、線 `#e2e6f0`、操作 `#4f63d9`（薄 `#dfe4ff`）、良 `#16856b`、注意 `#a66300`、問題 `#b83b48`。役割色: まとめ役 `#6876e8`、調べる係 `#36ad88`、つくる係 `#eea93b`、確かめる係 `#eb6e9a` |
| Type | `frontend/src/styles.css` の `--sans` / `--serif` / `--mono` | アプリの見出しと本文はゴシック体。明朝体は公開サイトの見出しだけで使っている（アプリと不一致。未整理） |
| Spacing | 変数なし | 12 / 14 / 16 / 18 / 22px が混在。未整理 |
| Shape | `--r:20px`（quiet-cinema） | 実際は 14 / 18 / 20 / 22 / 26 / 999px が混在。ボタンと状態は999px。未整理 |
| Elevation | 変数なし | 主に `0 30px 80px rgba(47,58,110,.12)` と `0 10px 24px rgba(79,99,217,.16)` |
| Motion | `frontend/src/bot-polish.css`、`quiet-cinema.css` | まばたき5.2秒、浮遊4.4秒、作業中の点1秒、移り変わり0.2〜0.35秒。reduced-motion と `.motion-paused` で停止 |
| Layout | `frontend/src/journey.css` | 作業の画面は最大1280px、左列400px、切り替えは1000 / 700 / 480px |
| Character | `quiet-cinema.css`（形）+ `bot-polish.css`（質感） | 公開サイトは `docs/site/build_site.py` がこの2つをコピーする |

## 分かっている負債
- スタイルシートが `styles → workroom → quiet-cinema → ui-polish → bot-polish → journey → welcome` の順に上書きし合っている。5回の方向転換の跡で、同じ要素の値が複数のファイルにある。
- 角丸と余白に変数がなく、値が散らばっている。
- 次に主要画面を作り直すときは、代表画面で値を決めてから変数にまとめる。探索の前に大量の値を固定しない。

## 2026-09-22 — Obsidian surface（移行中）

利用者の指示「obsidianui.dev を参考に」「ライトのみ」「アプリ全体、お願いする画面から」による。正本は `frontend/src/obsidian.css` の `:root`（`--ob-*`）。最後に読み込まれ、旧変数（`--paper` `--ink` `--line` `--signal` `--r` `--sans`）も同じ値へ向け直す。

| 分類 | 値 |
|---|---|
| Color | 地 `#fff`、外枠 `#f5f5f5`、文字 `#0a0a0a` / `#404040` / `#666`、線 `#e5e5e5` / `#ededed`、主操作 黒 `#2b2b2b→#0d0d0d`。状態は 良 `#0f6b55`、注意 `#8a5700`、問題 `#a02f3c`、進行 `#3346b0`（各々に薄い地と線）。役割色は変更なし |
| Type | Inter → IBM Plex Sans JP → Hiragino Sans。Webフォントは読み込まない。見出し 700 / −0.045em |
| Spacing | 4 / 8 / 12 / 16 / 24 / 40 / 64px（`--ob-s1`〜`--ob-s7`） |
| Shape | 8 / 10 / 16 / 24px（`--ob-r-sm`〜`--ob-r-xl`）。ピルは選択肢のチップと状態タグだけ |
| Elevation | `--ob-shadow-sm`、`--ob-shadow`。カードは影なし・細線 |
| Character | 白いタイル＋細線＋下辺に役割色の線。常時の浮遊は止め、ポインターを載せたときだけ4°傾く。reduced-motion と「動きを止める」で停止 |

構成から作り直した画面: お願いする画面。色・枠・ボタン・担当タイルだけ移した画面: 作業の画面、マイチーム、作業一覧、はじめての案内（構成とマークアップは変えていない）。上の「分かっている負債」は未解消で、このシートが8枚目の上書きになっている。旧シートの該当値を削る作業は別の変更として残す。

撮影: `frontend/scripts/ask-capture.mjs`（お願いする画面の各状態）と `frontend/scripts/work-capture.mjs`（確認済みファイルの採用前、キーボードでの採用、他の3画面）。どちらも台本のテストサーバーが必要。
