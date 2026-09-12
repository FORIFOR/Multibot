"""ID and time helpers. The runtime, never the model, decides ids and timestamps."""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    """Time-ordered, collision-resistant id: <prefix>_<ms hex><random>."""
    ms = int(time.time() * 1000)
    return f"{prefix}_{ms:011x}{secrets.token_hex(4)}"
