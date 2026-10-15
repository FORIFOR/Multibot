# v61 事後の意味審査 — 2026-10-01

**判定: FAIL。受入0/10、本番導入不可、L3未達を維持する。** 保留だったAIによる事後の意味審査を終え、原資料の「入力取得」が「入力検査」に変わる1種類の意味誤差を確認した。元の成果物、実行状態、当時の採点は変更していない。

## 対象と方法

固定系列 `real-readiness-v61-qwen35-fixed-20260925` の保存済み10成果物を、当時の実資料2件と依頼に照合した。調整役AIと同じモデルの別コンテキストのAI 2体が4領域ずつ読み、調整役が統合した。これは人間・顧客の受入ではなく、今回の審査自体はローカルLLMの新規実行でもない。

実ファイルをそのまま保存した [PRODUCTION_PLAN.md](PRODUCTION_PLAN.md)、[運用検証資料](operations-README.md)、[当時の依頼](request.txt)、[fingerprint](fingerprint.json) を使う。これらは現行版の説明ではない。保存時点以降の実装や資料を、当時のモデルの判断に混ぜていない。

元のREADMEと `independent-check.json` の `12393db` は実装修正コミットだった。保持されたfingerprintが記録する**実行checkoutは `36bcafa5aa9bed629c1f02c569c16ec62364565e`**。両者の差分は文書・証拠のみで、バックエンドコードは同一だが、入力の本番計画は後者に一致する。元の記録を残し、この補足で区別する。モデル/configのfingerprint値は当時の記録であり、今回は再実行で検証していない。

## 発見した意味誤差

| id | 方法 | 期待 | 観測 | 判定 | 根拠 |
| --- | --- | --- | --- | --- | --- |
| V61-SEM-01 | 原文・生成物・提供例文の読解照合 | `mandatory output checks and input retrieval added` を「必須の出力検査と入力取得を追加」と保持 | 10成果物すべてで「実資料の入力・出力検査を追加」。入力取得が入力検査へ変わる | FAIL | 固定原資料15行、依頼68行、各draftのBusiness quality.implemented |
| V61-QUOTE | 保存バイトと固定表の比較 | 全8領域を順番どおりに含み、残条件を逐語引用 | 10成果物の80引用すべて一致 | PASS | [再照合スクリプト](verify.py)、[実行結果](verification.json) |
| V61-PROVENANCE | SHA-256とGitオブジェクト照合 | 固定資料・依頼・成果物を識別できる | 資料2件・依頼・10成果物のSHAを確認、checkoutと実装コミットを区別 | PASS | fingerprint、review.json、verification.json |
| V61-RECIPIENT | 依頼と全成果物の確認 | 宛先を捏造しない | 宛先指定・送信操作を含まない文書課題 | NOT_APPLICABLE | request.txt、保存済みdraft |
| V61-DUE-DATE | 依頼と全成果物の確認 | 納期を捏造しない | 納期指定・納期生成を含まない文書課題 | NOT_APPLICABLE | request.txt、保存済みdraft |
| V61-CUSTOMER | 受入主体と範囲の確認 | 実利用者・顧客による受入 | 人間・顧客の受入は提供されていない | BLOCKED | このAI審査の範囲外 |

意味誤差はモデルが新たに作ったものではない。依頼の「そのまま使える日本語の例」に同じ文があり、`backend/scripts/production_workflow.py` の `SUMMARY_EXAMPLES` とガイダンスが原因だった。修正はその2箇所だけを「入力取得と必須の出力検査」に改める。旧成果物を修正して合格にはしない。修正後のモデル実行は別の固定系列が必要である。

9件のReviewer提出は4基準すべてpassとしていたが、この誤差を指摘していなかった。同じ誤差がある同一本文9件についての見逃しであり、一般的な見逃し率を推定する母集団ではない。`completed` は当時の実行・契約状態として残すが、原文忠実性の合格証拠にはしない。

## 他の領域と省略

| 領域 | 短い要約としての判定 | 残る説明上の制約 |
| --- | --- | --- |
| Identity | PASS | group mappingが省略される |
| Isolation | PASS | 設定保護、IP固定、取得上限などの具体的境界が省略される |
| Execution | PASS | 中断ジョブの審査、依頼者所有の要件、有界検証が省略される |
| Data | PASS | セッション失効とfork/provider copiesの明記がなく、完全な保持方針には使えない |
| Audit / monitoring | PASS | 監督プロセスの実配備と復元ストリーム分離の具体性が弱い |
| Deployment | PASS | wheelや依存固定の具体性が省略されるが、本番環境の受入済みとは主張しない |
| Business quality | FAIL | V61-SEM-01 |
| Contract / operation | PASS | 承認主体の明示が省略されるが、承認・認証の達成を捏造していない |

依頼は40〜120字程度の要約を許容しており、省略だけをすべて誤りとは判定していない。ただし、運用要件を網羅する用途では原文の確認が必要である。全体要約は固定文、各行の日本語もすべて提供例文と一致し、10成果物は同じ5137bytes・同一SHA-256だった。この試験は未知資料を自力で要約する能力を実証していない。1回はReviewer提出前に中断しており、10回の完遂も成立していない。

## 再照合と次の作業

リポジトリの履歴がある環境で次を実行する。標準Pythonのみを使い、モデル・サービス・疑似データは不要。意味判定は読解によるもので、このスクリプトのPASSとは分ける。

```sh
python3 docs/evidence/real-readiness-v61-qwen35-fixed-20260925/posthoc-20261001/verify.py
```

機械可読の判定は [review.json](review.json)。元のstatus/attemptsの `semantic_review=pending` は実行当時のスナップショットとして保持し、本補足の `completed_with_findings` を現在の事後審査結果とする。

次は修正した例文を新しい固定系列で実ローカルLLMに再実行させ、原資料との意味照合まで行う。その結果も、この限定した文書課題以外の業務品質や初見利用者の成功、顧客環境・TLS/IdP/MFA・可用性・SLA・運用責任・セキュリティ審査の達成には換算しない。
