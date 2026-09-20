# Product quality verification — local working tree

**Overall: FAIL — three improvement rounds completed; first-success and generated-content requirements remain unmet.** Start revision `9afbfe4`; verification HEAD `aad83ddf682606fc024b29b5855273472d345db8`, branch `fix/issue-19-results-panel`, plus the final working tree. A separate concurrent commit added existing local readiness evidence during this task; it was preserved. The user's pre-existing UI edits are preserved. Exact final source hashes are in `artifacts/product-quality/source-manifest.json`; environment and commands have separate records. No push, merge, publication, paid API, cloud model or third-party data transfer is performed in this work.

## Scope and changes

One task: real source document → source-grounded Markdown guide → inspect exact-version checks → select → save exact bytes. Existing runtime/provider/UI boundaries are kept. Corrections address first-result Hook ordering, ambiguous mutation retries, actual data destinations, recoverable drafts, adoption concurrency, exact-version verification and selected-version exports. README and the HTTP example describe the same behavior; no stable SDK claim is introduced.

The four requested skills (`oss-standard-audit`, `outcome-first-ux`, `contract-first-build`, `independent-product-verification`) were searched in the repository and installed local skill/plugin locations and were absent. They were **not used**. Existing `.claude/skills/ui-craft/SKILL.md` was used for the local UI workflow; its `frontend-design` dependency was not installed. The independent subagent read `.claude/skills/ui-review/SKILL.md`. Its review is AI review in a separate context, not real-user acceptance. The user prohibition on stubs overrides the skill's scripted-provider capture instructions.

## Evidence and commands

Local evidence directory: `artifacts/product-quality/` (ignored, intentionally not committed). Its `commands.jsonl` records exact commands, exit codes and full-log paths. `environment.json` records OS, Python, Node, pnpm and base revision. Chrome version is recorded in browser JSON files. Each browser script uses the real loopback FastAPI service on port 8796 and real SQLite; no intercepted/fabricated API replies.

- `contract-tests.log`: 9 tests passed, real document bytes / SQLite / issued credentials.
- `durable-tests.log`: 5 tests passed, real process-death / queue / receipt persistence.
- `final-contract-tests.log`: all 14 selected no-mock tests passed together.
- `build*.log`: TypeScript and Vite build; `lint*.log`: exit 0 with warnings retained.
- `local-probe.log`: installed loopback Ollama `agentteam-qwen35-9b-16k`, tool calling + structured-output probe passed. No cloud fallback.
- `browser-start.json`: actual example editing, source attachment, settings round trip/reload, Chromium composition events, real offline mode and exactly one attempted POST. OS input-method behavior is not proven by CDP composition.
- `draft-quota.json`: actual browser quota exhausted with repository evidence bytes; latest draft preserved through settings navigation. The first quota harness attempt left enough space for the new draft and timed out; that failed command is retained. The harness now fills the remaining space with real evidence lines; the expectation was not changed.
- `accepted-idempotency.json`: two concurrent accepted HTTP requests with a real probed configuration return the same run; start:false made zero model calls.
- `interrupted-run.json`, `resume.json`: real generation hit its wall-clock limit with zero tool effects; explicit keyboard resume kept the same run ID and returned to running.

## Real run, not a scripted demonstration

Input: the actual `docs/quality/integration.md` attached from the browser. Requested output: Japanese `guide.md`, three named sections, 400–700 characters, source-section references, explicit 202/selected ZIP/ambiguous-response semantics. Profile: existing local Qwen 3.5 9B config, restricted to loopback inference and no web-fetch/web-search/sandbox shell/external-action tools; 30 model calls, 480s per execution, no milestone replans. Actual profile is under `/tmp/multibot-product-quality/data/agents.yaml`. Environment: macOS 26.6.2 arm64, Python 3.12.12, Node 25.2.1, pnpm 10.12.2, Chrome 153.0.8010.53. This host was not isolated from other workloads; elapsed times do not establish comparative performance.

Run `run_1a0b8f5c9511106dcd2`: first plan rejected for missing independent reviewer; second accepted. Initial execution interrupted at 480.44s, 3 model-call attempts, 0 tool calls, 0 artifacts. **First-attempt success: FAIL**, not BLOCKED/PASS. The first browser script also exited 1 after 540s waiting for a real artifact; page exceptions were empty. The plan and source are persisted. After an explicit keyboard resume, the real model published `guide.md` v1. The reviewer read it but the second 480s interval expired before review completion. Final state: **interrupted**, builder **review_pending**, reviewer **interrupted**, 8 model-call attempts and 4 tool calls. No passing review is claimed. The artifact and selection persisted across service restart.

## Independent rounds

1. Initial audit: P1 local duplicate execution, conditional Hook, false external-send disclosure, missing selected-version save; P2 lost draft during setup. These drove the bounded patch.
2. Round-one implementation review: code fixes confirmed; actual home/empty screenshots inspected, recovery logs read. New P2: quota failure could let stale storage overwrite latest in-memory draft. Fixed by hydrating storage once. Actual quota test passed. The separate-context reviewer confirmed this fix.
3. Actual-result browser tests found a scrollable region without keyboard focus. Added a labeled focusable region and visible outline; both new-run and recorded-run final matrices passed. The independent final review remains overall FAIL for first success and output quality; see `independent-review.md`.

## Unverified / restricted

Real OS Japanese IME, physical phone, user testing and same-task comparison with an excellent existing product require an appropriate session/device or third-party data-send authorization: **BLOCKED**. No superiority claim. Web native-app testing: **NOT_APPLICABLE**. CSS 200% reflow must not be mislabeled as a physical browser/UI zoom or OS test.

The existing UI-quality aggregate gate invokes mocked browser fixtures and unit fixtures. It is **BLOCKED under this task's no-mock constraint**; existing tests and thresholds were not loosened. Its old `artifacts/ui/review.json` and screenshots were not overwritten or presented as current evidence. `ui-quality inspect` was run only to inspect the fingerprint. The dedicated real-service browser scripts supplement rather than replace or disable existing CI.


## Final acceptance decisions

| ID | Verdict | Observation / evidence |
|---|---|---|
| A1 First request | PASS in tested setup | Editable real-source task, local destination/permissions/budget visible, keyboard example selection; browser-start.json, live-round3/home-1440-ja.png |
| A2 First result / source accuracy | FAIL | Initial attempt 0 artifacts; recovered guide is 1225 characters vs 400–700 and gives unsafe unconditional 409→new-key advice. Final runtime review incomplete. guide.md, final-run.json, final-events.json |
| A3 Recovery | PASS in measured scope | Offline request not auto-repeated; actual accepted/blocked key replay; process restart; real quota/navigation/reload; explicit resume. draft-quota.json, accepted-idempotency.json, server-restart.json, resume.json, cancel.json (real created→cancelled, no invalid resume action) |
| A4 Results/save | PASS | Real empty→first-file transition without page exceptions; keyboard adoption and retained selection; browser/client ZIP hashes match. live-round3/verified-exports.json, recorded-round3/verified-exports.json (selected v1 while latest v3) |
| A5 Contracts | PASS in documented scope | integration.md, OpenAPI capture, authored HTTP client used against both real services; no stable-SDK promise |
| A6 Access/concurrency | PASS in tested single-writer setup | 14 actual SQLite/API/credential/process tests; stale concurrent adoption yields one 202 and one 409; no mocks |
| A7 Web access | BLOCKED overall; measured checks PASS | 20 final axe scans total, 0 findings; no horizontal overflow at 4 widths, Japanese/English, keyboard PageDown/focus, real network recovery, CSS 200% and reduced motion (0 running infinite animations). OS IME, real browser zoom, touch device and full accessibility conformance not established |
| A8 Regression | PASS for selected checks; aggregate gate BLOCKED | Build/typecheck exit 0, lint exit 0 with warnings, 14 tests pass. Bundled files byte-match final dist. Fixture-dependent full suite/gate not executed under no-mock instruction |
| A9 Independent review | FAIL overall | Separate AI reviewer confirmed implementation improvements but identified two remaining P1 output/first-success issues; independent-review.md |
| A10 Comparable-product task | BLOCKED | No same-task external product run or real-user study authorized/executed. No superiority/equivalence claim |

The returned generated guide must not be used as safe developer documentation: use the authored `integration.md` and `examples/http_client.py`. The artifact remains **unverified** in the UI; adoption in the test exercised saving, not content approval. Do not replace this evidence with hand-corrected model output and call it a model success.

## Reproduction

- Real-service scripts live in `frontend/scripts/product-quality-{live,resume,results,draft,cancel}.mjs`. Run with `pnpm -C frontend exec node scripts/<name>.mjs`. Default service: loopback 8796. `product-quality-live` submits a real request; only use an explicitly chosen local model profile. It does not provision or probe models automatically.
- Results matrix environment: `QUALITY_BASE=http://127.0.0.1:8796 QUALITY_OUT=../artifacts/product-quality/live-round3 QUALITY_RUN_ID=run_1a0b8f5c9511106dcd2`. Recorded matrix: port 8797, output `../artifacts/product-quality/recorded-round3`, run ID `run_1a0a139e5220378ea4d`, `QUALITY_OLD_REVISION=1`.
- `backend/scripts/serve_recorded_quality.py --source docs/evidence/real-readiness-v18-qwen35-fixed-2026-09-15/01 --data-dir <new-isolated-directory> --port 8797` imports an actual historical run and verifies artifact hashes. It does not execute a provider; this is replay evidence, not a fresh success.
- `backend/scripts/verify_product_exports.py --url http://127.0.0.1:8796 --evidence artifacts/product-quality/live-round3` independently hashes the browser ZIP and exercises the HTTP example. The SDK-example destination intentionally refuses overwrite; use a fresh evidence directory on a repeat.
- Saved local service data: `/tmp/multibot-product-quality/data` (new run) and `/tmp/multibot-product-quality/recorded` (historical copy). The service restart confirmed receipt/selection persistence and zero automatic replay. Original user bundle backup: `/tmp/multibot-product-quality/original-ui`; original tracked diff: `/tmp/multibot-before-quality.patch`.

Failed intermediate commands remain in the ledger: initial real-model/browser timeout, initial quota harness with residual capacity, and pre-fix scroll-region accessibility scans. No test assertion or expected output was loosened. OS/device/permission-dependent work remains explicitly BLOCKED. No cloud comparison, package installation, push, merge or deployment was performed.

State coverage: actual empty/planning/running/interrupted/unverified and explicit cancellation were exercised, plus historical completed work. A live approval-required flow and a fresh run.failed flow were not exercised: **BLOCKED** for this pass because no corresponding authorized real operation/observed failure was available, and fabricated state was prohibited. This is a scope limitation, not a whole-state-machine PASS.

## Continuation index (latest local work)
The user's request to continue until PASS supersedes the three-round guideline. See [text-delivery.md](text-delivery.md) for unchanged criteria, all failed generation attempts, effective configuration corrections and new contract enforcement. Actual browser200% is now PASS in the tested flows ([browser-native-zoom.md](browser-native-zoom.md)); newly added condition inputs and opt-in document workflow passed independent checks ([delivery-condition-independent.md](delivery-condition-independent.md), [document-workflow-independent.md](document-workflow-independent.md)). Human/OS-IME/touch-device checks remain BLOCKED. Original failed artifact findings above are retained, not relabeled.

Latest checkpoint:36 selected real-data tests PASS; build/typecheck/lint PASS (warnings retained). Source-to-guide first success remains FAIL: the fourth attempt produced an unpublished770-character draft, timed out at480s and did not establish source accuracy. Do not interpret the experimental document workflow as proven first-success quality. Current detailed verdicts and source fingerprint: [text-delivery.md](text-delivery.md). A local Ollama CLI comparison is prepared to avoid external data transfer, but remains unexecuted under resource contention: [local-comparison.md](local-comparison.md).

## 2026-09-20 completion follow-up

The latest continuation is recorded in [live-completion.md](live-completion.md) and [original-outcome-final.md](original-outcome-final.md), with independent findings in [original-outcome-independent.md](original-outcome-independent.md). Short intro.md content/export success does not replace the original guide task. Reviewer write permissions, counted text validation, literal exclusion contracts and low-storage recovery were corrected locally. The original guide still has content/completion failures; no release-ready or all-PASS claim is made. The installed model is also shared with another local evaluation; record this contention separately from actual output errors.

Current consolidated verdict: [completion-status.md](completion-status.md). The fourth final-guide run was interrupted at480.926s with no published artifact; browser first-result wait exited1. Core checks reject the775-character draft. Overall completion remains FAIL.
