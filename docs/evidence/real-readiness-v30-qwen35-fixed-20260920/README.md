# Local readiness v30 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `69d484a` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. It followed the v29 terminology checks.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Attempts started: 7; six attempts reached the wall-clock limit and were retained; the seventh admission was refused with HTTP 503
- Mechanical result: 0 accepted; the retained outputs failed the delivery contract for English/malformed summaries, schema shape, or exact source anchors
- Reviewer submissions: 0
- Semantic result: pending; **0 accepted**; `production_ready=false`
- The run stopped on the API admission error and did not auto-claim success or restart the old series.

The retained artifacts are preserved without editing. They are not production or customer evidence. The 503 is recorded as an operational failure, not as a successful run.

## Preserved artifacts

- `observed-rep04-readiness.json` — source run `run_1a0bb20652630cdacb4`, revision 4, SHA-256 `fcfb088e09d68e2536a7f53a9a41166e32110bfdf2646421212ddd37d3277461`
- `observed-rep05-readiness.json` — source run `run_1a0bb32b745f80f186a`, revision 4, SHA-256 `fcfb088e09d68e2536a7f53a9a41166e32110bfdf2646421212ddd37d3277461`
- `observed-rep06-readiness.json` — source run `run_1a0bb450c1fd93e5ab0`, revision 2, SHA-256 `6ba55be3f32309ed27ed28c07354129440b3b8d0fb5d609af5cf5759a0012705`

The full per-attempt run records, event streams, SQLite database, and process output remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v30-qwen35-fixed-20260920`. The fixed checkout fingerprint, model digest, and failed artifacts are retained there and are not production or customer evidence.

## Acceptance boundary

This series does not establish L1/L2/L3, semantic correctness, availability, SLA, or customer-environment readiness. The next fixed series must correct the observed contract defect and investigate the HTTP 503 admission failure before another ten-run acceptance attempt.
