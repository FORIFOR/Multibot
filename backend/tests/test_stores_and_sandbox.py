import sys

import pytest

from agentteam.runtime.sandbox import run_command
from agentteam.runtime.webtools import FetchDenied, check_url
from agentteam.store.artifact_store import ArtifactStore, artifact_id_for
from agentteam.store.db import Database
from agentteam.store.event_store import EventStore


async def test_event_seq_is_insertion_order_even_at_same_time(tmp_path):
    db = await Database(tmp_path / "t.db").connect()
    es = EventStore(db)
    import asyncio
    evs = await asyncio.gather(*[es.append("r", "tool.called", {"i": i}, causation_id="r:0") for i in range(20)])
    seqs = sorted(e.seq for e in evs)
    assert seqs == list(range(1, 21))
    listed = await es.list("r", after_seq=15)
    assert [e.seq for e in listed] == [16, 17, 18, 19, 20] and all(e.causation_id == "r:0" for e in listed)
    await db.close()


async def test_artifact_revisions_are_immutable_and_hashed(tmp_path):
    db = await Database(tmp_path / "t.db").connect()
    st = ArtifactStore(db, tmp_path / "a")
    m1 = await st.publish("r", "docs/readme.md", b"v1", agent_id="b", task_id="t")
    m2 = await st.publish("r", "docs/readme.md", b"v2", agent_id="b", task_id="t")
    assert (m1.revision, m2.revision) == (1, 2) and m1.sha256 != m2.sha256
    assert st.read_bytes(m1) == b"v1" and st.read_bytes(m2) == b"v2"
    assert artifact_id_for("docs/readme.md") == "docs-readme.md"
    latest = await st.list("r", latest_only=True)
    assert len(latest) == 1 and latest[0].revision == 2
    await db.close()


async def test_sandbox_denies_tokens_and_confines_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTTEAM_SANDBOX", "seatbelt" if sys.platform == "darwin" else "subprocess")  # docker path is covered separately
    r = await run_command("curl https://example.com", tmp_path)
    assert r.denied
    r = await run_command("echo ok > out.txt; cat out.txt", tmp_path)
    assert r.exit_code == 0 and "ok" in r.stdout
    if sys.platform == "darwin" and r.backend == "sandbox-exec":
        outside = tmp_path.parent / "escape.txt"
        r2 = await run_command(f"touch {outside}; echo rc=$?", tmp_path)
        assert not outside.exists() and "rc=1" in r2.stdout
        r3 = await run_command("python3 -c 'import urllib.request;urllib.request.urlopen(\"https://example.com\",timeout=3)'; echo rc=$?", tmp_path, timeout=30)
        assert "rc=1" in r3.stdout, "network must be denied inside the seatbelt"


@pytest.mark.parametrize("url", ["http://localhost/x", "http://127.0.0.1:8787", "http://169.254.169.254/latest", "file:///etc/passwd", "ftp://x.y/z"])
def test_ssrf_guard(url):
    with pytest.raises(FetchDenied):
        check_url(url)


async def test_docker_sandbox_isolation(tmp_path):
    """Runs only when a Docker daemon answers: no network, read-only root, writes confined to the workspace."""
    import os, tempfile, shutil, pathlib
    from agentteam.runtime.sandbox import docker_available, backend_name
    if not await docker_available(refresh=True):
        pytest.skip("docker daemon not available")
    # Colima/Lima share only $HOME with the VM, so use a workspace under the home directory
    cache_dir = pathlib.Path.home() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)  # absent on fresh CI runners
    home_tmp = pathlib.Path(tempfile.mkdtemp(prefix="agentteam-sbx-", dir=cache_dir))
    tmp_path = home_tmp
    old = os.environ.get("AGENTTEAM_SANDBOX")
    os.environ["AGENTTEAM_SANDBOX"] = "docker"
    try:
        assert await backend_name() == "docker"
        r = await run_command("echo hi > out.txt && cat out.txt && id -u", tmp_path, timeout=120)
        assert r.backend == "docker" and r.exit_code == 0 and "hi" in r.stdout and "0\n" not in r.stdout.splitlines()[-1] + "\n"
        assert (tmp_path / "out.txt").read_text().strip() == "hi"
        r2 = await run_command("touch /etc/escape 2>&1; echo rc=$?", tmp_path, timeout=60)
        assert "rc=1" in r2.stdout, r2
        r3 = await run_command("python3 -c 'import urllib.request;urllib.request.urlopen(\"https://example.com\",timeout=5)' 2>&1; echo rc=$?", tmp_path, timeout=60)
        assert "rc=1" in r3.stdout, r3
    finally:
        if old is None:
            os.environ.pop("AGENTTEAM_SANDBOX", None)
        else:
            os.environ["AGENTTEAM_SANDBOX"] = old
        shutil.rmtree(home_tmp, ignore_errors=True)


async def test_no_sandbox_is_denied_not_silently_unsafe(tmp_path, monkeypatch):
    import agentteam.runtime.sandbox as sb
    monkeypatch.setenv("AGENTTEAM_SANDBOX", "docker")
    monkeypatch.setattr(sb, "docker_available", lambda refresh=False: _false())
    r = await run_command("echo hi", tmp_path)
    assert r.denied and r.backend == "none" and "no sandbox available" in (r.reason or "")


async def _false():
    return False
