# Local readiness v34 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `16a5285` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. The generation prompt included explicit replacements for the v32 terminology defects (`鍵轮換`, `エGRESS`, and `stale`).

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 1 attempt completed at the run boundary; the series was stopped before attempt 2 after attempt 1 consumed the 1,200-second per-run limit
- Mechanical result: 0 passes; five Builder revisions were retained and the final revision still failed the delivery contract and source/summary checks
- Reviewer submissions: 0
- Semantic result: pending; **0 accepted**; `production_ready=false`
- Model usage for the recorded attempt: 28 model calls, 22 tool calls, 252,258 input tokens, 10,709 output tokens, 1,200.4 seconds
- No run was auto-claimed as successful.

The final retained artifact still copied English source text into Japanese fields, omitted or changed required top-level/area fields across revisions, and produced mixed or malformed terminology. These are recorded failures; the artifact was not edited into success.

## Preserved artifact

- `observed-rep01-readiness.json` — source run `run_1a0bd114771842549ae`, revision 5, SHA-256 `45c8050b686139b0c38e5b497649f196f2b35e8e68cd149b6fbb125f5fd67762`

Revisions 1–4, the full run record, event stream, SQLite database, fixed checkout fingerprint, STOP marker and process output remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v34-qwen35-fixed-20260920`. The raw cache is retained and is not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. It is not a valid ten-attempt series. The generation/review path still needs an implementation-level fix for schema adherence and source-grounded Japanese summaries before another fixed series; no artifact may be rewritten after generation to manufacture a pass.
