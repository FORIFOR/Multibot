# Execution boundary checks — 2026-09-14

Code review found three concrete gaps: DNS validation and HTTP connection used separate resolutions; bodies were read in full before truncation; and a secured installation could fall back to macOS Seatbelt, whose existing profile permits broad host reads. Command capture also accumulated full output and cancellation did not reliably remove the owned Docker container.

The changes now:

- Resolve at connection time, reject non-public addresses and dial a validated numeric address. HTTPCore keeps the original HTTP origin for Host, SNI and certificate verification. Environment proxies are disabled. Each redirect uses the guarded transport. Public research fetch supports ports 80/443 and requires identity content encoding.
- Stop body collection at 2,000,000 bytes, bound text/search output and apply an overall fetch deadline. JSON Schema checks refuse identifiers and external/dynamic references that could otherwise create another fetch path.
- Require Docker for command tools in secured runs, including nested command checks. The existing host-readable fallback remains available only in trusted local mode and is not a production isolation boundary.
- Drain command output with a bounded retained buffer. On timeout/cancellation, remove the owned Docker container using a container-ID file outside the mounted workspace, terminate the client process group and reap it. Command deadlines are capped at 300 seconds.

[Actual public-site checks](public-fetch.json) passed: exact bytes of this repository's published source over HTTPS, Python documentation's HTTP-to-HTTPS redirect, and a real Python source archive truncated at the enforced body limit. No controlled DNS-rebinding infrastructure or external penetration test was used; the connection-pinning design and real routing checks do not stand in for such a review.

[Backend verification](backend-tests.xml): **98 passed**. Added regression checks use an actual local listening socket (no connection received), a freshly issued real credential (fallback command never launched), and actual Docker processes. The Docker check outputs real repository source text to exercise bounded capture, then cancels a sleeping container and verifies that container is absent. These are explicit process-failure injections, not fabricated business records or model responses.

Docker daemon/host loss can prevent immediate cleanup; recovered jobs remain interrupted and external effects/resources require inspection. No highly available worker or exactly-once guarantee is claimed. Independent security review and deployment-specific egress controls remain acceptance work.
