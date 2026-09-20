# Local readiness v32 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `addeadc` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. The prompt was strengthened to require Japanese wording for `export`. The run was stopped after an unrelated local `agentteam serve` process on port 8807 was observed making a concurrent Ollama request; the one-workflow-at-a-time boundary required stopping this series rather than allowing concurrent model execution.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 1 attempt started; the run was interrupted during the first attempt
- Mechanical result: not graded at the attempt boundary because the workflow was stopped while the Builder task was still running
- Reviewer submissions: 0
- Semantic result: pending; **0 accepted**; `production_ready=false`
- No run was auto-claimed as successful.

The retained artifact is evidence of an interrupted run only. It is not accepted business work or production/customer evidence. Its generated Japanese fields still contain observed translation/terminology defects, including `鍵轮换`, `エGRESS`, and `stale`; these remain failures rather than being corrected in the artifact.

## Preserved artifact

- `observed-rep01-readiness.json` — source run `run_1a0bc76377ba2da749f`, revision 1, SHA-256 `18b876782e199c39b03de3834a72d519ec578e31d0b02344479deb58b5cf7c22`

The full run record, event stream, SQLite database, fixed checkout fingerprint, STOP marker and process output remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v32-qwen35-fixed-20260920`. The raw cache is retained and is not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. It also does not establish a valid ten-attempt series: the attempt was intentionally interrupted after the concurrency conflict was detected. A future fixed series requires an exclusive local-model window after unrelated Ollama callers have stopped, with the observed terminology defects still addressed by the generation/review path.
