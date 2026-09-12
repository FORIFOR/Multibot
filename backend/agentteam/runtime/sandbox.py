"""Sandboxed command execution for builder/reviewer checks.

Backends (recorded in every result so nobody mistakes one for another):
  - "sandbox-exec": macOS seatbelt profile: no network, writes only inside the workspace.
  - "subprocess": plain subprocess with cleared env, cwd=workspace, timeout, output cap. NOT an isolation boundary.
Docker/other OS sandboxes are not implemented in this build; see SECURITY.md.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

DENY_TOKENS = ("sudo", "rm -rf /", "curl ", "wget ", "ssh ", "scp ", "nc ", "docker ", "osascript", "open ")
SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


@dataclass
class SandboxResult:
    backend: str
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    denied: bool = False
    reason: str | None = None


def _seatbelt_profile(workspace: Path) -> str:
    ws = str(workspace.resolve()).replace('"', '\\"')
    return f"""(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow sysctl-read)
(allow mach-lookup)
(allow file-read*)
(deny network*)
(allow file-write* (subpath "{ws}"))
(allow file-write-data (literal "/dev/null"))
(allow file-write-data (literal "/dev/stdout"))
(allow file-write-data (literal "/dev/stderr"))
(deny file-read* (subpath "{Path.home() / '.ssh'}"))
(deny file-read* (subpath "{Path.home() / '.aws'}"))
(deny file-read* (subpath "{Path.home() / '.config'}"))
"""


def backend_name() -> str:
    if sys.platform == "darwin" and shutil.which("sandbox-exec") and os.environ.get("AGENTTEAM_NO_SEATBELT") != "1":
        return "sandbox-exec"
    return "subprocess"


async def run_command(command: str, workspace: Path, *, timeout: float = 120.0, max_output: int = 12000,
                      allow_network: bool = False) -> SandboxResult:
    lowered = f" {command.strip()} "
    for tok in DENY_TOKENS:
        if tok in lowered:
            return SandboxResult(backend="policy", command=command, exit_code=None, stdout="", stderr="",
                                 timed_out=False, denied=True, reason=f"command contains denied token {tok.strip()!r}")
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    env = {"PATH": SAFE_PATH, "HOME": str(workspace), "LANG": "C.UTF-8", "TMPDIR": str(workspace / ".tmp"),
           "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"}
    (workspace / ".tmp").mkdir(exist_ok=True)
    backend = backend_name()
    if backend == "sandbox-exec":
        profile = _seatbelt_profile(workspace)
        if allow_network:
            profile = profile.replace("(deny network*)", "(allow network*)")
        argv = ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command]
    else:
        argv = ["/bin/sh", "-c", command]
    try:
        proc = await asyncio.create_subprocess_exec(*argv, cwd=str(workspace), env=env,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                    stdin=asyncio.subprocess.DEVNULL)
    except FileNotFoundError as e:
        return SandboxResult(backend=backend, command=command, exit_code=None, stdout="", stderr=str(e), timed_out=False)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        proc.kill()
        out, err = b"", b"timed out"
        timed_out = True
    o = out.decode("utf-8", errors="replace")
    e = err.decode("utf-8", errors="replace")
    if len(o) > max_output:
        o = o[:max_output] + f"\n...[truncated {len(o) - max_output} chars]"
    if len(e) > max_output:
        e = e[:max_output] + f"\n...[truncated {len(e) - max_output} chars]"
    return SandboxResult(backend=backend, command=command, exit_code=proc.returncode, stdout=o, stderr=e, timed_out=timed_out)
