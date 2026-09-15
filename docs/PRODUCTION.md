# Dedicated deployment: implementation and operating guide

Status, 2026-09-14: **pre-production hardening is in progress; L3 has not been attained**. This guide covers one organization per process, SQLite database, data directory and access configuration. It does not describe a shared multi-tenant SaaS or a highly available cluster. See [the remaining acceptance criteria](PRODUCTION_PLAN.md).

## What is enforced

- The UI uses installed/system font fallbacks and makes no Google Fonts request. Local mode accepts loopback hosts/clients and rejects foreign browser origins. `agentteam serve` refuses a non-loopback bind without an access configuration. Forwarded headers are not trusted.
- Secured mode requires a private access file and an exact public origin. HTTPS is mandatory outside loopback. The API checks authentication and authorization on every matched API route; unknown routes are not implicitly available to non-admin roles.
- Administrators manage settings, credentials outside the API, and access grants. Operators create work, see their own runs and work explicitly shared with them, and cannot raise the installation budget or override models when forking. Viewers can read explicitly shared work. Raw artifacts, versions, events, SSE, exports, approvals and lists follow the same access boundary. Historic runs without grants are admin-only.
- Provider-key settings reject plaintext values and accept only secret references. Keys contain 256 bits of randomness. The access configuration holds SHA-256 digests, never plaintext keys. Browser sessions use random tokens, store only digests in SQLite, expire by default after one hour, and use HttpOnly / SameSite=Strict cookies; Secure is set for HTTPS. Cookie mutations require the exact Origin. Bearer credentials are accepted only in Authorization, never query strings.
- The OpenAI-compatible/Ollama HTTP transport ignores ambient proxy and CA environment overrides and connects to its configured `base_url`. This prevents an implicit proxy from rerouting a local model request. Corporate proxy/custom-CA arrangements and other provider SDK/CLI transports need their own evaluated configuration; see [the actual routing check](evidence/provider-transport-2026-09-14/README.md).
- Key rotation/revocation invalidates bearer access and sessions as soon as the new access file becomes visible to the server. The access directory is mounted, so atomic file replacement remains visible. Our Mac/Colima check observed revocation in about 1.05 seconds; this is a measurement, not an SLA. SSE rechecks authorization between events or after its 15-second idle wait.
- Access attempts, denials, actor identity, response status, request IDs and permission grants are recorded separately from agent events. Request bodies, cookies, keys and query strings are not stored in this audit table. Serve-mode access logs use sanitized structured audit records instead of Uvicorn request URLs. This is a local audit log, not an immutable external audit service.
- SQLite uses FULL synchronous mode, WAL and a busy timeout. A process lock prevents two servers from using the same data directory. Shutdown interrupts and checkpoints workers before closing the database. Restart marks unfinished work interrupted, without automatically repeating an external operation. An explicit resume requeues cancelled work while retaining accepted tasks.
- Request bodies and execution requests are bounded. The secured API has a [durable single-host queue](DURABLE_EXECUTION.md), defaults to two active runs and twenty queued/leased jobs, and retains the configured task/worker/model/tool/budget limits. New work is refused when storage has less than 500 MiB free. This does not provide distributed workers or HA.
- The container runs without root, with a read-only root filesystem, dropped capabilities and resource limits. Runtime Python dependencies are pinned with hashes, and the base image is pinned by digest. The Docker socket is **not** mounted. Secured command tools require Docker isolation and refuse host-readable Seatbelt/subprocess fallbacks; the shipped API container does not provide a nested sandbox service. Choose a supported dedicated worker/host arrangement before enabling command tools.
- Public research fetch pins a validated public IP at connection time, preserves HTTPS hostname verification, rechecks redirects, ignores environment proxies and stops body collection at 2,000,000 bytes. Only ports 80/443 and identity encoding are supported. Command output capture is bounded, and cancellation removes the identified owned container while Docker remains available. See [execution-boundary evidence](evidence/execution-boundaries-2026-09-14/README.md).
- API callers can supply [delivery requirements](DELIVERY_REQUIREMENTS.md) that independently gate artifact/task/run completion. A passing model review cannot override a failed requirement. Schema/regex validation runs in a bounded process; original request attachments can be retrieved by source hash/range. These checks enforce encoded constraints, not arbitrary semantic correctness.

Authorization follows [OWASP's deny-by-default and per-request guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html). Proxy trust is explicit, consistent with [FastAPI's deployment guidance](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

## Provision an installation

Install the package from this checkout in a Python 3.12 environment, using `backend/requirements.lock`. The commands below create real credentials; plaintext keys are written only to newly created private files, never stdout. Choose a data path outside the repository and set `AGENTTEAM_PUBLIC_ORIGIN` to the actual HTTPS origin without a trailing slash. Loopback HTTP is allowed only for local validation.

```bash
export AGENTTEAM_INSTALL_DIR="$HOME/.local/share/agentteam-install"
mkdir -p "$AGENTTEAM_INSTALL_DIR/security" "$AGENTTEAM_INSTALL_DIR/credentials" "$AGENTTEAM_INSTALL_DIR/data"
chmod 700 "$AGENTTEAM_INSTALL_DIR" "$AGENTTEAM_INSTALL_DIR/security" "$AGENTTEAM_INSTALL_DIR/credentials" "$AGENTTEAM_INSTALL_DIR/data"
agentteam access --file "$AGENTTEAM_INSTALL_DIR/security/access.json" \
  --organization 'FORIFOR/Multibot' --public-origin "$AGENTTEAM_PUBLIC_ORIGIN" \
  --subject forifor --role admin \
  --credential-file "$AGENTTEAM_INSTALL_DIR/credentials/forifor.key"
```

Use the organization's actual identifier and administrator subject when adapting this deployment. Choose and copy an evaluated model configuration to `data/agents.yaml` before first startup. Existing installations load their current configuration from SQLite; changing that YAML alone does not update it.

For native hosting (which can use the host's Docker sandbox):

```bash
export AGENTTEAM_MODE=production
export AGENTTEAM_ACCESS_FILE="$AGENTTEAM_INSTALL_DIR/security/access.json"
agentteam serve --data-dir "$AGENTTEAM_INSTALL_DIR/data" --host 127.0.0.1 --port 8787
```

Put a TLS reverse proxy on the same host in front of this loopback service, preserving the configured Host and original Origin. The application does not need to trust X-Forwarded-For/Proto to issue secure cookies: it uses the configured public origin. Do not expose the backend port separately. A public certificate, DNS, chosen identity provider and firewall policy have not been provisioned by this change.

For the supplied container:

```bash
export AGENTTEAM_UID="$(id -u)"
export AGENTTEAM_GID="$(id -g)"
export AGENTTEAM_DATA_PATH="$AGENTTEAM_INSTALL_DIR/data"
export AGENTTEAM_ACCESS_DIR="$AGENTTEAM_INSTALL_DIR/security"
docker compose -f deploy/compose.yaml up -d --build
```

Only `security/` is mounted, read-only, at `/run/secrets`; keep plaintext issued keys in the separate `credentials/` directory. A bind-mounted single `access.json` can continue exposing the old inode after atomic rotation. Directory mounting is deliberate; see [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/). The data and security directories must be owned by the configured container UID/GID.

`127.0.0.1` inside a container is that container, not the host's Ollama. Configure the model service's reachable private address and run a real probe before claiming readiness. Neither a failed probe nor an unavailable sandbox is silently bypassed.

## Access and credential rotation

Issue an operator or viewer with the same command, a new subject and a new private credential file. Distribute the credential over the organization's existing secure channel. These are installation access keys. [OIDC SSO](SSO.md) is available separately through OAuth2 Proxy, with independently verified API tokens and explicit IdP group roles. Corporate MFA is enforced by the chosen IdP and remains deployment acceptance work.

Repeat `agentteam access` for the same subject with a fresh credential filename to rotate it. Use `--revoke` to disable a subject; disabling the last enabled administrator is refused. Changes are picked up per request. Do not change the organization's identity in place: SQLite is bound to its original organization and rejects a mismatch or an attempted startup without authentication.

Administrators can `PUT /api/runs/{run_id}/access` with `subject` and `permission` (`read`, `write`, `revoke`). Viewer roles remain read-only even if assigned a write grant. Grant changes are audited with actor, target subject and permission. No API endpoint changes the access file itself.

## Health, monitoring and incidents

- `GET /api/health/live`: anonymous process liveness, no run identifiers or configuration.
- `GET /api/admin/ready`: administrator/auditor authentication; checks SQLite, free storage, configured connection readiness and required sandbox availability. Returns 503 if prerequisites are missing. A passed past probe does not prove the provider is currently responsive or the generated work is correct.
- `GET /api/admin/metrics`: authenticated Prometheus text for run statuses, active runs and disk space. No user/run IDs are metric labels.
- `GET /api/admin/audit?after_id=...&limit=...`: administrator/auditor cursor export with a server stream identity. The [separate audit collector](OPERATIONS.md) commits records/cursors durably and reports health transitions; immutable external custody and actual alert routing remain deployment work.

For an authentication failure, check the access file permissions, public origin/Host and key validity. For unexpected access, revoke the credential, retain the audit records and identify affected runs. For provider or sandbox failure, keep the run's interrupted/blocked state and review the reason before resume. For storage pressure, refuse new work, snapshot the data, then apply the agreed retention policy; no automatic deletion is enabled.

A supervisor can restart the process: previously unstarted queued jobs are recovered, while interrupted work needs a deliberate resume. Snapshot restore interrupts all restored queued/leased jobs because their later history on the original host is unknown. The system does not promise exactly-once external side effects. The organization must define escalation contacts, acceptable downtime and recovery objectives before deployment acceptance.

## Backup and restore

The initial backup tool is **offline**: stop this installation, then create a snapshot in a new separate directory. It obtains the same process lock, uses the [SQLite backup API](https://www.sqlite.org/backup.html), copies run/workspace files and verifies file checksums plus published artifacts against their database hashes. Symlinks and special files are rejected. Existing destinations are never overwritten.

```bash
agentteam backup --source "$AGENTTEAM_INSTALL_DIR/data" --destination "$AGENTTEAM_BACKUP_DESTINATION"
agentteam verify-backup --source "$AGENTTEAM_BACKUP_DESTINATION"
agentteam restore --source "$AGENTTEAM_BACKUP_DESTINATION" --destination "$AGENTTEAM_RESTORE_DESTINATION"
```

Restore into a new data directory, retain the original until acceptance, and start with the same organization's current access configuration. Access-key browser sessions are cleared, and OIDC tokens issued before restore are rejected; users must log in again. Verify the recovered artifacts and interrupted tasks before routing traffic. The [offline release procedure](RELEASE_OPERATIONS.md) pairs a compatible application version and snapshot, preserves current key revocations and requires reconciliation of any permissions/work changed after the snapshot. It is not a rolling-upgrade or zero-downtime claim.

Snapshots contain confidential source data, artifacts, prompts and audit records. They do not bundle external environment/keychain/file-based provider secrets or issued plaintext access keys. [Run deletion and age-encrypted recovery](DATA_OPERATIONS.md) provide previewed retention, failure-resumable cleanup, stale-request rejection and verified encryption/decryption. Encrypt host storage and manage recovery identities separately. Automated off-site backups, approved retention across historical copies and disaster-recovery objectives remain acceptance work.

## Evidence and limitations

[Recorded validation](evidence/production-boundary-2026-09-14/README.md) covers real credential provisioning, API/SQLite authorization, a hardened container, browser login, revocation and recovery of saved real-model artifacts. [SSO validation](evidence/oidc-2026-09-14/README.md) adds a real local IdP, role mapping, key rotation, expiry and session recovery. These do not reclassify saved artifacts as correct business work. The v24 series completed ten actual-source workflow attempts; three machine-contract passes were observed, but one retained pass contained mixed-script/half-transliterated terms and independent semantic review remained pending, so zero runs are accepted. The L1 business-quality condition therefore remains open, along with production IdP/MFA acceptance, durable distributed workers, availability testing, external security review and the customer's operational acceptance.
