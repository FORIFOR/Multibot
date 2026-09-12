"""API key resolution. Config stores references only; values never enter prompts, logs or events."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class SecretResolutionError(Exception):
    pass


def resolve_secret(ref: str | None) -> str | None:
    """Resolve `env:NAME`, `keychain:service[/account]`, `file:/path`. Returns None if ref is None."""
    if ref is None or ref == "":
        return None
    kind, _, rest = ref.partition(":")
    if kind == "env":
        val = os.environ.get(rest)
        if not val:
            raise SecretResolutionError(f"environment variable {rest} is not set")
        return val
    if kind == "file":
        p = Path(rest).expanduser()
        if not p.is_file():
            raise SecretResolutionError(f"secret file {rest} not found")
        return p.read_text(encoding="utf-8").strip()
    if kind == "keychain":
        service, _, account = rest.partition("/")
        cmd = ["security", "find-generic-password", "-s", service, "-w"]
        if account:
            cmd[3:3] = ["-a", account]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise SecretResolutionError(f"keychain lookup failed: {type(e).__name__}") from e
        if out.returncode != 0:
            raise SecretResolutionError(f"keychain item {rest} not found")
        return out.stdout.strip()
    raise SecretResolutionError(f"unsupported secret reference kind: {kind}")
