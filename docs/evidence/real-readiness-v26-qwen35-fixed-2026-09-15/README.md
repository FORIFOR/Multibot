# Local readiness v26 (Qwen 3.5 9B, fixed actual-source series)

This directory records the tenth fixed series that used the actual repository documents in `docs/PRODUCTION_PLAN.md` and `docs/evidence/operations-2026-09-14/README.md` with the local Ollama profile `agentteam-qwen35-9b-16k`. It is separate from the paused synthetic comparison and from v22–v25.

## Result

- Series root: `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v26-qwen35-fixed-20260915`
- Fixed checkout: `ecf7b1b` (local-output guidance series)
- Target: 10 actual-source workflow attempts, one local-model call at a time
- Outcome: 10 attempts recorded; **0 accepted**; `production_ready=false`
- Status: mechanical trials complete, semantic review pending
- Attempt states: 1 completed with a machine-contract pass and one Reviewer submission, 1 completed with a false completion caught by source-anchor checks, 1 partial, 1 failed for missing JSON, and 6 interrupted

The machine-contract pass is not business-quality acceptance. The retained pass still contains output defects such as `with Keycloak`, `mappiung`, `export`, `auditor`, `collector`, `outage`, `pinned`, `TLSDNS`, and the malformed phrase `操作主体ごとな冪等受入`. These are preserved as evidence; the artifact was not edited into success.

## Preserved artifact

`observed-rep02-readiness.json` is the latest `readiness.json` revision from run `run_1a0a5492a866a8c6bce` (revision 3), copied byte-for-byte from the fixed-series evidence. SHA-256:

`21aa8c446edd05deae0dff947fb7d56029ec9ebadc5e5a2b423d0a1a435054d0`

The full per-attempt run records, event streams, and artifacts remain under the series root above and are not treated as production or customer evidence.

## Acceptance boundary

The series does not establish L1/L2/L3, customer-environment readiness, SLA, semantic correctness, or safe external actions. A new fixed series is required after the observed terminology and summary-quality failures are rejected by the delivery contract and the generation/repair guidance is updated.
