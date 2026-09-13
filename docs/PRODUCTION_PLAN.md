# Production acceptance plan

Goal: advance Multibot to L3 for a clearly scoped enterprise workflow. **L3 remains unachieved.** The first deployment shape is an isolated installation per organization. A shared multi-tenant SaaS would require another architecture and isolation audit.

The working code and each evaluated checkout are tracked separately. The legacy 300-trial comparison stays pinned and preserved, but is paused: its 50 tasks include fictional products and synthetic business data, contrary to the user's no-dummy-data requirement for new acceptance work. It is not real-enterprise acceptance evidence. The replacement workflow uses actual repository source documents with recorded hashes and a separate fixed series.

| Area | Implemented / verified | Remaining acceptance work |
| --- | --- | --- |
| Identity | Real access keys, hashed sessions, role checks; OIDC SSO with actual Keycloak/browser verification, group mapping, token revocation, expiry, key rotation and restore boundary | Production IdP configuration, organization identity policy, MFA enforcement and account lifecycle acceptance |
| Isolation | Per-installation organization binding, per-run grants, artifact/event/SSE/export access checks, protected settings; Docker-only secured command tools; pinned public-IP fetch and bounded capture | Independent attack review, customer-specific role/connector/egress policy, permission lifecycle acceptance |
| Execution | Per-run budgets; durable single-host queue, actor-scoped idempotent acceptance, worker leases, interrupted-job review, ordinary/snapshot recovery and actual local-LLM SIGKILL drill | Workload/load acceptance, external-action retry policy, approved availability topology; no distributed workers/HA |
| Data | Offline snapshot/restore, checksum and artifact validation, session invalidation; resumable run deletion with stale-retry rejection; actual age encryption/verified decryption | Approved retention policy including historical backups/forks/provider copies, host encryption and recovery-key custody, off-site recovery drill, agreed RPO/RTO |
| Audit / monitoring | Actor audit records; restricted auditor role; separate durable collector/cursor, restore stream separation, readiness/metrics, recorded outage/rotation/recovery, browser operations view | Independent retained/WORM custody, actual alert delivery and escalation, collector supervision deployment, service objectives and incident acceptance |
| Deployment | Locked runtime dependencies, pinned base, non-root/read-only container, resource limits, browser/API checks | Real TLS/DNS environment, identity service, operating owner, upgrade/rollback rehearsal, security review |
| Business quality | Original failures preserved; legacy comparison paused after synthetic inputs were identified; actual-source readiness workflow prepared separately | Ten repeated actual-source runs, source/summary correctness, review miss/false-positive evaluation, latency and acceptance thresholds |
| Contract / operation | Technical limitations documented | Owner-approved service scope, SLO/SLA, support and incident responsibility; no invented approvals or certifications |

Next engineering sequence:

1. Done: authenticated deployment boundary with recorded API/browser/backup evidence and passing CI.
2. Implemented: standards-based SSO and explicit identity/role mappings. Real local Keycloak integration verified; corporate IdP acceptance remains open.
3. Implemented: persistent single-host admission/worker leases and real crash/recovery checks. Delivery failure drills passed without an automatic replay or false completion claim; distributed workers and workload acceptance remain open.
4. Implemented run retention/deletion, encrypted snapshot recovery and separate audit/readiness collection with real failure drills. A constrained collector supervision unit is supplied; actual systemd deployment, independent retention, alert routing, off-site recovery and policy acceptance remain open.
5. Run the representative workflow repeatedly with a fixed real local model; inspect outputs beyond regex grades. Fix observed implementation faults and preserve every attempt.
6. Assemble the production release and acceptance evidence. Only then request any indispensable real deployment/identity/operating details that cannot be supplied from the available environment. Do not mark external obligations or business quality complete from unit-test counts.
