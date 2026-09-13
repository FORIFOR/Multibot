# Operational monitoring and audit collection

Status: implemented with actual local HTTP/SQLite/browser failure drills. This is a separate collector process and database, not an immutable off-site audit service or an agreed SLA. The application remains a dedicated, single-host installation.

## Restricted access

The `auditor` role can read readiness, metrics, recent jobs, audit records and its own identity. It cannot read run goals, inputs, artifacts, exports, settings or approval payloads, and it cannot submit/cancel work or change configuration. A run grant cannot override these restrictions. Browser login opens **Operations**, with current prerequisites and recent audit records. Request and Settings navigation are absent for auditors.

Administrators retain full access. OIDC group mappings can select `auditor`; the resolution order for multiple matching groups is `admin`, `operator`, `viewer`, `auditor`. Roles are not combined: use a dedicated audit identity. The collector deliberately requires a native installation key with the auditor role and refuses workspace/admin roles. Rotate/revoke it using the normal access-key mechanism.

```bash
agentteam access --file "$AGENTTEAM_INSTALL_DIR/security/access.json" \
  --subject audit-collector --role auditor --credential-file "$AGENTTEAM_AUDITOR_KEY"
agentteam observe --url "$AGENTTEAM_PUBLIC_ORIGIN" \
  --private-backend "$AGENTTEAM_PRIVATE_BACKEND" \
  --credential-file "$AGENTTEAM_AUDITOR_KEY" --state-dir "$AGENTTEAM_OBSERVER_DIR" --once
```

For a collector on the application host, `AGENTTEAM_PRIVATE_BACKEND` is the actual private loopback HTTP origin. The collector preserves the configured public Host, so it can reach the independently authenticated backend without needing a browser OAuth session. Only loopback HTTP is accepted for this override. Never expose that backend publicly. For an independently hosted collector using a reachable HTTPS endpoint with the required API authentication route, omit `--private-backend`; actual TLS/proxy acceptance is still required. Redirects and environment proxies are disabled; HTTPS certificate validation is enabled.

The URL must be an origin without a trailing slash, path, credentials or query. Keep the credential file private and separate from the collector's data directory. `--once` returns zero for healthy prerequisites and two for a degraded/failed collection. Continuous mode samples every 30 seconds; `--interval` permits 5–86,400 seconds. Health indicates configuration/queue/storage/sandbox prerequisites, not current model responsiveness or business quality.

## Durable collection

The collector writes a separate private SQLite database (`observer.sqlite`), `health.json` and a Prometheus textfile (`metrics.prom`). The collection cursor and received records commit in one SQLite transaction. A second collector cannot use the same directory concurrently. Records are keyed by both server stream ID and remote event ID. An ordinary process restart retains its stream; a supported snapshot restore generates another stream, so its lower/reused sequence numbers are collected without overwriting pre-restore evidence.

Each cycle collects at most 5,000 records. A backlog is reported and continued from the committed cursor; records are never silently skipped. The `alerts` table records readiness state changes, initial degradation and audit-stream changes. Audit collection, key failures and connection failures are visible states. Failed cycles clear previously published server metrics and set `agentteam_observer_ready` to zero. Consumers must check `agentteam_observer_sample_timestamp_seconds` too: a dead collector cannot report its own outage. Monitor the collector from a separate supervisor/monitoring system.

Audit and alert records are retained until the organization's approved retention process removes them. Health samples retain 30 days. Collection refuses to proceed below 500 MiB of free collector storage. The directory must have mode 0700, with the SQLite database and published files mode 0600. Requests, exception details and response bodies are not included in connection-failure messages. Native audit records still contain actor IDs and run/permission metadata and require access/retention controls.

No email, Slack message or external alert has been sent. Configure the organization's actual alert routing and on-call ownership before deployment acceptance. An operator with filesystem access can modify the collector database; retained/WORM storage, restricted external custody and its recovery test are separate requirements. The application purge command does not delete this external copy.

## Supervision

[`deploy/agentteam-observer.service`](../deploy/agentteam-observer.service) provides a Linux systemd service for a dedicated unprivileged `agentteam-observer` OS account. Install the reviewed package environment at `/opt/agentteam/venv`, set the two actual origins in `/etc/agentteam-observer/environment`, and provision the collector-only key at `/etc/agentteam-observer/collector.key`, readable only by that service account. The unit owns `/var/lib/agentteam-observer`, constrains memory/processes, and has no write access to the application data directory. It is supplied for deployment and has not been installed on this macOS host.

Before routing production traffic, exercise actual alert delivery, revocation, full disk handling, supervisor restart, independent log retention and off-site restore. Agree the escalation owner, acceptable latency/error rate, recovery objectives and supported workload. No contract or security certification is inferred from the checks below.

## Evidence

The [recorded operations checks](evidence/operations-2026-09-14/README.md) include a real listening server being stopped/restarted, real credential rotation, snapshot restore and browser access. The saved local-model capability probe is reused only as a prerequisite record; no current model call or successful business task is claimed by these tests.
