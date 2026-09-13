# Security

Trust boundaries, what is enforced, and what is not yet: see [`docs/STATUS.md`](docs/STATUS.md) and the requirements in [`docs/blueprint/SECURITY.md`](docs/blueprint/SECURITY.md).

Short version:

- Runs on loopback, single user, local SQLite. If you pick a cloud connection, the request text and artifacts are sent to that provider.
- API keys are never stored; config holds references (`env:NAME`, `keychain:service/account`, `file:/path`). Events, tool results and errors are redacted before persistence.
- Agents cannot widen their own permissions: tool scope, write scope, budget and approvals are enforced by the runtime, not by prompt wording.
- `web_fetch` refuses private, loopback and metadata addresses on every redirect hop.
- Commands run in a Docker container when a daemon answers (`--network none`, read-only root filesystem, host uid, `--cap-drop ALL`, `no-new-privileges`, CPU/memory/pid limits, only the task workspace mounted), otherwise under macOS `sandbox-exec` (no network, writes only inside the workspace). With neither available the runtime **refuses** to run commands; `AGENTTEAM_SANDBOX=subprocess` opts into an unsandboxed subprocess explicitly. Every result records which backend ran. Colima/Lima share only your home directory with the VM, so keep the data dir under `$HOME`.
- Generated HTML is served with a `sandbox` CSP and framed with `<iframe sandbox>`.

To report a vulnerability, open a GitHub issue with the label `security` (no public exploit details) or contact the maintainer via the profile email.
