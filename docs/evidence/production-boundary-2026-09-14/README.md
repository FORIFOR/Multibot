# Authenticated deployment boundary — actual validation

2026-09-14. **This is pre-production evidence, not L3 acceptance.** The implementation and operating limits are described in [PRODUCTION.md](../../PRODUCTION.md); unresolved acceptance work is in [PRODUCTION_PLAN.md](../../PRODUCTION_PLAN.md).

| Check | Actual result | Scope |
| --- | --- | --- |
| Backend regression suite | 82 passed | Includes six new security/backup tests using real credential provisioning, SQLite and previously recorded real-model work. The repository's older fake-provider tests were retained unchanged apart from their loopback URL. No new fake provider or scripted model response was added |
| Frontend build | Passed | TypeScript and Vite; bundled UI updated |
| Container | Built and run | Non-root UID, read-only root, dropped capabilities, private data/config mounts, resource bounds; [recorded configuration](container.json) |
| Real HTTP | Anonymous 401; other user's run/artifact 404; unauthorized configuration 403 | [HTTP results](http-smoke.json). Health liveness 200; readiness 503 because this separate installation's model connection is unprobed and its container has no command sandbox |
| Key rotation | Old bearer and old session rejected; replacement key accepted | The server reloads its mounted access directory. Host-to-VM propagation was measured, rather than assuming instantaneous revocation; elapsed time is in the HTTP record |
| Browser | Four checks passed; zero page errors | [Browser results](browser-result.json): admin login/settings, a saved real run, logout, operator view. A logout/navigation rejection bug found during this check was fixed |
| Offline recovery | Snapshot verified; same artifact hash restored; zero sessions retained | [Recovery results](recovery-smoke.json). Three files in this small installation; the measured duration is not a production RTO |
| Python dependency audit | 38 packages; no known vulnerabilities reported | [pip-audit output](dependency-audit.json), pip-audit 2.10.1 against the hashed runtime lock. No claim of a penetration test, OS-image audit or absence of undiscovered vulnerabilities |

The referenced artifact is the real Qwen3.5 thinking trial's `email.md`, SHA-256 `23ed248581fd6129b2f0146b10189defd71b71d8603b404174d8d085ed5e80ea`. It remains **business-quality unapproved** and its run remains interrupted. Replaying it here verifies access control and data recovery, not a new successful model execution.

Other observed fixes include a cancellation/resume timing case: cancelled task states were omitted from the requeue set. Explicit resume now requeues cancelled work while preserving accepted tasks; the existing lifecycle regression verifies this. Bound organization data cannot be reopened by accidentally omitting authentication.

Reproduce without fake model responses:

1. Run `backend/scripts/provision_secure_smoke.py` into a new private directory. It issues real temporary installation keys and imports the existing real run from this repository.
2. Build/run the Dockerfile using the private data mount and the **directory** mount for `security/`. Keep port 8796 on loopback.
3. Run `frontend/scripts/production-auth-smoke.mjs` with the generated key filenames, then `backend/scripts/check_secure_server.py`. The latter rotates the operator credential and measures rejection of the former bearer/session.
4. Stop the installation and run the offline backup/verify/restore commands. Preserve source data and restore into a new directory.

The `secured-container` CI job executes the HTTP/browser boundary against the built container. CI status is recorded in GitHub Actions; a configured workflow alone is not a passing execution.
