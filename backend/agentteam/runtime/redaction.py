"""Secret redaction for anything persisted or shown: events, tool results, errors."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(x-api-key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)([?&](?:api[_-]?key|token|access_token|secret|password)=)[^&\s]+"),
    re.compile(r"(?i)((?:ANTHROPIC|OPENAI|BRAVE|GEMINI|OPENROUTER)[A-Z_]*_KEY\s*[:=]\s*)[^\s]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]
REDACTED = "[REDACTED]"


class Redactor:
    def __init__(self, known_secrets: list[str] | None = None):
        self.known = [s for s in (known_secrets or []) if s and len(s) >= 8]

    def add(self, secret: str | None) -> None:
        if secret and len(secret) >= 8 and secret not in self.known:
            self.known.append(secret)

    def text(self, s: str) -> str:
        for k in self.known:
            s = s.replace(k, REDACTED)
        for p in _PATTERNS:
            s = p.sub(lambda m: (m.group(1) if m.lastindex else "") + REDACTED, s)
        return s

    def __call__(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, dict):
            return {k: self(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self(v) for v in obj]
        return obj
