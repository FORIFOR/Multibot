# Installed release and dependency verification — 2026-09-14 JST

Two real wheels were built from clean fixed checkouts, installed in separate Python 3.12.12 environments and verified through actual loopback HTTP on this Mac. Both use the recorded hash-locked 42-package runtime dependency set; this drill is not a Python/OS/dependency-version migration.

| Release | Commit | Wheel SHA-256 |
| --- | --- | --- |
| Prior | `08ca1b730efcaef37947905d238a77e032b22d94` | `6184ff800c9966bf412fd29d5c25ed4701e703a8b6bdadc836876d65c1691997` |
| Candidate | `c69c27ddc15eb489be8f675e0804a3e9c9b2cbba` | `b85be197222f17168665b45a9b9d33519ac04b75eeb736093bde792c698d7c41` |

The final drill passed **13 checks**: unauthenticated denial; old-version session and original artifact bytes; real grant; live-backup refusal; updated session/artifact/grant retention; old-key rejection after real rotation; new-key acceptance; backup rejection after deliberately corrupting the disposable candidate's artifact; restored-session rejection; retained key revocation; and original artifact/grant recovery using the current credential. The original failed business output hash is `dd68d14539ccb1549eb1abc539eab12c54f398a2a52fccd489902941d6d531ee`; preserving its bytes does not make that business result correct.

Local measured intervals were **3.764 s** for stop/backup/new startup/read and **0.650 s** for verified restore/old startup/read on this tiny dataset. They exclude real ingress switching, off-site transfer, large data, production load and operator decision time. They are not RPO/RTO guarantees. No TLS, corporate IdP, real traffic or LLM call was exercised by this drill.

`result.json` records the final outcome. `attempt-1.json` and `attempt-2.json` preserve two harness failures: the first helper omitted the required access-file environment before importing the application's module-level factory; the second treated Uvicorn's post-shutdown SIGTERM re-raise as failure. The corrected harness supplies the explicit isolated paths and requires both an expected exit code and the actual lifespan shutdown-complete log. These failures are not counted as passed trials or product business results. Both attempted installation roots remain private.

`pip-audit.json` contains the live PyPI-advisory query by **pip-audit 2.10.1**: **42 pinned runtime dependencies, zero reported known vulnerabilities, zero skipped packages**. Their hashes were independently enforced during wheel-environment installation. The first audit-tool invocation used an unsuitable cached Python 3.10 runtime and failed before collecting an audit; the successful query used Python 3.12 and the complete hash-locked list with pip resolution disabled. [pip-audit's scope](https://github.com/pypa/pip-audit) is known package advisories, not arbitrary application vulnerability discovery.

`frontend-audit.json` records the actual `pnpm audit --prod --json` result for the frontend lockfile. These snapshots do not establish future vulnerability absence, provenance of every transitive source, container/OS security, or an independent penetration test. The [release procedure](../../RELEASE_OPERATIONS.md) also documents point-in-time data/grant reconciliation and why current revocations must not be rolled back.
