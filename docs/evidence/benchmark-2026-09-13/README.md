# Benchmark audit — 2026-09-14

This is an audit of existing real-model runs from September 13, not a new experiment. The requests include constructed evaluation inputs; this is **not evidence of 50 real customer workflows**. No new synthetic inputs or runs were made for this audit.

## What happened

| Measurement | Team | Single agent |
| --- | ---: | ---: |
| Scheduled task/repetition pairs | 150 (50 × 3) | 150 (50 × 3) |
| Completed | 47 | 150 |
| Partial | 3 | 0 |
| Provider-limit failures | 100 | 0 |
| Correct by original programmatic grader | 50 | 146 |
| Correct after existing grader corrections | Not regraded | 150 |

The team exhausted the Claude CLI session allowance. 98 failures occurred in planning and 2 in workers. Two of the three partial runs were also affected when their reviewers hit the same provider limit (102 affected runs total). The first repetition produced 50 grader-correct artifacts, but three runs remained partial. Do not silently drop the 100 failures or present the remaining runs as a complete three-repetition comparison.

The single-agent raw file contains 152 rows, including two pilot/repeated task/repetition pairs. The table uses the last recorded attempt for each pair. All 152 original and regraded rows remain available here. The team has 150 main rows and two separately recorded pilots; both are exported. Grader corrections accepted equivalent Japanese wording (see commit `10a7c35`); they were applied to existing artifacts, without rerunning the models. Keep original and regraded verdicts separate.

**Conclusion:** these results do not establish a team quality advantage. Provider availability differed, the team series is incomplete, and the deterministic graders test only their encoded conditions. Zero recorded false completions is not proof of zero incorrect claims or enterprise reliability.

## Sources and reproducibility

- `team-results.jsonl`: all 150 main attempts, including every failure.
- `team-pilot-results.jsonl`: two earlier pilots.
- `single-results.jsonl`: all 152 original attempts.
- `single-results.regraded.jsonl`: the same 152 attempts after grader correction.
- `manifest.json`: source hashes and export scope. Exports retain metrics and reasons; omit private workspace paths and input data.
- Task definitions: [`evals/benchmark/tasks.py`](../../../evals/benchmark/tasks.py).
- Runner: [`backend/scripts/benchmark.py`](../../../backend/scripts/benchmark.py).

The runner now stops queued work on recognized provider-wide quota/authentication errors and returns exit code 2. In-flight work is allowed to finish. `--resume` skips recorded pairs. `--resume --retry-exhausted` retries only recorded provider-blocked pairs, appending new attempts without erasing failures. Use the same model, configuration and task definitions; report resumed attempts separately. A provider reset is not evidence that the remaining runs have been completed.

## Business readiness

Use the product to demonstrate local agent orchestration with a visible review trail. L1 demonstration material is available; ten repeated demonstrations of one business workflow remain unverified. L2 paid customer-data trials and L3 production readiness are not claimed. Organization isolation, enterprise identity, retention controls, operational monitoring and support commitments require separate scoping and verification.
