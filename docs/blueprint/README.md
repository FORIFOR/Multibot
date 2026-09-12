# Agent Team — 実装仕様・初期プロンプト
作成日: 2026-09-12 / 対象: ローカルファーストの成果物中心マルチエージェント製品

## この成果物の範囲
これは設計・契約・初期プロンプトのパッケージです。動作するアプリ、実装済みエージェント基盤、完成したGitHubリポジトリではありません。
実LLM/API、ブラウザ操作、複数Bot実行、課金、復旧はこのパッケージでは実行していません。
サンプル設定とイベントのJSON Schema検証、ファイル参照・Skillハッシュ整合性のみ検査しています。

## 読む順序
1. PRODUCT_SPEC.md — 体験、実行モデル、データ契約、差別化。
2. IMPLEMENTATION_BRIEF.md — 開発エージェントに渡す実装指示。
3. config/agents.example.yaml — 各Botの接続先・モデル・プロンプト・権限。
4. prompts/ — Master、Worker、Researcher、Builder、Reviewer、Reporterとチーム生成。
5. SECURITY.md / evals/ACCEPTANCE.md — 停止・権限・実API評価・公開基準。
6. REFERENCES.md — 確認した一次資料、採用点と採用しない点。

## 方針
一つの依頼から、必要最小限のBotが実際に作業し、成果物を完成させる。
ボット間チャット、実行時系列、最終報告は同じ実行記録に結び付ける。
チャットを増やすことではなく、完成率・検証可能性・ユーザー介入の少なさで評価する。

## 重要な区別
- prompts/ はこの製品向けに新規作成した初期候補。外部プロンプトの転載ではなく、最適化済みという実測の主張もしない。
- skills/ は新規作成した3つの初期Skill。自製のSKILL.mdであり、外部Skillを同梱・自動実行していない。
- config内の接続先とモデルはプレースホルダー。実モデルの能力検証と予算承認が済むまで実行不可。
- examples/ は合成した契約例。実際のBot実行ログや成果物ではない。
- evals/cases.jsonl はこれから実行する受入テストケース。試験結果ではない。

## 設定ファイルの検査
Python環境に PyYAML と jsonschema がある場合:
```bash
python validate_blueprint.py
```
これは構造整合性を調べるだけであり、LLM/API疎通や製品動作を証明しない。
