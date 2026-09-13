"""Durable single-host execution admission; leases never authorize automatic replay.

Every transaction owns a separate SQLite connection, so scheduler writes cannot
accidentally join an admission transaction on the application's shared connection.
The service data-directory lock is the single-writer process boundary. This is not
a distributed queue and does not support a database on NFS/shared block storage.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import aiosqlite

from ..ids import new_id, now_iso


class JobConflict(ValueError):
    pass


class JobStore:
    def __init__(self, db):
        self.db = db

    @asynccontextmanager
    async def transaction(self):
        async with aiosqlite.connect(self.db.path, isolation_level=None) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute('PRAGMA foreign_keys=ON')
            await conn.execute('PRAGMA synchronous=FULL')
            await conn.execute('PRAGMA busy_timeout=5000')
            await conn.execute('BEGIN IMMEDIATE')
            try:
                yield conn
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise

    async def enqueue(self, run_id: str, *, resume: bool, max_pending: int, receipt=None):
        job_id, now = new_id('job'), now_iso()
        async with self.transaction() as conn:
            cursor = await conn.execute("SELECT count(*) FROM execution_jobs WHERE state IN ('queued','leased')")
            if (await cursor.fetchone())[0] >= max_pending:
                raise JobConflict('execution queue limit reached')
            cursor = await conn.execute('SELECT status FROM runs WHERE run_id=?', (run_id,))
            run = await cursor.fetchone()
            if run is None:
                raise KeyError(run_id)
            cursor = await conn.execute("SELECT job_id FROM execution_jobs WHERE run_id=? AND state IN ('queued','leased')", (run_id,))
            if await cursor.fetchone():
                raise JobConflict('run already queued or executing')
            if run['status'] in ('running', 'planning', 'completed', 'blocked'):
                raise JobConflict('run cannot be queued from its current status')
            await conn.execute("INSERT INTO execution_jobs(job_id,run_id,resume,state,created_at) VALUES(?,?,?,'queued',?)", (job_id, run_id, int(resume), now))
            await conn.execute("UPDATE runs SET status='queued',cancel_requested=0,finished_at=NULL WHERE run_id=?", (run_id,))
            if receipt:
                await self._save_receipt(conn, run_id, receipt)
        return await self.get(job_id)

    async def receipt(self, scope_key):
        row = await self.db.fetchone('SELECT * FROM request_receipts WHERE scope_key=?', (scope_key,))
        if row:
            return dict(row)
        deleted = await self.db.fetchone('SELECT request_hash FROM deleted_request_receipts WHERE scope_key=?', (scope_key,))
        return {**dict(deleted), 'deleted': True} if deleted else None

    async def save_receipt(self, run_id, receipt):
        if receipt:
            async with self.transaction() as conn:
                await self._save_receipt(conn, run_id, receipt)

    @staticmethod
    async def _save_receipt(conn, run_id, receipt):
        await conn.execute('INSERT INTO request_receipts(scope_key,request_hash,run_id,status,response_json,created_at) VALUES(?,?,?,?,?,?)',
                           (receipt['scope_key'], receipt['request_hash'], run_id, receipt['status'], receipt['response_json'], now_iso()))

    async def get(self, job_id):
        row = await self.db.fetchone('SELECT * FROM execution_jobs WHERE job_id=?', (job_id,))
        return dict(row) if row else None

    async def pending(self):
        return [dict(r) for r in await self.db.fetchall("SELECT * FROM execution_jobs WHERE state='queued' ORDER BY created_at,job_id")]

    async def claim(self, job_id, owner, lease_seconds=30):
        now = time.time()
        async with self.transaction() as conn:
            cursor = await conn.execute("UPDATE execution_jobs SET state='leased',owner=?,lease_until=?,started_at=? "
                "WHERE job_id=? AND state='queued' RETURNING *", (owner, now + lease_seconds, now_iso(), job_id))
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def renew(self, job_id, owner, lease_seconds=30):
        now = time.time()
        async with self.transaction() as conn:
            cursor = await conn.execute("UPDATE execution_jobs SET lease_until=? WHERE job_id=? AND state='leased' AND owner=? AND lease_until>? RETURNING job_id",
                                        (now + lease_seconds, job_id, owner, now))
            return await cursor.fetchone() is not None

    async def finish(self, job_id, owner, state, reason=None):
        if state not in ('finished', 'interrupted', 'cancelled'):
            raise ValueError('invalid delivery state')
        async with self.transaction() as conn:
            cursor = await conn.execute('UPDATE execution_jobs SET state=?,reason=?,finished_at=?,lease_until=NULL '
                "WHERE job_id=? AND owner=? AND state='leased' RETURNING job_id", (state, reason, now_iso(), job_id, owner))
            return await cursor.fetchone() is not None

    async def cancel_queued(self, run_id):
        async with self.transaction() as conn:
            cursor = await conn.execute("UPDATE execution_jobs SET state='cancelled',reason='cancelled before execution',finished_at=? "
                "WHERE run_id=? AND state='queued' RETURNING job_id", (now_iso(), run_id))
            cancelled = await cursor.fetchone() is not None
            if cancelled:
                await conn.execute("UPDATE runs SET status='cancelled',cancel_requested=1,finished_at=? WHERE run_id=?", (now_iso(), run_id))
            return cancelled

    async def recover(self):
        """Only after acquiring the exclusive service lock: old leased work is ambiguous."""
        async with self.transaction() as conn:
            cursor = await conn.execute("SELECT j.job_id,j.run_id,r.status FROM execution_jobs j JOIN runs r USING(run_id) WHERE j.state='leased'")
            abandoned = [dict(r) for r in await cursor.fetchall()]
            for row in abandoned:
                terminal = row['status'] in ('completed', 'partial', 'failed', 'cancelled')
                await conn.execute('UPDATE execution_jobs SET state=?,reason=?,finished_at=?,lease_until=NULL WHERE job_id=?',
                    ('finished' if terminal else 'interrupted', 'previous worker process exited; no automatic replay', now_iso(), row['job_id']))
                if not terminal:
                    await conn.execute("UPDATE runs SET status='interrupted',blocked_reason='worker process exited; inspect external effects before resume' WHERE run_id=?", (row['run_id'],))
        return abandoned
