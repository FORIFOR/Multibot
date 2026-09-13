# Dedicated installation upgrades and rollback

This is an offline, single-host maintenance procedure. It does not promise zero downtime, distributed execution, exactly-once external effects or a recovery-time SLA. A real installed-wheel drill covers the specific `08ca1b7` → `c69c27d` transition and rollback; [recorded evidence](evidence/release-operations-2026-09-14/README.md) is separate from business acceptance.

## Identify the release before changing traffic

Keep an immutable application checkout/wheel or image, dependency lock and SHA-256 digest for both candidate and last accepted release. The current historical wheel version is `0.2.1` in multiple commits, so the version string alone is insufficient: identify the exact commit and wheel/image digest. Install in a separate environment; do not overwrite the only working release or mutate a frozen benchmark checkout.

Run the target environment's dependency, authentication, authorization, artifact, durable execution and chosen workload checks before acceptance. Python package advisory and frontend production dependency scans identify known advisories only; a clean scan is not an application security review. Missing advisories or new vulnerabilities remain possible.

## Upgrade with an offline recovery point

1. Put the deployment into maintenance at its actual ingress. Stop admitting user work and wait for or explicitly interrupt in-flight runs. Record pending external actions and notify the actual operating owner through the agreed process. Do not claim the separate API process handles all external side effects atomically.
2. Stop the service gracefully. Take and verify an offline snapshot with the accepted tool version. Retain the original data and current access/IdP/provider configuration separately; the data snapshot intentionally does not contain issued credentials or external secrets. Use encrypted/off-site copies according to the actual retention and key-custody policy.
3. Start the candidate against the selected data directory with the current access configuration and existing organization binding. Keep ingress in maintenance while checking health, real role logins, the expected artifact hashes/grants, queue/recovery state and the scoped workload. A past provider probe or process liveness alone is not acceptance.
4. Route traffic only after the actual acceptance criteria pass. Record release digest, snapshot digest, operator and decision. Once traffic resumes, point-in-time rollback may lose later work; it requires a new recovery decision, not an automatic command.

## Roll back a failed candidate

Stop the candidate and retain its data/logs for diagnosis. Verify the pre-upgrade snapshot and restore it into a **new** directory, paired with its compatible last accepted release. Never blindly run old code against data modified by newer migrations. The tool verifies checksums and SQLite/artifact consistency before publishing the restored directory.

Use the **current** compatible access configuration and secrets. Do not restore an old credential file that revives revoked keys or removes current IdP restrictions. If old code cannot enforce the current identity policy/configuration, do not downgrade to it. The verified transition in this repository supports the current key schema; this is not evidence that every historical version does.

Snapshot restore clears browser sessions, rejects pre-restore OIDC tokens and interrupts restored queued/leased jobs. Log in again with current credentials, verify artifacts and review ambiguous external actions before resuming. The snapshot also restores database grants and recorded run state at its timestamp. Keep permission/workload changes frozen during the maintenance window; if production activity has occurred since the snapshot, reconcile revocations, grants, completed actions and later data before reopening traffic. Current access-key revocation alone does not reconcile all historical database policy changes.

Run the old release against the new restored directory while ingress remains in maintenance. Verify real login/denial cases and the restored artifact hashes, then make the actual operational acceptance decision. Preserve failed-candidate evidence and recovery logs. Measured local drill time is not the customer's RPO/RTO.

## Reproduce the bounded verification

`backend/scripts/check_release_upgrade.py` accepts a manifest with `old` and `new` installed-wheel Python paths, wheel paths/digests and exact commits. Both installations must use their recorded locked dependencies. Its `--root` must not exist; it never targets a live customer installation. Supply the real saved output/source and evaluated model profile explicitly:

```bash
backend/.venv/bin/python -I backend/scripts/check_release_upgrade.py \
  --root "$AGENTTEAM_NEW_DRILL_DIR" \
  --releases "$AGENTTEAM_RELEASE_MANIFEST" \
  --source "$AGENTTEAM_REAL_READINESS_EVIDENCE" \
  --profile "$AGENTTEAM_EVALUATED_PROFILE"
```

The script uses real TCP, private issued keys, sessions, SQLite and two installed application versions. It checks update/rollback, live-backup refusal and a deliberate one-byte corruption of its disposable artifact copy. No source artifact or business result is rewritten. It performs no LLM call and uses no production traffic. All verification servers stop afterward; the original evidence, failed candidate, recovery snapshot and structured report are retained.
