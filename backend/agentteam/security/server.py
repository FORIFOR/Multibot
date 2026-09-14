"""Deny-by-default API authorization for one organization's isolated deployment."""
from __future__ import annotations

import json
import logging
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request

from .accounts import Account, digest, read_access_config
from .oidc import OIDCVerifier, Principal

COOKIE = 'agentteam_session'
PUBLIC = {'/api/health/live', '/api/auth/status', '/api/auth/login'}
READ_ROUTES = {'/api/health', '/api/config', '/api/runs', '/api/approvals', '/api/auth/me'}
AUDITOR_ROUTES = {'/api/auth/me', '/api/admin/ready', '/api/admin/metrics', '/api/admin/audit', '/api/admin/jobs'}
WRITE_ROUTES = {'/api/runs', '/api/runs/{run_id}/cancel', '/api/runs/{run_id}/resume',
                '/api/runs/{run_id}/fork', '/api/runs/{run_id}/instructions',
                '/api/approvals/{approval_id}/resolve', '/api/auth/logout'}
RUN_READ_ROUTES = {'/api/runs/{run_id}', '/api/runs/{run_id}/events', '/api/runs/{run_id}/chat',
                   '/api/runs/{run_id}/timeline', '/api/runs/{run_id}/stream', '/api/runs/{run_id}/export',
                   '/api/artifacts/{run_id}/{artifact_id}/versions/{revision}',
                   '/api/artifacts/{run_id}/{artifact_id}/versions/{revision}/raw'}


class ServerAccess:
    def __init__(self, service, path: Path | None):
        self.svc, self.path = service, path
        self.config = read_access_config(path) if path else None
        self.initial_organization = self.config.organization if self.config else None
        self.initial_origin = self.config.public_origin if self.config else None
        self.login_attempts: dict[str, list[float]] = {}
        self.oidc = OIDCVerifier(self.config.oidc) if self.config and self.config.oidc else None

    @property
    def enabled(self):
        return self.path is not None

    def reload(self):
        if self.path:
            try:
                cfg = read_access_config(self.path)
                if cfg.organization != self.initial_organization or cfg.public_origin != self.initial_origin:
                    raise ValueError('organization/origin changes require a separate deployment or restart')
                if cfg.oidc != self.config.oidc:
                    self.oidc = OIDCVerifier(cfg.oidc) if cfg.oidc else None
                self.config = cfg
            except (OSError, ValueError):
                raise HTTPException(503, 'access configuration unavailable')

    def by_token(self, token: str) -> Account | None:
        if len(token) < 32 or len(token) > 256:
            return None
        hashed = digest(token)
        return next((a for a in self.config.users if not a.disabled and secrets.compare_digest(a.token_sha256, hashed)), None)

    async def authenticate(self, request: Request) -> Principal | None:
        self.reload()
        if not self.enabled:
            return None
        auth = request.headers.get('authorization')
        if auth is not None:
            scheme, _, token = auth.partition(' ')
            if scheme.lower() != 'bearer':
                return None
            account = self.by_token(token)
            if account:
                return Principal(account.subject, account.role)
            return await self._oidc_principal(token)
        forwarded = request.headers.get('x-forwarded-access-token')
        if forwarded is not None:
            # Signed access tokens are verified even on direct backend requests.
            # Identity/email/role forwarding headers have no authority.
            return await self._oidc_principal(forwarded)
        token = request.cookies.get(COOKIE, '')
        if not token:
            return None
        row = await self.svc.db.fetchone('SELECT token_digest FROM auth_sessions WHERE session_digest=? AND expires_at>?',
                                        (digest(token), time.time()))
        account = next((a for a in self.config.users if not a.disabled and row and a.token_sha256 == row['token_digest']), None)
        return Principal(account.subject, account.role) if account else None

    async def _oidc_principal(self, token: str) -> Principal | None:
        if await self.svc.db.fetchone('SELECT token_digest FROM oidc_revoked_tokens WHERE token_digest=? AND expires_at>?',
                                      (digest(token), time.time())):
            return None
        p = await self.oidc.authenticate(token) if self.oidc else None
        boundary = await self.svc.db.fetchone("SELECT value FROM deployment_metadata WHERE key='oidc_valid_after'") if p else None
        if p and boundary and p.issued_at <= float(boundary['value']):
            return None
        if p:
            await self.svc.db.execute('INSERT INTO oidc_identities(subject,issuer,display_name,last_seen) VALUES(?,?,?,?) '
                'ON CONFLICT(subject) DO UPDATE SET display_name=excluded.display_name,last_seen=excluded.last_seen',
                (p.subject, self.config.oidc.issuer, p.display_name, time.time()))
        return p

    async def logout_oidc(self, request: Request):
        p = self.principal(request)
        if p and p.source == 'oidc':
            auth = request.headers.get('authorization', '')
            token = auth.partition(' ')[2] if auth else request.headers.get('x-forwarded-access-token', '')
            await self.svc.db.execute('DELETE FROM oidc_revoked_tokens WHERE expires_at<=?', (time.time(),))
            await self.svc.db.execute('INSERT OR IGNORE INTO oidc_revoked_tokens(token_digest,expires_at) VALUES(?,?)', (digest(token), p.expires_at))

    def principal(self, request: Request) -> Principal | None:
        return getattr(request.state, 'principal', None)

    def admin(self, request: Request) -> bool:
        return not self.enabled or self.principal(request).role == 'admin'

    async def can_access(self, request: Request, run_id: str, *, write=False) -> bool:
        if self.admin(request):
            return True
        p = self.principal(request)
        if p.role == 'auditor':
            return False
        if write and p.role == 'viewer':
            return False
        row = await self.svc.db.fetchone('SELECT permission FROM run_access WHERE run_id=? AND subject=?', (run_id, p.subject))
        return bool(row and (not write or row['permission'] == 'write'))

    async def grant_creator(self, request: Request, run_id: str):
        if self.enabled:
            await self.svc.db.execute('INSERT INTO run_access(run_id,subject,permission) VALUES(?,?,?)',
                                      (run_id, self.principal(request).subject, 'write'))

    async def audit(self, request: Request, outcome: str, status: int, details: dict | None = None):
        if not self.enabled:
            return
        p = self.principal(request)
        route = request.scope.get('route')
        await self.svc.db.execute('INSERT INTO audit_log(recorded_at,request_id,subject,method,route,run_id,outcome,status,details_json) '
                                  'VALUES(?,?,?,?,?,?,?,?,?)',
                                  (time.time(), request.state.request_id, p.subject if p else None, request.method,
                                   route.path if route else '/unmatched', request.path_params.get('run_id'), outcome, status,
                                   json.dumps(details or dict(request.path_params), ensure_ascii=False)))
        logging.getLogger('uvicorn.error').info(json.dumps({'event': 'access_audit', 'request_id': request.state.request_id,
            'subject': p.subject if p else None, 'method': request.method, 'route': route.path if route else '/unmatched',
            'outcome': outcome, 'status': status}, ensure_ascii=False))

    async def authorize(self, request: Request):
        if not request.url.path.startswith('/api/'):
            return
        if request.url.path in PUBLIC:
            return
        if not self.enabled:
            return
        request.state.principal = await self.authenticate(request)
        p = self.principal(request)
        async def reject(status, detail):
            await self.audit(request, 'denied', status)
            raise HTTPException(status, detail)
        if p is None:
            await reject(401, 'authentication required')
        route = request.scope['route'].path
        read = request.method in ('GET', 'HEAD')
        if not read and not request.headers.get('authorization'):
            if request.headers.get('origin') != self.config.public_origin:
                await reject(403, 'same-origin request required')
        if p.role == 'auditor':
            if not (route in AUDITOR_ROUTES if read else route == '/api/auth/logout'):
                await reject(403, 'insufficient role')
        elif p.role != 'admin':
            allowed = route in READ_ROUTES | RUN_READ_ROUTES if read else route in WRITE_ROUTES and (p.role == 'operator' or route == '/api/auth/logout')
            if not allowed:
                await reject(403, 'insufficient role')
        run_id = request.path_params.get('run_id')
        if 'approval_id' in request.path_params:
            ap = await self.svc.runs.get_approval(request.path_params['approval_id'])
            if ap is None:
                await reject(404, 'approval not found')
            run_id = ap.run_id
        if run_id and not await self.can_access(request, run_id, write=not read):
            await reject(404, 'run not found')
        await self.audit(request, 'authorized', 0)

    async def login(self, request: Request, token: str):
        self.reload()
        if not self.enabled:
            raise HTTPException(404)
        if request.headers.get('origin') != self.config.public_origin:
            raise HTTPException(403, 'same-origin request required')
        # One deployment-wide bound also prevents unbounded attacker-controlled IP buckets.
        now = time.time()
        recent = [t for t in self.login_attempts.get('all', []) if now - t < 60]
        self.login_attempts['all'] = recent
        if len(recent) >= 30:
            raise HTTPException(429, 'too many login attempts', headers={'Retry-After': '60'})
        recent.append(now)
        account = self.by_token(token)
        request.state.principal = account
        if account is None:
            await self.audit(request, 'login_denied', 401)
            raise HTTPException(401, 'invalid access key')
        session = secrets.token_urlsafe(32)
        await self.svc.db.execute('DELETE FROM auth_sessions WHERE expires_at<=?', (now,))
        await self.svc.db.execute('INSERT INTO auth_sessions(session_digest,token_digest,expires_at) VALUES(?,?,?)',
                                  (digest(session), account.token_sha256, now + self.config.session_seconds))
        await self.audit(request, 'login', 200)
        return account, session
