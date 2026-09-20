# Independent AI verification — final round

Separate read-only agent/context, 2026-09-19. The requested `independent-product-verification` skill was absent and was not used. The reviewer used the repository's `ui-review` skill, read source/contracts/input/output/logs, opened three actual screenshots, and independently opened browser-downloaded ZIPs to recompute artifact hashes. This is not user approval or a user study.

**Overall: FAIL (revise).** Safe operation, recovery and saving improved; first-attempt success and accuracy of the selected task's output are not met.

| Condition | Verdict | Evidence read independently |
|---|---|---|
| No automatic repeat of ambiguous mutations | PASS | Code, local receipt concurrency/restart checks, actual offline browser log |
| Empty→first result Hook order | PASS | Unconditional Hook placement; actual new artifact appeared with no page exceptions |
| Destination/permissions before execution | PASS | Actual home screenshot and code |
| Save selected revision | PASS | New guide.md v1 and archived readiness.json v1, manifests and recomputed ZIP hashes |
| Draft navigation/reload/quota recovery | PASS | Once-only hydration and real storage exhaustion evidence |
| Width/automated accessibility | PASS within measured scope | Each real/recorded matrix: 10 scans, 0 findings; widths 390/768/1100/1440; not whole WCAG conformance |
| First attempt obtains the requested file | FAIL | 480s interruption, no artifact; explicit resume required |
| Generated guide meets the request | FAIL | 1225 characters (1127 excluding whitespace) vs 400–700; omitted contract conditions |
| OS Japanese IME, physical device, user/comparator evaluation | BLOCKED | No corresponding interactive device/user/authorization evidence |
| Native app | NOT_APPLICABLE | Web UI |

## Remaining findings

- **P1 — Unsafe generated retry advice:** `artifacts/product-quality/guide.md` says a 409 conflict requires a new key. The source requires reconciling the prior result first, and a new key only for a deliberate new action. Following the generated advice could bypass duplicate protection. This output is not safe integration guidance and is not the repository's authored HTTP contract.
- **P1 — First success:** the real local model did not produce a file in the initial 480s. Recovery is valuable but does not substitute for initial success or establish a beginner success rate.
- **P2 — Output constraints:** length exceeded; stale-adoption conflict advice omits the required `expected_selected_revision` condition and legacy unconditional semantics when omitted.
- **P2 — Report staleness during review:** the reviewer initially saw an in-progress report. The primary agent subsequently updated it with final outcomes and limitations; this documentation update is not an additional user evaluation.

The reviewer inspected `recorded-round3/workroom-1440-ja.png`, `workroom-390-ja.png` and `selected-focus.png`. No additional major operation obstruction was observed. Preserve the distinction between adoption and verified correctness, the unverified warning, selected/latest exports, and the result-focused layout.

The recorded keyboard-scroll metric was sampled just before scrolling finished (`scrollTop:0`); the script then successfully waited for `scrollTop>0`. CSS 200% reflow and reduced-motion checks are valid within their stated scope, but not substitutes for OS input or physical browser zoom.
