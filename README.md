<h1 align="center">Agent Team</h1>
<p align="center"><strong>Ask once. One AI makes the file, another AI checks that exact version,<br />and you keep the record of what was checked.</strong></p>
<p align="center">A local-first AI team for people who will not ship an AI result they cannot verify.<br /><sub>Product: <strong>Agent Team</strong> · repository: <strong>FORIFOR/Multibot</strong> · MIT · English / 日本語 UI</sub></p>

<p align="center">
  <a href="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml"><img src="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml/badge.svg" alt="ci" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-1b1a17" alt="MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.12-1b1a17" alt="python 3.12" />
  <img src="https://img.shields.io/badge/providers-Claude%20%7C%20OpenAI--compatible%20%7C%20Ollama-c8471f" alt="providers" />
  <a href="https://forifor.github.io/Multibot/"><img src="https://img.shields.io/badge/site-forifor.github.io%2FMultibot-1b1a17" alt="site" /></a>
</p>

<p align="center"><a href="https://forifor.github.io/Multibot/">Website</a> · <a href="#quickstart">Quickstart</a> · <a href="#how-it-works">How it works</a> · <a href="#status-and-evidence">Status and evidence</a> · <a href="docs/STATUS.md">What's verified</a> · <a href="#日本語">日本語</a></p>

<p align="center">
  <img src="docs/media/app-results-en.webp" alt="The Agent Team work screen: the chosen guide.md version, 'Recorded checks passed for this version', and the team roster" width="760" />
</p>
<p align="center"><sub>A real screen, not a mock-up: a local Qwen 3.5 9B run recorded on 14 September 2026. The site has <a href="https://forifor.github.io/Multibot/">a captioned recording</a> of another real run.</sub></p>

## Why Agent Team

- **The maker is not the checker.** A coordinator plans the work, a maker writes the files, and a separate reviewer checks each finish condition. Reviews can fail, and the file goes back for a fix.
- **Checks are bound to bytes.** Every check and review applies to one revision's SHA-256. A new version starts unchecked, and "unverified" is never shown as "passed".
- **It runs on your machine, with your model.** Claude Code (no API key), the Anthropic API, OpenAI-compatible APIs or local Ollama. With a local model your input stays on your computer; with a cloud model it goes to that provider. The team does not post or send anything else on your behalf; the work stops at drafts.
- **Nothing is scripted.** The team chat shows messages that were really delivered between bots. The final report is compiled from the event log, and failed or partial runs stay visible.

```bash
uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart
```

One command with [uv](https://docs.astral.sh/uv/) and a logged-in [Claude Code](https://claude.com/claude-code). It checks the connection with one small real call, then opens the app at http://127.0.0.1:8787. Details and other providers are in [Quickstart](#quickstart).

You type **one request**. Attach the source files the team should use, then a Master plans the deliverables, a Researcher, a Builder and a Reviewer actually do the work. You get the files **plus** the real bot-to-bot messages, a timeline, and verification bound to each artifact revision. While a run is active, a human direction is recorded as an event and handed to the next task session; the existing plan is not silently rewritten.

<details>
<summary><strong>All features in detail</strong></summary>

- **Choose work by status.** Open **Work** (`/runs`), search request text, and switch between All, In progress, Needs you, Stopped or partial, and Completed. Each row shows the team size, cost and duration. Search stays in the browser tab and covers only the fetched requests. A row opens that request’s team conversation; returning preserves the filter. The list covers up to 50 recent accessible requests.
- **Follow the work.** The workroom shows reception → planning → creation → review → end from recorded states, with the current task and transition history available under Progress. Routine explanations, activity records and source context are collapsed so the conversation stays central. The workroom has one request header, Conversation / Results navigation and a compact emoji roster. The wide conversation panel keeps sender, recipient and original text together, follows live updates, and lets you pause following while reading. During active work it shows animated waiting dots, the current stage and recorded task owners even before a message arrives; connection loss switches to a static state check. Conversation search can narrow by text or participating bot without rewriting messages. Referenced artifacts link to their exact revision. Activity records remain separate when the bots have not sent a message. Reached stages do not certify deliverable quality. [Verification and limits](docs/quality/workroom-live.md).
- **Task handoffs.** Task workers with cross-agent dependencies must deliver a handoff, finding or decision to their downstream owner (reviewers report to the producer) before normal or inferred completion. Publishing new output requires a new handoff. Inbox reads include all messages addressed to that agent in the run. This does not require idle bots to speak or make the planning session a chat session.
- **No scripted chat.** The chat panel is a projection of `message.sent` events — messages that were really delivered to another bot's mailbox. A question wakes the other bot to answer.
- **Evidence, not vibes.** Checks and review verdicts are events bound to an artifact revision hash. The final report is compiled from the event log; a model summary cannot upgrade “started” to “done”.
- **Runtime-enforced limits.** Tool scope, write scope, budget reservation, approvals and cancellation are enforced in code, not by prompt wording.
- **Emoji icons.** In My team, choose an emoji for each bot or enter your own, preview it, then save. Blank uses a role emoji. Saved identities apply to new requests; past runs keep their recorded identities.
- **Per-bot configuration.** Each bot inherits a default connection and model and can override endpoint, model, effort and system prompt (lockable). Configured vs. provider-reported model are both shown. No silent fallbacks.
- **Replay, resume, fork, export.** Replay never calls a model. Fork from a checkpoint with a different model for one bot and compare. Export the whole run as JSONL.
- **Real inputs and handoff.** Attach `.txt`, `.md` or `.csv` material (up to 512KB per file in the UI). Send a change, question or edit from the team chat and keep the received direction in the run timeline.

</details>

## Quickstart

One command if you have [Claude Code](https://claude.com/claude-code) installed and logged in (no API key), plus [uv](https://docs.astral.sh/uv/):

```bash
uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart
```

`quickstart` makes one small real call through `claude -p` to confirm tool calling and JSON-schema output, then serves the UI at http://127.0.0.1:8787 and opens it. From a checkout:

```bash
git clone https://github.com/FORIFOR/Multibot && cd Multibot/backend
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/agentteam quickstart          # the built UI ships inside the package; `cd ../frontend && pnpm build` only if you change it
```

Other providers: set `defaults.connection_id` in Settings (or seed `data/agents.yaml` before the first start) to `anthropic` with `ANTHROPIC_API_KEY`, to an OpenAI-compatible endpoint (verified live with `gpt-4.1-mini`), or to local Ollama (`driver: ollama`, `http://localhost:11434/v1`). Every effective connection/model pair must match a successful probe before a run can start; placeholder models and unknown prices refuse to start with a structured reason.

Ollama's OpenAI-compatible endpoint can override Modelfile sampling defaults. To control runtime generation, set optional connection fields `ollama_temperature` (0–2) and `ollama_top_p` (>0–1) in the seed YAML or connection API; omitted values use the endpoint's defaults. Existing installations use the connection API because the saved database revision takes precedence over the YAML mirror. Connectivity probes always request `temperature: 0`; a successful probe does not establish document or review quality.


**Sandbox.** Builder/Reviewer commands run in Docker when a daemon answers (`--network none`, read-only root, host uid, CPU/memory/pid limits; Docker Desktop, Colima or any engine), otherwise in the macOS seatbelt; with neither, commands are refused rather than run unsandboxed (set `AGENTTEAM_SANDBOX=subprocess` to opt out knowingly).

**Language.** The app UI has an EN/JA toggle in the header (defaults to your browser language).

## First useful result / 最初の成果物

1. Open **My team / マイチーム** and check the configured model and destination. Connection probes and `quickstart` make a real model call; cloud providers may charge and receive your input. For local processing, select an already installed Ollama model with a loopback endpoint. Installation and model downloads are separate steps.
2. On the home screen, choose the editable “Summarize my notes / 資料を分かりやすくまとめて” example and attach a real `.md`, `.txt` or `.csv` document. Ask for `guide.md` with prerequisites, first steps and limitations. Review the destination, allowed tools and estimated budget before starting. Drafts and attachments remain in the current browser tab when you visit settings or reload; discard them explicitly when finished.
3. Watch the work and open the actual file. **Received / 受付** means the command arrived; **completed / 完了** is a runtime state. Neither guarantees factual correctness. Read the check record for that exact version and keep unverified findings visible.
   Optional: open **Check the output file / 成果物の条件を指定する** to set a filename, character bounds, and **Phrases to exclude / 使わない表現** (one literal phrase per line, case-sensitive, including quotations). The runtime checks the actual file before completion; these checks do not detect paraphrases or establish factual correctness. These exclusions use standard JSON Schema `not` / `anyOf` / escaped `pattern`, with the same validation for HTTP clients. With supplied text or attachments, you can explicitly select **Create one document / 添えた資料から1つの文書を作る**: the existing team writes the declared file and independently reviews it, skipping model-generated planning. This experimental workflow still depends on model capability.
4. Select a version, then choose **Save selected files / 採用したファイルを保存**. Its ZIP contains exactly the chosen revisions plus a SHA-256 manifest, report and events. **Get all latest files** remains a separate option and can contain different versions. You can edit a text copy in the browser and download it separately. A local edited copy does not inherit the published version's review record; publishing that copy as a new server revision is not implemented.
5. If a response is lost, inspect recent requests before explicitly retrying unchanged input. The app does not automatically repeat mutations. For a paused run with a plan, **Save correction / 修正指示を保存** records your direction before you explicitly resume; reload and open the last saved direction to confirm it. Saving does not start work or redo completed tasks. A paused/interrupted run must be inspected before an explicit resume; stopping cannot undo data already sent or external effects already completed.

**開発者向け:** [HTTP契約・互換性・エラー・権限](docs/quality/integration.md) · [標準ライブラリだけのHTTP利用例](examples/http_client.py) · [合格条件](docs/quality/acceptance.md) · [今回の検証結果と未達](docs/quality/report.md)。APIはpre-1.0です。安定版SDKや分散実行の保証はありません。組込み先ではビルドを固定し、生成されたファイルを信頼済みコードとして実行しないでください。

**Demo distinction:** `agentteam-demo` is an explicitly synthetic offline work record, useful for looking around but not proof of model behavior. For a real local walkthrough, use the task above with your own source document. This quality pass does not use the synthetic demo or scripted provider as acceptance evidence.

**Document review:** The document workflow includes separate language and source-accuracy criteria. Reviewers must compare the actual revision with the original request, including exceptions and abbreviation restrictions. This is model review, not a guarantee: real local-model trials missed language restrictions and a source qualification. Failed attempts and subsequent verification are retained in [live completion evidence](docs/quality/live-completion.md). Instructions received during a task are passed to the next task session; they do not retroactively change an already running review.

## How it works

| Component | Responsibility |
| --- | --- |
| **Master (planner)** | Request → deliverables, recorded assumptions, task DAG (structured output). The runtime validates schema, cycles, owners, tools, write scopes and limits; invalid plans get up to two retries, then the run fails with a recorded reason. |
| **AgentRunner** | One bot session = its own conversation state + a tool loop through the gateway. A worker receives its task, input artifact refs and its own inbox — not the whole history. |
| **MessageBus** | `send_message` really delivers to the recipient's mailbox and records `message.sent`. Purposes are limited to request / question / answer / handoff / finding / decision. |
| **ArtifactStore** | `publish_artifact` creates an immutable, SHA-256-hashed revision with an atomic write. Reviews and checks bind to a revision. |
| **Scheduler** | Dependency resolution, concurrency limit, review fail → revise → re-review (bounded), Master exception decisions, checkpoints, and bounded **milestone replanning**: when the DAG finishes, the Master may add tasks if the goal is not met (`max_replans`). |
| **PolicyEngine** | Budget = spent + reserved for in-flight calls; call/tool/message limits; tool and path scope; cancellation. Unknown cloud prices are never treated as free. |
| **Sandbox** | Docker (`--network none`, read-only root, host uid, resource limits) or macOS `sandbox-exec`; with neither available commands are refused, never silently unsandboxed. Every result records which backend ran. |
| **Providers** | `claude_cli` (local Claude Code, no key), `anthropic_messages` (official SDK), `openai_compatible_chat`, `ollama`. Per-bot choice; real probe before start. |

Everything is written to an append-only event store (SQLite WAL, per-run `seq`, UTC timestamps, redaction before persistence). Chat, timeline and report are projections of it. The event types are the blueprint's 11 plus runtime extensions, all validated against [`backend/agentteam/schemas/event.schema.json`](backend/agentteam/schemas/event.schema.json).

```
backend/agentteam/
  contracts.py    TeamPlan · Task · Event · Message · Artifact · Approval · Run
  config/         YAML + JSON Schema · secret references (env: / keychain: / file:)
  store/          EventStore · ArtifactStore · RunStore
  providers/      anthropic_messages (official SDK) · openai_compatible_chat / ollama (httpx) · fake (tests only)
  runtime/        PolicyEngine · MessageBus · ToolGateway · Sandbox · Checks · Web tools · AgentRunner · Planner · Scheduler · RunManager
  api/            REST + SSE + static UI
frontend/         React + TypeScript (request · run · settings)
docs/             website, blueprint (spec, security, references), status
evals/            40-case acceptance plan and coverage map
```

## Status and evidence

Agent Team is pre-1.0. These notes are kept at the same size as the good news; each links to the unedited evidence.

> **A real run, on the site:** [forifor.github.io/Multibot](https://forifor.github.io/Multibot/) shows the record of a real `claude-opus-5` run — request → first draft → three review findings → the changed passages → re-verification — where clicking a finding jumps to the changed part of the deliverable, plus a 29-second replay of the same run. Files: [`docs/evidence/scenarios/research2/`](docs/evidence/scenarios/research2/).
>
> [▶ 実モデルの作業記録・日本語解説（32秒）](https://forifor.github.io/Multibot/media/real-walkthrough-ja.mp4). Edited replay of a real run, with synthesized Japanese narration. The run ended **partial**, with the unfinished source check disclosed. No scripted provider is used in this video.
>
> **Benchmark audit (2026-09-14, updated):** latest attempts across 50 tasks × 3 repetitions: team 69 completed / 5 partial / 76 failed; single agent 150 completed. The team has 79 provider-blocked pairs. All 252 team attempts remain accounted for, including earlier failures. These are constructed evaluation inputs, not customer workflows; no team quality advantage is established. [Metrics and Reviewer audit](docs/evidence/readiness-2026-09-14/README.md).
>
> **Production work:** Authenticated dedicated deployments now include role checks, per-run access, audit records and offline backup/restore. SSO, distributed recovery and production acceptance remain in progress. [Controls and deployment](docs/PRODUCTION.md) · [Acceptance plan](docs/PRODUCTION_PLAN.md).
> **Creation workspace:** Desktop pairs the artifact with team conversation; mobile switches between them while keeping drafts. Text artifacts support a browser-local editable copy and file download, exact-version comparisons, and change instructions prepared from a selected excerpt. Editing a copy does **not** publish a server revision or inherit its checks. [Scope and verification](docs/quality/creation-studio.md).
> **Local evaluation:** Ollama trials exposed review, tool-recovery, source-input, artifact-ownership and completion-state bugs. The historical evaluation recorded **107 deterministic tests (1 skipped)**; this is not the current working-tree test result. The legacy 300-run comparison is preserved and stopped because its inputs contain fictional products and synthetic business data; it is not acceptance evidence. The fixed-series test using the actual repository documents and a local Qwen model was stopped after two v18 runs exposed translation drift. A v20 retry with explicit repair examples still failed its first current-contract check, so no local run is counted as accepted. [Fixes](docs/evidence/local-fixes-2026-09-14/README.md) · [v18 evidence](docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/README.md) · [v20 evidence](docs/evidence/real-readiness-v20-qwen35-fixed-2026-09-15/README.md).
>
> **Enterprise readiness:** demonstration material is available, but the required ten repeated runs of one workflow are not yet verified. The latest local-Qwen retry failed the current delivery contract on its first run. L2 customer-data PoC and L3 production readiness are not claimed. [L1 / L2 / L3 acceptance criteria](docs/ENTERPRISE_READINESS.md).
>
> **Latest readiness series (v61, 2026-09-25):** ten real local-Qwen runs of the same document workflow; all ten passed the mechanical and delivery contracts, nine reached a reviewer submission and all nine passed the four criteria, one was stopped by the time limit before review. The semantic review of the series is still pending, so **0 of 10 runs are accepted** and `production_ready=false`. [v61 evidence](docs/evidence/real-readiness-v61-qwen35-fixed-20260925/README.md).
>
> [Workplace benchmark: measured local pilot, failures, and remaining enterprise gates](docs/WORKPLACE_BENCHMARK.md).

## What is verified — and what isn't

Real runs through the local Claude Code CLI (`claude-opus-5`, provider-reported). Artifacts, reports and full event logs are committed unedited under [`docs/evidence/`](docs/evidence/).

**Reproducibility, 2026-09-13 afternoon — the same four requests, three runs each, nothing filtered** ([`docs/evidence/scenarios/rerun-2026-09-13/`](docs/evidence/scenarios/rerun-2026-09-13/), budget $6 and 120 model calls per run):

| Request | Completed | Plan size | Review pass | Cost / run | Time / run |
| --- | --- | --- | --- | --- | --- |
| CLI tool in Python with unittest + README | **3 / 3** | 2 tasks every time | 22/22 | $2.09–3.14 | 16–19 min |
| 4-file static docs site | **3 / 3** | 2 tasks every time | 22/22 | $1.62–1.72 | 15–17 min |
| Launch page + 3 post drafts | **2 / 3** | 2 (one run grew to 6) | 38/39 | $1.70–5.67 | 20–37 min |
| Source-grounded comparison of 3 web pages | **0 / 3** (all *partial*) | 4–5 | 21/24 | $5.48–6.11 | 31–35 min |

I re-ran the generated unit tests myself for all three code runs (18 / 19 / 17 tests, OK) and checked the three generated sites for broken internal links (none). The launch-page run that ended *partial* had both planned tasks accepted at $1.29; the Master then added two rounds of wording polish and the last task hit the model-call limit. All three research runs had their planned `research.md` accepted, then ended *partial* for one structural reason: the default reviewer had no `web_fetch`, so it could not check claims against their sources as the request asked, and the Master's workaround tasks exhausted the budget. Both are fixed after this evaluation (reviewer gets `web_fetch`; a milestone replan is skipped and recorded when less than one agent session of budget or model calls remains; the Master is told not to add polish once every deliverable is accepted; partial runs carry a reason). The fixes are covered by deterministic tests; one post-fix research run **completed** (reviewer fetched all three sources, 5/5 review pass, $2.05, 8m44s, [`research-postfix/`](docs/evidence/scenarios/rerun-2026-09-13/research-postfix/)) — one run, not a new 3-run series.

Earlier single runs (v0.2.0, 2026-09-13 morning): launch page completed ($1.66, 18 min); code completed ($1.87, 16 min); research failed on a scheduler deadlock, then *partial* after the fix ($6.07, 24 min); docs site completed ($3.03, 15 min). Other providers on the launch-page request: OpenAI-compatible `gpt-4.1-mini` completed in 29 s for $0.02; local Ollama `qwen2.5:7b` reached *partial*; `qwen2.5:3b` could not produce a valid plan.

Also verified: **107 deterministic tests, 1 skipped** (DAG validation, real delivery with a question/answer round trip, review → revise → re-review, milestone replanning and its budget gate, budget reservation, approvals with hash/nonce, cancel → resume, fork, redaction, SSRF guard, Docker and seatbelt sandbox confinement, SSE cursor replay, event-schema conformance), and in CI on every push: the Docker isolation test on Linux and a headless-Chrome UI smoke of the bundled UI in English and Japanese (start a request → run view → final report → settings, exits non-zero on any error).

Still open: three runs per request is a record, not a benchmark; plans vary because the Master decides; research-heavy requests are the most expensive (about $6 at list price) and the least reliable; local 7B models complete the mechanics but not the review protocol; no one outside the author has used it yet. Full matrix and the list of bugs found by real runs: [`docs/STATUS.md`](docs/STATUS.md). Security boundaries: [`SECURITY.md`](SECURITY.md).

## Read more

- [dev.to: I built an AI team that ships real work — and shows you the conversation](https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a)
- [Zenn（日本語）: Claude Codeで調査・レビュー・修正を回すOSSを作った。3件直っても「未完了」だった](https://zenn.dev/forifori/articles/agent-team-launch)
- Launch threads on X: [English](https://x.com/i/status/2098800226199130220) · [日本語](https://x.com/i/status/2098800307421716835)

## Design notes

The product was built from a written blueprint ([`docs/blueprint/`](docs/blueprint/)): spec, implementation brief, security requirements, references, and 40 acceptance cases. Deliberate deviations (no Deep Agents/LangGraph dependency, extended event enum, refusal fallback off by default) are recorded in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md). Changes by version: [`CHANGELOG.md`](CHANGELOG.md).

## 日本語

**依頼は一度。成果物も、検証の経緯も。** AI チームが作成・レビュー・修正を進め、誰が何を確かめたかまで、成果物と一緒に残します。（製品名 Agent Team、リポジトリ FORIFOR/Multibot、MIT）

Master が成果物と完了条件を決め、必要な Bot（Researcher / Builder / Reviewer）だけが実際に作業します。成果物、Bot 間の実メッセージ、時系列、最終報告は同じ実行記録（append-only Event Store）から表示され、台本の会話や固定の成功ログは使いません。

- 成果物を開くと、誰が作り、何を引き継ぎ、どの検証を通ったかまで辿れる
- 成果物の版間差分を確認して採用版を明示でき、成果物・最終報告・イベントログを run 単位の ZIP で取得できる
- 各 Bot の接続先・モデル・システムプロンプトを個別に上書きできる（共通設定を継承、手動固定あり）
- 停止・再開・分岐（Bot のモデルを変えて別案）・再生（LLM 呼出なし）・JSONL エクスポート
- 権限・予算・回数上限・承認はプロンプトではなく Runtime が強制

上の画像は、ローカルの Qwen 3.5 9B による実際の実行画面です（2026-09-14）。[32秒の映像](https://forifor.github.io/Multibot/media/real-walkthrough-ja.mp4)は別の実行（`claude-opus-5`）の記録を編集し、日本語合成音声を付けたものです。この実行は予算上限で部分完了し、未検証の出典照合を明示しています。

```bash
uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart
```

uv とログイン済みの Claude Code があれば、この1行で始められます。ほかの接続先（Anthropic API、OpenAI互換、Ollama）は [Quickstart](#quickstart) を参照してください。企業紹介用のデモ・導入設計相談は可能ですが、有償PoCや本番運用への適合は別途検証が必要です。

## Third-party

- The "thinking" orb in the app header is a standalone export of the [Liquid Orb Editor](https://github.com/LerSent001/orb) (MIT, © 2026 LerSent001), vendored under `frontend/src/assets/` with its license and parameter snapshot.

## License

MIT. Bundled prompts and skills are original to this project (see `docs/blueprint/REFERENCES.md`).

### Bot conversation voices

In **My team / マイチーム**, edit **性格・話し方** to give each bot its own conversational style (up to600 characters). A blank value uses the role default. Settings apply to new requests and are frozen in the run configuration. Style does not change permissions, review criteria, factual claims, or the requested writing style of deliverables. Actual messages are delivered through the existing message gateway; distinct model-generated voices still require live verification.

### 依頼に合わせたAIチーム（experimental）

通常の依頼画面では「この依頼に合うチームを自動で組む」が既定です。AIが必要な専門性・人数・個人名・話し方を提案し、そのチームに作業を割り当てます。画面の「今回のチーム構成」で理由を確認できます。固定のマイチームを使う場合はチェックを外してください。既存の接続先・権限・上限を継承し、編成のために追加のモデル呼び出しが発生します。文書専用・単独モードは従来の構成です。

HTTPでは `inputs.team_selection: "adaptive"` を指定します。省略時は従来の固定チームです。編成完了と成果物の完成・検証合格は別に扱います。詳しくは [統合契約](docs/quality/integration.md#adaptive-teams-experimental) を参照してください。

現在のローカル実行では、人数の異なる編成、メンバーへの割当、会話の保存、成果物の改訂を確認しています。一方、設定した話し方の遵守と、設計内容を正しく審査して最後まで完成させる精度には未達があります。モデルによる審査の合格表示だけで正確性を保証しません。[実行結果と未達条件](docs/quality/adaptive-team-status.md)を確認してください。

マイチームでは、🐣まめ・🐻ぽん・🐱むぎ・🐧るるのキャラクターから名前・絵文字・話し方を選び、その後も自由に編集できます。「変更を保存」するまで設定は変わりません。キャラクターは担当業務や人数とは独立しており、進行中のチームは開始時の設定を保ちます。

依頼画面の「自分で選ぶ」では、設定したキャラクターから参加メンバーを選べます。
名前・絵文字・話し方は設定画面で変更できます。案内役とレポート担当は自動で参加し、
選んだ仲間の仕事は既存の権限内で計画されます。確認担当が必須の設定では、外すと開始できません。
「おまかせ」は依頼ごとに別のチームを提案します。
