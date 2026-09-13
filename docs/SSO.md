# OIDC SSO for a dedicated installation

Implemented and locally verified on 2026-09-14. **This integration does not by itself attain L3.** The verification uses a real local Keycloak 26.7.3 and OAuth2 Proxy 7.15.4, actual credentials, browser authorization codes, PKCE S256 and real signed access tokens. See [evidence](evidence/oidc-2026-09-14/README.md).

## Deployment boundary

Browser → organization TLS reverse proxy → OAuth2 Proxy → Agent Team on a private loopback interface. OAuth2 Proxy owns OAuth code/state/nonce/PKCE handling and its encrypted browser cookie. The Agent Team API independently verifies every forwarded access token using PyJWT/cryptography and the configured JWKS URL. User, email and group forwarding headers are not trusted as authentication.

The supported token profile is a signed RS256 access JWT containing `iss`, `sub`, `iat`, `exp`, `aud`, `azp` and a `groups` array. The API audience must differ from the browser client ID. An ID token for the browser client is rejected. Providers that issue opaque access tokens, omit `azp`/group claims or use another algorithm require an explicitly reviewed adapter; do not disable signature/audience/issuer checks to accommodate them.

Use one organization per installation. Only an operator of the private host edits `security/access.json`. Preserve the initial `organization`, `public_origin`, administrator access key and file mode 0600. Add an `oidc` object with these values from the actual registered IdP:

| Access configuration field | Required value |
| --- | --- |
| `issuer` | Exact HTTPS issuer from the IdP; no trailing slash |
| `jwks_url` | Administrator-approved HTTPS JWKS URL; never a URL supplied by a JWT |
| `client_id` | The registered confidential browser client ID; must match token `azp` |
| `audience` | Separate API resource audience, present in access tokens but absent from ID tokens |
| `group_roles` | Explicit mapping of real IdP group values to `admin`, `operator` or `viewer` |
| `max_token_seconds` | 300 by default; permitted range 30–900 seconds |
| `disabled_subjects` | Optional list of Agent Team `oidc-…` subjects to deny immediately |

No matching group means no access. If several allowed groups apply, the highest configured role wins. The stable subject is derived from the verified issuer and IdP subject, not a changeable email address. `/api/auth/me` returns that subject and display name. An administrator can grant work to a subject after its first successful login with the existing `PUT /api/runs/{run_id}/access` API. Grants do not override viewer restrictions.

## OAuth2 Proxy settings

Use the following settings with values from the real deployment. Private client/cookie secret files stay outside the repository, access file, artifacts and logs. The cookie secret is 32 random bytes. The client secret file contains the issued secret without a trailing newline.

| Setting | Value / requirement |
| --- | --- |
| `provider` | `oidc` |
| `oidc_issuer_url`, `client_id` | Same issuer and browser client as the API |
| `client_secret_file`, `cookie_secret_file` | Private absolute secret paths |
| `redirect_url` | Configured public origin plus `/oauth2/callback`; register this exact URL at the IdP |
| `http_address`, `upstreams` | Private loopback listeners; upstream preserves configured public Host |
| `email_domains` | Organization-approved email domains |
| `scope` | `openid email profile`; arrange a signed `groups` claim at the IdP |
| `api_routes` | `["^/api/"]`; return 401 for expired API sessions instead of redirecting fetch/SSE into an IdP HTML page |
| `code_challenge_method` | `S256` |
| `insecure_oidc_skip_nonce` | `false` |
| `pass_access_token` | `true` (`X-Forwarded-Access-Token`) |
| `pass_authorization_header`, `pass_basic_auth`, `pass_user_headers` | `false` |
| `skip_auth_strip_headers` | `true` |
| `cookie_secure`, `cookie_httponly` | `true` |
| `cookie_samesite` | `lax`, allowing the IdP callback |
| `cookie_refresh`, `cookie_expire` | `2m`, `1h` for the verified five-minute token profile |
| `backend_logout_url` | Actual IdP logout endpoint accepting `{id_token}`; verify its session invalidation behavior |
| `request_logging` | `false` |
| `auth_logging`, `auth_logging_format` | `true`, `[{{.Timestamp}}] [{{.Status}}]` |
| `standard_logging_format` | `[{{.Timestamp}}] [{{.File}}] proxy event (details suppressed)` |

The default proxy error format can include full failed callback requests even if request logging is disabled. The supplied format omits request/code/cookie details and retains event location/status. API audit records retain authenticated subject and authorization outcome. Do not upload raw proxy debug logs. Obtain additional diagnostic context privately with the organization's security procedure.

Terminate public HTTPS at the same host's managed proxy, preserve Host/Origin, set ingress body/rate/connection limits, and block direct public access to Agent Team/OAuth2 Proxy. If enabling OAuth2 Proxy's `reverse_proxy`, explicitly set `trusted_proxy_ips` to the ingress addresses; do not trust arbitrary forwarded headers. MFA, account lifecycle, signing-key policy, certificate renewal and IdP resilience remain the organization's responsibilities and require acceptance tests.

## Revocation, outage and recovery behavior

- An API logout records the access-token digest until expiry and redirects to OAuth2 Proxy logout. The local drill also verifies that the Keycloak SSO session ends and replaying the pre-logout proxy cookie cannot regain API access.
- For emergency revocation across sessions, add the actual subject to `disabled_subjects` and invalidate its IdP sessions. The local deny list is reloaded each request. IdP group/account changes otherwise affect already issued tokens at expiry, bounded by `max_token_seconds` (five minutes by default). Access JWTs are not introspected on each request.
- JWKS is cached for up to 60 seconds. New signing keys trigger a refresh, bounded to one unknown-key refresh per five seconds. A removed/compromised key can remain cached for that interval; use local subject revocation/installation isolation for urgent containment.
- If uncached keys cannot be fetched, authentication returns 503. It never falls back to the forwarded user name or an unverified JWT. Previously verified keys can continue validating unexpired tokens during the cache interval. Keep one private access-key administrator for recovery through the private backend.
- Snapshot restore clears access-key browser sessions and records an OIDC issuance boundary. Tokens issued before restore are refused even when their signature/expiration remains valid. Sign in again after restore. This prevents restoring an old revocation database from re-enabling a logged-out token.
- SSE periodically rechecks token validity and run access; an expired/revoked session must reconnect through the normal authentication flow.

## Reproduce the local integration drill

The committed `backend/scripts/provision_oidc_staging.py` generates a **new** private directory, real random credentials, a Keycloak realm and proxy configuration. It imports the previously recorded interrupted Qwen run and original artifact; no model output or IdP is mocked. `frontend/scripts/oidc-smoke.mjs` drives real Chrome and the real authorization-code endpoint. `backend/scripts/check_oidc_restore.py` verifies restore and actual stopped-IdP behavior. CI runs the same drill with immutable Keycloak image digest and checksum-verified OAuth2 Proxy archive.

This drill uses loopback HTTP, Keycloak `start-dev`, a writable disposable container and a second loopback callback for token verification. Direct access grants are disabled for the application client. The drill's bootstrap administrator uses Keycloak's administration endpoint to rotate real RSA keys and briefly issue a real 30-second access token; original client settings are restored afterwards. **Do not deploy this development IdP/configuration as production infrastructure.** No production IdP, corporate MFA policy, public domain or TLS certificate has been provisioned.

References: [OAuth2 Proxy configuration](https://oauth2-proxy.github.io/oauth2-proxy/configuration/overview/), [PyJWT verification API](https://pyjwt.readthedocs.io/en/stable/api.html), [Keycloak administration](https://www.keycloak.org/docs/latest/server_admin/index.html).
