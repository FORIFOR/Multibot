# Actual-source enterprise readiness workflow

The user requires real work and no dummy business data. The earlier 50-task benchmark contains deterministic synthetic sales/contact records and a fictional product brief. Its original results and immutable checkout remain available, but the continuing 300-trial campaign was asked to stop after its in-flight result. Do not resume it as production acceptance or merge its numbers into this series.

The replacement task creates a Japanese enterprise-readiness handoff from this project's actual `PRODUCTION_PLAN.md` and operations verification report. It asks for `readiness.json`: the real product and deployment shape, the documented L3 conclusion, and all eight areas with Japanese summaries and exact source quotations. This is useful project handoff work using original documents, not invented customer logs or a fictional prospect.

`backend/scripts/production_workflow.py` sends the same request ten times through the secured API in-process, real local Ollama and the durable queue. It uses actual native credentials, a real capability probe, one active run/worker, four tasks at most and a 900-second runtime budget. The master, builder and independent reviewer are enabled; a researcher is unnecessary because the complete source is supplied. The profile is recorded separately from older comparisons.

The first 600-second series failed on its first actual output: all eight remaining-work summaries were English, while the reviewer and runtime reported success. Inspection also found `age` mistranslated as 「年齢」. [Original failed evidence](evidence/real-readiness-v1-2026-09-14/README.md) is preserved. The next series includes explicit technical-name guidance, original-attachment retrieval, and [requester-owned delivery requirements](DELIVERY_REQUIREMENTS.md) derived from the actual source table. Missing fields, wrong source quotes/order or absent Japanese text cannot be overridden by a model's passing review. The 900-second budget provides room to revise; it is not presented as the same configuration as v1.

Run only from a clean, fixed checkout and while no other local LLM campaign is running:

```bash
backend/.venv/bin/python backend/scripts/production_workflow.py --root "$AGENTTEAM_REAL_WORKFLOW_ROOT" --repeat 10
```

The script fingerprints the commit, source files, goal, configuration, Ollama version and model digest. Changed inputs require a new series. It persists request keys before admission, keeps every result and exports actual events and artifact bytes/hashes. A STOP file pauses after the current attempt. Interrupted/rejected/partial attempts remain in the record; no artifact is edited to turn a failure into a pass.

The mechanical grader checks JSON, documented readiness/deployment, eight-area coverage, source names, exact quotations and presence of Japanese summaries. **It does not prove the Japanese summaries faithfully convey the source.** Semantic review remains explicitly pending until the outputs are inspected; reviewer participation, successful runtime completion and mechanical grade are reported separately. False completion against those mechanical requirements is recorded. L1/L3 is not granted merely because ten calls were made or JSON validation passed.

After the first attempt, inspect the actual source, output, plan, review decisions and failure events. Correct implementation defects when supported by evidence. If code/configuration/prompt changes, keep that failed series and begin a new fixed series. Retain the security/recovery evidence independently of business-quality results.
