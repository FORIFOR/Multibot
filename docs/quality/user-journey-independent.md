# 独立した利用想定テスト

2026-09-20 02:00–02:10 JST。AIによる初見補助評価であり、人間の初心者評価ではない。実装・既存レポート・正解ルートを読まず、ユーザーの目的と起動URLのみから探索した。アプリコードは変更していない。

## 環境と範囲

- URL: `http://127.0.0.1:8798`。実過去記録の隔離コピー。作業 `run_1a09c8485503d406bf4`、成果 `readiness.json` 版3。
- macOS 26.6.2 (25G83)、Chrome 153.0.8010.53、Playwright-core 1.63.0 / channel chrome / headless。
- 1440×1000、390×844。新規ブラウザーから開始。導入時間・依存物DL・モデルDL・アカウント準備は対象外。
- HEAD `18763d8a7c02ce3ec28bcd6725334efaf81bd7e6`。並行作業のある未コミット状態。試験中取得した `git diff --binary` SHA256: `92c3829fc5794aabfcfb11258b7a2641b61f7d130183ad647caa55f97f389dab`。配信済みビルドとこのdiffの同一性は未確認。
- GET閲覧、ブラウザー内コピー編集、ファイルDLのみ。送信・再開・採用・モデル呼び出しは行っていない。操作中は非GETをabortするPlaywright routeも併用。モック・スタブ・ダミーレコードなし。
- 証拠基準パス: `artifacts/product-quality/user-journey-independent/`（以下ファイル名はこの配下）。

## 判定

| id | method / 手順 | expected | observed | status | evidence | environment |
|---|---|---|---|---|---|---|
| UJ01 | トップから「作業一覧」→実作業を開く | 既存の依頼と実状態を見つける | 一覧に1件、中断表示、日時、会話への導線。readiness.json検索で1件を発見 | PASS | 01-first.png, 02-tasks.png, 10-keyboard.png | desktop |
| UJ02 | 作業の会話とAIチームを読む | 誰が何をしており完了しているか理解できる | まとめ役/つくる係/確かめる係は停止中。保存会話1件、確かめる係→つくる係の指摘。依頼全体未完了と途中成果が明示 | PASS | 03-conversation.png | desktop |
| UJ03 | 成果物と「確認の記録を見る」「前の版との差分」を開く | 成果・版・確認根拠を区別して確認できる | JSON本文、版2→3差分、版1/2/3、版3識別子、必須条件通過を確認。「完全な正しさを保証しない」と明示 | PASS | 12-diff.png, 13-review.png, observations.json | desktop |
| UJ04 | 「コピーを編集」→実本文の「鍵轮换手続き」を「鍵ローテーション手続き」に修正→「コピーをファイルに保存」 | 手元の修正を持ち出せる | readiness.jsonをDL。ファイルbytesが編集欄と完全一致、JSON parse成功、product=Multibot。チーム原文表示は旧表記のまま | PASS | check-edit.cjs, readiness.json, observations.json, 11-keyboard-editor.png | desktop |
| UJ05 | 編集後に再読込しコピー編集を再度開く | 下書きが失われない | 修正済み全文が完全一致で復元された | PASS | check-edit.cjs, observations.json | desktop |
| UJ06 | 編集欄の実語句を選択→「この版の修正を頼む」 | 対象と選択箇所が入った指示を準備できる | readiness.json / 版3 / SHA256 / 「選択箇所（編集中のコピー）」/ 選択語句 / 修正内容欄を挿入。team-directionへフォーカスが移動。送信は未実行 | PASS | revision-draft.txt, 06-revision.png, 09-mobile-revision.png | desktop/mobile |
| UJ07 | 390pxで会話→成果物タブ→コピー編集→対象修正指示 | 狭幅でも主要導線が操作できる | 横スクロール幅390px=viewport。会話と成果をタブ切替。指示作成で会話へ戻り入力欄に移動 | PASS | 07-mobile.png, 08-mobile-artifact.png, 09-mobile-revision.png, observations.json | mobile viewport |
| UJ08 | Tabで一覧のナビ・検索・フィルタ・作業カードへ移動。Enterで作業とコピー編集を開く。編集欄からTab | キーボードで到達でき、フォーカスが見える | 論理的順序で移動、3px outline確認。カードEnterで開く。編集欄の次は「コピーをファイルに保存」、輪郭は目視でも明瞭 | PASS | keyboard.json, 10-keyboard.png, 11-keyboard-editor.png | desktop keyboard |
| UJ09 | 生成済み本文の日本語を読む | そのまま導入担当者へ渡せる自然な日本語 | 「鍵轮换」「陈旧」「復解密」「彩演」「録出」等が残る。操作フローは成立するが、この歴史的成果物を修正なしで業務利用可とは判定できない | FAIL | readiness.json（1語のみ手修正済み）、03-conversation.png、observations.json | 実過去成果、現モデル新規実行ではない |
| UJ10 | 新規依頼・再開・修正指示保存/送信・モデル完遂 | 実サービスの変更を伴う完了確認 | 今回の許可範囲はGET/ローカル編集/DL。実行しない | BLOCKED | 試験範囲 | 実処理未実行 |
| UJ11 | VoiceOver、日本語IME実入力、OSの200%ズーム、実タッチ端末、reduced-motion動作 | 支援技術を含む操作確認 | 今回は未試験。Playwrightの文字列fillをIME検証と呼ばない | BLOCKED | 試験範囲 | 実機・支援技術未試験 |

## 見つけにくさと見た目の観測

主導線の文言は具体的で、初見探索時に手順の助言を必要としなかった。デスクトップでは成果と会話が同時に見え、スマートフォン幅ではタブで分離される。余白・境界・状態バッジは読み取りを助ける。画像01/03/04/06/07/08/09/10/11/12/13は保存後に開いて目視した。静止画からアニメーションの良否は判定していない。

改善提案（操作不成立の欠陥とは区別）:

1. 「確認の記録を見る」は下方のセクションを開くが、この実JSONと差分が長い状態ではクリック直後のviewportに記録が現れなかった。展開先へスクロールまたはフォーカス移動すると、根拠を探す距離を減らせる。13-review.pngはクリック直後、observations.jsonに展開後の確認記録がある。
2. コピー編集は本文の上に追加されるため、長文JSONが編集欄と原文で重複する。原文を折り畳む、構造化表示を選べるなどで確認負荷を下げられる。11-keyboard-editor.png。
3. モバイルの修正指示欄は高さが小さく、挿入後は末尾が見えるため、対象版とハッシュは欄内スクロールが必要。選択した対象を欄外に短く示すと確認しやすい。09-mobile-revision.png。

## 証拠と再現

`check-edit.cjs` は、Chromeをremote debugging port 9338で起動し、該当実作業のコピー編集欄を開いた状態を前提に、実表記修正・DL内容照合・reload保持を検証する補助スクリプト。実行コマンド `node artifacts/product-quality/user-journey-independent/check-edit.cjs` はexit 0。出力は downloadName=readiness.json / exactMatch=true / jsonValid=true / reloadPersisted=true。ブラウザーの状態を前提とするため単独のE2E全体スクリプトとは呼ばない。

DLファイルSHA256: `de7c4c1bd458795ddee6bdbc972b5867724d5151a5cf6f03ef2b67f51f5a1af9`。チーム版3の元SHA256: `69c5f155f0283ce6b74e3456b9e56a9a0b211dbc14a9c4f59180fff2f7d65499`。保存したJSONは検証で手修正したコピーであり、新しいチーム版ではない。

キーボード試験の初回スクリプトには検索欄をtextboxと指定した誤りがあり、実UIの `type=search` を確認後searchboxに直して再実行した。これは製品の不具合に数えていない。

操作範囲の主要目的は成立。ただし、モデル完遂・支援技術・人間の初回成功率・業務成果品質・競合優位はこの検証のPASSから推論しない。通信切断/保存失敗等の試験は親タスク側の別担当範囲。

## 初見試験後の追加静的確認

親タスクから依頼された `frontend/src/components/ElapsedTime.tsx` の経過時間修正を、初見試験完了後に確認した。`isSettled`の6状態と停止イベント6種が一致し、`finished_at`を最優先、稼働中は現在時刻、停止時は最後の停止イベント、それがない場合のみ最後のイベントを使用する。後から`instruction.received`が追加されても、停止イベントが存在する実ケースでは経過時間が増えない構造になっている。静的確認PASS。`events`が時系列順に提供される既存前提は残る。親タスクが別ポート8799で保存前後15分不変の実測を担当したため、その実測を本担当の独立実行としては計上しない。
