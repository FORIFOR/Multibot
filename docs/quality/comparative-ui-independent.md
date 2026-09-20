# 検索・会話絞り込みの独立検証

2026-09-20。independent-product-verification適用。実装担当とは別AIセッションによる検証であり、人間の初見評価ではない。macOS / Chrome 153、独立した一時プロファイル、1440×1000 / 390×1000。対象は配信済み8796作業一覧と8798の実過去run `run_1a09c8485503d406bf4`。実装・受入条件を参照した補助あり検証。製品コード変更なし、モデル呼出・実行状態変更なし。業務データのモックなし。

主要な再現問題は確認されなかった。

| ID | 方法・期待 | 観測 | 判定 | 証拠 |
|---|---|---|---|---|
| L1 | 実依頼文検索をAPI結果と照合、reload保持 | 実作業8件中 `Jev` で2件、API期待2件。reload後も同一query | PASS | verification.json |
| L2 | 状態との組合せ、0件からクリア | completed併用0件。実ファイル名readiness.json検索0件。クリアで8件 | PASS | verification.json、1440-list.png、390-list.png |
| C1 | 実本文検索＋宛先Bot指定、原文照合 | PRODUCTION_PLAN.md / builderで実発言1件。API本文とtextContent完全一致 | PASS | verification.json、1440-filters.png、390-filters.png |
| C2 | 絞り込み中追従停止、0件、Enterで最新復帰 | aria-live off、自動追従停止。integration.mdで一致なし。最新へ戻るにフォーカスしてEnter後、query/agent空、aria-live polite、1件復帰 | PASS | verification.json |
| C3 | 複数新着によるスクロール位置保持 | 実会話1件のみ。新着を生成していない | BLOCKED | 対象データの制約 |
| V1 | 390/1440のスクリーンショットを実際に開き、幅計測 | 検索欄・担当選択・解除・本文・最新復帰を読める。会話画面document/body幅はそれぞれ390/1440で横溢れなし | PASS | final-layout.json、6枚の実画像 |
| S1 | ブラウザ要求・pageerror監視 | GET以外0、pageerror0。非GETを中止するガードも発動0 | PASS | verification.json、final-layout.json |
| R1 | artifact_refsの正確なrevisionリンク | コードは参照のartifact_id/revisionをraw URLに渡す。実発言のrefsは空で実クリック不可 | 静的PASS / 実測BLOCKED | TeamConversation.tsx / api.ts、verification.json refs=[] |

証拠ディレクトリ: `artifacts/product-quality/comparative-ui-independent/`。検証経路は一覧検索→reload→状態併用→ゼロ件→クリア、実会話で「会話を探す」→本文検索→担当builder→0件→「最新へ戻る」をEnterで実行。390/1440を別途撮影し画像を開いて確認。

暫定指摘の訂正: raw URLのartifact_id未エンコードをP2候補として伝えたが、artifact_id_forが英数字・ドット・アンダースコア・ハイフンへ正規化する実装を追加確認し、現行の実生成データでの再現経路がないため撤回。潜在的懸念を実在障害として数えない。

競合の公式公開説明は同条件の製品操作測定ではない。VoiceOS/OpenClawを超えたとの認定、人間評価、OS日本語IMEはBLOCKEDを維持。今回の検索改善では実200%拡大・読み上げを追加実測していない。build/lintは実装担当の結果を独立実行したと主張しない。成果物生成品質の既存FAILを本UI検証で解消扱いにしない。

対象基準commitは `18763d8a7c02ce3ec28bcd6725334efaf81bd7e6`、未コミット実装を配信した環境。最終通知後、api.tsのrunId/artifactIdにencodeURIComponentが適用されたことを静的再確認した。防御的変更であり、現行IDで実障害を再現・修正したとの扱いにはしない。追加のrawリンク実クリックは引き続きBLOCKED。
