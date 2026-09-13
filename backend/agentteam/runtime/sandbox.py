"""Sandboxed command execution for builder/reviewer checks.

Backends (recorded in every result so nobody mistakes one for another):
  - "docker":       container with --network none, workspace bind-mounted at /workspace, read-only root,
                    non-root user, CPU / memory / pids limits, timeout. Works on macOS, Linux and Windows.
  - "sandbox-exec": macOS seatbelt profile: no network, writes only inside the workspace.
  - "subprocess":   plain subprocess with cleared env, cwd=workspace, timeout, output cap. NOT an isolation
                    boundary; only used when explicitly allowed (AGENTTEAM_SANDBOX=subprocess).
Selection: AGENTTEAM_SANDBOX=auto (default) picks docker if the daemon answers, else sandbox-exec on macOS,
else refuses to run commands (denied result) unless subprocess is explicitly chosen.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import signal
import math
import re
from dataclasses import dataclass
from pathlib import Path

DENY_TOKENS = ("sudo", "rm -rf /", "curl ", "wget ", "ssh ", "scp ", "nc ", "docker ", "osascript", "open ")
SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
DEFAULT_IMAGE = os.environ.get("AGENTTEAM_SANDBOX_IMAGE", "python:3.12-slim")
_docker_state: dict[str, bool | None] = {"available": None}


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


async def docker_available(refresh: bool = False) -> bool:
    if _docker_state["available"] is not None and not refresh:
        return bool(_docker_state["available"])
    if shutil.which("docker") is None:
        _docker_state["available"] = False
        return False
    try:
        proc = await asyncio.create_subprocess_exec("docker", "info", "--format", "{{.ServerVersion}}",
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        ok = proc.returncode == 0 and bool(out.strip())
    except Exception:
        ok = False
    _docker_state["available"] = ok
    return ok


def _mode() -> str:
    return (os.environ.get("AGENTTEAM_SANDBOX") or "auto").lower()


async def backend_name() -> str:
    """The backend that run_command will use right now ('none' means commands will be denied)."""
    mode = _mode()
    if mode == "docker":
        return "docker" if await docker_available() else "none"
    if mode in ("seatbelt", "sandbox-exec"):
        return "sandbox-exec" if (sys.platform == "darwin" and shutil.which("sandbox-exec")) else "none"
    if mode == "subprocess":
        return "subprocess"
    # auto
    if await docker_available():
        return "docker"
    if sys.platform == "darwin" and shutil.which("sandbox-exec") and os.environ.get("AGENTTEAM_NO_SEATBELT") != "1":
        return "sandbox-exec"
    return "none"


def backend_name_sync() -> str:
    """Best-effort synchronous view for config/precheck displays (does not probe docker)."""
    mode = _mode()
    if mode == "subprocess":
        return "subprocess"
    if mode == "docker":
        return "docker" if shutil.which("docker") else "none"
    if _docker_state["available"]:
        return "docker"
    if sys.platform == "darwin" and shutil.which("sandbox-exec") and os.environ.get("AGENTTEAM_NO_SEATBELT") != "1":
        return "sandbox-exec"
    return "docker?" if shutil.which("docker") else "none"


async def ensure_docker_image(image: str = DEFAULT_IMAGE, timeout: float = 600.0) -> tuple[bool, str]:
    """Pull the sandbox image once (needs network; the sandbox itself runs with --network none)."""
    proc = await asyncio.create_subprocess_exec("docker", "image", "inspect", image, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if proc.returncode == 0:
        return True, "present"
    proc = await asyncio.create_subprocess_exec("docker", "pull", image, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "pull timed out"
    return proc.returncode == 0, (err or out).decode("utf-8", errors="replace")[-300:]


def _container_user() -> str:
    """Run as the host user so bind-mounted workspace files stay writable and owned by the user (non-root inside)."""
    try:
        uid, gid = os.getuid(), os.getgid()  # type: ignore[attr-defined]
        return f"{uid}:{gid}" if uid != 0 else "1000:1000"
    except AttributeError:  # Windows
        return "1000:1000"


async def _run_docker(command: str, workspace: Path, *, timeout: float, allow_network: bool, image: str, cidfile: Path | None = None) -> tuple[list[str], dict]:
    argv = ["docker", "run", "--rm", "-i",
            "--network", "host" if allow_network else "none",
            "--memory", os.environ.get("AGENTTEAM_SANDBOX_MEMORY", "1g"),
            "--cpus", os.environ.get("AGENTTEAM_SANDBOX_CPUS", "1"),
            "--pids-limit", "256",
            "--read-only", "--tmpfs", "/tmp:rw,size=256m",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "--user", _container_user(),
            "-v", f"{workspace}:/workspace:rw",
            "-w", "/workspace",
            "-e", "HOME=/tmp", "-e", "PATH=/usr/local/bin:/usr/bin:/bin", "-e", "LANG=C.UTF-8",
            image, "/bin/sh", "-c", command]
    if cidfile:
        argv[2:2] = ['--cidfile', str(cidfile)]
    return argv, {}


async def run_command(command: str, workspace: Path, *, timeout: float = 120.0, max_output: int = 12000,
                      allow_network: bool = False, image: str | None = None, require_container: bool = False) -> SandboxResult:
    timeout = min(max(timeout, 0.1), 300) if math.isfinite(timeout) else 120
    max_output = max(1, min(max_output, 100000))
    lowered = f" {command.strip()} "
    for tok in DENY_TOKENS:
        if tok in lowered:
            return SandboxResult(backend="policy", command=command, exit_code=None, stdout="", stderr="",
                                 timed_out=False, denied=True, reason=f"command contains denied token {tok.strip()!r}")
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    backend = await backend_name()
    if require_container and backend != 'docker':
        return SandboxResult(backend=backend, command=command, exit_code=None, stdout='', stderr='', timed_out=False,
                             denied=True, reason='secured work requires Docker isolation; host-readable sandbox fallbacks are refused')
    if backend == "none":
        return SandboxResult(backend="none", command=command, exit_code=None, stdout="", stderr="", timed_out=False, denied=True,
                             reason="no sandbox available: start Docker (recommended) or set AGENTTEAM_SANDBOX=subprocess to run "
                                    "commands WITHOUT isolation")
    env = {"PATH": SAFE_PATH, "HOME": str(workspace), "LANG": "C.UTF-8", "TMPDIR": str(workspace / ".tmp"),
           "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"}
    (workspace / ".tmp").mkdir(exist_ok=True)
    if backend == "docker":
        img = image or DEFAULT_IMAGE
        ok, note = await ensure_docker_image(img)
        if not ok:
            return SandboxResult(backend="docker", command=command, exit_code=None, stdout="", stderr=note, timed_out=False,
                                 denied=True, reason=f"sandbox image {img} unavailable")
        # preflight: the workspace must be writable inside the container (Colima/Lima share only $HOME by default)
        pre_argv, _ = await _run_docker("test -w /workspace && echo WRITABLE", workspace, timeout=30, allow_network=False, image=img)
        pre = await asyncio.create_subprocess_exec(*pre_argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=dict(os.environ))
        pre_out, pre_err = await asyncio.wait_for(pre.communicate(), timeout=60)
        if b"WRITABLE" not in pre_out:
            return SandboxResult(backend="docker", command=command, exit_code=None, stdout="", stderr=pre_err.decode("utf-8", errors="replace")[-300:],
                                 timed_out=False, denied=True,
                                 reason=f"workspace {workspace} is not writable inside the sandbox container. With Colima/Lima only your home "
                                        "directory is shared with the VM: keep the data dir under $HOME (or share the path in the VM settings).")
        # Outside the mounted workspace: generated commands cannot replace the
        # container ID and trick cleanup into targeting another container.
        container_dir = tempfile.TemporaryDirectory(prefix='agentteam-container-')
        cidfile = Path(container_dir.name) / 'cid'
        argv, _ = await _run_docker(command, workspace, timeout=timeout, allow_network=allow_network, image=img, cidfile=cidfile)
        env = dict(os.environ)  # docker CLI needs its own env (DOCKER_HOST etc.); the container env is set via -e
    elif backend == "sandbox-exec":
        profile = _seatbelt_profile(workspace)
        if allow_network:
            profile = profile.replace("(deny network*)", "(allow network*)")
        argv = ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command]
    else:
        argv = ["/bin/sh", "-c", command]
    try:
        proc = await asyncio.create_subprocess_exec(*argv, cwd=str(workspace), env=env,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                    stdin=asyncio.subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError as e:
        if backend == 'docker':
            container_dir.cleanup()
        return SandboxResult(backend=backend, command=command, exit_code=None, stdout="", stderr=str(e), timed_out=False)
    buffers = [bytearray(), bytearray()]
    counts = [0, 0]
    async def drain(stream, index):
        while chunk := await stream.read(65536):
            counts[index] += len(chunk)
            buffers[index].extend(chunk[:max(0, max_output * 4 - len(buffers[index]))])
    readers = [asyncio.create_task(drain(proc.stdout, 0)), asyncio.create_task(drain(proc.stderr, 1))]
    async def terminate():
        for reader in readers:
            if not reader.done():
                reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        if backend == 'docker' and cidfile.exists():
            cid = cidfile.read_text().strip()
            if re.fullmatch(r'[0-9a-f]{64}', cid):
                cleanup = await asyncio.create_subprocess_exec('docker', 'rm', '-f', cid,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                try:
                    await asyncio.wait_for(cleanup.wait(), timeout=10)
                except asyncio.TimeoutError:
                    cleanup.kill(); await cleanup.wait()
        if proc.returncode is None:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
        await asyncio.wait_for(asyncio.gather(proc.wait(), drain(proc.stdout, 0), drain(proc.stderr, 1)), timeout=10)
    try:
        await asyncio.wait_for(asyncio.gather(proc.wait(), *readers), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        await terminate()
        timed_out = True
    except asyncio.CancelledError:
        await terminate()
        raise
    finally:
        for reader in readers:
            if not reader.done():
                reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        if backend == 'docker':
            container_dir.cleanup()
    o = buffers[0].decode("utf-8", errors="replace")
    e = buffers[1].decode("utf-8", errors="replace")
    if len(o) > max_output:
        o = o[:max_output] + f"\n...[truncated {len(o) - max_output} chars]"
    if len(e) > max_output:
        e = e[:max_output] + f"\n...[truncated {len(e) - max_output} chars]"
    if counts[0] > len(buffers[0]):
        o += f'\n...[discarded {counts[0] - len(buffers[0])} additional bytes]'
    if counts[1] > len(buffers[1]):
        e += f'\n...[discarded {counts[1] - len(buffers[1])} additional bytes]'
    if timed_out:
        e += '\ntimed out'
    return SandboxResult(backend=backend, command=command, exit_code=proc.returncode, stdout=o, stderr=e, timed_out=timed_out)
