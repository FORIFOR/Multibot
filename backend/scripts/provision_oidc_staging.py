"""Private local Keycloak/OAuth2 Proxy staging, using actual issued accounts and a recorded run.

This creates real credentials, not a token-signing stub. Keycloak start-dev,
loopback HTTP and the additional verifier callback are strictly for this drill.
"""
import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path

from provision_secure_smoke import provision


def private(path: Path, content: str | bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(content.encode() if isinstance(content, str) else content)


async def main(root: Path):
    origin = 'http://127.0.0.1:8800'
    issuer = 'http://127.0.0.1:8801/realms/agentteam'
    await provision(root, origin)
    config_file = root / 'security/access.json'
    config = json.loads(config_file.read_text())
    config['oidc'] = {'issuer': issuer, 'jwks_url': issuer + '/protocol/openid-connect/certs',
                      'audience': 'agentteam-api', 'client_id': 'agentteam-login',
                      'group_roles': {'/agentteam-admin': 'admin', '/agentteam-operator': 'operator', '/agentteam-viewer': 'viewer'}}
    config_file.write_text(json.dumps(config, indent=2) + '\n')
    (root / 'keycloak-import').mkdir(mode=0o700)
    credentials = {name: secrets.token_urlsafe(32) for name in ('forifor', 'verification-operator', 'verification-viewer', 'verification-unassigned')}
    private(root / 'staging-users.json', json.dumps(credentials))
    client_secret = secrets.token_urlsafe(32)
    private(root / 'client-secret', client_secret)
    private(root / 'cookie-secret', secrets.token_bytes(32))
    private(root / 'keycloak.env', 'KC_BOOTSTRAP_ADMIN_USERNAME=forifor\nKC_BOOTSTRAP_ADMIN_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    users = []
    for name, role in zip(credentials, ('admin', 'operator', 'viewer', None)):
        users.append({'username': name, 'enabled': True, 'email': name + '@localhost.local', 'emailVerified': True,
                      'firstName': 'Agent Team', 'lastName': name,
                      'credentials': [{'type': 'password', 'value': credentials[name], 'temporary': False}],
                      'groups': ['/agentteam-' + role] if role else []})
    client = {'clientId': 'agentteam-login', 'secret': client_secret, 'protocol': 'openid-connect',
              'enabled': True, 'publicClient': False, 'standardFlowEnabled': True, 'directAccessGrantsEnabled': False,
              'redirectUris': [origin + '/oauth2/callback', 'http://127.0.0.1:8802/callback'],
              'webOrigins': [origin], 'attributes': {'pkce.code.challenge.method': 'S256'},
              'protocolMappers': [
                  {'name': 'api-audience', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-audience-mapper',
                   'config': {'included.custom.audience': 'agentteam-api', 'id.token.claim': 'false', 'access.token.claim': 'true'}},
                  {'name': 'groups', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-group-membership-mapper',
                   'config': {'claim.name': 'groups', 'full.path': 'true', 'id.token.claim': 'true', 'access.token.claim': 'true'}}]}
    realm = {'realm': 'agentteam', 'enabled': True, 'sslRequired': 'none', 'accessTokenLifespan': 300,
             'registrationAllowed': False, 'groups': [{'name': 'agentteam-' + role} for role in ('admin', 'operator', 'viewer')],
             'users': users, 'clients': [client]}
    private(root / 'keycloak-import/agentteam-realm.json', json.dumps(realm))
    # This directory is mounted into Keycloak at /opt/keycloak/data/import.
    # The container runs with the calling UID so private credentials stay 0600.
    proxy = {
        'provider': 'oidc', 'client_id': 'agentteam-login', 'client_secret_file': str(root / 'client-secret'),
        'cookie_secret_file': str(root / 'cookie-secret'), 'oidc_issuer_url': issuer,
        'redirect_url': origin + '/oauth2/callback', 'http_address': '127.0.0.1:8800',
        'upstreams': ['http://127.0.0.1:8798/'], 'email_domains': ['localhost.local'],
        'scope': 'openid email profile', 'code_challenge_method': 'S256', 'insecure_oidc_skip_nonce': False,
        'pass_access_token': True, 'pass_authorization_header': False, 'pass_basic_auth': False,
        'pass_user_headers': False, 'skip_auth_strip_headers': True,
        'cookie_secure': False, 'cookie_httponly': True, 'cookie_samesite': 'lax',
        'cookie_refresh': '2m', 'cookie_expire': '1h',
        'backend_logout_url': issuer + '/protocol/openid-connect/logout?id_token_hint={id_token}',
        'request_logging': False, 'auth_logging': True, 'skip_provider_button': True,
        'api_routes': ['^/api/'],
        # Default standard error logs include full callback requests even with
        # request/auth logging disabled. Never retain OAuth codes or cookies.
        'standard_logging_format': '[{{.Timestamp}}] [{{.File}}] proxy event (details suppressed)',
        'auth_logging_format': '[{{.Timestamp}}] [{{.Status}}]',
    }
    private(root / 'oauth2-proxy.cfg', '\n'.join(k + ' = ' + json.dumps(v) for k, v in proxy.items()) + '\n')
    print(json.dumps({'root': str(root), 'issuer': issuer, 'origin': origin, 'accounts': list(credentials), 'passwords_logged': False}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    asyncio.run(main(p.parse_args().root.resolve()))
