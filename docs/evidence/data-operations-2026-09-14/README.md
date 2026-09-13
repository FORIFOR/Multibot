# Data-operation verification — 2026-09-14

Five added checks execute real SQLite, HTTP, filesystem permissions and age v1.3.2. They use isolated copies of actual saved local-model work, real issued access credentials and freshly generated native age identities. No provider, response, key service or store is mocked.

- Preview/offline deletion, compacted SQLite payload removal, symlink target preservation and successful restart.
- Actual permission failure after database deletion; startup refuses partial cleanup; resume finishes the recorded deletion.
- UTC retention selection using the [actual cancelled model run](../durable-execution-2026-09-14/cancelled-real-run.json), and refusal to delete active work.
- Actual API request, offline purge and retry after restart: **410**, with no recreated run.
- Actual encrypted snapshot, decrypt and restore with identical recorded artifact bytes. A different actual private identity, ciphertext corruption, excessive extraction and unsafe identity permissions are refused; failed operations leave no published plaintext destination.

The preserved artifact has SHA-256 `23ed248581fd6129b2f0146b10189defd71b71d8603b404174d8d085ed5e80ea`. Its earlier business-quality failure remains unchanged. The cancelled run is a real interruption drill, not a successful workflow.

Run the checks with an installed `age` and adjacent `age-keygen`, or set `AGENTTEAM_AGE_BIN` to the actual binary:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_retention.py backend/tests/test_encrypted_backup.py -q
```

CI installs the official Linux age archive pinned to SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`. The verified macOS arm64 archive digest is `e2020b073c44f692685a24d6abc378817eb81ffaaf49fd0531ef8565f767f2f5`. No identity or plaintext credential is included in this evidence directory.

The current Mac reports FileVault enabled. This establishes neither encryption on a future production host nor physical-media erasure. No off-site storage or recovery deadline was tested.
