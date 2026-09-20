# Same-task local comparison protocol (not yet executed)

Comparator: installed Ollama CLI0.33.3, the same existing agentteam-qwen35-9b-16k model on loopback. This compares the document production task only; it does not claim that CLI chat and a reviewed workflow have identical capabilities or that one is universally superior. No cloud account or third-party data transfer is necessary.

Freeze the exact user goal and attachment bytes from a measured Agent Team run. Send the same complete text to `ollama run agentteam-qwen35-9b-16k --think=false --nowordwrap`, saving stdout directly as guide.md and stderr separately. Use a subprocess deadline480s; do not trim code fences, edit content, or rerun automatically on a timeout. Capture CLI version, exact argv, input/output SHA-256, elapsed wall clock, exit code and resource contention. The CLI uses its own documented defaults; record them rather than claiming configuration parity.

For both tools, check the unchanged400–700 Unicode-code-point bound, three headings, source-fidelity conditions and exceptions, and exact saved bytes. Count actual required operations; do not treat an expert scripted replay as a human novice success test. For recovery, distinguish the artifact already saved from a new explicitly requested generation. Human first-use time remains BLOCKED until an actual participant performs the task.

Current status: BLOCKED pending an uncontended model environment. No comparator generation has been executed; the installed CLI help was read only. Do not add another model request during the current shared-endpoint trial.
