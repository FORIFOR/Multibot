---
name: evidence-review
description: 成果物の受入条件を検証するときに使う。実テストと対象revisionからpass/fail/unverifiedを判定する。
metadata:
  origin: bundled-original
  evaluation: seed-unvalidated
---

# Evidence review
受入条件を一つずつ対応付ける。各条件に対象artifact revision、検査方法、結果、証拠eventを記録する。
実行可能な検査は実行し、実行できない検査はunverifiedにする。
静止画は外観の証拠であり、決済やフォーム送信成功などの操作全体を証明しない。
不具合の最低件数、最低修正回数、先に決めた採点を置かない。
検証結果に関係しない好みや追加機能で合格を妨げない。
報告は発見した差分に集中し、同じ指摘を重複しない。
