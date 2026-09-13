<p align="center">
  <img src="docs/media/demo.gif" alt="Agent Team: one request, real bot-to-bot messages, artifact revisions, final report" width="880" />
</p>

<h1 align="center">Agent Team</h1>
<p align="center"><strong>One request. The deliverable, and how it was checked.</strong><br />An AI team drafts, reviews and revises the work, and keeps who checked what next to the deliverable.</p>
<p align="center"><sub>Product name: <strong>Agent Team</strong> · repository: <strong>FORIFOR/Multibot</strong> · MIT</sub></p>

<p align="center">
  <a href="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml"><img src="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml/badge.svg" alt="ci" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-1b1a17" alt="MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.12-1b1a17" alt="python 3.12" />
  <img src="https://img.shields.io/badge/providers-Claude%20%7C%20OpenAI--compatible%20%7C%20Ollama-c8471f" alt="providers" />
  <a href="https://forifor.github.io/Multibot/"><img src="https://img.shields.io/badge/site-forifor.github.io%2FMultibot-1b1a17" alt="site" /></a>
</p>

<p align="center"><a href="https://forifor.github.io/Multibot/">Website: a real work record you can click through</a> · <a href="#quickstart">Quickstart</a> · <a href="#how-it-works">How it works</a> · <a href="docs/STATUS.md">What's verified</a> · <a href="#日本語">日本語</a></p>

> **A real run, on the site:** [forifor.github.io/Multibot](https://forifor.github.io/Multibot/) shows the record of a real `claude-opus-5` run — request → first draft → three review findings → the changed passages → re-verification — where clicking a finding jumps to the changed part of the deliverable, plus a 29-second replay of the same run. Files: [`docs/evidence/scenarios/research2/`](docs/evidence/scenarios/research2/).
>
> [▶ Narrated intro (59s, English)](https://forifor.github.io/Multibot/media/intro-en.mp4) · [日本語版 (58s)](https://forifor.github.io/Multibot/media/intro.mp4). The GIF above drives the real UI and runtime with the **scripted test provider** (no LLM calls, labelled “FAKE PROVIDER” on screen) so it is deterministic and free to reproduce. With a real connection the same screens are fed by live model calls; the run header shows the model the provider actually reported and the measured cost.

You type **one request**. A Master plans the deliverables, a Researcher, a Builder and a Reviewer actually do the work, and you get the files **plus** the real bot-to-bot messages, a timeline, and verification bound to each artifact revision.

- **No scripted chat.** The chat panel is a projection of `message.sent` events — messages that were really delivered to another bot's mailbox. A question wakes the other bot to answer.
- **Evidence, not vibes.** Checks and review verdicts are events bound to an artifact revision hash. The final report is compiled from the event log; a model summary cannot upgrade “started” to “done”.
- **Runtime-enforced limits.** Tool scope, write scope, budget reservation, approvals and cancellation are enforced in code, not by prompt wording.
- **Per-bot configuration.** Each bot inherits a default connection and model and can override endpoint, model, effort and system prompt (lockable). Configured vs. provider-reported model are both shown. No silent fallbacks.
- **Replay, resume, fork, export.** Replay never calls a model. Fork from a checkpoint with a different model for one bot and compare. Export the whole run as JSONL.

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

Other providers: set `defaults.connection_id` in `data/agents.yaml` (or in Settings) to `anthropic` with `ANTHROPIC_API_KEY`, to an OpenAI-compatible endpoint (verified live with `gpt-4.1-mini`), or to local Ollama (`driver: ollama`, `http://localhost:11434/v1`). Every connection must pass the probe before a run can start; placeholder models and unknown prices refuse to start with a structured reason.

**Sandbox.** Builder/Reviewer commands run in Docker when a daemon answers (`--network none`, read-only root, host uid, CPU/memory/pid limits; Docker Desktop, Colima or any engine), otherwise in the macOS seatbelt; with neither, commands are refused rather than run unsandboxed (set `AGENTTEAM_SANDBOX=subprocess` to opt out knowingly).

**Language.** The app UI has an EN/JA toggle in the header (defaults to your browser language).

## How it works

| Component | Responsibility |
| --- | --- |
| **Master (planner)** | Request → deliverables, recorded assumptions, task DAG (structured output). The runtime validates schema, cycles, owners, tools, write scopes and limits; invalid plans are sent back once, then the run fails honestly. |
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

## What is verified — and what isn't

Real runs through the local Claude Code CLI (`claude-opus-5`, provider-reported), 2026-09-13. Every row is one run of the request as written; artifacts, reports and full event logs are committed unedited under [`docs/evidence/`](docs/evidence/).

| Request | Result | Tasks | Artifacts | Checks | Review | Cost | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Launch page + 3 post drafts | completed | 2 | 4 | 10/10 | 6/6 | $1.66 | 18 min |
| CLI tool in Python with unittest + README | completed | 2 | 4 | 14/14 | 7/7 | $1.87 | 16 min |
| Source-grounded comparison of 3 web pages (1st) | **failed** | 3 | 2 | – | – | $0.91 | 5 min |
| … same, after the scheduler fix | partial | 7 | 5 | 10/13 | 5/8 | $6.07 | 24 min |
| 4-file static docs site | completed | 2 | 5 | 39/39 | 12/12 | $3.03 | 15 min |

The reviewer re-ran the generated unit tests inside the Docker sandbox; I re-ran them independently as well (16 tests, OK). The failed research run exposed a real scheduler deadlock (a task depending on a task that itself awaited review), now fixed and covered by a test; the re-run produced a revised memo with the reviewer's three findings fixed and cited, but hit the per-session budget cap twice, so it ended *partial* with the budget exhausted (cap raised, continuation added). Other providers on the launch-page request: OpenAI-compatible `gpt-4.1-mini` completed in 29 s for $0.02; local Ollama `qwen2.5:7b` reached *partial* (artifacts published, review incomplete); `qwen2.5:3b` could not produce a valid plan.

Also verified: **46 deterministic tests** (DAG validation, real delivery with a question/answer round trip, review → revise → re-review, milestone replanning, budget reservation, approvals with hash/nonce, cancel → resume, fork, redaction, SSRF guard, Docker and seatbelt sandbox confinement, SSE cursor replay, event-schema conformance) and a headless-Chrome UI smoke in English and Japanese.

Still open: five request types, one run each, is not a benchmark; plans vary between runs because the Master decides; research-heavy requests are the most expensive and the least reliable; local 7B models complete the mechanics but not the review protocol. Full matrix and the list of bugs found by real runs: [`docs/STATUS.md`](docs/STATUS.md). Security boundaries: [`SECURITY.md`](SECURITY.md).

## Read more

- [dev.to: I built an AI team that ships real work — and shows you the conversation](https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a)
- [Zenn（日本語）: Bot 同士を会話させるのではなく、仕事の経緯がそのままチャットになるマルチエージェントを OSS で作った](https://zenn.dev/forifori/articles/agent-team-launch)
- Launch threads on X: [English](https://x.com/i/status/2098800226199130220) · [日本語](https://x.com/i/status/2098800307421716835)

## Design notes

The product was built from a written blueprint ([`docs/blueprint/`](docs/blueprint/)): spec, implementation brief, security requirements, references, and 40 acceptance cases. Deliberate deviations (no Deep Agents/LangGraph dependency, extended event enum, refusal fallback off by default) are recorded in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md). Changes by version: [`CHANGELOG.md`](CHANGELOG.md).

## 日本語

**依頼は一度。成果物も、検証の経緯も。** AI チームが作成・レビュー・修正を進め、誰が何を確かめたかまで、成果物と一緒に残します。（製品名 Agent Team、リポジトリ FORIFOR/Multibot、MIT）

Master が成果物と完了条件を決め、必要な Bot（Researcher / Builder / Reviewer）だけが実際に作業します。成果物、Bot 間の実メッセージ、時系列、最終報告は同じ実行記録（append-only Event Store）から表示され、台本の会話や固定の成功ログは使いません。

- 成果物を開くと、誰が作り、何を引き継ぎ、どの検証を通ったかまで辿れる
- 各 Bot の接続先・モデル・システムプロンプトを個別に上書きできる（共通設定を継承、手動固定あり）
- 停止・再開・分岐（Bot のモデルを変えて別案）・再生（LLM 呼出なし）・JSONL エクスポート
- 権限・予算・回数上限・承認はプロンプトではなく Runtime が強制

上の GIF はテスト用のスクリプト provider（LLM 呼出なし、画面に「FAKE PROVIDER」と表示）で実 UI と実 Runtime を動かしたものです。実 LLM での協働は 2026-09-13 にローカルの Claude Code CLI（`claude-opus-5`）で実施し、LP・投稿案・レビュー・最終報告まで `completed` で完走しました（証拠: `docs/evidence/run4-*`）。API キー不要で、`claude` にログイン済みなら `agentteam probe` → `agentteam serve` で始められます。詳細は [`docs/STATUS.md`](docs/STATUS.md)。

## License

MIT. Bundled prompts and skills are original to this project (see `docs/blueprint/REFERENCES.md`).
