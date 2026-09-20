# Local readiness v31 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `c4c7e31` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. The goal was strengthened after v30 so the top-level summary could not repeat English area labels, and admission failures would be captured with diagnostics.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 10 attempts
- Mechanical result: 4 attempts reached a machine-contract pass, but each was interrupted by the wall-clock limit before Reviewer submission; six attempts failed the contract, mainly because `export` remained in a Japanese summary
- Reviewer submissions: 0
- Semantic result: pending; **0 accepted**; `production_ready=false`
- No admission 503 occurred in this series; no run was auto-claimed as successful.

The machine-pass artifacts are not accepted business work because they have no independent semantic review and were interrupted. The retained artifacts are preserved without editing and are not production or customer evidence.

## Preserved artifacts

- `observed-rep03-readiness.json` — source run `run_1a0bbb83ded729e9d24`, revision 3, SHA-256 `07f4093e23b0778e7ea2b47fe45aee15387977fd38f9670c0572d9438d6ac9f8`
- `observed-rep06-readiness.json` — source run `run_1a0bbef3f6419a73c49`, revision 3, SHA-256 `07f4093e23b0778e7ea2b47fe45aee15387977fd38f9670c0572d9438d6ac9f8`
- `observed-rep10-readiness.json` — source run `run_1a0bc388eb9864a4d43`, revision 5, SHA-256 `ac86cd060bf2a17051901b51fd3df7fdbdb1c2fe635e3e20acd0123581896057`

The full per-attempt run records, event streams, SQLite database, and process output remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v31-qwen35-fixed-20260920`. The fixed checkout fingerprint and all ten attempt results are retained there and are not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. The next fixed series must translate `export` consistently and allow enough time for an independent Reviewer to inspect machine-pass artifacts before any acceptance claim.
