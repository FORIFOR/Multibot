"""Separate-process audit collection and health transitions using a restricted key."""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import sqlite3
import time
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class ObservationError(ValueError):
    pass


class Observer:
    def __init__(self, url: str, credential_file: Path, state_dir: Path, *, private_backend: str | None = None):
        u = urlsplit(url)
        if not u.hostname or u.username or u.password or u.query or u.fragment or u.path:
            raise ValueError('observer URL must be an exact origin without credentials or a trailing slash')
        if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('observer requires HTTPS outside loopback')
        self.url, self.credential_file = url, credential_file
        self.connect_url = private_backend or url
        self.host = u.netloc
        if private_backend:
            target = urlsplit(private_backend)
            if (target.scheme != 'http' or target.hostname not in ('127.0.0.1', 'localhost', '::1') or
                    target.username or target.password or target.path or target.query or target.fragment):
                raise ValueError('private backend must be a loopback HTTP origin')
        if state_dir.is_symlink():
            raise ValueError('observer directory must not be a symlink')
        self.root = state_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise ValueError('observer directory requires mode 0700')
        for name in ('observer.sqlite', '.observer.lock', 'health.json', 'metrics.prom'):
            if (self.root / name).is_symlink():
                raise ValueError('observer files must not be symlinks')

    @contextmanager
    def _database(self):
        with (self.root / '.observer.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ObservationError('another collector is using this directory') from None
            if shutil.disk_usage(self.root).free < 500 * 1024 * 1024:
                raise ObservationError('collector storage below 500 MiB')
            with closing(sqlite3.connect(self.root / 'observer.sqlite', isolation_level=None)) as db:
                os.chmod(self.root / 'observer.sqlite', 0o600)
                db.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
                    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS cursors (stream_id TEXT PRIMARY KEY,last_id INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS audit_records (stream_id TEXT NOT NULL,remote_id INTEGER NOT NULL,payload_json TEXT NOT NULL,
                        PRIMARY KEY(stream_id,remote_id));
                    CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY,recorded_at REAL NOT NULL,state TEXT NOT NULL,details_json TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY,recorded_at REAL NOT NULL,kind TEXT NOT NULL,details_json TEXT NOT NULL);''')
                old = db.execute("SELECT value FROM settings WHERE key='origin'").fetchone()
                if old and old[0] != self.url:
                    raise ObservationError('collector belongs to another origin; use a separate directory')
                db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('origin',?)", (self.url,))
                yield db

    def _credential(self):
        path = self.credential_file
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077 or path.stat().st_size > 1024:
            raise ObservationError('collector credential requires a regular private file')
        key = path.read_text().strip()
        if not 32 <= len(key) <= 256:
            raise ObservationError('invalid collector credential')
        return key

    @staticmethod
    def _get(client, path, *, ready=False):
        with client.stream('GET', path) as response:
            if response.status_code in (401, 403):
                raise ObservationError('collector authentication or role rejected')
            if response.status_code != 200 and not (ready and response.status_code == 503):
                raise ObservationError('monitored endpoint returned an unexpected status')
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 2 * 1024 * 1024:
                    raise ObservationError('monitored response exceeds the collection limit')
            return response.status_code, response.headers, bytes(body)

    def _publish(self, name, text):
        fd, temporary = tempfile.mkstemp(prefix='.' + name + '.', dir=self.root)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(text); f.flush(); os.fsync(f.fileno())
            temporary.replace(self.root / name)
        finally:
            temporary.unlink(missing_ok=True)

    def collect(self):
        with self._database() as db:
            now = time.time()
            state, details, batches, metrics, stream = 'unreachable', {}, [], '', None
            try:
                with httpx.Client(base_url=self.connect_url, headers={'Authorization': 'Bearer ' + self._credential(), 'Host': self.host},
                                  timeout=10, follow_redirects=False, trust_env=False) as client:
                    _, _, identity = self._get(client, '/api/auth/me')
                    if json.loads(identity).get('role') != 'auditor':
                        raise ObservationError('collector requires an auditor key, not a workspace/admin key')
                    status, _, raw = self._get(client, '/api/admin/ready', ready=True)
                    details = json.loads(raw)
                    stream = details.get('audit_stream_id')
                    if not isinstance(stream, str) or not re.fullmatch(r'audit_[a-zA-Z0-9_-]+', stream):
                        raise ObservationError('server audit stream identity is unavailable')
                    state = 'healthy' if status == 200 and details.get('ready') is True else 'not_ready'
                    _, _, raw_metrics = self._get(client, '/api/admin/metrics')
                    metrics = raw_metrics.decode('utf-8')
                    previous = db.execute('SELECT last_id FROM cursors WHERE stream_id=?', (stream,)).fetchone()
                    cursor = previous[0] if previous else 0
                    # Bound each collection cycle; a busy source is continued at
                    # its committed cursor on the next cycle, never skipped.
                    for _ in range(5):
                        _, headers, raw_audit = self._get(client, f'/api/admin/audit?after_id={cursor}&limit=1000')
                        if headers.get('X-Agentteam-Audit-Stream') != stream:
                            raise ObservationError('audit source changed during collection; retry required')
                        rows = json.loads(raw_audit)
                        if not isinstance(rows, list) or len(rows) > 1000:
                            raise ObservationError('invalid audit batch')
                        for row in rows:
                            if not isinstance(row, dict) or not isinstance(row.get('id'), int) or row['id'] <= cursor:
                                raise ObservationError('audit cursor did not advance')
                            cursor = row['id']
                        batches.extend(rows)
                        if len(rows) < 1000:
                            break
                    else:
                        details['audit_backlog'] = True
                    details['collected_records'] = len(batches)
            except ObservationError as exc:
                state, details, batches, metrics, stream = 'collection_failed', {'reason': str(exc)}, [], '', None
            except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError):
                # No URL query, response body, credential or exception payload is
                # copied into alerts. The server's own audit remains authoritative.
                state, details, batches, metrics, stream = 'unreachable', {'reason': 'connection or response validation failed'}, [], '', None
            db.execute('BEGIN IMMEDIATE')
            try:
                previous = db.execute('SELECT state FROM samples ORDER BY id DESC LIMIT 1').fetchone()
                if (previous and previous[0] != state) or (not previous and state != 'healthy'):
                    db.execute('INSERT INTO alerts(recorded_at,kind,details_json) VALUES(?,?,?)',
                               (now, 'health_transition', json.dumps({'previous': previous[0] if previous else None, 'current': state})))
                if stream:
                    old_stream = db.execute("SELECT value FROM settings WHERE key='last_stream'").fetchone()
                    if old_stream and old_stream[0] != stream:
                        db.execute('INSERT INTO alerts(recorded_at,kind,details_json) VALUES(?,?,?)',
                                   (now, 'audit_source_changed', json.dumps({'previous': old_stream[0], 'current': stream})))
                    db.execute("INSERT INTO settings(key,value) VALUES('last_stream',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (stream,))
                    for row in batches:
                        db.execute('INSERT OR IGNORE INTO audit_records(stream_id,remote_id,payload_json) VALUES(?,?,?)',
                                   (stream, row['id'], json.dumps(row, ensure_ascii=False, sort_keys=True)))
                    if batches:
                        db.execute('INSERT INTO cursors(stream_id,last_id) VALUES(?,?) ON CONFLICT(stream_id) DO UPDATE SET last_id=excluded.last_id',
                                   (stream, batches[-1]['id']))
                db.execute('INSERT INTO samples(recorded_at,state,details_json) VALUES(?,?,?)', (now, state, json.dumps(details)))
                db.execute('DELETE FROM samples WHERE recorded_at<?', (now - 30 * 86400,))
                db.commit()
            except BaseException:
                db.rollback(); raise
            result = {'recorded_at': now, 'state': state, 'details': details,
                      'audit_records_retained': db.execute('SELECT count(*) FROM audit_records').fetchone()[0],
                      'alerts_recorded': db.execute('SELECT count(*) FROM alerts').fetchone()[0]}
            self._publish('health.json', json.dumps(result, indent=2) + '\n')
            # Clear stale server metrics on failure rather than leaving healthy
            # values in a textfile collector. Consumers must also check timestamp.
            self._publish('metrics.prom', metrics + f'agentteam_observer_ready {int(state == "healthy")}\nagentteam_observer_sample_timestamp_seconds {now}\n')
            return result
