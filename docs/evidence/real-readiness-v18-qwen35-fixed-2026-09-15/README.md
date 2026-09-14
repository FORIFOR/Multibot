# Real-source local-Qwen acceptance series v18 (stopped)

Date: 2026-09-15 JST. This series used commit `6013e73`, one local Ollama model (`agentteam-qwen35-9b-16k`), one active LLM worker, and the actual repository documents `PRODUCTION_PLAN.md` and `docs/evidence/operations-2026-09-14/README.md`. No Claude, cloud provider, fictional product, or synthetic business input was used.

The series was intentionally stopped after two completed repetitions when a delivery-contract gap was observed. Both runs completed the older contract's mechanical checks and received one Reviewer submission each, but their generated Japanese summaries contained translation drift that the contract did not reject: `パイン`, `ロカル`, `アデュータ`, and `actual-source`; run 2 also used `サマリー` in a field that requires a Japanese factual summary. The artifacts and event logs are retained unchanged. The new contract rejects these observed fragments before a run can be accepted.

| repetition | run | result under v18 contract | reason for stopping |
| --- | --- | --- | --- |
| 1 | `run_1a0a139e5220378ea4d` | completed, mechanical pass under the pre-v18 contract | retained as an observed output; independent semantic review not complete |
| 2 | `run_1a0a14661f12703d41d` | completed, mechanical pass under the pre-v18 contract | translation drift observed in the published summaries |
| 3–10 | — | not run | STOP marker created after the contract gap was fixed in the checkout |

This evidence does **not** satisfy the ten-run L1 condition and does not establish L2 or L3 production readiness. `access.json`, private keys, SQLite state, and other credentials are deliberately excluded.
