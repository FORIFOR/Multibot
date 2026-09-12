---
name: artifact-handoff
description: 成果物を別Botへ引き継ぐときに使う。実ファイルのrevisionと次の作業に必要な情報だけを渡す。
metadata:
  origin: bundled-original
  evaluation: seed-unvalidated
---

# Artifact handoff
1. 入力taskの成果物が保存済みであることを確認する。
2. Runtime発行のartifact_id、revision、hash、media typeを取得する。
3. 出力の要点、検証、残課題、次の担当者の作業を短くまとめる。
4. 許可されたsend_messageで担当者へ参照を送る。全文を複製しない。
5. 宛先と配送eventを確認する。会話を後付けしない。
元の成果物を修正するときは新revisionを作り、旧検証を引き継がない。
