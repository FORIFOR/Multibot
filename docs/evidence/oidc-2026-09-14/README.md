# Actual OIDC integration evidence — 2026-09-14

Status: SSO integration verified in local staging. **L3 remains unachieved.** No corporate IdP/MFA, public TLS/DNS, HA/SLA, external security review or business-quality acceptance is implied.

| Verification | Observed result |
| --- | --- |
| Real Chrome → OAuth2 Proxy → Keycloak → API | 14 integration assertions/groups passed; zero browser JavaScript errors |
| Actual IdP accounts | Admin, operator, viewer map correctly; an account with no allowed group is denied |
| Protocol | Authorization code, S256 PKCE, nonce; application password grants disabled |
| Authorization | Per-run read sharing, admin endpoints and viewer writes enforced; forwarded identity strings have no authority |
| JWT validation | Real ID token, wrong configured issuer/audience/client, excessive lifetime and a one-bit damaged actual signature rejected |
| Logout | API revokes actual token; copied proxy cookie cannot regain access; actual Keycloak session ends |
| Key rotation | Keycloak generated a new RSA signing key; API fetched JWKS and accepted new and retained old valid keys |
| Expiry | Real 30-second token accepted before expiry and rejected after elapsed time |
| Restore | Same real token: 200 before snapshot → 401 after restore; private recovery administrator: 200 |
| Actual IdP shutdown | Uncached signature verification: 503; private recovery administrator: 200 |
| Original artifact | SHA-256 `23ed248581fd6129b2f0146b10189defd71b71d8603b404174d8d085ed5e80ea` preserved |
| Dependencies | 42 locked Python runtime dependencies; pip-audit reported no known vulnerabilities |
| Existing backend suite | 82 passed locally after integration; no new mocked providers added |

Machine-readable records: [SSO/browser](oidc-smoke.json), [restore](oidc-restore.json), [stopped IdP](oidc-outage.json), [dependency audit](dependency-audit.json).

Keycloak: `quay.io/keycloak/keycloak@sha256:ff4257d0d64efbe99ed1ddfaf07765cc3c36dc7518bf8324d41961327f441c54` (26.7.3). Local OAuth2 Proxy: 7.15.4, macOS ARM64 release archive SHA-256 `ec5acdd46df12da2a2449e77aa9e16bc6ff0ad46c87b9e19c8c93c18be6dbb4d`, checked against its upstream release checksum. CI verifies the Linux AMD64 archive separately.

The drill uses actual randomly issued accounts and signed credentials in a private local Keycloak, not an IdP stub or manufactured success responses. The artifact is the original saved interrupted Qwen run; its contents are **not** counted as a successful business workflow. Restoring three small files is not an enterprise recovery-time benchmark.

Observed issues were corrected rather than excluded:

1. Proxy default error logging included OAuth callback details despite disabled request logs. The supplied standard/auth formats now omit request details; the successful drill checks actual issued token strings and callback code against application/proxy logs.
2. Node native `fetch` did not preserve the configured Host for direct-backend checks. The verification client now uses the actual HTTP request API; the production Host validation remains enabled.
3. A repeated drill encountered its previously granted access. The repeatable drill explicitly revokes its own earlier grant before measuring isolation and re-granting read access.
4. Snapshot restore needed to invalidate still-valid SSO tokens, not only local cookie sessions. Restore now writes an issuance boundary and the API rejects tokens issued before it.

The complete CI result for the published commit is tracked in GitHub Actions. Local checks do not substitute for that result. All issued passwords, bearer/refresh/ID tokens, proxy cookie material, bootstrap credentials and raw private logs are excluded from this evidence directory.
