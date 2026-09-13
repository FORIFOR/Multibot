"""Application services wired together: database, stores, config revisions, run manager."""
from __future__ import annotations

import os
import asyncio
import fcntl
from pathlib import Path
from typing import Any

from ..config.loader import DEFAULT_CONFIG_YAML, ConfigError, config_to_yaml, effective_all, list_skills, load_config_text
from ..config.models import AgentTeamConfig
from ..providers.base import ProviderAdapter
from ..runtime.orchestrator import RunManager
from ..runtime.redaction import Redactor
from ..store.artifact_store import ArtifactStore
from ..store.db import Database
from ..store.event_store import EventStore
from ..store.run_store import RunStore


class AppService:
    def __init__(self, data_dir: Path | str | None = None, *, fake_adapters: dict[str, ProviderAdapter] | None = None,
                 config_yaml: str | None = None, approval_wait_seconds: float = 120.0,
                 access_file: Path | str | None = None):
        self.data_dir = Path(data_dir or os.environ.get("AGENTTEAM_DATA_DIR") or "./data").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "agents.yaml"
        self.fake_adapters = fake_adapters or {}
        self._seed_yaml = config_yaml
        self.approval_wait_seconds = approval_wait_seconds
        self.config: AgentTeamConfig | None = None
        self.config_revision: int = 0
        from ..security.server import ServerAccess
        path = access_file or os.environ.get('AGENTTEAM_ACCESS_FILE')
        mode = os.environ.get('AGENTTEAM_MODE', 'local')
        if mode not in ('local', 'production'):
            raise ValueError('AGENTTEAM_MODE must be local or production')
        if mode == 'production' and not path:
            raise ValueError('production mode requires AGENTTEAM_ACCESS_FILE')
        self.access = ServerAccess(self, Path(path).expanduser().absolute() if path else None)
        self.admission_lock = asyncio.Lock()
        self.stopping = False
        self._process_lock = None

    async def start(self) -> "AppService":
        if self._process_lock is not None:
            raise RuntimeError('service already started')
        self._process_lock = (self.data_dir / '.service.lock').open('a')
        try:
            fcntl.flock(self._process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._process_lock.close()
            self._process_lock = None
            raise RuntimeError('data directory is already in use by another process')
        try:
            return await self._start()
        except BaseException:
            if hasattr(self, 'db'):
                await self.db.close()
            self._process_lock.close()
            self._process_lock = None
            raise

    async def _start(self) -> "AppService":
        self.stopping = False
        if self.access.enabled:
            if self.fake_adapters or os.environ.get('AGENTTEAM_SANDBOX', 'auto').lower() == 'subprocess':
                raise ValueError('secured deployments cannot use fake providers or the unsandboxed subprocess backend')
            os.chmod(self.data_dir, 0o700)
        self.db = await Database(self.data_dir / "agentteam.sqlite").connect()
        bound = await self.db.fetchone("SELECT value FROM deployment_metadata WHERE key='organization'")
        if bound and not self.access.enabled:
            raise ValueError('this data directory requires its organization access configuration')
        if self.access.enabled:
            if bound and bound['value'] != self.access.config.organization:
                raise ValueError('this data directory belongs to a different organization')
            await self.db.execute("INSERT OR IGNORE INTO deployment_metadata(key,value) VALUES('organization',?)",
                                  (self.access.config.organization,))
        self.redactor = Redactor()
        self.events = EventStore(self.db, self.redactor)
        self.artifacts = ArtifactStore(self.db, self.data_dir / "runs")
        self.runs = RunStore(self.db)
        latest = await self.runs.latest_config_revision()
        if latest is None:
            text = self._seed_yaml or (self.config_path.read_text(encoding="utf-8") if self.config_path.is_file() else DEFAULT_CONFIG_YAML)
            self.config = load_config_text(text, allow_fake=bool(self.fake_adapters))
            self.config_revision = await self.runs.add_config_revision(config_to_yaml(self.config), "initial")
        else:
            self.config_revision, text = latest
            self.config = load_config_text(text, allow_fake=bool(self.fake_adapters))
        self._mirror_file()
        self.manager = RunManager(runs=self.runs, events=self.events, artifacts=self.artifacts, data_dir=self.data_dir / "runs",
                                  config_getter=lambda: self.config, redactor=self.redactor, fake_adapters=self.fake_adapters,
                                  approval_wait_seconds=self.approval_wait_seconds)
        # runs left 'running' by a previous process are interrupted, never silently resumed
        for row in await self.db.fetchall("SELECT run_id FROM runs WHERE status IN ('running','planning')"):
            await self.events.append(row['run_id'], "run.interrupted", {"reason": "server restarted while running"})
            await self.runs.update_run(row['run_id'], status="interrupted", blocked_reason="server restarted while running")
        return self

    async def stop(self) -> None:
        self.stopping = True
        try:
            if hasattr(self, 'manager'):
                await self.manager.shutdown()
        finally:
            await self.db.close()
            if self._process_lock:
                self._process_lock.close()
                self._process_lock = None

    def _mirror_file(self) -> None:
        try:
            self.config_path.write_text(config_to_yaml(self.config), encoding="utf-8")
        except OSError:
            pass

    async def save_config(self, cfg: AgentTeamConfig, note: str) -> int:
        load_config_text(config_to_yaml(cfg), allow_fake=bool(self.fake_adapters))  # re-validate
        self.config = cfg
        self.config_revision = await self.runs.add_config_revision(config_to_yaml(cfg), note)
        self._mirror_file()
        return self.config_revision

    def public_config(self) -> dict[str, Any]:
        cfg = self.config
        assert cfg is not None
        d = cfg.model_dump(mode="json")
        for c in d["connections"]:
            c["api_key_ref"] = c.get("api_key_ref")  # reference only, never the value
        d["revision"] = self.config_revision
        d["problems"] = self.manager.precheck(cfg)
        d["skills"] = list_skills()
        d["effective_agents"] = {aid: a.model_dump() for aid, a in effective_all(cfg).items()}
        return d
