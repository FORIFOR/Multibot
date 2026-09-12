<p align="center">
  <img src="docs/media/demo.gif" alt="Agent Team: one request, real bot-to-bot messages, artifact revisions, final report" width="880" />
</p>

<h1 align="center">Agent Team</h1>
<p align="center"><strong>An open-source AI team that ships real work — with a conversation you can follow.</strong></p>

<p align="center">
  <a href="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml"><img src="https://github.com/FORIFOR/Multibot/actions/workflows/ci.yml/badge.svg" alt="ci" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-1b1a17" alt="MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.12-1b1a17" alt="python 3.12" />
  <img src="https://img.shields.io/badge/providers-Claude%20%7C%20OpenAI--compatible%20%7C%20Ollama-c8471f" alt="providers" />
  <a href="https://forifor.github.io/Multibot/"><img src="https://img.shields.io/badge/site-forifor.github.io%2FMultibot-1b1a17" alt="site" /></a>
</p>

<p align="center"><a href="https://forifor.github.io/Multibot/">Website &amp; 58s narrated intro</a> · <a href="#quickstart">Quickstart</a> · <a href="#how-it-works">How it works</a> · <a href="docs/STATUS.md">What's verified</a> · <a href="#日本語">日本語</a></p>

> [▶ Narrated intro (59s, English)](https://forifor.github.io/Multibot/media/intro-en.mp4) · [日本語版 (58s)](https://forifor.github.io/Multibot/media/intro.mp4). The GIF above drives the real UI and runtime with the **scripted test provider** (no LLM calls, labelled “FAKE PROVIDER” on screen) so it is deterministic and free to reproduce. With a real connection the same screens are fed by live model calls; the run header shows the model the provider actually reported and the measured cost.

You type **one request**. A Master plans the deliverables, a Researcher, a Builder and a Reviewer actually do the work, and you get the files **plus** the real bot-to-bot messages, a timeline, and verification bound to each artifact revision.

- **No scripted chat.** The chat panel is a projection of `message.sent` events — messages that were really delivered to another bot's mailbox. A question wakes the other bot to answer.
- **Evidence, not vibes.** Checks and review verdicts are events bound to an artifact revision hash. The final report is compiled from the event log; a model summary cannot upgrade “started” to “done”.
- **Runtime-enforced limits.** Tool scope, write scope, budget reservation, approvals and cancellation are enforced in code, not by prompt wording.
- **Per-bot configuration.** Each bot inherits a default connection and model and can override endpoint, model, effort and system prompt (lockable). Configured vs. provider-reported model are both shown. No silent fallbacks.
- **Replay, resume, fork, export.** Replay never calls a model. Fork from a checkpoint with a different model for one bot and compare. Export the whole run as JSONL.

## Quickstart

**No API key needed if you have [Claude Code](https://claude.com/claude-code) installed and logged in** — the default connection runs every agent session through the local `claude` CLI (its cost/usage and the model it actually used are read from the CLI's JSON result).

```bash
git clone https://github.com/FORIFOR/Multibot && cd Multibot
cd backend && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e '.[dev]'
cd ../frontend && pnpm install && pnpm build && cd ../backend
.venv/bin/agentteam probe                   # real capability check through `claude -p` (a few cents)
.venv/bin/agentteam serve                   # http://127.0.0.1:8787
```

Prefer the API? Set `defaults.connection_id: anthropic` in `data/agents.yaml` and export `ANTHROPIC_API_KEY` (the config stores only the reference `env:ANTHROPIC_API_KEY`). Any OpenAI-compatible chat endpoint and local Ollama (`driver: ollama`, `http://localhost:11434/v1`) work the same way.

First run: **Settings → Probe** (or `agentteam probe`). It confirms tool calling and JSON-schema output on the model you picked, then unlocks Start. Placeholder models, unknown prices and unverified connections refuse to start with a structured reason.

How the CLI path works: Claude Code owns the agent loop for one session; the team's tools (`send_message`, `publish_artifact`, `run_check`, …) are exposed to it as MCP tools through a stdio proxy that forwards every call to this process's ToolGateway, so policy, budget and the event log are identical to the API path. Claude Code's own built-in tools are disabled for these sessions.

CLI:

```bash
.venv/bin/agentteam validate                        # config check
.venv/bin/agentteam probe [connection] --model ID   # real capability probe
.venv/bin/agentteam run "Turn this into a launch page and 3 posts" --url https://example.com --budget 1.5
```

## How it works

| Component | Responsibility |
| --- | --- |
| **Master (planner)** | Request → deliverables, recorded assumptions, task DAG (structured output). The runtime validates schema, cycles, owners, tools, write scopes and limits; invalid plans are sent back once, then the run fails honestly. |
| **AgentRunner** | One bot session = its own conversation state + a tool loop through the gateway. A worker receives its task, input artifact refs and its own inbox — not the whole history. |
| **MessageBus** | `send_message` really delivers to the recipient's mailbox and records `message.sent`. Purposes are limited to request / question / answer / handoff / finding / decision. |
| **ArtifactStore** | `publish_artifact` creates an immutable, SHA-256-hashed revision with an atomic write. Reviews and checks bind to a revision. |
| **Scheduler** | Dependency resolution, concurrency limit, review fail → revise → re-review (bounded), Master exception decisions, checkpoints. |
| **PolicyEngine** | Budget = spent + reserved for in-flight calls; call/tool/message limits; tool and path scope; cancellation. Unknown cloud prices are never treated as free. |
| **Sandbox** | macOS `sandbox-exec` (no network, writes only inside the task workspace). Elsewhere a plain subprocess that says so in every result. |
| **Providers** | `claude_cli` (local Claude Code, no key), `anthropic_messages` (official SDK), `openai_compatible_chat`, `ollama`. Per-bot choice; real probe before start. |

Everything is written to an append-only event store (SQLite WAL, per-run `seq`, UTC timestamps, redaction before persistence). Chat, timeline and report are projections of it. The event types are the blueprint's 11 plus runtime extensions, all validated against [`backend/schemas/event.schema.json`](backend/schemas/event.schema.json).

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

**A real end-to-end run (2026-09-13)** through the local Claude Code CLI, model reported by the provider: `claude-opus-5`. Request: Japanese launch page + three social-post drafts from a product description, stop before publishing.

| | |
| --- | --- |
| Plan | Master chose 1 builder task + 1 reviewer task and skipped the researcher; 8 recorded assumptions (no prices, no invented numbers, placeholder URLs) |
| Deliverables | `index.html` r1 (single file), `posts.md` r1, `HANDOFF.md` r1, `final-report.md` |
| Verification | 10 programmatic checks → all pass; reviewer verdict 6/6 pass + 4 optional findings delivered as a real message |
| Messages | builder → reviewer *handoff*, reviewer → builder *finding* |
| Usage | 39 model turns · 35 tool calls · $1.66 list-price equivalent · 18 min 37 s |
| Status | **completed** |

Evidence is committed unedited under [`docs/evidence/`](docs/evidence/): the generated files, the final report and the 77-event JSONL log (`run4-*`). Earlier runs are there as well: run 1 ended *partial* and exposed a bug (a reviewer verifying two tasks had only its last verdict applied — fixed), runs 2–3 hit limits that were then tuned (`docs/STATUS.md`).

Also verified: **39 deterministic tests** (`cd backend && .venv/bin/python -m pytest -q`) covering DAG validation, real delivery with a question/answer round trip, review → revise → re-review, budget reservation, approvals with hash/nonce, cancel → resume, fork, redaction, SSRF guard, sandbox write confinement, SSE cursor replay and event-schema conformance; headless-Chrome UI smoke with zero console errors.

Still open: one request and four runs is not a benchmark; plans vary between runs because the Master decides; prompts are original seeds. The Anthropic API and OpenAI-compatible drivers are implemented and unit-tested but have not had a live run yet. Full matrix: [`docs/STATUS.md`](docs/STATUS.md). Security boundaries: [`SECURITY.md`](SECURITY.md).

## Read more

- [dev.to: I built an AI team that ships real work — and shows you the conversation](https://dev.to/forifor/i-built-an-ai-team-that-ships-real-work-and-shows-you-the-conversation-251a)
- [Zenn（日本語）: Bot 同士を会話させるのではなく、仕事の経緯がそのままチャットになるマルチエージェントを OSS で作った](https://zenn.dev/forifori/articles/agent-team-launch)
- Launch threads on X: [English](https://x.com/i/status/2098800226199130220) · [日本語](https://x.com/i/status/2098800307421716835)

## Design notes

The product was built from a written blueprint ([`docs/blueprint/`](docs/blueprint/)): spec, implementation brief, security requirements, references, and 40 acceptance cases. Deliberate deviations (no Deep Agents/LangGraph dependency, extended event enum, refusal fallback off by default) are recorded in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 日本語

**依頼は一度。AI チームが作り、確かめ、成果物と経緯を残す。**

Master が成果物と完了条件を決め、必要な Bot（Researcher / Builder / Reviewer）だけが実際に作業します。成果物、Bot 間の実メッセージ、時系列、最終報告は同じ実行記録（append-only Event Store）から表示され、台本の会話や固定の成功ログは使いません。

- 成果物を開くと、誰が作り、何を引き継ぎ、どの検証を通ったかまで辿れる
- 各 Bot の接続先・モデル・システムプロンプトを個別に上書きできる（共通設定を継承、手動固定あり）
- 停止・再開・分岐（Bot のモデルを変えて別案）・再生（LLM 呼出なし）・JSONL エクスポート
- 権限・予算・回数上限・承認はプロンプトではなく Runtime が強制

上の GIF はテスト用のスクリプト provider（LLM 呼出なし、画面に「FAKE PROVIDER」と表示）で実 UI と実 Runtime を動かしたものです。実 LLM での協働は 2026-09-13 にローカルの Claude Code CLI（`claude-opus-5`）で実施し、LP・投稿案・レビュー・最終報告まで `completed` で完走しました（証拠: `docs/evidence/run4-*`）。API キー不要で、`claude` にログイン済みなら `agentteam probe` → `agentteam serve` で始められます。詳細は [`docs/STATUS.md`](docs/STATUS.md)。

## License

MIT. Bundled prompts and skills are original to this project (see `docs/blueprint/REFERENCES.md`).
