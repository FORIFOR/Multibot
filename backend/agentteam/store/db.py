"""SQLite (WAL) database with a single shared connection and a write lock."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  goal TEXT NOT NULL,
  inputs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  config_snapshot_json TEXT,
  plan_json TEXT,
  usage_json TEXT NOT NULL,
  parent_run_id TEXT,
  fork_from_seq INTEGER,
  final_report_json TEXT,
  blocked_reason TEXT,
  provider_kind TEXT NOT NULL DEFAULT 'real',
  cancel_requested INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  event_id TEXT NOT NULL UNIQUE,
  recorded_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  actor_kind TEXT NOT NULL,
  task_id TEXT,
  causation_id TEXT,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS tasks (
  run_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  state_json TEXT NOT NULL,
  status TEXT NOT NULL,
  owner TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (run_id, task_id)
);
CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  from_agent_id TEXT NOT NULL,
  to_agent_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  text TEXT NOT NULL,
  artifact_refs_json TEXT NOT NULL,
  reply_to TEXT,
  recorded_at TEXT NOT NULL,
  read_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_run_to ON messages(run_id, to_agent_id, seq);
CREATE TABLE IF NOT EXISTS artifacts (
  run_id TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  media_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  logical_path TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  task_id TEXT,
  agent_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  event_id TEXT,
  sources_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (run_id, artifact_id, revision)
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  task_id TEXT,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  nonce TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  resolved_at TEXT,
  resolution_json TEXT
);
CREATE TABLE IF NOT EXISTS config_revisions (
  revision INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  config_yaml TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS checkpoints (
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS auth_sessions (
  session_digest TEXT PRIMARY KEY,
  token_digest TEXT NOT NULL,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_identities (
  subject TEXT PRIMARY KEY,
  issuer TEXT NOT NULL,
  display_name TEXT NOT NULL,
  last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_revoked_tokens (
  token_digest TEXT PRIMARY KEY,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deployment_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_access (
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  permission TEXT NOT NULL CHECK(permission IN ('read','write')),
  PRIMARY KEY(run_id,subject)
);
CREATE TABLE IF NOT EXISTS execution_jobs (
  job_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  resume INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('queued','leased','finished','interrupted','cancelled')),
  owner TEXT,
  lease_until REAL,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  reason TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_active_run ON execution_jobs(run_id) WHERE state IN ('queued','leased');
CREATE INDEX IF NOT EXISTS idx_job_pending ON execution_jobs(state,created_at);
CREATE TABLE IF NOT EXISTS request_receipts (
  scope_key TEXT PRIMARY KEY,
  request_hash TEXT NOT NULL,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  status INTEGER NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recorded_at REAL NOT NULL,
  request_id TEXT NOT NULL,
  subject TEXT,
  method TEXT NOT NULL,
  route TEXT NOT NULL,
  run_id TEXT,
  outcome TEXT NOT NULL,
  status INTEGER NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_access_subject ON run_access(subject,run_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(recorded_at);
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._conn: aiosqlite.Connection | None = None
        self.write_lock = asyncio.Lock()

    async def connect(self) -> "Database":
        self._conn = await aiosqlite.connect(self.path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        columns = {r['name'] for r in await self.fetchall('PRAGMA table_info(audit_log)')}
        if 'details_json' not in columns:
            await self.execute("ALTER TABLE audit_log ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'")
        return self

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "database not connected"
        return self._conn

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.conn.execute(sql, tuple(params))

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        cur = await self.conn.execute(sql, tuple(params))
        row = await cur.fetchone()
        await cur.close()
        return row

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
        await cur.close()
        return list(rows)


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def loads(text: str | None, default: Any = None) -> Any:
    if text is None:
        return default
    return json.loads(text)
