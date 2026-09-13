# 3ページ比較調査メモ（deepagents / DeerFlow / Agent Skills 仕様）— 最終版

> 本ファイルは `research.md` revision 1 の後継（最終版）です。rev1 の内容をすべて引き継いだうえで、根拠抜粋が欠落していた記述の削除・出典追加、および deer-flow README 再取得の結果を反映しています。以降 `research.md` rev1 ではなく本ファイルを参照してください。差分は末尾の「改訂履歴」を参照。

作成日: 2026-09-13 / 作成者: researcher / 根拠: `sources-v2.md`（取得ログ・原文抜粋）

## 概要

本メモは、指定された3つの公開ページを web_fetch で実際に取得し、取得できた本文のみを根拠に「主張・対象読者・ライセンス」を比較したものです。

- 取得対象
  1. https://github.com/langchain-ai/deepagents（取得成功・全文）
  2. https://github.com/bytedance/deer-flow（**部分取得**。README 後半は取得不可。raw README での再取得も切り詰め）
  3. https://agentskills.io/specification（取得成功・全文）
- 3ページの位置づけの違い（取得本文から読み取れる範囲）
  - deepagents と DeerFlow はいずれも自らを「agent harness（エージェントの実行基盤）」と名乗る**実装プロジェクト**であり、sub-agents・サンドボックス・メモリ・skills といった構成要素の語彙が重なる。
  - agentskills.io/specification は実装ではなく、`SKILL.md` というファイル形式を定義する**フォーマット仕様書**であり、比較軸が1つ上のレイヤーにある。
  - 3ページに共通する接点は「skills（エージェントが必要時に読み込む再利用可能な振る舞い）」という概念で、deepagents は機能一覧に Skills を挙げ（出典1）、DeerFlow は "extensible skills" を前面に出し（出典2）、agentskills.io はその skill のファイル仕様を定義している（出典3）。
  - ただし、deepagents / DeerFlow の各ページが agentskills.io の仕様に準拠すると明示しているかどうかは、取得本文からは**確認できなかった**（推測しない）。
- ライセンスは deepagents / DeerFlow の2つとも、リポジトリページ表示および LICENSE ファイル本文で MIT License を確認。agentskills.io/specification はページ本文にサイト／仕様自体のライセンス記載を**確認できず**。

## 比較表

| 観点 | ① langchain-ai/deepagents | ② bytedance/deer-flow | ③ agentskills.io/specification |
| --- | --- | --- | --- |
| 種別 | OSS のエージェント・ハーネス（実装） | OSS のスーパーエージェント・ハーネス（実装） | ファイル形式の仕様書（ドキュメント） |
| 掲げる主張（キャッチ） | "The batteries-included agent harness."／"an opinionated agent that runs out of the box. Extend, override, or replace any piece."<br>出典: https://github.com/langchain-ai/deepagents | "an open-source super agent harness that orchestrates sub-agents, memory, and sandboxes to do almost anything — powered by extensible skills"<br>出典: https://github.com/bytedance/deer-flow | "The complete format specification for Agent Skills."<br>出典: https://agentskills.io/specification |
| 主張の柱 | Opinionated / Extensible / Model-agnostic / Production-ready の4原則。機能として Sub-agents, Filesystem, Context management, Shell access, Persistent memory, Human-in-the-loop, Skills, Tools を列挙<br>出典: https://github.com/langchain-ai/deepagents | 2.0 は v1 とコードを共有しないフルリライト。数分〜数時間かかる長時間タスクを sandbox・memory・tools・skill・subagents・message gateway で扱うと説明<br>出典: https://github.com/bytedance/deer-flow | skill は最低限 `SKILL.md` を含むディレクトリ。YAML frontmatter（name/description 必須、license/compatibility/metadata/allowed-tools 任意）＋Markdown 本文。`scripts/` `references/` `assets/` は任意。Progressive disclosure により段階的に読み込む<br>出典: https://agentskills.io/specification |
| 対象読者 | Python（`uv add deepagents` / `create_deep_agent`）および JS/TS でエージェントを組む開発者。LangChain / LangGraph / LangSmith 利用者、本番運用を検討する層を FAQ で明示的に想定<br>出典: https://github.com/langchain-ai/deepagents | ローカル環境にセルフホストする開発者・運用者（`git clone` → `make setup` → `make doctor`）。および Claude Code / Codex / Cursor / Windsurf 等の「コーディングエージェント」自身に手順を渡す使い方を明記<br>出典: https://github.com/bytedance/deer-flow , https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md | ナビゲーションで読者を2分。"For skill creators"（skill を書く人）と "For client implementors"（skills 対応を実装するクライアント開発者）<br>出典: https://agentskills.io/specification |
| ライセンス | MIT License。リポジトリページに "MIT license" 表示があり、LICENSE 本文に "MIT License / Copyright (c) LangChain, Inc." を確認<br>出典: https://github.com/langchain-ai/deepagents , https://raw.githubusercontent.com/langchain-ai/deepagents/main/LICENSE | MIT License。リポジトリページに "MIT license" 表示、README 本文冒頭に MIT バッジ（リンク先 `./LICENSE`）があり、LICENSE 本文に "MIT License / Copyright (c) 2025 Bytedance Ltd. and/or its affiliates / Copyright (c) 2025-2026 DeerFlow Authors" を確認（README 本文の "License" セクションは**取得不可**）<br>出典: https://github.com/bytedance/deer-flow , https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md , https://raw.githubusercontent.com/bytedance/deer-flow/main/LICENSE | **記載確認できず**。取得本文にサイト／仕様自体のライセンス表記はなく、`license` は SKILL.md の任意フィールドの説明として登場するのみ<br>出典: https://agentskills.io/specification |

## 個別メモ

### ① langchain-ai/deepagents

出典: https://github.com/langchain-ai/deepagents （取得日時 2026-09-13T04:01:18Z および 04:19:25Z, HTTP 200, 全文取得）

- **主張・売り**（出典: https://github.com/langchain-ai/deepagents）
  - 見出しは "The batteries-included agent harness."。本文で "Deep Agents is an open source agent harness — an opinionated agent that runs out of the box. Extend, override, or replace any piece." と定義。
  - 4つの原則を明示: Opinionated（long-horizon・multi-step 向けにデフォルトを調整）、Extensible（fork せずに任意の部分を差し替え可能）、Model-agnostic（tool calling 対応の LLM なら frontier / open-weight / local いずれも可）、Production-ready（LangGraph 上に構築、LangSmith でトレース・評価・デプロイ）。
  - 機能として Sub-agents（隔離コンテキストへの委譲）、Filesystem、Context management、Shell access、Persistent memory、Human-in-the-loop、Skills、Tools（自作関数または任意の MCP サーバ）を列挙。
  - 差別化の説明として、LangGraph（グラフ実行時）→ LangChain `create_agent`（最小ハーネス）→ Deep Agents（より意見の強いハーネス）というレイヤ関係を FAQ で提示。
  - "Inspired by Claude Code: an attempt to identify what makes it general-purpose, and push that further." と着想元を明記。
  - セキュリティ方針として "trust the LLM" モデルを採り、境界の強制は tool/sandbox レベルで行うべきと明記。
- **対象読者**（出典: https://github.com/langchain-ai/deepagents）
  - Python 開発者。Quickstart が `uv add deepagents` と `create_deep_agent(...)` のコード片で構成される。
  - JavaScript/TypeScript 利用者も対象（"available as a JavaScript/TypeScript library — see deepagents.js"）。
  - 既存の LangChain / LangGraph / LangSmith 利用者。FAQ が「LangGraph や LangChain との違い」「いつ Deep Agents を使うか」に割かれている。
  - 本番導入を検討する層。FAQ に "Can I use this in production? Yes! ... Pair it with LangSmith for tracing, evaluation, and monitoring. See Going to production for the full guide." とあり、本番移行ガイドへのリンクを案内している（リンク先 URL とガイド本文は未取得のため内容には触れない）。
  - ターミナルで使う既製のコーディングエージェント "Deep Agents Code" の利用者にも言及。
- **ライセンス**（出典: https://github.com/langchain-ai/deepagents および https://raw.githubusercontent.com/langchain-ai/deepagents/main/LICENSE）
  - リポジトリページの表示に "MIT license"（Repository files navigation および Resources 欄）。
  - LICENSE ファイル本文で "MIT License / Copyright (c) LangChain, Inc." を確認。

### ② bytedance/deer-flow

出典: https://github.com/bytedance/deer-flow （取得日時 2026-09-13T04:01:19Z および 04:01:24Z, HTTP 200, **部分取得 / truncated=True**）、https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md （取得日時 2026-09-13T04:18:37Z, HTTP 200, **部分取得 / truncated=True, 末尾 28,180 文字が切り詰め**）

> 注意: 以下は取得できた README 前半（冒頭〜Quick Start > Configuration）のみを根拠にしています。README 後半（Running the Application / Advanced 以降、Core Features、⚠️ Security Notice、"License" セクション本文などを含む）は**取得不可**であり、その内容には触れていません。詳細は「取得できなかったページ・範囲」を参照。

- **主張・売り**（出典: https://github.com/bytedance/deer-flow , https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md）
  - リポジトリ説明文（ページタイトル）: "An open-source long-horizon SuperAgent harness that researches, codes, and creates. With the help of sandboxes, memories, tools, skill, subagents and message gateway, it handles different levels of tasks that could take minutes to hours."
  - README 冒頭: "DeerFlow (Deep Exploration and Efficient Research Flow) is an open-source super agent harness that orchestrates sub-agents, memory, and sandboxes to do almost anything — powered by extensible skills."
  - 実績アピール: "On February 28th, 2026, DeerFlow claimed the 🏆 #1 spot on GitHub Trending following the launch of version 2."（ページ側の主張であり、第三者検証はしていない）
  - バージョン方針を明記: "DeerFlow 2.0 is a ground-up rewrite. It shares no code with v1."。旧 Deep Research フレームワークは `1.x` ブランチで維持、開発の主軸は 2.0 へ移行。
  - 多言語 README（English / 中文 / 日本語 / Français / Русский）を用意。
  - 自社エコシステムとの結び付きが強い。README に "Coding Plan from ByteDance Volcengine" 節があり "We strongly recommend using Doubao-Seed-2.0-Code, DeepSeek v3.2 and Kimi 2.5 to run DeerFlow" と推奨モデルを挙げ、BytePlus / Volcengine の Coding Plan へ誘導する。続く "InfoQuest" 節では "DeerFlow has newly integrated the intelligent search and crawling toolset independently developed by BytePlus--InfoQuest" と、BytePlus 製の検索・クロールツール群 InfoQuest の統合を紹介している。
- **対象読者**（出典: https://github.com/bytedance/deer-flow , https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md）
  - 自分の環境にセルフホストする開発者・運用者。導入手順は `git clone` → `make setup`（対話ウィザードで LLM プロバイダ、Web 検索、sandbox mode / bash access / file-write tools などの実行・安全設定を選択し `config.yaml` と `.env` を生成、所要約2分）→ `make doctor` で検証。
  - 手動設定を好む上級者向けに `make config`（フルテンプレートのコピー）と `config.example.yaml` を案内し、README 本文に OpenRouter（`base_url` 指定）、Responses API（`use_responses_api: true` / `output_version: responses/v1`）、vLLM（`deerflow.models.vllm_provider:VllmChatModel`）、CLI-backed providers（Codex CLI / Claude Code OAuth）の設定例を掲載している。
  - 特徴的なのは「コーディングエージェント自身」を読者に含める点: "If you use Claude Code, Codex, Cursor, Windsurf, or another coding agent, you can hand it the setup instructions in one sentence"、"That prompt is intended for coding agents."
  - 不具合報告者・メンテナ向けに `make support-bundle` による issue 用サマリ生成を案内。
  - 比較して、deepagents がライブラリ API（`create_deep_agent`）を最初に見せるのに対し、DeerFlow は clone と Makefile ベースのセットアップを最初に見せる。つまり「アプリケーション／プラットフォームとして立ち上げる利用者」寄りの導線である（取得できた前半部分の構成から読み取れる範囲の解釈）。
- **ライセンス**（出典: https://github.com/bytedance/deer-flow , https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md , https://raw.githubusercontent.com/bytedance/deer-flow/main/LICENSE）
  - リポジトリページの表示に "MIT license"。
  - README 本文の冒頭バッジに `[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)`（リンク先は同リポジトリの `./LICENSE`）。
  - README 本文の "License" セクションは目次に見出しが存在するが**本文は取得不可**。
  - 追跡した LICENSE ファイル本文で "MIT License / Copyright (c) 2025 Bytedance Ltd. and/or its affiliates / Copyright (c) 2025-2026 DeerFlow Authors" を確認。

### ③ agentskills.io/specification

出典: https://agentskills.io/specification （取得日時 2026-09-13T04:01:19Z および 04:18:38Z, HTTP 200, 全文取得）

- **主張・売り**（出典: https://agentskills.io/specification）
  - ページ冒頭の定義: "The complete format specification for Agent Skills."。製品ではなく仕様文書として自らを位置づけている。
  - ディレクトリ構造: skill は最低限 `SKILL.md` を含むディレクトリ。任意で `scripts/`（実行可能コード）、`references/`（ドキュメント）、`assets/`（テンプレート・リソース）。
  - `SKILL.md` は YAML frontmatter ＋ Markdown 本文。frontmatter は必須2項目（`name` 最大64文字・小文字英数字とハイフンのみ・親ディレクトリ名と一致、`description` 最大1024文字で「何をするか」と「いつ使うか」の両方を書く）と、任意4項目（`license`、`compatibility` 最大500文字、`metadata` 文字列マップ、`allowed-tools` は実験的）。
  - Progressive disclosure（段階的開示）を設計原則として提示: メタデータ（約100トークン、起動時に全 skill 分ロード）→ 指示本文（5000トークン未満推奨、skill 起動時にロード）→ リソース（必要時のみ）。`SKILL.md` は500行未満を推奨。
  - 検証手段として参照実装ライブラリ `skills-ref` の `skills-ref validate ./my-skill` を案内。
  - 記述スタイルとして、良い `description` の例（"Good example: Extracts text and tables from PDF files, ... Use when working with PDF documents ..."）と悪い例（"Poor example: Helps with PDFs."）を並べ、`name` では Valid / Invalid の例を示す。また要件は "Must be 1-64 characters" のように "Must" で、推奨は "Should describe both what the skill does and when to use it"、"We recommend keeping it short" のように "Should" / "We recommend" で書き分けている（ただし RFC 2119 のようなキーワード定義はページ本文にない）。
- **対象読者**（出典: https://agentskills.io/specification）
  - ナビゲーションが読者を明示的に2グループへ分けている: "For skill creators"（Quickstart / Best practices / Optimizing descriptions / Evaluating skills / Using scripts）と "For client implementors"（Adding skills support）。
  - すなわち skill を作る側と、skills 対応を自プロダクトに実装する側の双方が対象。特定のベンダー製品に限定しない書き方で、"Supported languages depend on the agent implementation"、"Support for this field may vary between agent implementations"、"Clients can use this to store additional properties not defined by the Agent Skills spec" といった実装差を前提とした記述が並ぶ。
  - コミュニティ導線として公式 Discord サーバーの告知バナーがある。
- **ライセンス**（出典: https://agentskills.io/specification）
  - **記載確認できず**。取得したページ本文（2回の全文取得とも）に、このページや Agent Skills 仕様そのものに適用されるライセンス表記・著作権表示は見当たらなかった。
  - ページ中の `license` はすべて「SKILL.md の任意 frontmatter フィールド」としての説明である（"license / No / License name or reference to a bundled license file."、"The optional license field: Specifies the license applied to the skill"）。例示に現れる `license: Apache-2.0` や `license: Proprietary. LICENSE.txt has complete terms` は**記述例**であり、サイト自体のライセンスではない。

## 取得できなかったページ・範囲

- 完全に取得できなかったページ: **なし**（3URL とも HTTP 200 を取得）。
- **取得不可（部分）: https://github.com/bytedance/deer-flow の README 後半**
  - GitHub の HTML ページ: 1回目 2026-09-13T04:01:19Z（`truncated=True`、末尾 8,425 文字が切り詰め）、2回目 2026-09-13T04:01:24Z（`max_chars=40000`、`truncated=True`、末尾 28,425 文字が切り詰め）。なお 1回目のリクエストで指定した `max_chars` の値は取得ログに記録が残っていない（未記録）ため、本メモでは数値を示さない。`max_chars` を拡大しても取得範囲は伸びず、同一箇所（Manual model configuration examples 付近）で打ち切られた。
  - raw README（https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md）: 2026-09-13T04:18:37Z、`max_chars=40000`（web_fetch の上限値）、HTTP 200、`truncated=True`。応答末尾に `...[truncated 28180 chars]` と表示され、README 後半 28,180 文字が取得できなかった。web_fetch にオフセット指定の手段がないため、複数回に分けても後半を取得できない。
  - 取得できた範囲: 冒頭バッジ 〜 Official Website / Sister Projects / Coding Plan from ByteDance Volcengine / InfoQuest / Table of Contents / One-Line Agent Setup / Quick Start > Configuration（Manual model configuration examples、CLI-backed provider examples を含む）まで。
  - **取得できなかった範囲（内容に踏み込んでいない箇所）**: Running the Application（Deployment Sizing / Docker / Local Development）、Advanced（Sandbox Mode / MCP Server / IM Channels / 各種 Tracing / Using Multiple Providers / Personal Access Tokens）、From Deep Research to Super Agent Harness、Core Features 以降のすべて（Skills & Tools, Claude Code Integration, Session Goals, Manual Context Compaction, Sub-Agents, Sandbox & File System, Context Engineering, Long-Term Memory, Recommended Models, Embedded Python Client, Scheduled Tasks, Terminal Workbench (TUI), Documentation, ⚠️ Security Notice, Contributing, **License**, Acknowledgments, Key Contributors, Star History）。これらの見出し名は目次から確認できたが本文は未取得のため、本メモでは内容に触れていない。
- **未取得のリンク先**（本メモで内容に触れていないもの）
  - deepagents の "Going to production" ガイド本体。FAQ 中のリンクテキストの存在のみ確認しており、リンク先 URL も本文も未取得。
  - DeerFlow の `Install.md`、`config.example.yaml` の実体、InfoQuest のドキュメント、BytePlus / Volcengine の Coding Plan ページ。
  - agentskills.io の `skills-ref` リポジトリおよび下位ページ（Quickstart / Best practices 等）。
- **確認できなかった事項**
  - agentskills.io/specification のサイト／仕様自体のライセンス表記（全文取得したが本文に見当たらず、「記載確認できず」）。
  - deepagents / DeerFlow の各ページが agentskills.io の仕様に準拠しているかどうかの明示。

## 出典一覧

| # | URL | 取得日時（UTC） | 取得可否 |
| --- | --- | --- | --- |
| 1 | https://github.com/langchain-ai/deepagents | 2026-09-13T04:01:18Z / 2026-09-13T04:19:25Z | 取得成功（全文、truncated=False） |
| 2 | https://raw.githubusercontent.com/langchain-ai/deepagents/main/LICENSE | 2026-09-13T04:01:35Z | 取得成功（HTTP 200, text/plain） |
| 3 | https://github.com/bytedance/deer-flow | 2026-09-13T04:01:19Z / 2026-09-13T04:01:24Z | 部分取得（truncated=True、末尾 8,425 文字 / 28,425 文字が切り詰め） |
| 4 | https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md | 2026-09-13T04:18:37Z | 部分取得（HTTP 200、truncated=True、末尾 28,180 文字が未取得） |
| 5 | https://raw.githubusercontent.com/bytedance/deer-flow/main/LICENSE | 2026-09-13T04:01:35Z | 取得成功（HTTP 200, text/plain） |
| 6 | https://agentskills.io/specification | 2026-09-13T04:01:19Z / 2026-09-13T04:18:38Z | 取得成功（全文、truncated=False） |

各 URL の原文抜粋は `sources-v2.md` を参照。

## 改訂履歴

### `research.md` rev1 → `research-v2.md` rev1

- **追加した根拠抜粋（`sources-v2.md` に追記）**
  1. deepagents の "Going to production" ガイドへの案内 — FAQ 原文 "…Pair it with LangSmith for tracing, evaluation, and monitoring. See Going to production for the full guide."（2026-09-13T04:19:25Z 再取得）。
  2. DeerFlow の "Coding Plan from ByteDance Volcengine" 節と "InfoQuest" 節の原文（BytePlus 製ツール群の統合）。
  3. DeerFlow の `config.example.yaml` 案内および OpenRouter / Responses API / vLLM / CLI-backed providers の設定例原文。
  4. agentskills.io の Good / Poor description の具体例原文。
  5. agentskills.io の "Must" / "Should" / "We recommend" の書き分け原文。
- **削除・修正した記述**
  - 根拠となる取得ログがない「1回目 max_chars=20000」という数値記述を削除。
  - deer-flow の取得可否記述を再取得結果（raw README の truncated 28,180 文字）に合わせて更新。
- **取得可否の変化**
  - 新たに https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md を `max_chars=40000` で取得し、README 前半（Quick Start > Configuration まで）を原文で確保。ただし後半 28,180 文字は引き続き取得不可。
  - README の "License" セクション本文は再取得後も取得できず、ライセンス欄の根拠はリポジトリページ表示・README のバッジ・LICENSE ファイル本文のままとした。

### `research-v2.md` rev1 → 本改訂（rev2）

- レビュー指摘（t3a1 の項目6）に対応し、「取得できなかったページ・範囲」節に残っていた deer-flow 1回目取得の「（max_chars=20000）」という数値記述を削除し、「1回目のリクエストで指定した `max_chars` の値は取得ログに記録が残っていない（未記録）」と明記した。`sources-v2.md` の「1回目の max_chars 値は記録が残っていない（未記録）」という記載と一致させたもの。
- 上記以外の本文の主張・出典・取得可否記述は rev1 から変更していない（新たな取得は行っていない）。
