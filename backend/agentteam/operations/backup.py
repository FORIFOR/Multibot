"""Offline, integrity-checked snapshots. Never overwrite a live or existing installation."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def exclusive_data_dir(root: Path):
    with (root / '.service.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('stop the service before taking an offline snapshot')
        yield


def file_digest(path: Path):
    sha = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def _regular_files(root: Path):
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('snapshot cannot include symlinks')
        if p.is_dir():
            continue
        if not p.is_file():
            raise ValueError('snapshot cannot include special files')
        yield p


def backup(source: Path, destination: Path):
    source, destination = source.resolve(), destination.resolve()
    if not (source / 'agentteam.sqlite').is_file():
        raise ValueError('source is not an Agent Team data directory')
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('snapshot and data directories must be separate')
    if destination.exists():
        raise FileExistsError('snapshot destination must not exist')
    with exclusive_data_dir(source):
        destination.mkdir(parents=True, mode=0o700)
        try:
            with closing(sqlite3.connect(source / 'agentteam.sqlite')) as src, closing(sqlite3.connect(destination / 'agentteam.sqlite')) as dst:
                if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('source database failed integrity check')
                src.backup(dst)
            for p in _regular_files(source):
                rel = p.relative_to(source)
                if rel.parts[0] != 'runs' and str(rel) != 'agents.yaml':
                    continue
                target = destination / rel
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(p, target)
                target.chmod(0o600)
            manifest = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                        'files': {str(p.relative_to(destination)): file_digest(p) for p in _regular_files(destination)}}
            (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            for p in _regular_files(destination):
                p.chmod(0o600)
            verify(destination)
        except BaseException:
            # Only our newly-created incomplete directory is removed.
            shutil.rmtree(destination)
            raise
    return manifest


def verify(source: Path):
    source = source.resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('unsupported snapshot format')
    observed = {str(p.relative_to(source)): p for p in _regular_files(source) if p.name != 'manifest.json' or p.parent != source}
    if set(observed) != set(manifest['files']):
        raise ValueError('snapshot file inventory mismatch')
    for rel, expected in manifest['files'].items():
        if file_digest(observed[rel]) != expected:
            raise ValueError(f'snapshot checksum mismatch: {rel}')
    db = source / 'agentteam.sqlite'
    if not db.is_file():
        raise ValueError('snapshot database missing')
    with closing(sqlite3.connect(f'file:{db}?mode=ro&immutable=1', uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('snapshot database failed integrity check')
        for storage_path, expected in conn.execute('SELECT storage_path,sha256 FROM artifacts'):
            artifact = (source / 'runs' / storage_path).resolve()
            if not artifact.is_relative_to(source / 'runs') or not artifact.is_file() or file_digest(artifact) != expected:
                raise ValueError('published artifact does not match the database')
    return manifest


def restore(source: Path, destination: Path):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError('restore destination must not exist')
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('snapshot and restore directories must be separate')
    manifest = verify(source)
    destination.mkdir(parents=True, mode=0o700)
    try:
        for rel in manifest['files']:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source / rel, target)
            target.chmod(0o600)
            if file_digest(target) != manifest['files'][rel]:
                raise ValueError('source changed during restore')
        with closing(sqlite3.connect(destination / 'agentteam.sqlite')) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'auth_sessions' in tables:
                conn.execute('DELETE FROM auth_sessions')
            conn.execute('CREATE TABLE IF NOT EXISTS deployment_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            conn.execute("INSERT INTO deployment_metadata(key,value) VALUES('oidc_valid_after',?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(time.time()),))
            conn.commit()
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {'restored_files': len(manifest['files']), 'sessions_revoked': True, 'pre_restore_oidc_tokens_revoked': True}
