# Actual-source readiness workflow v1 — failed

On 2026-09-14 JST, the actual local Qwen3.5 9B model processed this repository's source documents through the authenticated API in-process and durable queue, with master, builder and independent reviewer. The frozen checkout was `08ca1b730efcaef37947905d238a77e032b22d94`; model/config/source hashes and the real probe are preserved here. No synthetic business records or replacement model responses were used.

The first attempt took 578.91 seconds and 12 model calls. The runtime said `completed`, but **all eight `remaining` fields copied English instead of providing the requested Japanese summaries**. The reviewer passed all four criteria in its plan and missed this explicit requester requirement. Mechanical result: **fail; false completion against the stated mechanical requirements**. The series stopped after this attempt; it is not ten successful repetitions.

Inspection of the original output also found a substantive translation defect: the `Data` summary translated the encryption tool **age** as 「年齢暗号化」. Other unnatural terminology includes 「演者スコープ」 for actor-scoped and 「リカデネス」 for readiness. These are additional reasons this handoff is not acceptable. The quote/order/product/deployment checks passed, but that does not establish semantic quality. This is an inspection of one output, not a general translation-quality benchmark.

The reviewer's attempt to read `PRODUCTION_PLAN.md` as an artifact returned `NOT FOUND`: original request attachments were inline source inputs, without artifact revisions. It did not retrieve that source through a dedicated input tool. Source files, original goal, events, final report, output bytes and hashes are retained unchanged. `result.json` retains the grader's original `semantic_review: pending`; the observations above are separate subsequent inspection, not a rewritten model artifact or successful grade.

Corrections derived from this failure:

- Optional requester-owned JSON Schema delivery requirements survive planning and independently gate task completion, auto-completion and final completion. Checks are bound to the actual artifact revision/hash and appear in the event log and report. A model's review cannot override them.
- Original source attachments have an explicit `read_input_file` tool with source hash and character range. Reading an attachment as an artifact gives the correct retrieval instruction.
- JSON Schema/regex checks run in a real bounded worker process. A deliberately hostile regex on the actual output is terminated; no fabricated business content is needed for the availability test.
- The next fixed series explicitly preserves technical names, enforces source-derived required fields/quotes and budgets 900 seconds to allow a correction cycle. It is a separate configuration from this 600-second attempt.

These checks cannot prove faithful Japanese summaries, real customer workload quality, SLA or L3 readiness. Subsequent outputs require separate semantic inspection.

After the corrections, the backend suite passed **101 tests in 9.22 seconds** on this Mac/Colima environment; see `backend-tests.xml`. The three added checks replay this actual failed artifact through completion gates, read the original attachment with its hash/range, and terminate the deliberately hostile regex in a real worker. The broader suite includes legacy test providers; its count is not 101 real LLM workflows. GitHub CI verifies the same code separately on Linux.
