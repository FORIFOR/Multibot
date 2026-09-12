---
title: I built an AI team that ships real work — and shows you the conversation
published: true
tags: ai, opensource, python, agents
canonical_url: https://github.com/FORIFOR/Multibot
cover_image: https://forifor.github.io/Multibot/media/og.png
---

Most "multi-agent" demos are bots narrating to each other. The log is the product; the work is secondary. I wanted the opposite: one request in, real files out, and a trail I could audit afterwards.

**Agent Team** is an open-source (MIT), local-first runtime where a Master plans, a Researcher / Builder / Reviewer actually do the work, and you get the artifacts **plus** the real bot-to-bot messages, a timeline, and verification bound to each artifact revision.

Repo: https://github.com/FORIFOR/Multibot · Site + 59s intro: https://forifor.github.io/Multibot/

## What makes it different

- **No scripted chat.** The chat panel is a projection of `message.sent` events — messages that were really delivered to another bot's mailbox. A question from the Builder wakes the Researcher, which answers with `reply_to`. Acknowledgements never wake a model.
- **Evidence, not vibes.** Checks and review verdicts are events bound to an artifact revision hash. The final report is compiled from the event log; a model summary cannot upgrade "started" to "done".
- **Runtime-enforced limits.** Tool scope, write scope, budget reservation (spent + reserved for in-flight calls), approvals with hash + nonce, cancel / resume / fork — enforced in code, not prompt wording. Unknown model prices refuse to start.
- **Per-bot configuration.** Each bot inherits a default connection and model and can override endpoint, model, effort and system prompt (lockable). Configured vs. provider-reported model are both shown. No silent fallbacks.
- **Replay never calls a model.** Fork from a checkpoint with a different model for one bot and compare. Export the whole run as JSONL.

## No API key needed (Claude Code)

The default connection runs every agent session through the local `claude -p`. Claude Code owns the loop for one session; the team's tools (`send_message`, `publish_artifact`, `run_check`, …) are exposed to it as MCP tools through a small stdio proxy that forwards each call to the runtime's ToolGateway. Policy, budget and the event log are identical to the API path; Claude Code's own built-in tools are disabled for these sessions. Cost and usage are read from the CLI's JSON result, and the model it actually used comes from `modelUsage`, never from the model's own claims.

Claude API (official SDK), any OpenAI-compatible chat endpoint and local Ollama work the same way, per bot.

## A real run, unedited

On 2026-09-13 I ran this request through the local Claude Code CLI: *"From this product description, build a Japanese launch page and three social-post drafts. Record assumptions for anything missing. Stop before publishing. Have the Reviewer verify."*

| | |
| --- | --- |
| Model (reported by the provider) | `claude-opus-5` |
| Plan | Master chose 1 builder task + 1 reviewer task and skipped the researcher; 8 recorded assumptions (no prices, no invented numbers, placeholder URLs only) |
| Deliverables | `index.html` (single-file page), `posts.md`, `HANDOFF.md`, `final-report.md` |
| Verification | 10 programmatic checks → all pass; reviewer verdict 6/6, plus 4 optional findings sent back as a real message |
| Usage | 39 model turns · 35 tool calls · $1.66 list-price equivalent · 18 min 37 s |
| Status | completed |

The generated files, the final report and the 77-event JSONL log are committed under `docs/evidence/` without edits. Four runs total: run 1 finished *partial* and exposed a bug (a reviewer verifying two tasks had only its last verdict applied — fixed), runs 2–3 hit limits that were then tuned. One request is not a benchmark, and the prompts are original seeds.

The demo video on the site drives the real UI and runtime with a **scripted test provider** (labelled on screen) so it is deterministic and free to reproduce.

## How it works

1. **One request → a checked plan.** The Master turns the request into deliverables, assumptions and a task DAG (structured output). The runtime validates schema, cycles, owners, tools, write scopes and limits before anything runs.
2. **Independent bots, real delivery.** Each bot has its own conversation state, mailbox, task scope, tools and workspace. A worker receives its task, input artifact refs and its own inbox — not the whole history.
3. **Verify, revise, report from evidence.** The Reviewer runs checks against a specific revision. Fail → the Builder revises → re-review, bounded. The final report is compiled from the event log.

Stack: Python 3.12 / FastAPI / SQLite (WAL, append-only events, SSE), React + TypeScript. macOS seatbelt sandbox for builder commands (no network, writes only inside the task workspace); elsewhere a plain subprocess that says so in every result.

## Try it

```bash
git clone https://github.com/FORIFOR/Multibot && cd Multibot
cd backend && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e '.[dev]'
cd ../frontend && pnpm install && pnpm build && cd ../backend
.venv/bin/agentteam probe    # real capability check through `claude -p`
.venv/bin/agentteam serve    # http://127.0.0.1:8787
```

I'd love feedback on two things: whether the review → revise → re-review loop bound to revisions holds up on your tasks, and where "fewer messages, more evidence" (workers get their task, artifact refs and inbox — not the history) breaks down.
