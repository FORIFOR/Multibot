"""High-entropy access keys for self-hosted installations; only their digests are stored."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


Role = Literal['admin', 'operator', 'viewer', 'auditor']


class OIDCConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issuer: str
    jwks_url: str
    audience: str = Field(min_length=1, max_length=256)
    client_id: str = Field(min_length=1, max_length=256)
    group_roles: dict[str, Role] = Field(min_length=1, max_length=100)
    max_token_seconds: int = Field(default=300, ge=30, le=900)
    disabled_subjects: list[str] = Field(default_factory=list, max_length=10000)

    @model_validator(mode='after')
    def validate_oidc(self):
        for value in (self.issuer, self.jwks_url):
            u = urlsplit(value)
            if not u.hostname or u.username or u.password or u.fragment or u.query:
                raise ValueError('OIDC endpoints require explicit trusted URLs without credentials or query')
            if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1')):
                raise ValueError('OIDC requires HTTPS outside loopback')
        if self.issuer.endswith('/') or self.audience == self.client_id:
            raise ValueError('Use an exact issuer and a separate API audience, not the browser client ID')
        return self


class Account(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: str = Field(pattern=r'^[a-zA-Z0-9_.@-]{1,128}$')
    role: Role
    token_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    disabled: bool = False


class AccessConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    organization: str = Field(min_length=1, max_length=128)
    public_origin: str
    session_seconds: int = Field(default=3600, ge=60, le=86400)
    max_active_runs: int = Field(default=2, ge=1, le=32)
    max_pending_runs: int = Field(default=20, ge=1, le=1000)
    max_request_bytes: int = Field(default=2_000_000, ge=1024, le=20_000_000)
    users: list[Account] = Field(min_length=1)
    oidc: OIDCConfig | None = None

    @model_validator(mode='after')
    def validate_config(self):
        u = urlsplit(self.public_origin)
        if u.username or u.password or u.query or u.fragment or u.path or not u.hostname:
            raise ValueError('public_origin must contain only scheme and host (no trailing slash)')
        if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('HTTPS is required outside loopback')
        if len({a.subject for a in self.users}) != len(self.users) or len({a.token_sha256 for a in self.users}) != len(self.users):
            raise ValueError('duplicate subject or credential')
        if any(a.subject.startswith('oidc-') for a in self.users):
            raise ValueError('oidc- subjects are reserved for verified SSO identities')
        if self.max_pending_runs < self.max_active_runs:
            raise ValueError('max_pending_runs must be at least max_active_runs')
        if not any(a.role == 'admin' and not a.disabled for a in self.users):
            raise ValueError('at least one enabled administrator is required')
        return self


def read_access_config(path: Path) -> AccessConfig:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('access configuration must be a regular private file (chmod 600)')
    return AccessConfig.model_validate_json(path.read_text())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_key(path: Path, subject: str, role: str, credential_path: Path, *, organization: str | None = None,
              public_origin: str | None = None, revoke: bool = False) -> None:
    """Create/rotate one credential, or revoke it; plaintext is written only to a new private file."""
    path, credential_path = path.expanduser().resolve(), credential_path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / (path.name + '.lock')).open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            cfg = read_access_config(path)
            users = [a for a in cfg.users if a.subject != subject]
        elif revoke:
            raise ValueError('access configuration does not exist')
        else:
            cfg = None
            users = []
        token = secrets.token_urlsafe(32)
        if revoke:
            old = next((a for a in cfg.users if a.subject == subject), None)
            if old is None:
                raise ValueError('unknown subject')
            users.append(old.model_copy(update={'disabled': True}))
        else:
            users.append(Account(subject=subject, role=role, token_sha256=digest(token)))
        data = cfg.model_dump() if cfg else {'organization': organization, 'public_origin': public_origin}
        updated = AccessConfig.model_validate({**data, 'users': users})
        if not revoke:
            credential_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(token + '\n')
        tmp = path.parent / (path.name + '.' + secrets.token_hex(8) + '.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(updated.model_dump_json(indent=2) + '\n')
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
