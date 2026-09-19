# Review evidence

レビュー前に次を実行すると現在のソース指紋と必要画像のハッシュが分かる。

```sh
node scripts/ui-quality.mjs inspect
```

ui-reviewerには指紋、brief、acceptance、参照画像、実装画像を渡す。
親エージェントは独立レビューを忠実に保存する。次のJSONは未完了テンプレート。
ファイル名: artifacts/ui/review.json

```json
{
  "status": "blocked",
  "reviewer": "ui-reviewer",
  "sourceFingerprint": "INSPECTの値",
  "images": [
    { "path": "artifacts/ui/desktop.png", "sha256": "INSPECTの値" },
    { "path": "artifacts/ui/mobile.png", "sha256": "INSPECTの値" }
  ],
  "blockingFindings": ["未レビュー"],
  "findings": [],
  "unverified": ["実機Safari", "通常motion"],
  "notes": "実際に開いた画像、確認範囲、観察・操作・推定を区別して記載する"
}
```

statusはpass/fail/blocked。ローカルゲートが受け付けるのはpassかつblockingFindingsが空のものだけ。
ただしこれは記録の整合性チェックであり、レビューの真実性や美しさを自動的に証明しない。
画像を見ていないのに見たと記録してはならない。
必須の手動確認が未実施ならblockingFindingsへ記載する。unverifiedへ逃がさない。

## 最終報告の型
対象 / 変更内容 / 採用案と理由 / 実行したテスト / 画像 / 主導線の操作結果 / 未達・未確認。
「AIレビューPASS」「機械テストPASS」「人間が承認済み」を別に表示する。
