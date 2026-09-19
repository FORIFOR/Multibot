# Local readiness v29 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `18763d8` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. It followed the v28 area-label and glossary checks.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 10 attempts
- Mechanical result: 6 attempts produced a machine-contract pass; 4 did not reach an accepted completion because of contract violations, interruption, or a failed run
- Reviewer submissions: 5
- Semantic result: pending; **0 accepted**; `production_ready=false`

The retained machine passes still show semantic drift that the mechanical schema alone cannot establish as correct. Observed examples include the English phrase `Real access keys`, the malformed role phrase `アクター監査`, and the English boolean `false` inside Japanese summaries. These reports were preserved without editing and are not production or customer evidence.

## Preserved artifacts

- `observed-rep01-readiness.json` — run `run_1a0ba06ecd1b4952d5f`, revision 7, SHA-256 `b205feb9095c86b02be9b370f2fa5a78e7a80107ce1dbe848f8e07748ea54ae0`
- `observed-rep02-readiness.json` — run `run_1a0ba1940921d4293b4`, revision 4, SHA-256 `b262ca4f89831b6801a492722aa53e9e7acd4a4f3c026df581567547d612ba6a`
- `observed-rep03-readiness.json` — run `run_1a0ba2b92f517505c79`, revision 5, SHA-256 `c68afac26d4b4f969dcbf082fd5795296918965bb6e6415dbbc3d824c4af49fe`

The full per-attempt run records, reviewer messages, event streams, and artifacts remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v29-qwen35-fixed-20260919` and are not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. A new fixed series is required after the observed English and malformed-terminology drift is rejected at the delivery boundary.
