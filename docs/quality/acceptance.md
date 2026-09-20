# Product outcome acceptance — 2026-09-19

This extends, rather than replaces, `docs/design/acceptance.md`. Freeze these checks before implementation. Target: the local Web app and its HTTP integration surface, based on 0.2.1 / `9afbfe4` plus the pre-existing working-tree edits. No visual superiority or user-study claim.

## One task
A first-time user supplies a real repository document, asks for a short source-grounded Markdown onboarding guide, reviews the generated file and recorded checks, explicitly chooses a revision, and saves those exact bytes. Success requires an actual model-generated artifact, honest unresolved findings, a persisted selection after reload, and a download whose SHA-256 matches that revision. A received request or an adopted file is not proof of correctness.

Use macOS, installed Chrome, Python >=3.12, Node and pnpm; record exact versions. Use an isolated data directory, real SQLite/API/stores and loopback Ollama only. No scripted provider, injected response, fabricated event, or network interception that manufactures responses. Actual disconnection/offline mode is allowed. Do not call cloud models, web tools or publish anything. Preserve the existing user edits.

| ID | Expected outcome | Method / measurement | Required evidence |
|---|---|---|---|
| A1 First request | Editable example specifies a file and verification; data destination, configured cost limit and tool permissions visible before submit | Actual home screen; fill/edit via keyboard; inspect effective config vs displayed destination | Home capture, DOM observations, config snapshot |
| A2 First result | Real source file → model-generated Markdown; state remains partial/unverified if checks incomplete | Local Ollama, real repo input; record plan, events, file, final state; manually compare source and output | Run ID, events, output bytes and hash, report |
| A3 Recovery | No automatic repeat of an ambiguous mutation; explicit repeat with same key returns same run; draft survives navigation to settings | Actual API concurrent identical requests, restart and replay; browser offline then reconnect, settings round trip | HTTP status/body, DB run/event count, browser observations |
| A4 Results | Empty→first artifact causes no Hook crash; adopted revision persists; chosen ZIP exports that version | Running browser plus real store; adopt, reload, download, SHA-256 comparison; old revision if real versions exist | Console errors, adoption event, ZIP/hash |
| A5 Contracts | Local and authenticated API semantics, error/status/event/permission contracts documented; legacy latest ZIP unchanged | Real API checks, OpenAPI inspection, independent code review; no business-rule duplication in examples | Integration guide, executable HTTP example, command logs |
| A6 Access and concurrency | Execution layer checks authorization and serializes adoption compare-and-set; stale selection rejected | Real service/SQLite tests with actual repo artifacts, concurrent requests and real issued local credentials | Test commands, exit codes, conflict statuses |
| A7 Web access | No unwanted overflow at 390/768/1100/1440; visible keyboard focus; Japanese composition safe; 200% zoom/reflow and reduced motion | Running Chrome; keyboard navigation, actual composition API where available; distinguish real IME from automation | Captures, measurements, limitations |
| A8 Regression | Build/typecheck/lint and relevant no-mock tests pass; bundled UI matches sources | Run actual commands; do not execute legacy fixture-provider tests in this task | Revision+working diff fingerprint, environment, command and exit-code ledger |
| A9 Independent review | Separate AI session reviews outcome and failures without implementer's quality scores | Read-only subagent, current app/evidence and acceptance | Independent findings and remaining gaps, not user approval |
| A10 Comparison | Same document→file→review→save; measure steps, success and recovery for Agent Team and an actual comparator | Existing product on the same task, only if credentials/data-send permission available | Otherwise BLOCKED; never infer superiority from screenshots |

Statuses: PASS / FAIL / BLOCKED / NOT_APPLICABLE. Missing device, interactive Japanese IME, external authorization or user research is BLOCKED, not PASS. Native testing is NOT_APPLICABLE: this repository's supported UI is Web. Maximum three implementation/review rounds; report unresolved conditions without weakening expectations.

Evidence index: `docs/quality/report.md`. Machine logs/captures: `artifacts/product-quality/` (local). Legacy mocked tests and offline synthetic demo are separate from real-product evidence.

## Continued outcome verification (user requested until PASS)
Original 400–700-character/source-fidelity and first-attempt requirements remain fixed. New hard enforcement must use requester-owned JSON Schema on UTF-8 text; Unicode code points, including Markdown/whitespace, count. Default JSON contracts and persisted receipt hashes must remain backward-compatible. A failed check cannot become accepted/completed by model claim. Token-limit recovery must retain the actual task, role, sources, human instructions and findings, without task-specific filenames. Bound recovery attempts. Test with real prior artifact bytes and actual repository documents, then run the same source-to-guide task through the live UI with a local model. No hand-written replacement artifact or threshold relaxation. Human/physical-device/external-comparator BLOCKED items cannot be marked PASS by AI checks; continue all work possible locally. The user's latest instruction supersedes the previous three-round stopping guideline.

## Task-specific team request — 2026-09-20

The user requests variable staffing and expertise, with personal bot names and distinct personalities. These checks are additions; earlier artifact-quality gates remain required.

| ID | Expected | Method/environment | Evidence |
|---|---|---|---|
| T1 | AI recommends a task-specific roster, not always four bots or one of each old role | Real local model, original trading request and a second real repository task; compare selected count/expertise | `adaptive-team/` recommendation snapshots/events |
| T2 | Every recommended specialist receives meaningful work; tasks finish through existing artifact and review gates | Real plan/tasks/chat/artifact lifecycle | Run events and exact artifact revisions |
| T3 | Personal names, emojis, expertise and speaking styles appear consistently in UI and prompt | Actual Chrome 1440/390, persisted config and sent messages | Browser evidence plus voice review; configured styles alone are insufficient |
| T4 | Resume keeps the selected team; locked prompts/names/permissions stay intact | Real saved roster/config roundtrip and runtime rehydration | Contract tests and snapshots |
| T5 | Model cannot add connections, models, tools, skills or budget; selection failure starts no worker | Server compiler checks and invalid proposal rejection based on actual proposals | Test commands/exit codes; no generated credentials |
| T6 | Existing fixed/single/document workflows remain compatible | API inputs default to fixed; Web offers automatic selection for regular team tasks | Regression tests, actual UI and docs |

### Long-artifact recovery contract

On the local Python runtime with actual saved Japanese model output, `read_artifact` without range arguments must retain full-text behavior. Optional zero-based Unicode-code-point `start_char` and `max_chars` must return exact slices with pinned revision/SHA, explicit range/partial metadata, no gaps when reconstructed, and schema errors for invalid bounds. Partial reads are not full-review evidence. Recovery guidance must leave room for corrections without weakening acceptance or changing artifact bytes. Evidence: `artifact-range-contract` command log and `adaptive-team-round2/context-recovery-observation.json`; model recovery itself requires a subsequent real execution and remains unverified until observed.

Range reads that would exceed the configured tool-output character limit including metadata are explicitly rejected before recording a read. Retry with a smaller range; no silently truncated range is reported as delivered.

### Exact draft replacement

Local Python/SQLite, actual saved Japanese model text: `workspace_write` must keep complete-write compatibility while allowing a single exact replacement guarded by the full draft SHA. Stale SHA, ambiguous/empty old text, and simultaneous complete/edit input must leave bytes unchanged. A successful edit must change only the selected passage and never publish or accept it. Existing scope and delivery checks remain required. Evidence: `exact-draft-edit-contract` command and independent review; real model use and successful final document remain separate, unverified conditions.
