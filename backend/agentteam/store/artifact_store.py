"""Immutable, content-addressed artifact revisions with atomic publish."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path

from ..contracts import ArtifactManifest
from ..ids import now_iso
from .db import Database, dumps, loads

_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def artifact_id_for(logical_path: str) -> str:
    """Stable id derived from the logical path: 'site/index.html' -> 'site-index.html'."""
    p = logical_path.strip().strip("/").replace("\\", "/")
    return _SLUG_RE.sub("-", p.replace("/", "-")) or "artifact"


def guess_media_type(logical_path: str, data: bytes) -> str:
    mt, _ = mimetypes.guess_type(logical_path)
    if mt:
        return mt
    if logical_path.endswith(".md"):
        return "text/markdown"
    try:
        data.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


class ArtifactStore:
    def __init__(self, db: Database, root: Path):
        self.db = db
        self.root = Path(root)

    def _dir(self, run_id: str, artifact_id: str, revision: int) -> Path:
        return self.root / run_id / "artifacts" / artifact_id / f"r{revision}"

    async def publish(
        self, run_id: str, logical_path: str, data: bytes, *, agent_id: str, task_id: str | None,
        media_type: str | None = None, sources: list[str] | None = None,
    ) -> ArtifactManifest:
        artifact_id = artifact_id_for(logical_path)
        sha = hashlib.sha256(data).hexdigest()
        media_type = media_type or guess_media_type(logical_path, data)
        filename = os.path.basename(logical_path) or "artifact"
        async with self.db.write_lock:
            row = await self.db.fetchone(
                "SELECT COALESCE(MAX(revision),0)+1 AS n FROM artifacts WHERE run_id=? AND artifact_id=?",
                (run_id, artifact_id),
            )
            revision = int(row["n"])
            target_dir = self._dir(run_id, artifact_id, revision)
            target_dir.mkdir(parents=True, exist_ok=True)
            final = target_dir / filename
            tmp = target_dir / (filename + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, final)  # atomic publish
            m = ArtifactManifest(
                run_id=run_id, artifact_id=artifact_id, revision=revision, sha256=sha, media_type=media_type,
                size=len(data), logical_path=logical_path, storage_path=str(final.relative_to(self.root)),
                task_id=task_id, agent_id=agent_id, created_at=now_iso(), sources=sources or [],
            )
            await self.db.execute(
                "INSERT INTO artifacts(run_id,artifact_id,revision,sha256,media_type,size,logical_path,storage_path,"
                "task_id,agent_id,created_at,event_id,sources_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (m.run_id, m.artifact_id, m.revision, m.sha256, m.media_type, m.size, m.logical_path, m.storage_path,
                 m.task_id, m.agent_id, m.created_at, None, dumps(m.sources)),
            )
        return m

    async def set_event(self, run_id: str, artifact_id: str, revision: int, event_id: str) -> None:
        await self.db.execute("UPDATE artifacts SET event_id=? WHERE run_id=? AND artifact_id=? AND revision=?",
                              (event_id, run_id, artifact_id, revision))

    async def get(self, run_id: str, artifact_id: str, revision: int | None = None) -> ArtifactManifest | None:
        if revision is None:
            r = await self.db.fetchone(
                "SELECT * FROM artifacts WHERE run_id=? AND artifact_id=? ORDER BY revision DESC LIMIT 1", (run_id, artifact_id))
        else:
            r = await self.db.fetchone(
                "SELECT * FROM artifacts WHERE run_id=? AND artifact_id=? AND revision=?", (run_id, artifact_id, revision))
        return self._row(r) if r else None

    async def list(self, run_id: str, latest_only: bool = False) -> list[ArtifactManifest]:
        rows = await self.db.fetchall("SELECT * FROM artifacts WHERE run_id=? ORDER BY artifact_id, revision", (run_id,))
        items = [self._row(r) for r in rows]
        if latest_only:
            latest: dict[str, ArtifactManifest] = {}
            for m in items:
                latest[m.artifact_id] = m
            return list(latest.values())
        return items

    def read_bytes(self, m: ArtifactManifest) -> bytes:
        return (self.root / m.storage_path).read_bytes()

    def read_text(self, m: ArtifactManifest) -> str:
        return self.read_bytes(m).decode("utf-8", errors="replace")

    @staticmethod
    def _row(r) -> ArtifactManifest:
        return ArtifactManifest(
            run_id=r["run_id"], artifact_id=r["artifact_id"], revision=r["revision"], sha256=r["sha256"],
            media_type=r["media_type"], size=r["size"], logical_path=r["logical_path"], storage_path=r["storage_path"],
            task_id=r["task_id"], agent_id=r["agent_id"], created_at=r["created_at"], event_id=r["event_id"],
            sources=loads(r["sources_json"], []),
        )
