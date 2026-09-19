# Local readiness v28 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `e344859` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`, after the v27 Deployment-anchor fix.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 10 attempts
- Mechanical result: 2 completed with a machine-contract pass and Reviewer submission; 8 were interrupted by a contract failure, chiefly missing the required `アーティファクト` Isolation anchor
- Semantic result: pending; **0 accepted**; `production_ready=false`

The retained machine passes still contain semantic quality defects. For example, the report uses English area/source labels such as `Production IdP` and `Contract / operation` inside Japanese summaries, and it uses `成果物` where the requested technical glossary calls for `アーティファクト`. A machine-contract pass and Reviewer submission therefore do not establish business-quality acceptance. The artifact was preserved without editing.

## Preserved artifact

`observed-rep07-readiness.json` is the latest `readiness.json` revision from run `run_1a0b997a717a4d5c783` (revision 5), copied byte-for-byte from the fixed-series evidence. SHA-256:

`3b7357e1810ac4c4c9c06b03203befb63ede12ae0ef4816cf81faf09d9bcb982`

The corresponding completed run 9 produced the same bytes. Full per-attempt run records, reviewer messages, event streams, and artifacts remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v28-qwen35-fixed-20260919` and are not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. A new fixed series is required after the observed area-label and glossary drift is rejected at the delivery boundary.
