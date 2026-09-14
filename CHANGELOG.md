# Changelog

All notable changes. Versions follow `backend/pyproject.toml`; the API, `/api/health` and the UI header read the same value.

## Unreleased

### Added
- A liquid-glass "thinking" orb in the run header while a run is live and next to the start button while a request starts (WebGPU; browsers without a WebGPU adapter keep the pulse dot). The orb is a standalone export of the MIT-licensed Liquid Orb Editor (LerSent001/orb), vendored as `frontend/src/assets/orb.html` with its parameter snapshot and license.

### Changed
- The run view's team chat uses a brighter conversation layout: deterministic bot avatars, role and route context, purpose and artifact badges, a delivered-message count, and one-click links back to the matching timeline event. The underlying chat data remains the delivered-message projection.
- The run view now makes the delivered-message log the primary workspace, with team state and artifacts arranged in a supporting rail. The message log is exposed as an accessible live region and the layout collapses into a single-column reading order on smaller screens.

## 0.2.1 — 2026-09-13

### Changed (from the 3-run reproducibility evaluation, `docs/evidence/scenarios/rerun-2026-09-13/`)
- The default reviewer can `web_fetch`, so source-grounded claims can be checked against their sources (all three research re-runs ended partial without it).
- Milestone replanning is skipped — and recorded as `plan.milestone` with `skipped: limits` — when less than one agent session of budget or model calls remains; the Master is told how many sessions remain and not to add polish once every deliverable is accepted.
- Partial and failed runs carry a one-line reason naming the unaccepted tasks (and note when every task of the original plan was accepted).

### Added
- Reproducibility record: four requests × three runs, unfiltered, with per-run evidence, plus one post-fix research run (completed, $2.05, 8m44s).
- CI runs the headless-Chrome UI smoke (JA and EN) against the bundled UI with the scripted test provider, and the Docker sandbox isolation test on the Linux runner.
- `agentteam probe` prints a structured JSON reason with a one-line next step (claude CLI missing / not logged in / API key) instead of a traceback; exit code 2 on failure.
- `scripts/summarize_evals.py` aggregates `results.jsonl` files from `eval_scenarios.py` into a reproducibility table.
- Feature-request issue template.

### Fixed
- CI on `main` had been red since v0.2.0: the Docker sandbox test assumed `~/.cache` exists.
- The UI header and the FastAPI title were hard-coded to 0.1.0.

## 0.2.0 — 2026-09-13

Driven by real runs through the local Claude Code CLI (`claude-opus-5`) and two other providers; unedited artifacts and event logs are under `docs/evidence/`.

### Added
- Docker sandbox (`--network none`, read-only root, host uid, cap-drop, CPU/memory/pid limits); backend selection docker → seatbelt → refuse (`AGENTTEAM_SANDBOX=subprocess` opts out explicitly).
- One-command install: `uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart`. UI, prompts, skills and schemas ship inside the wheel.
- English UI with an EN/JA toggle.
- Milestone replanning: after the DAG finishes, the Master may add tasks if the goal is not met (`max_replans`).
- Checks: `html_links`, `json_schema`, `python_syntax`, `file_size_max`, `regex_count`.
- `scripts/eval_scenarios.py`; `docs/config/cost-optimized.yaml`.

### Fixed (all found by real runs, all covered by deterministic tests)
- A reviewer verifying two tasks had only its last verdict applied.
- Structured single-shot CLI calls hit `max_turns`.
- Milestone-added reviewer tasks never started; a reviewer ending without a verdict left its target stuck in `review_pending`.
- Diamond dependencies (t2→t1, reviewer→t1,t2) deadlocked the scheduler.
- Per-session budget-cap failures now continue once; weak models that publish every output but skip `finish_task` are accepted with an explicit runtime note.

## 0.1.0 — 2026-09-12

First public release: Master / Researcher / Builder / Reviewer runtime with an append-only event store, real bot-to-bot delivery, revisioned artifacts with checks and reviews bound to revisions, approvals, cancel/resume/fork, replay, JSONL export, and the local-first UI. Providers: `claude_cli`, `anthropic_messages`, `openai_compatible_chat`, `ollama`.
