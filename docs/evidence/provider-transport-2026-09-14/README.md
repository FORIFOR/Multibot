# Explicit local-model transport — 2026-09-14 JST

The OpenAI-compatible/Ollama driver previously inherited HTTPX's environment-based proxy behavior. With proxy variables set and `NO_PROXY` empty, its HTTP client attempted the actual loopback connection-drop endpoint instead of the configured service. This is a reproduced routing behavior, not evidence of customer-data exposure.

The client now uses `trust_env=False`: proxy variables cannot silently redirect the configured local/approved model endpoint. The regression uses the actual secured Multibot API, real newly issued credentials and TCP connections. A separate owned listener closes connections as a deliberate network fault. The corrected client reaches `/api/auth/me`, authenticates successfully, and never connects to that listener. It makes no model call and fabricates no HTTP/model success response. All environment changes are confined to the verification process and restored afterward.

The original test helper first used a relative URL without a client base URL and was corrected before reproducing the proxy route. The reproduced pre-fix failure then traversed `httpcore/_async/http_proxy.py` and raised `httpx.ReadError` at the real dropped connection. After the transport correction, the entire backend suite passed **102 tests in 13.34 seconds**; see `backend-tests.xml`.

This behavior applies to the OpenAI-compatible and Ollama driver. It does not assert control of another provider's CLI or SDK transport. HTTPX environment trust also covers implicit CA overrides; corporate proxy/custom-CA arrangements require an explicitly evaluated configuration. The app still needs customer-specific egress policy and an independent security review. Test counts do not measure business-workflow quality.
