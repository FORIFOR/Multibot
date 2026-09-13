"""Validate API access tokens. Browser OAuth/PKCE is delegated to OAuth2 Proxy."""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

import jwt
from fastapi import HTTPException

from .accounts import OIDCConfig, Role, digest


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role
    source: str = 'key'
    display_name: str = ''
    expires_at: float = 0
    issued_at: float = 0


class OIDCVerifier:
    def __init__(self, config: OIDCConfig):
        self.config = config
        self.client = jwt.PyJWKClient(config.jwks_url, timeout=2, lifespan=60, cache_keys=False)
        self.lock = threading.Lock()
        self.last_unknown_refresh = 0.0

    def _decode(self, token: str) -> Principal | None:
        if len(token) > 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str) or not 1 <= len(header['kid']) <= 256:
                return None
            # Use only the configured JWKS URL, never URLs from JWT headers. A lock
            # coalesces refreshes; unknown kids cannot force unbounded network calls.
            with self.lock:
                keys = self.client.get_signing_keys()
                key = next((k for k in keys if k.key_id == header['kid']), None)
                if key is None and time.monotonic() - self.last_unknown_refresh >= 5:
                    self.last_unknown_refresh = time.monotonic()
                    keys = self.client.get_signing_keys(refresh=True)
                    key = next((k for k in keys if k.key_id == header['kid']), None)
                if key is None:
                    return None
            claims = jwt.decode(token, key.key, algorithms=['RS256'], issuer=self.config.issuer,
                                audience=self.config.audience, options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'azp']})
            if claims['azp'] != self.config.client_id or not claims['sub']:
                return None
            if claims['exp'] - claims['iat'] > self.config.max_token_seconds or time.time() - claims['iat'] > self.config.max_token_seconds:
                return None
            groups = claims.get('groups', [])
            if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
                return None
            roles = {self.config.group_roles[g] for g in groups if g in self.config.group_roles}
            role = next((r for r in ('admin', 'operator', 'viewer', 'auditor') if r in roles), None)
            subject = 'oidc-' + digest(self.config.issuer + '\x00' + claims['sub'])
            if role is None or subject in self.config.disabled_subjects:
                return None
            display = claims.get('preferred_username', '')
            return Principal(subject, role, 'oidc', display[:128] if isinstance(display, str) else '', float(claims['exp']), float(claims['iat']))
        except jwt.PyJWKClientConnectionError:
            raise HTTPException(503, 'identity verification unavailable') from None
        except (jwt.PyJWTError, ValueError, TypeError):
            return None

    async def authenticate(self, token: str) -> Principal | None:
        return await asyncio.to_thread(self._decode, token)
