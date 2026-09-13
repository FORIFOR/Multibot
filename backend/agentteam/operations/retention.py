"""Offline, explicit run-data deletion with resumable cleanup and no backup-erasure claim."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime, time, timezone
from pathlib import Path

from .backup import exclusive_data_dir

JOURNAL = """CREATE TABLE IF NOT EXISTS purge_journal (
run_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL, finished_at TEXT, state TEXT NOT NULL,
actor TEXT NOT NULL, details_json TEXT NOT NULL)"""
RUN_TABLES = ('events', 'tasks', 'messages', 'artifacts', 'approvals', 'checkpoints', 'run_access', 'execution_jobs', 'request_receipts')


def _root(source: Path):
    root = source.resolve()
    if not (root / 'agentteam.sqlite').is_file() or (root / 'agentteam.sqlite').is_symlink():
        raise ValueError('source is not an Agent Team data directory')
    if (root / 'runs').is_symlink():
        raise ValueError('run storage must not be a symlink')
    return root


def _target(root, run_id):
    if not re.fullmatch(r'run_[A-Za-z0-9_-]+', run_id):
        raise ValueError('unsafe run identifier')
    target = root / 'runs' / run_id
    if target.is_symlink():
        raise ValueError('run directory must not be a symlink')
    return target


def plan(source: Path, *, run_ids=(), before: str | None = None):
    root = _root(source)
    if bool(run_ids) == bool(before):
        raise ValueError('choose explicit run IDs or an exclusive UTC date cutoff')
    with closing(sqlite3.connect(f'file:{root / "agentteam.sqlite"}?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        if before:
            cutoff = datetime.combine(date.fromisoformat(before), time.min, tzinfo=timezone.utc).isoformat()
            selected = list(conn.execute("SELECT run_id,status,finished_at FROM runs WHERE status IN ('completed','partial','failed','cancelled') "
                'AND finished_at IS NOT NULL AND finished_at<? ORDER BY finished_at LIMIT 1000', (cutoff,)))
        else:
            if len(set(run_ids)) > 1000:
                raise ValueError('purge at most 1000 explicit runs per operation')
            selected = []
            for run_id in dict.fromkeys(run_ids):
                _target(root, run_id)
                row = conn.execute('SELECT run_id,status,finished_at FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if row is None:
                    raise ValueError('unknown run identifier')
                selected.append(row)
        if any(r['status'] in ('running', 'planning', 'queued') for r in selected):
            raise ValueError('interrupt or cancel active/queued work before deleting it')
        ids = [r['run_id'] for r in selected]
        files, size = 0, 0
        for run_id in ids:
            target = _target(root, run_id)
            if not target.exists():
                continue
            for directory, dirs, names in os.walk(target, followlinks=False):
                for name in [*names, *(d for d in dirs if (Path(directory) / d).is_symlink())]:
                    p = Path(directory) / name
                    files += 1; size += p.lstat().st_size
        children = [r[0] for run_id in ids for r in conn.execute('SELECT run_id FROM runs WHERE parent_run_id=?', (run_id,)) if r[0] not in ids]
    return {'source': str(root), 'run_ids': ids, 'file_count': files, 'file_bytes': size,
            'retained_fork_run_ids': children, 'security_audit_metadata_retained': True, 'backups_and_provider_copies_deleted': False}


def purge(source: Path, *, run_ids=(), before=None, resume=False):
    root = _root(source)
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError('this platform cannot safely remove untrusted workspace trees')
    with exclusive_data_dir(root), closing(sqlite3.connect(root / 'agentteam.sqlite', isolation_level=None)) as conn:
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.execute('PRAGMA secure_delete=ON')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute(JOURNAL)
        pending = [r[0] for r in conn.execute("SELECT run_id FROM purge_journal WHERE state='pending'")]
        if pending and not resume:
            raise ValueError('unfinished deletion exists; resume it first')
        if resume:
            if run_ids or before:
                raise ValueError('resume cannot select additional data')
            selection = {'source': str(root), 'run_ids': pending, 'resumed': True,
                         'security_audit_metadata_retained': True, 'backups_and_provider_copies_deleted': False}
        else:
            selection = plan(root, run_ids=run_ids, before=before)
        ids = selection['run_ids']
        for run_id in ids:
            _target(root, run_id)
        if shutil.disk_usage(root).free < (root / 'agentteam.sqlite').stat().st_size * 2 + 10_000_000:
            raise RuntimeError('insufficient space to compact SQLite after deletion')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.execute('BEGIN IMMEDIATE')
        try:
            for run_id in ids:
                conn.execute("INSERT INTO purge_journal(run_id,requested_at,state,actor,details_json) VALUES(?,?,'pending',?,?) "
                    "ON CONFLICT(run_id) DO UPDATE SET state='pending',finished_at=NULL",
                    (run_id, datetime.now(timezone.utc).isoformat(), 'os-uid:' + str(os.getuid()), json.dumps({'scope': 'run data; audit metadata retained'})))
                if 'request_receipts' in tables:
                    conn.execute('CREATE TABLE IF NOT EXISTS deleted_request_receipts (scope_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, deleted_at TEXT NOT NULL)')
                    conn.execute('INSERT OR IGNORE INTO deleted_request_receipts(scope_key,request_hash,deleted_at) '
                                 'SELECT scope_key,request_hash,? FROM request_receipts WHERE run_id=?', (datetime.now(timezone.utc).isoformat(), run_id))
                for table in RUN_TABLES:
                    if table in tables:
                        conn.execute(f'DELETE FROM {table} WHERE run_id=?', (run_id,))
                if 'audit_log' in tables:
                    conn.execute("UPDATE audit_log SET details_json='{}' WHERE run_id=?", (run_id,))
                conn.execute('DELETE FROM runs WHERE run_id=?', (run_id,))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        # Payload rows are already unavailable to the API. If filesystem cleanup
        # fails, the durable journal remains pending and startup refuses traffic.
        for run_id in ids:
            target = _target(root, run_id)
            if target.exists():
                shutil.rmtree(target)
        conn.execute('VACUUM')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('database integrity check failed after deletion')
        if conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] != 0:
            raise RuntimeError('SQLite checkpoint could not complete')
        conn.execute('BEGIN IMMEDIATE')
        for run_id in ids:
            conn.execute("UPDATE purge_journal SET state='completed',finished_at=? WHERE run_id=?", (datetime.now(timezone.utc).isoformat(), run_id))
        conn.commit()
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return {**selection, 'completed': True, 'sqlite_compacted': True, 'physical_media_erasure_claimed': False}
