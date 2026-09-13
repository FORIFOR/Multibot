# Run retention and encrypted recovery

These operations support a dedicated, single-host installation. They do not establish a retention contract, erase a provider's copies, or prove an off-site recovery objective. Stop the service before deleting data or taking a snapshot. No automatic deletion policy is enabled.

## Preview and delete

Set `AGENTTEAM_INSTALL_DIR` to the installation and `AGENTTEAM_RUN_ID` to the actual run approved for deletion. Preview is the default:

```bash
agentteam purge --source "$AGENTTEAM_INSTALL_DIR/data" --run-id "$AGENTTEAM_RUN_ID"
agentteam purge --source "$AGENTTEAM_INSTALL_DIR/data" --run-id "$AGENTTEAM_RUN_ID" --apply
```

Alternatively use `--before "$AGENTTEAM_RETENTION_CUTOFF"`, with an exclusive UTC date in `YYYY-MM-DD` format. It selects at most 1,000 completed, partial, failed or cancelled runs with a recorded finish time older than the date. Interrupted and blocked runs are not automatically selected. Explicit IDs can select those states; running, planning and queued work must first be interrupted or cancelled. Review the preview before applying an organization's actual retention policy.

Deletion covers the selected run's database payload, tasks, messages, events, approvals, checkpoints, artifacts, workspace files, access grants and execution records. It reports forks which remain: a fork is independent work and may contain copied source data. Configuration history and minimal security audit metadata remain. Audit details for deleted runs are cleared. Hashes of accepted request keys are retained so a retry of a deleted request returns **410**, instead of creating the work again.

The operation acquires the service lock, records deletion intent, removes payload rows, removes files without following workspace symlinks, compacts SQLite and checks integrity. A cleanup failure leaves a pending journal. Startup and backup refuse to proceed until the recorded deletion is finished:

```bash
agentteam purge --source "$AGENTTEAM_INSTALL_DIR/data" --resume --apply
```

Fix the reported storage/permission problem first. Resume does not select additional runs. Free space for SQLite compaction is required. [SQLite secure deletion](https://www.sqlite.org/pragma.html#pragma_secure_delete), [VACUUM](https://www.sqlite.org/lang_vacuum.html) and WAL truncation reduce recoverable application payload in the current database. They do not establish physical-media erasure on SSDs, filesystem snapshots, swap or backups. Encrypted host storage and its key lifecycle remain operating requirements.

Historical snapshots, retained audit copies, forks, exported/downloaded artifacts and provider-held data require their own retention treatment. Restoring a snapshot taken before deletion can restore that data; replay the approved deletion ledger before routing traffic. This release does not synchronize deletion to off-site backups or third-party providers.

## Encrypt an offline snapshot

Install a verified release of [age](https://github.com/FiloSottile/age). The recorded drill and CI use v1.3.2. This integration accepts native X25519 recipients and private identities; it does not invoke plugins or prompt for passwords. Generate and protect recovery identities on the recovery system using `age-keygen`. Transfer only public recipients to the backup host. Keep the private identity outside the installation, repository, snapshot and backup host; permissions must exclude group/other access.

```bash
agentteam backup --source "$AGENTTEAM_INSTALL_DIR/data" --destination "$AGENTTEAM_BACKUP_DESTINATION"
agentteam seal-backup --source "$AGENTTEAM_BACKUP_DESTINATION" \
  --destination "$AGENTTEAM_ENCRYPTED_BACKUP" --recipients-file "$AGENTTEAM_AGE_RECIPIENTS"
```

Encryption streams a verified snapshot through the actual age CLI. Plaintext tar archives are not written. The input snapshot still exists and contains confidential data; apply the approved storage/retention policy to it. Output is a new private encrypted file. Record its reported SHA-256, application commit, creation time and public recipient in a separately trusted backup inventory. Anyone knowing a public recipient can encrypt new data, so encryption alone does not prove who created a backup.

## Verify, decrypt and restore

```bash
agentteam unseal-backup --source "$AGENTTEAM_ENCRYPTED_BACKUP" \
  --destination "$AGENTTEAM_DECRYPTED_SNAPSHOT" \
  --identity-file "$AGENTTEAM_AGE_IDENTITY" --expected-sha256 "$AGENTTEAM_BACKUP_SHA256"
agentteam restore --source "$AGENTTEAM_DECRYPTED_SNAPSHOT" --destination "$AGENTTEAM_RESTORE_DESTINATION"
```

Use the checksum from the trusted inventory. Decryption rejects mismatched ciphertext, wrong identities, authentication failures, symlinks, non-file archive entries, path traversal, duplicate names and excessive extraction. The default extraction limit is 10 GiB and 100,000 files; `--max-bytes` can adjust the byte limit. It authenticates the complete age stream and verifies the snapshot manifest, SQLite integrity and published artifact hashes before publishing the decoded directory. Existing destinations are not overwritten. Only incomplete directories created by that invocation are cleaned up on failure.

`unseal-backup` creates a verified snapshot, not a running installation. The separate restore command invalidates prior sessions and interrupts restored queued/leased jobs. Start the compatible application against the new directory, verify actual artifacts, inspect ambiguous external effects and perform the agreed acceptance checks before routing traffic.

## Evidence

The [data-operation checks](evidence/data-operations-2026-09-14/README.md) use real issued keys, real age encryption, SQLite, actual permission failures and copies of a recorded local-model artifact. They include wrong-key and damaged-ciphertext rejection, no partial publication, deletion recovery and rejection of a stale HTTP retry. These are recovery/control checks, not business-quality or RPO/RTO claims.
