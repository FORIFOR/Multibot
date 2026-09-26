# Changelog

All notable changes. Versions follow `backend/pyproject.toml`; the API, `/api/health` and the UI header read the same value.

## Unreleased

- Keep guidance written for the readiness acceptance series (`readiness.json`: production_ready=false, L3, PRODUCTION_PLAN.md, evidence_quote) out of other requests. The bundled builder/reviewer prompts no longer carry it; `prompts/readiness-series.md` is appended only when the delivery contract is `readiness.json`. Series criteria and reviewer wording are unchanged, but the series system prompt now differs from v61 in placement, so the next series must record this change.

- Ask for a concise, complete team rationale separately from member descriptions to avoid generation ending mid-sentence at schema limits.

- Allow SHA-guarded exact replacements through the existing workspace write permission, so long drafts can be corrected without regenerating the whole document; retain publication and review gates.

- Clarify that queued peer requests do not start reply sessions or delegate ownership; distinguish immediate questions in the tool description and delivery receipt.

- Add optional character ranges to agent artifact reads, preserving complete reads and marking partial-read evidence explicitly; guide token-limit recovery toward focused reads.

- Distinguish a bot's current task from its other assignments, and keep cross-task publication errors from suggesting renamed copies of another task's deliverable.

- Keep coordinator completion scoped to verified request deliveries; preserve raw model claims in logs without promoting them to completed production or review results.

- Reserve reviewers' remaining peer-message capacity for formal review handoffs, preventing optional messages from consuming the final required delivery slots without increasing limits.

- Request concrete sentence endings and teammate responses separately from temperament when recommending a team; preserve existing saved profiles and user-locked identities.
- Include exact required artifact revisions in incomplete-review errors, without accepting partial review coverage.

- Reject explicit and inferred task completion when a saved output differs from its latest published revision; require publication and a new handoff.
- During document context recovery, identify saved unpublished edits and direct the bot to inspect them before rewriting older published outputs.
- Show the same latest publications and unpublished edits when a task resumes, so earlier review references are not mistaken for current output revisions.
- Recover submitted review records and pending post-review handoffs after a no-tool reviewer turn, without finishing the task or accepting its artifacts.

- Suggest the declared review targets and acceptance IDs in session-specific tool schemas, retaining strict runtime coverage and revision checks.
- Guide concise role-specific handoffs without replacing user voice settings; explain that failing reviews need formal submission before correction can start.
- Include each bot's configured voice beside the model's message-text field, without rewriting sent messages or expanding tool permissions.
- Reflect exact-revision checks and reviews in live result tabs before the final report is available, without treating a failed review as a pass.
- Restore saved failing-review findings to a producer after interrupted correction work, retaining the original reviewed revisions and hashes.
- Require real coordinator handoffs to task owners in normal team runs, retaining tool permissions, budgets and persisted deliveries on resume.
- End the normal LLM coordinator dispatch phase from verified persisted deliveries, avoiding an extra acknowledgement call; production and review completion stay separate. CLI sessions are unchanged.
- When an agent confuses a generated artifact with an original attachment, suggest its exact artifact ID/revision if reading artifacts is allowed. Keep the lookup unsuccessful until the correct tool is used, without creating a false source-read record.


- Add per-bot conversation voice settings with role defaults, revision-checked persistence, and frozen run configuration.


- Advertise requester text length bounds on the document-writing tool while retaining persisted-byte validation as the authority.


- Add explicit Ollama temperature/top-p connection settings. The OpenAI-compatible endpoint does not inherit these Modelfile defaults; omitted values retain endpoint defaults. Deterministic temperature is limited to capability probes.


### Product outcome and integration (local patch)
- Separate document request fulfillment from source accuracy, prevent writing instructions from becoming deliverable content, and restrict document reviewers to reading/checking/review handoffs at the tool boundary. Text checks return measured Unicode length and byte size.
- Add optional, draft-persisted literal phrase exclusions to output conditions. Compile them to standard JSON Schema and enforce them on saved file content through the existing execution layer; model claims cannot override these checks. Semantic and paraphrase review remains separate.
- Add explicit document language review and prevent reviewers from waiting on producers blocked by their pending verdict. Clarify semantic review versus exact-string checks and distinguish design intent from measured usability; refresh the app design brief, and explain low-storage admission failures without dropping request drafts.
- Keep elapsed time anchored to the recorded stop event when a user saves a new direction on an interrupted run; verify offline recovery, real browser storage exhaustion and instruction persistence using actual recorded work.
- Redesign the workroom as a quiet creation desk: compact expandable emoji teammates, an immediately visible instruction composer, and a pre-resume disclosure that keeps execution separate from inspection.
- Add an artifact-first creation workspace, browser-local editable copies/downloads, selected-excerpt change instructions, and previous-version comparisons. Keep mobile drafts mounted and distinguish local edits from published, checked versions.
- Add tab-persisted request search, optional conversation text/participant filters and exact-revision links for referenced artifacts. Pause live following during filtering and clear filters when jumping to the latest messages. Record official VoiceOS/OpenClaw reference observations without claiming unmeasured superiority.
- Refine the conversation-first workroom: one request header, Conversation / Results navigation, a compact emoji roster and quieter surfaces. Collapse attention details while keeping resumption risks visible; tighten mobile navigation and preserve keyboard focus feedback.
- Require dependent task workers to deliver actual handoffs/review findings before task completion, including auto-finish. Read all run-scoped messages addressed to the worker so cross-task handoffs cannot be silently filtered out. Reply sessions must send an answer before finishing.
- Show elapsed start-to-end time beside the conversation, updating every second while live and freezing at the recorded end. Elapsed time includes approval waits and pauses.
- Replace default drawn bot characters with role emoji. Add emoji choices and immediate preview to each bot’s settings; preserve custom emoji in team chat as well as the roster. Existing run snapshots remain unchanged.
- Simplify the workroom: shorten active labels, remove repeated explanatory text, and collapse progress, task details, activity records and source context. Preserve original messages, outcome warnings, permissions and cost controls.
- Show an animated execution indicator inside the conversation while work is active, with the current stage, recorded task and last record time. Stop the motion for approval, connection uncertainty, settled runs, reduced motion and the existing pause control; keep this feedback separate from delivered messages.
- Add a status-filtered work index at `/runs` with counts, refresh recovery and direct navigation to each team conversation. Keep the selected filter when returning, disclose the existing 50-request API window, and retain interrupted/failed states without classifying them as completed.
- Show recorded work phases, current task and state history without invented completion percentages. Move original bot messages into the wide main column, with live connection status, follow/pause controls and separate activity records; keep conversation before the roster on mobile. See `docs/quality/workroom-live.md` for actual-record verification and limits.
- Add an opt-in supplied-document workflow: Core compiles one creation task and an independent review, preserving delivery checks while avoiding a model planning call. Reject plans that omit requester-owned output paths.
- Bind capability probes to each enabled agent’s effective model; changed or unrecorded model evidence blocks before execution. Keep CLI and real-model benchmark probe records consistent.
- Enforce requester JSON Schema string constraints on UTF-8 text artifacts; expose optional output character bounds in the request form while preserving legacy JSON receipt hashes.
- Rebuild token-limit recovery from actual task/source/review context and retain retry bounds; remove task-specific readiness instructions from shared execution prompts. Extend recovery to tasks restricted to durable document tools even without a delivery schema; show existing outputs and sent messages without replaying them.
- Allow corrections to be saved on paused runs with a plan before explicit resume; expose server-derived instruction capability and the last saved direction without claiming it was applied.
- Clear stale stop reasons when runs/tasks actually resume; retain recorded failure history.
- Install the five user-supplied OSS quality Skills locally under `.agents/skills` (2.0.0-draft); record scoped independent verification and remaining product failures.
- Disclose effective model destinations and tool permissions before a request; preserve tab-scoped request drafts and source attachments through setup/reload.
- Stop automatic mutation retries; honor persisted create/fork/resume idempotency receipts in local mode as well as authenticated mode.
- Fix the empty-to-first-artifact React Hook order; bind check badges to exact artifact revision and hash.
- Add explicit selected-revision ZIP exports and hash manifests while preserving the latest-file ZIP default; serialize adoption compare-and-set (0 means no prior selection).
- Document the pre-1.0 HTTP contract and limits, add a stdlib client example and real API/SQLite regression checks. See `docs/quality/report.md` for evidence and unverified conditions.

### Added
- An automated accessibility scan of the everyday screens (`frontend/scripts/a11y-smoke.mjs`: axe, WCAG 2.x A/AA; home, home with a request written, welcome, My team and the work screen, in Japanese and English at two widths), run in CI. The sandboxed deliverable preview is excluded and stays a manual check; zero findings is not a conformance claim.
- `site-check.mjs` can run in WebKit (`BROWSER=webkit`).
- The 2026-09-14 publishing audit is filed under `marketing/audit-2026-09-14/`.
- A UI quality workflow for contributors using Claude Code: a project `CLAUDE.md`, UI rules scoped to the UI files, a `/ui-craft` skill, a read-only `ui-reviewer` agent with its review protocol, the app's design contract in `docs/design/` (brief, acceptance criteria, token record, reference log, review template), `frontend/scripts/ui-capture.mjs` for review screenshots, and a local evidence gate (`scripts/ui-quality.mjs`, 14 tests) wired to nine real checks. The Stop hook is not committed; it belongs in a personal `.claude/settings.local.json`.
- A first-visit introduction at `/welcome` (meet the team → check the model connection → pick a first request). It is offered from the home screen until it has been seen or a first request exists, never blocks the request box, and never starts work: a chosen example arrives in the request box as a draft.
- Evidence for the 2026-09-18 local team-vs-single comparison (10 tasks, one run each, Qwen 3.5 9B via Ollama) and its 2026-09-19 follow-up: `docs/evidence/local-recompare-2026-09-18/`.
- A liquid-glass "thinking" orb in the run header while a run is live and next to the start button while a request starts (WebGPU; browsers without a WebGPU adapter keep the pulse dot). The orb is a standalone export of the MIT-licensed Liquid Orb Editor (LerSent001/orb), vendored as `frontend/src/assets/orb.html` with its parameter snapshot and license.
- Requests can include real `.txt`, `.md`, `.markdown` or `.csv` attachments (the UI reads each file locally and caps it at 512KB). Human directions sent from the run chat are persisted as `instruction.received` events and included in the next task session.
- Artifact revisions expose text diffs, an explicit human adoption event, and a run-level ZIP containing the latest artifacts, report, and event log.

### Removed
- `docs/portfolio.css`, `docs/workflow.css` and `docs/launch.js`: nothing referenced them after the homepage rewrite.

### Changed
- Results panel, second review cycle: the actions sit between the check state and the document, so adopting is on the first screen at 1440×900 and the main action is one full-width row on narrow screens; adopting a version that has no passed check is an outlined, plainly labelled action ("use this version unverified") instead of the strongest button; the chosen version shows on its tab and as a labelled pill beside the actions; the check record looks like the disclosure it is; all four teammates' states fit the first screen. Main buttons moved from `#5b72e8` to `#4558d0` after axe measured white text on the old colour below 4.5:1 (now 5.90:1). The connection check result no longer prints `undefined` for fields the server did not report.
- Results panel, from an independent image review: a version without a check record says so in a prominent line with a symbol and a direct link to the check record; file tabs mark files whose latest version has no check record; the status line reports how many such files exist instead of pointing at checks that do not exist; the panel opens on the page deliverable when there is one; short documents no longer leave a large blank reader; "nothing attached" is one quiet line; on narrow screens settled teammates collapse to one row; the disabled main button is readable; the history badge says テスト/Test instead of FAKE.
- The work screen is one page. A compact status card (the coordinator's progress line, the request clamped to two lines, cost and actions) sits on top; below it the notes, the team roster, what came with the request and the conversation are on the left, and the results reader is on the right, on the first screen at desktop widths. The three-step bar stays as in-page navigation that scrolls to an area instead of swapping screens. On narrow screens the order is status → notes → team → results → request → conversation.
- Results read like documents: Markdown deliverables are shown formatted (headings, lists, tables, code, http(s) links) with a "show source" toggle. The reader builds elements from parsed data only, so raw HTML in a deliverable stays text and non-http links are not linked. The per-version check record lists each automatic check and reviewer check with a plain outcome instead of raw JSON; an unknown outcome is shown as unverified, never as passed.
- "My team" replaces the settings heading and its runtime wording; teammates without a custom name show their role name instead of an internal id. Setup problems on Home, the welcome page and My team read plainly in both languages, keyed by the backend's problem codes (the original message stays on hover).
- After a run has settled, a coordinator that produced the plan shows "assigned work done" instead of "on standby"; while work is live it stays on standby, because it may still replan.
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

- Add same-run full artifact-ID recovery hints to failed reads and message references, without automatic selection or delivery.
- Reset per-attempt planner parse data so malformed responses reach the existing rejection/retry path without an unbound variable or stale proposed-plan payload.
- Reject unwritable task output paths during planning with the existing workspace path policy.
- Clarify coordinator input handoffs and enforce positive published artifact revisions in message/reference tool schemas; original attachments are not revision-zero artifacts.
- Clarify the scope of literal/structural tool checks without altering their verdicts, targets or recorded evidence. Preserve required content during source-based semantic review.
- Label generated plan assumptions as provisional in task handoffs, preserve unresolved choices and the original request scope, and clarify source-access limits for researchers.
- Explain why publication invalidates earlier handoffs and how to deliver current revisions before finishing; preserve the existing completion guards.
- Guide missing workspace reads to existing same-run published artifact references when the caller has artifact-read permission; preserve local-file precedence and path policy.

- Add experimental task-specific AI team recommendations with variable specialist count, personal names and distinct voices. Inherit approved capabilities and persist the chosen roster for resume; retain fixed-team API compatibility.

- Adaptive plans now reject insufficient compulsory handoff/revision communication capacity before starting workers, using the same dependency recipients as runtime delivery. Configured limits are not increased. Optional-message reservation across future revisions remains outstanding.
- Versioned adaptive communication reservations now protect future corrections and unanswered questions. Reply sessions count toward the same stored task budget on both execution and resume. Older saved runs do not retroactively adopt future-round reservations.
- Coordinator message schemas now require an explicit existing task ID and describe its owner, matching the runtime's delivery requirement. Dispatch guidance distinguishes the sender's request from the recipient's own voice.
- Re-review prompts explicitly label previous verdict summaries as historical and require reassessing current passages, including fixed and still-failing findings, rather than copying earlier verdict text.
- Task prompts clarify that applicable corrections received during a run refine the work while preserving original requirements, mandatory delivery contracts and permissions; receipt alone is not evidence of completion.
- Clarify that literal text checks include raw Markdown markers, whitespace, case and punctuation; repeated identical checks cannot resolve a rendering mismatch. Verdicts and artifact content remain unchanged.
- Bind message-writing guidance to the actual sender name and recipient display-name map, so tool IDs are not presented as conversational names. Stored messages remain unchanged.
- Add editable animal character presets to My team, with draft previews and explicit save. Keep character identity separate from capabilities and variable team size; guide future adaptive recommendations toward simple nicknames and animal emojis.

- 依頼ごとに「自分で選ぶ」からキャラクターを選択。選択の下書き保存、権限と人格の保持、必須確認担当の開始前検証、選択済みチームのfork継承に対応。
