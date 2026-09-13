# Durable execution for one organization on one host

Secured API installations now commit execution intent to SQLite before acknowledging a request. This is a **single-host queue**, protected by the existing exclusive data-directory process lock. It does not implement a distributed worker cluster, HA, NFS/shared-disk coordination or exactly-once external side effects.

## Acceptance and delivery

- `POST /api/runs`, resume and fork persist queued delivery before returning success. A stored run may exist without an accepted job if the process fails before admission; that run has not been dispatched. The API never acknowledges job admission before the job transaction commits.
- `Idempotency-Key` accepts 8–128 letters, digits, dots, underscores or hyphens. Scope includes the authenticated subject and concrete operation path. Reusing a key with the same normalized request returns the recorded response/run. Different input returns 409. Current run access is rechecked before returning a stored response. Keys do not cross user boundaries.
- An accepted job and its response receipt commit in one transaction on a dedicated SQLite connection. That transaction cannot accidentally include unrelated scheduler writes. Use the same key when retrying a create/resume/fork after a lost response; a new key expresses a new request. Receipts survive service restart and are retained with the run.
- The bundled client retries one network failure with the same key and retains the key for an ambiguous failure while the page remains open. A page reload loses that in-memory retry state. Integrators needing recovery across client restarts must persist their own request key. This is not automatic deduplication of differently keyed business requests.
- `max_active_runs` chooses worker concurrency at server startup (default 2). `max_pending_runs` bounds queued plus leased jobs (default 20). Restart the service after changing these limits. A full queue returns 429. Disk/sandbox/configuration checks remain enabled.
- The dispatcher recovers newly committed waiting work even if a request handler disappears before scheduling its task. SSE remains connected while work waits; the UI displays an explicit waiting state and supports cancellation before a model call.

## Ownership, interruption and recovery

Each job is claimed by one conditional SQLite update and a unique worker owner, with a 30-second lease renewed every ten seconds. Another owner cannot renew or finish the lease. A lease renewal failure interrupts the local delivery. Slots remain occupied until provider cleanup finishes. The process lock remains the authority preventing concurrent service processes; leases do not make this a distributed/failover architecture.

On normal shutdown, queued jobs stay queued and active work is interrupted/checkpointed. On restart, only previously unstarted jobs are dispatched. A previously leased job whose run did not reach a terminal state becomes interrupted and is not automatically retried. An explicit resume is a new delivery attempt and may repeat unfinished external actions; inspect the recorded effects and approvals first. `finished` in the job table means delivery ended; consult the run's `completed`, `partial`, `failed` or `cancelled` outcome for task status.

**Snapshot restore is stricter than an ordinary restart.** Since the original host could have processed work after the snapshot was taken, restored queued/leased jobs are interrupted and require review before resume. No snapshot automatically replays pending operations. This complements the restored-session revocation described in [SSO](SSO.md).

## Operations and evidence

- `GET /api/admin/jobs?state=queued&limit=100` lists delivery records, timestamps, lease expiry and interruption reason for administrators. Non-admin access is denied.
- `/api/admin/ready` includes dispatcher health; admission returns 503 if the dispatcher has stopped.
- `/api/admin/metrics` includes run outcomes, actual live runs and delivery-state counts. No user/run IDs are metric labels.
- Provider errors saved as run failure reasons pass through the existing secret redactor.

[Recorded verification](evidence/durable-execution-2026-09-14/README.md) includes competing real SQLite connections, a child process dying after claim, persistent HTTP receipts, snapshot recovery, actual Qwen inference during SIGKILL/restart, and the real browser waiting/cancel flow. No mocked provider or fabricated business input was added. These interruption drills are not successful business-workflow evidence.

Still required for L3 acceptance: operational alerting/escalation, retention and deletion, off-site disaster recovery, workload/load testing, security review, a validated deployment/identity environment and representative business-quality acceptance. A shared SaaS or active/active topology needs a separate storage and fencing design.
