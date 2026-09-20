# Claim-to-implementation audit

Scope: 0.2.1 at `9afbfe4` plus this local patch. “Implemented” is not the same as “verified on all providers”. See `report.md` for commands and limitations.

| Claim / expectation | Implementation | Evidence class / limitation |
|---|---|---|
| One request becomes files with a check record | `runtime/orchestrator.py`, scheduler, tools; `store/artifact_store.py`; Workroom | Implemented. Local real-model run recorded separately; generation quality and repeated first-success rate not assumed. |
| Actual teammate conversation | `runtime/bus.py` and `projections/views.py` project recorded messages | Implemented. Empty conversation remains empty; no scripted chat inserted by this patch. |
| Select a version and save it | `artifact.adopted`, serialized compare-and-set, `selection=adopted` export and hash manifest | Real SQLite/API and document-byte tests; live generated artifact verification in report. Latest-file export remains distinct. |
| Limits, permission and external-action approval | policy/tools, security/server, single-writer store | Real ACL and process-recovery tests. Budget is configured cost accounting, not provider-enforced billing. Not a blanket enterprise-readiness claim. |
| Lost response will not duplicate a request | scoped persisted request receipts; UI has no automatic mutation retries | Identical concurrent HTTP requests/restart checked. General external exactly-once semantics not implemented; browser key persistence across reload not implemented. |
| Safe model data disclosure | `/api/config.execution_summary`, Home preflight | Replaces misleading “no external sending” claim. Config summary is not proof of network isolation; configured URL/model and actual egress may differ with proxies. |
| Resume after interruption | `runtime/orchestrator.py`, `store/job_store.py` recovery | Real process tests. Uncertain external effects require explicit inspection; no transparent replay guarantee. |
| Developer integration | HTTP + OpenAPI + JSON Schema; stdlib example | Documented pre-1.0 HTTP contract. No published stable SDK; Python internals and multi-host deployment are not supported integration contracts. |
| Offline demo proves the system | `demo.py`, `demo_command.py` | Synthetic, explicitly marked. NOT used or executed as product acceptance evidence here. |
| Legacy browser/unit/provider tests prove real model success | Fixture-based tests / `FakeProvider` | They test isolated behavior only. Not executed for this task when they require stubs/dummy records; not evidence for output quality. |
| Cloud providers, SSO and enterprise production ready | provider adapters / security / operations | Some historical evidence exists; current task does not exercise third-party endpoints. External permission/device/customer evaluation required. |
| Better/equivalent to excellent existing products | No same-task comparative user study | BLOCKED. Compare source→output success, action counts, retained drafts and ambiguous-result recovery under equal conditions, not visual scores. |
