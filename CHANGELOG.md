# Changelog

All notable changes. Versions follow `backend/pyproject.toml`; the API, `/api/health` and the UI header read the same value.

## Unreleased

### Added
- A first-visit introduction at `/welcome` (meet the team → check the model connection → pick a first request). It is offered from the home screen until it has been seen or a first request exists, never blocks the request box, and never starts work: a chosen example arrives in the request box as a draft.
- Evidence for the 2026-09-18 local team-vs-single comparison (10 tasks, one run each, Qwen 3.5 9B via Ollama) and its 2026-09-19 follow-up: `docs/evidence/local-recompare-2026-09-18/`.
- A liquid-glass "thinking" orb in the run header while a run is live and next to the start button while a request starts (WebGPU; browsers without a WebGPU adapter keep the pulse dot). The orb is a standalone export of the MIT-licensed Liquid Orb Editor (LerSent001/orb), vendored as `frontend/src/assets/orb.html` with its parameter snapshot and license.
- Requests can include real `.txt`, `.md`, `.markdown` or `.csv` attachments (the UI reads each file locally and caps it at 512KB). Human directions sent from the run chat are persisted as `instruction.received` events and included in the next task session.
- Artifact revisions expose text diffs, an explicit human adoption event, and a run-level ZIP containing the latest artifacts, report, and event log.

### Changed
- The coordinator is the one you talk to: it stands in front on the home screen with a short explanation of what it does, and it voices the progress banner in the workroom with its real state. The rest of the team stays visible behind it.
- The four teammates keep their shapes, colours and accessories and gain depth: shaded heads with a highlight, glowing eyes that blink, a gentle idle float and a pulsing core while working. All of it stops under reduced motion and "pause animation".
- The public homepage uses the same polished characters (its character CSS is now copied from the app sources by `docs/site/build_site.py`), a sky-gradient hero and closing section, a serif display face and glass surfaces. Lighthouse stays 100 in all four categories locally.
- The public Japanese and English homepages were rewritten around the product's own characters and three-step flow: the team is on the first screen, each section makes one point, the three real review findings show their recorded before/after text, and the 2026-09-18 local team-vs-single comparison is shown with its unfavourable half (slower; 0/5 on research) and a link to the evidence. No testimonials, user counts or star counts are shown. The page shows three real app screens, is generated for both languages by `docs/site/build_site.py`, and scores 100 in all four Lighthouse categories locally (measured against voiceos.com in `docs/site/ACCEPTANCE.md`). `site-check.mjs` was rewritten for the new page and now also covers reduced motion and no-JavaScript.
- The team step is now a character stage: teammates appear large, in hand-off order (coordinator → researcher → maker → reviewer), the one working now is lifted and lit, each says what it is doing, and the state badge carries a symbol (moving dots, ✓, !, ?, Ⅱ) so state never depends on colour alone. Warnings on that step follow the teammates instead of pushing them off the first screen.
- Recurring runtime reasons in the everyday view are written plainly in Japanese and English (the original text stays on hover and in the detailed record).
- When an agent ends a turn without a tool call, the reminder names the exact next call for its role (for a reviewer: `read_artifact → run_check → submit_review → finish_task`). In the 2026-09-18 local comparison a 9B reviewer narrated its intent three times without calling a tool, which left two correct deliverables `partial`.
- The run view's first screen puts the result before the request: the request heading uses the full width and is clamped to two lines (expandable), Master assumptions move from chips into a collapsed list, a finished run with a report opens on the final report unless `?tab=` says otherwise, the report summary renders Markdown headings/lists/bold/code instead of raw markers, and a finished run with no delivered messages no longer says it is waiting for messages.
- The bundled UI (`backend/agentteam/ui`) was rebuilt from the current frontend source; the previous bundle dated from 2026-09-14 and did not include the approval deep-link fix, the workroom layout or Quiet Cinema.
- The public Japanese and English homepages were reorganized around one real work record: a shorter explanation, a readable deliverable/findings view, a deliverable-linked work list, explicit runtime/data conditions, and one consolidated business inquiry entry. The page uses a white, shared sans-serif theme and keeps the limitation (partial run and unverified source check) next to the example.
- The homepage's supporting workflow video now uses a real screen recording with its audio track removed and operation-focused captions. It remains behind a user-opened disclosure and never autoplays.
- The public Japanese and English homepages now lead with the chat-first app experience: collaboration flow, real message records, task organization, and supported local/provider connections. The static pages do not present fabricated conversation text or success logs.
- The run view's team chat uses a brighter conversation layout: deterministic bot avatars, role and route context, purpose and artifact badges, a delivered-message count, and one-click links back to the matching timeline event. The underlying chat data remains the delivered-message projection.
- The run view now makes the delivered-message log the primary workspace, with team state and artifacts arranged in a supporting rail. The message log is exposed as an accessible live region and the layout collapses into a single-column reading order on smaller screens.
- The chat view now summarizes the observed collaboration flow and offers labeled message search plus task-thread filters, so multi-bot handoffs can be followed without losing the underlying event order.
- The request and run screens now expose the handoff boundary directly: attached material is listed before start, and the instruction composer states that the current plan is not silently rewritten.
- The CSP now hash-pins the vendored thinking-orb srcdoc module so WebGPU-enabled browsers can render it without relaxing the app-wide script policy.

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
