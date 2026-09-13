# Production acceptance plan

Goal: advance Multibot to L3 for a clearly scoped enterprise workflow. **L3 remains unachieved.** The first deployment shape is an isolated installation per organization. A shared multi-tenant SaaS would require another architecture and isolation audit.

The working code and each evaluated checkout are tracked separately; the running 300-trial local-model comparison stays pinned and is not silently upgraded.

| Area | Implemented / verified | Remaining acceptance work |
| --- | --- | --- |
| Identity | Real access keys, hashed sessions, role checks; OIDC SSO with actual Keycloak/browser verification, group mapping, token revocation, expiry, key rotation and restore boundary | Production IdP configuration, organization identity policy, MFA enforcement and account lifecycle acceptance |
| Isolation | Per-installation organization binding, per-run grants, access checks for artifacts/events/SSE/export/approvals, protected settings and overrides | Independent attack review, customer-specific role/connector policy, permission lifecycle acceptance |
| Execution | Per-run budgets, admission bounds, process exclusion, graceful interruption/checkpoints and restart detection | Durable job queue and worker ownership/leases, crash/retry/idempotency validation, approved HA topology |
| Data | Offline snapshot/restore, checksum and artifact validation, session invalidation on restore | Data deletion/retention including backups, encryption/secret rotation strategy, off-site recovery drill, agreed RPO/RTO |
| Audit / monitoring | Actor audit records, request IDs, liveness, prerequisite readiness, Prometheus metrics | External retained audit sink, alert routing and escalation, service objectives and incident exercises |
| Deployment | Locked runtime dependencies, pinned base, non-root/read-only container, resource limits, browser/API checks | Real TLS/DNS environment, identity service, operating owner, upgrade/rollback rehearsal, security review |
| Business quality | Original failures preserved; 300 local-model comparisons running separately | A fixed representative workflow repeated ten times, source correctness, review miss/false-positive evaluation, latency and acceptance thresholds |
| Contract / operation | Technical limitations documented | Owner-approved service scope, SLO/SLA, support and incident responsibility; no invented approvals or certifications |

Next engineering sequence:

1. Done: authenticated deployment boundary with recorded API/browser/backup evidence and passing CI.
2. Implemented: standards-based SSO and explicit identity/role mappings. Real local Keycloak integration verified; corporate IdP acceptance remains open.
3. Add persistent run admission/worker leases and validate crash/recovery without duplicate work or false completion.
4. Add retention/deletion, external audit export and deployable monitoring/backup supervision. Rehearse recovery on actual saved work.
5. Run the representative workflow repeatedly with a fixed real local model; inspect outputs beyond regex grades. Fix observed implementation faults and preserve every attempt.
6. Assemble the production release and acceptance evidence. Only then request any indispensable real deployment/identity/operating details that cannot be supplied from the available environment. Do not mark external obligations or business quality complete from unit-test counts.
