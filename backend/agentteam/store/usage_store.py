"""Durable, per-principal admission throttles, not billing or quality counters.

Reserve before creating/forking/resuming, under the application's admission lock.
A failed attempt after reservation still counts: a crash must not reset a user's
allowance. Idempotency receipts are checked before reservation. Grants/deletion
do not reset the rolling window. Only opaque subject/run IDs and time are kept.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from ..ids import new_id
from .job_store import JobStore

WINDOW_SECONDS = 24 * 60 * 60


class AdmissionLimit(ValueError):
    def __init__(self, code: str, retry_after: int):
        super().__init__(code)
        self.code, self.retry_after = code, retry_after


class UsageStore(JobStore):
    @staticmethod
    async def _read(conn, subject, now):
        cursor = await conn.execute(
            'SELECT recorded_at FROM subject_admissions WHERE subject=? AND recorded_at>? ORDER BY recorded_at',
            (subject, now - WINDOW_SECONDS))
        times = [row[0] for row in await cursor.fetchall()]
        cursor = await conn.execute(
            "SELECT count(DISTINCT a.run_id) FROM subject_admissions a JOIN execution_jobs j ON j.run_id=a.run_id "
            "WHERE a.subject=? AND j.state IN ('queued','leased')", (subject,))
        pending = (await cursor.fetchone())[0]
        return times, pending

    async def summary(self, subject, daily_limit, pending_limit):
        now = time.time()
        async with self.transaction() as conn:
            await self._prune(conn, now)
            times, pending = await self._read(conn, subject, now)
        # When a limit is lowered, enough old reservations must expire, not just the first.
        next_at = times[len(times) - daily_limit] + WINDOW_SECONDS if len(times) >= daily_limit else None
        return {'limited': True, 'requests_last_24h': len(times), 'max_requests_per_24h': daily_limit,
                'requests_remaining': max(0, daily_limit - len(times)), 'pending_runs': pending,
                'max_pending_runs': pending_limit,
                'next_request_at': datetime.fromtimestamp(next_at, timezone.utc).isoformat() if next_at else None}

    @staticmethod
    async def _prune(conn, now):
        # Keep old rows only while their execution is active; pruning also runs at startup.
        await conn.execute(
            "DELETE FROM subject_admissions WHERE recorded_at<=? AND NOT EXISTS "
            "(SELECT 1 FROM execution_jobs j WHERE j.run_id=subject_admissions.run_id AND j.state IN ('queued','leased'))",
            (now - WINDOW_SECONDS,))

    async def prune(self):
        async with self.transaction() as conn:
            await self._prune(conn, time.time())

    async def reserve(self, subject, daily_limit, pending_limit, *, require_execution=True):
        now, admission_id = time.time(), new_id('admission')
        async with self.transaction() as conn:
            await self._prune(conn, now)
            times, pending = await self._read(conn, subject, now)
            if len(times) >= daily_limit:
                retry = max(1, math.ceil(times[len(times) - daily_limit] + WINDOW_SECONDS - now))
                raise AdmissionLimit('subject_daily_limit', retry)
            if require_execution and pending >= pending_limit:
                raise AdmissionLimit('subject_pending_limit', 30)
            await conn.execute('INSERT INTO subject_admissions(admission_id,subject,recorded_at) VALUES(?,?,?)',
                               (admission_id, subject, now))
        return admission_id

    async def bind(self, admission_id, run_id):
        if admission_id is not None:
            await self.db.execute('UPDATE subject_admissions SET run_id=? WHERE admission_id=?', (run_id, admission_id))
