# Security

Trust boundaries, what is enforced, and what is not yet: see [`docs/STATUS.md`](docs/STATUS.md) and the requirements in [`docs/blueprint/SECURITY.md`](docs/blueprint/SECURITY.md).

Short version for v0.1:

- Runs on loopback, single user, local SQLite. If you pick a cloud connection, the request text and artifacts are sent to that provider.
- API keys are never stored; config holds references (`env:NAME`, `keychain:service/account`, `file:/path`). Events, tool results and errors are redacted before persistence.
- Agents cannot widen their own permissions: tool scope, write scope, budget and approvals are enforced by the runtime, not by prompt wording.
- `web_fetch` refuses private, loopback and metadata addresses on every redirect hop.
- Commands run under macOS `sandbox-exec` (no network, writes only inside the task workspace). On other platforms the `subprocess` backend is **not** an isolation boundary; the result records which backend ran.
- Generated HTML is served with a `sandbox` CSP and framed with `<iframe sandbox>`.

To report a vulnerability, open a GitHub issue with the label `security` (no public exploit details) or contact the maintainer via the profile email.
