# 初回Chrome起動失敗を未確認のまま保全する

2026-10-02 JST。[0f2d377のCI36959652900](https://github.com/FORIFOR/Multibot/actions/runs/36959652900)は、既存の初回認証回復検証がChrome起動で失敗した。成果物本文の復帰改善をGitHubで通過したとは扱わない。

## 原CIの範囲

[原safe結果](ci-original-initial-recovery.json)と[独立source/merge照合](ci-original-service-review.json)は `failure_check=chrome_launch`、`error_type=Error`、cases未実施・writes0。page/context作成前なので、今回の成果物UIにも認証回復の操作にも到達していない。該当runnerと親wrapperは前版a32bの成功時と同一だったが、環境起因とも製品起因とも断定できない。生エラーは非公開のままrunner終了で失われ、例外名だけではChrome自身の拒否と外側期限を分けられなかった。

[親service原結果](ci-original-service-report.json)では受付・実資料応答の2段階まで成功。検証で追跡した所有9 processはsignal0/残留0、browser APIのtask/port/lifespan終了を確認。初回認証検証用DBは前後run/job/model/artifact0で、新しい推論はない。

[先行DB](ci-original-database-report.json)と[sandbox境界](ci-original-sandbox-report.json)は別の実行で成功している。一方、reading・親3 GET回復・新artifact回復・[site](ci-original-site-not-run.json)はSKIPPED。旧185項目やローカル40項目を今回のGitHub結果へ代入しない。[並行したOIDCの独立照合](ci-original-oidc-review.json)は成功だが、UIの起動原因や今回の未実施検証を説明する証拠ではない。

## 追加する観測

`auth-initial-recovery.mjs` に、起動開始時刻・単調時計の経過時間・STARTED/SUCCEEDED/FAILED、実15秒設定、wrapperの実remainingとtimer callback発火booleanだけを追加する。例外文字列に含まれる既知のtimeout/target closed/file不在/特定sandbox拒否文は固定booleanへ投影し、値・path・command line・生例外はsafe JSONへ出さない。全markerがfalseなら未分類であり、分類自体も原因の断定ではない。

Playwrightと外側wrapperの期限はともに従来の15秒のまま。全体90秒、親120秒、その他のbrowser段階180秒、所有終了の期限も維持する。自動再試行、失敗の黙殺、assertの削除、AuthGateや製品bundleの変更は行わない。模擬errorを作って診断分岐を通した証拠にはしない。実起動・実認証の検証結果と静的なsafe分岐の照合は別に記録する。

[独立した実diffの静的レビュー](static-review.json)では、既存2ケース以降のassert・cleanupがbyte同一で、markerへ生messageが流れないことを確認した。経過msは起動直前のsafe保存1回を含む区間で、Chrome内部だけの起動時間ではない。

## 同じ診断を実サービスで確認する

新しい私有rootの[7段階suite](local-suite.json)を一度実行し、40.42秒でPASS。追加した[起動記録](local-initial-recovery.json)はSUCCEEDED・741ms・Playwright/wrapper各15,000ms・wrapper期限発火false・失敗marker nullで、初回認証2ケース12項目も通過した。模擬例外で失敗分類を実行したものではない。5ブラウザー検証の所有58processはsignal0/残留0、browser APIのtask/lock/port/lifespan終了を確認。初回認証DBの前後run/job/model/artifactは0で、suite全DBを0とは扱わない。新たな推論はない。

[事後照合](local-postcheck-summary.json)ではcode116/input6/UI6が不変。response用DBに保持した過去v18のmodel20件と追加model0を区別し、browser再送の実start:false2件・admissionの取消job1も記録した。API3個の事後port閉鎖は確認したが、詳細lifespan観測はbrowser APIだけである。

この一度のローカル起動成功から、先のGitHub起動失敗を修正済み・環境起因とは断定しない。原FAIL、後段未実施、旧製品の受入未達はそのまま保持する。追加の診断は次の実行に対する観測であり、失われた原エラー内容を再現した証明ではない。

[別担当の独立事後レビュー](local-independent-review.json)も実source・条件・各結果・終了scopeを照合し、阻害指摘なし。これはAI独立検証であり、人間受入ではない。
