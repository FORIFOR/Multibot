# Local readiness v27 (Qwen 3.5 9B, fixed actual-source series)

This series used commit `aad83dd` and the actual repository documents with the local Ollama profile `agentteam-qwen35-9b-16k`. It was started after v26's observed English-label and malformed-Japanese output defects were added to the delivery contract.

## Result

- Target: 10 actual-source workflow attempts, one local-model call at a time
- Recorded: 1 attempt, then an unexpected `BrokenPipeError` stopped the workflow
- Outcome: 0 accepted; `production_ready=false`
- The stop is preserved as an operational failure. It was not converted into a success or used to resume the old synthetic comparison.

The retained attempt produced a mechanically rejected report because the Deployment `implemented` summary omitted the required Japanese term `アドバイザリ` and used the broader phrase `パッケージスキャン`. The report was preserved without editing. Its latest `readiness.json` revision is `observed-rep01-readiness.json` (run `run_1a0b8f5824e5f094fd0`, revision 3), SHA-256:

`19b03e1c40445301dd331385c2a5eddd52532596336c16c6ee6d54f4d1ebc2bd`

The full run, events, process status, and model fingerprint remain under `/Users/horioshuuhei/.cache/agentteam-bench/real-readiness-v27-qwen35-fixed-20260919` and are not production or customer evidence.

## Acceptance boundary

This stopped attempt does not establish L1/L2/L3, semantic correctness, availability, or customer-environment readiness. The next fixed series must include an explicit Deployment summary repair example and retain any further interruptions.
