# Simple bot characters — 2026-09-20

Revision: c4c7e3189fcdc620a2faa3728d009011bc0526e6 + existing and current working-tree changes. Scope: editable character presets and recommendation guidance; no change to model quality acceptance.

- PASS: build/typecheck (`npm --prefix frontend run build`, exit 0).
- PASS: adaptive/voice regression, 6 tests (`character-regression`, exit 0).
- PASS: actual Chrome with a copied real team configuration and isolated service at 8810: keyboard selection, draft-only state, explicit save/reload, preservation of model/tools/permissions, discard through reload, 390px reflow, reduced-motion setting and no page errors (`character-ui`, exit 0).
- PASS: desktop/mobile screenshots opened and visually inspected. This is AI inspection, not user preference research.
- BLOCKED: real Japanese IME and screen-reader testing were not repeated; no new handlers or animation were added. Do not infer those results from build or browser checks.
- BLOCKED: model adherence to each personality and actual affectionate user response are not established by the UI test.

Evidence: `artifacts/product-quality/characters/` and command ledger `artifacts/product-quality/commands.jsonl`. New preset data are actual product choices, not simulated conversations. Test configuration was copied from the real local team; no model call, mock backend or fabricated run was used.

Built UI is copied to the local 8808 service. Its current run remains live and was not restarted or modified. The backend recommendation prompt change is loaded in the isolated 8810 service but is not yet loaded by the running 8808 backend. Existing run identities are immutable snapshots. Character presets can already be selected and saved in the 8808 My team screen; no claim is made that the active team was renamed.

Round 2: collapsed detailed identity editing to shorten the mobile card; fixed-team versus adaptive selection is stated in the screen and save receipt. `character-ui-compact` exit 0 includes opening the editor, manual name editing with header preview, saving/reloading and discard. Updated 390px screenshot opened and inspected. The primary 8808 server returns the exact new bundled index; its running task remains untouched.

Independent review round 2 found no additional major issue in this localized UI change. Mobile image is approximately 610px tall with no clipping; fixed-team scope is explicit. Lint command `character-lint` exits 0 with existing set-state-in-effect warnings in settings components; warnings were not suppressed. The temporary 8810 validation service is stopped after verification; original 8808 stays running.

## User-selected team acceptance (2026-09-20)

Environment: same revision plus local changes, actual saved team config, isolated real API/SQLite on 8810 and Chrome. No fabricated chat/model responses.

1. Choose myself exposes enabled configured characters, keyboard toggles membership, and reload keeps the draft. Evidence: choice/check.json and browser screenshot.
2. New run with `inputs.selected_agent_ids` (experimental optional fixed-team API) persists the exact identities/capabilities of selected workers in its config snapshot. Coordinator and reporter remain automatic. Unknown/disabled/duplicate members or missing required producer/reviewer are rejected before execution. Evidence: regression log plus actual API-created, unstarted run and snapshot assertions.
3. Omitted field preserves legacy fixed/adaptive behavior and serialized hashes. Existing run snapshots remain unchanged. Evidence: contract regression.
4. Mobile 390px and reduced motion retain operability without horizontal overflow. Evidence: actual Chrome check and screenshot. This does not establish real Japanese IME or human affection.

Selecting characters does not invent expertise or grant tools. The existing planner assigns work to the chosen configured capabilities; insufficient capabilities can still block planning. Automatic mode continues recommending a separate roster. Settings edits affect future requests only.

Results for explicit selection: PASS build/typecheck (`character-choice-build-final`, exit 0), 7 regression tests (`character-choice-regression-final`, exit 0), actual browser/API (`character-choice-browser-final`, exit 0). Snapshot content was also compared with the real configured names, emoji, voice, tools, model and connection: PASS. API runs were deliberately created with `start:false`; no claim of completed model work is made. Screenshot `artifacts/product-quality/characters/choice/mobile.png` was visually inspected. Source fingerprints and environment are in `choice/revision.json`.

Independent review identified fork selection loss and whole-config readiness blocking unused members. Both were corrected: explicit-selection forks validate the selected snapshot; explicit selection delegates readiness to server checks after roster selection. The 8808 service was restarted only after checking `live_runs: []`; current backend and bundled frontend are now loaded. Actual model voice fidelity and real-user preference remain BLOCKED, unchanged from the prior report.

Independent final verification: PASS real API fork retains the exact selected snapshot; missing-reviewer blocked run fork returns 409; resulting child remains created/live=false/model_calls=0. UI readiness fix verified statically. Evidence: `choice/independent.md` and `choice/independent-fork-verification.json`. No additional major issue found in this scope.
