# Actual-source enterprise readiness workflow

The user requires real work and no dummy business data. The earlier 50-task benchmark contains deterministic synthetic sales/contact records and a fictional product brief. Its original results and immutable checkout remain available, but the continuing 300-trial campaign was asked to stop after its in-flight result. Do not resume it as production acceptance or merge its numbers into this series.

The replacement task creates a Japanese enterprise-readiness handoff from this project's actual `PRODUCTION_PLAN.md` and operations verification report. It asks for `readiness.json`: the real product and deployment shape, the documented L3 conclusion, and all eight areas with Japanese summaries and exact source quotations. This is useful project handoff work using original documents, not invented customer logs or a fictional prospect.

`backend/scripts/production_workflow.py` sends the same request ten times through the secured API in-process, real local Ollama and the durable queue. It uses actual native credentials, a real capability probe, one active run/worker, four tasks at most and a 1,200-second runtime budget for a correction loop. The master, builder and independent reviewer are enabled; a researcher is unnecessary because the complete source is supplied. The profile is recorded separately from older comparisons.

The first 600-second series failed on its first actual output: all eight remaining-work summaries were English, while the reviewer and runtime reported success. Inspection also found `age` mistranslated as 「年齢」. [Original failed evidence](evidence/real-readiness-v1-2026-09-14/README.md) is preserved. The next series includes explicit technical-name guidance, original-attachment retrieval, and [requester-owned delivery requirements](DELIVERY_REQUIREMENTS.md) derived from the actual source table. Missing fields, wrong source quotes/order or absent Japanese text cannot be overridden by a model's passing review. The 900-second budget provides room to revise; it is not presented as the same configuration as v1.

The first two v2 attempts are also preserved in [their evidence directory](evidence/real-readiness-v2-2026-09-14/README.md). The runtime rejected a model revision that still copied English `remaining` values and stopped at the wall limit. The subsequent [v3 series](evidence/real-readiness-v3-2026-09-14/README.md) used the local Qwen model three times: two completed runs and one interrupted run. The old runtime and reviewer marked the first two outputs as pass, but an independent regrade against the current contract found translation drift in all three. The series was stopped after that finding; no output was edited into a pass.

The [v4 qwen2.5-7B probe](evidence/real-readiness-v4-qwen25-2026-09-14/README.md) was stopped before admission: the real model returned `json_schema=true` but `tool_calling=false` for the current Ollama/OpenAI-compatible boundary. It produced no workflow run or artifact and does not count toward L1. A model that passes the actual capability gate is required for the next fixed series.

The [v5 qwen3.5 series](evidence/real-readiness-v5-qwen35-2026-09-14/README.md) passed the real capability gate. Its first run completed after one rejected revision and one accepted revision; the current mechanical contract and independent Reviewer both passed for revision 2. The target remains ten repeated runs, so this evidence is one accepted run and does not grant L1, L2 or L3.

The strengthened-contract [v6 qwen3.5 run](evidence/real-readiness-v6-qwen35-2026-09-14/README.md) and [v7 qwen3.5 run](evidence/real-readiness-v7-qwen35-2026-09-14/README.md) also passed the real capability gate but were stopped before Reviewer acceptance. v6 exposed an English-copy failure and a model-call stop; v7 exposed repeated omission of required Japanese terms after four published revisions. Neither run counts toward the ten-run L1 condition. The Builder prompt now states the required literal terms and the next fixed checkout is v8.

Run only from a clean, fixed checkout and while no other local LLM campaign is running:

```bash
backend/.venv/bin/python backend/scripts/production_workflow.py --root "$AGENTTEAM_REAL_WORKFLOW_ROOT" --repeat 10
```

The script fingerprints the commit, source files, goal, configuration, Ollama version and model digest. Changed inputs require a new series. It persists request keys before admission, keeps every result and exports actual events and artifact bytes/hashes. A STOP file pauses after the current attempt. Interrupted/rejected/partial attempts remain in the record; no artifact is edited to turn a failure into a pass.

別のローカルモデルを検証する場合は、同じコマンドに`--profile docs/config/local-qwen25-7b-team.yaml`のように明示し、新しい固定rootで実行する。モデル名・digestは系列ごとに記録される。

The current mechanical grader re-runs the same requester-owned JSON Schema used by the runtime, including source-quote exclusion, observed translation-drift guards and required technical terms. It still does not prove general Japanese writing quality or source fidelity beyond those explicit rules. Reviewer participation, runtime completion and contract grade are reported separately. L1/L3 is not granted merely because ten calls were made or JSON validation passed.

After the first attempt, inspect the actual source, output, plan, review decisions and failure events. Correct implementation defects when supported by evidence. If code/configuration/prompt changes, keep that failed series and begin a new fixed series. Retain the security/recovery evidence independently of business-quality results.
