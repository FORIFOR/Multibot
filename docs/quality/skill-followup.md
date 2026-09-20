# Skill installation and recovery follow-up — 2026-09-19

## Scope fixed before implementation
Base: `aad83ddf682606fc024b29b5855273472d345db8` plus the existing uncommitted product-quality work and user changes. Historical verdict in report.md remains FAIL. This follow-up does not claim a new successful model generation.

User requested local Skill installation and additional improvements. The attached master prompt is reference material, not independent permission to deploy, publish, send data, or rewrite the product. Install the five supplied Skills into `.agents/skills` for this project, with no global overwrite or instruction-file edits.

Source: user-supplied `/Users/horioshuuhei/Downloads/oss-quality-kit`, version `2.0.0-draft`. Installer and references reviewed; bundle validation and every SHA256SUMS entry passed. No separate distribution license was found in the bundle; local installation does not assert permission to publish it. No third-party Skill download. The supplied source research is attributed to the kit, not presented as freshly verified research by this task.

Applied sequence: oss-standard-audit → outcome-first-ux → world-class-ui (scoped interaction design) → contract-first-build → world-class-ui (running screen review) → independent-product-verification (separate agent). Existing docs/quality/{claims,integration,acceptance}.md remain the source of truth. No new interoperability protocol: existing HTTP/OpenAPI, JSON, append-only events and SQLite admission boundary remain.

## Audit and priorities
1. **P1 recovery**: Workroom/API reject correction instructions while interrupted, requiring execution to start before the correction can be stored. Allow a saved direction before explicit resume, when an existing plan can resume. Target API, Workroom; existing worker event handoff unchanged. Risk: readers could confuse saving with applying; state the distinction and preserve completed-task semantics.
2. **P1 state consistency**: resumed runs retain the old blocked_reason; active UI still says why work stopped. Clear current run/task reasons on actual transition; retain original reasons in event history. Target orchestrator, queue store, admission reply. Do not clear genuine unresolved tasks.
3. **P1 remaining outcome**: prior real local model guide exceeded requested length and contained unsafe retry advice. Keep FAIL; do not edit the generated file or hide its failed evaluation. Content fidelity and first-success latency need another real model evaluation; this bounded follow-up focuses on enabling deliberate correction safely.

## Additional acceptance (unchanged after implementation)
Environment: real SQLite/API, actual repository documents and saved local-model run records, installed macOS Chrome. No mock providers, response injection or fabricated business fixtures.

| ID | Expected | Method | Evidence |
|---|---|---|---|
| F1 | All five Skills installed byte-for-byte, existing files preserved | Installer dry-run/apply, SHA256 comparison | installation ledger |
| F2 | A correction can be saved before resuming an interrupted planned run; reload keeps it; zero new execution | Real API and keyboard browser submit against actual paused work; compare usage/status/plan and event text; inspect real worker prompt handoff | API test, browser JSON/screens |
| F3 | Viewer cannot write; completed/no-plan terminal runs cannot accept directions | Real issued credentials and actual stored runs | test log |
| F4 | Queuing/resuming clears stale current reason and finish/cancel flags, but keeps historical events | Real SQLite queue test, real local resumed run if safely exercised; never replace execution with stub | tests; unexercised paths marked separately |
| F5 | Corrective control is labelled as saving, not executing; readable at narrow width; build/types and relevant regressions pass | Browser 390/1440, keyboard, screenshots opened, build/lint/tests | logs, screenshots, independent review |

Overall product acceptance A2 remains FAIL until a new actual generation meets its original requirements. Human first-use, OS IME, competitor comparison remain BLOCKED. Native remains NOT_APPLICABLE (Web product).

## Results and evidence
Two implementation/check iterations: the initial new test failed because an older real capture contained no task records (`KeyError: tasks`); use the complete committed v12 run capture instead. This corrects the test's source selection, not the product criterion. The initial failure log is retained.

| Check | Verdict | Observation / evidence under artifacts/product-quality |
|---|---|---|
| F1 local installation | PASS | `skill-installation.json`: all 13 files match the supplied kit; validation and SHA256 ledger logs exit 0 |
| F2 correction before resume | PASS | API persistence and actual worker prompt builder, no provider stub; independent browser save and reload, usage/status/plan/artifact unchanged (`skill-followup-independent/pass-b-verification.json`) |
| F3 permission/state guards | PASS | Actual viewer credentials denied with 403; real completed and blocked/no-plan records rejected with 409 (`skill-followup-tests-round2.log`) |
| F4 durable queue / task preparation | PASS | Actual interrupted v12 run + original events imported into SQLite; enqueue clears current reason; preparation preserves every original event; no model call |
| F4 local model resume end-to-end | BLOCKED | Not rerun in this bounded follow-up; prior two 480-second attempts timed out. Local resume/receipt reset statically reviewed, not claimed as fresh model-run proof |
| F5 build/typecheck | PASS | `skill-followup-build.log`, `pnpm build`, exit 0 |
| F5 relevant regression | PASS | `skill-followup-tests-round2.log`, pytest product/security/durable suites, 17 passed, exit 0 |
| F5 lint | PASS (warnings) | `skill-followup-lint.log`, exit 0; 13 existing warnings remain |
| F5 Web matrix | PASS within measured scope | `skill-followup-matrix.log` and `skill-followup-matrix/browser-results.json`: 390/768/1100/1440, Japanese/English, 10 axe scans without violations, keyboard result scrolling, reload, offline recovery, CSS 200% reflow, reduced motion; no page exceptions |
| Export regression | PASS | `skill-followup-export.log`, browser ZIP and stdlib example agree with selected revision and SHA-256 |
| Product first success/content fidelity | FAIL | Prior actual guide still has 1225 characters and unsafe retry advice; saving a corrective instruction is not evidence it was applied |
| OS IME, real zoom, real users, competitor | BLOCKED | CSS reflow/AI exploration do not substitute for these measurements |
| Native | NOT_APPLICABLE | Web product |

Main command ledger: `artifacts/product-quality/commands.jsonl`; matrix command environment: `QUALITY_OUT=../artifacts/product-quality/skill-followup-matrix QUALITY_RUN_ID=run_1a0b8f5c9511106dcd2`, cwd `frontend`. Python/test commands run from repository root. Bundle checks run from the supplied kit directory. Environment remains recorded in `environment.json`; Chrome version is in browser-results.json. Independent commands and limits are in `skill-followup-independent.md` and its evidence folder.

Opened the independent desktop/mobile correction images (`05-correction-desktop.png`, `06-correction-mobile.png`): existing result-first desktop structure and team conversation area retained; saved long Japanese direction wraps, its disclosure is collapsible, and save/receipt text does not claim execution. No new fonts, imagery, animation, or visual superiority claim. Static images do not establish OS input or human usability.

Existing user edits and prior generated evidence remain intact. Bundled UI rebuilt from current frontend sources. No commit, push, publication, cloud model call or external message. The only new business mutation in the running app is the explicit corrective direction stored on the already interrupted local run; it remains interrupted. Skills were read from disk for this turn; project discovery applies on a subsequent task/turn reload.

Final source/working-tree hashes and bundled-UI match: `artifacts/product-quality/skill-followup-source-manifest.json`. Independent verdict: [skill-followup-independent.md](skill-followup-independent.md). Installed Skills are project-local; their own SKILL.md files remain byte-identical to the supplied kit.
