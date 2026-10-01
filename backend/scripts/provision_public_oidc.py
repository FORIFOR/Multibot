"""Prepare private real-Keycloak verification on a disposable GitHub runner only.

No application, IdP or model starts here. Only an unchanged v61 configuration and
the actual PRODUCTION_PLAN document are reused; no historical business run is seeded.
Technical accounts have usernames/passwords/groups, no invented person or email.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'backend'))
from agentteam.security.accounts import issue_key

ORIGIN = 'http://127.0.0.1:8798'
ISSUER = 'http://127.0.0.1:8801/realms/agentteam-verification'
CLIENT = 'agentteam-verification-login'


def private(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(value.encode() if isinstance(value, str) else value)


def prepare(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('this verification is restricted to disposable GitHub Actions runners')
    os.umask(0o077)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    access = root / 'security/access.json'
    issue_key(access, 'oidc-verification-emergency-admin', 'admin', root / 'emergency-admin.key',
              organization='FORIFOR/Multibot', public_origin=ORIGIN)
    config = json.loads(access.read_text())
    config['oidc'] = {'issuer': ISSUER, 'jwks_url': ISSUER + '/protocol/openid-connect/certs',
                      'audience': 'agentteam-api', 'client_id': CLIENT,
                      'group_roles': {'/agentteam-' + role: role for role in ('admin', 'operator', 'viewer')}}
    access.write_text(json.dumps(config) + '\n')
    source = REPO / 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-run.json'
    profile = json.loads(source.read_text())['config_snapshot']['config_yaml']
    private(root / 'data/agents.yaml', profile)
    document = REPO / 'docs/PRODUCTION_PLAN.md'
    private(root / 'source.md', document.read_bytes())
    users = {f'verification-{role}': secrets.token_urlsafe(32) for role in ('admin', 'operator', 'viewer', 'unassigned')}
    private(root / 'staging-users.json', json.dumps(users))
    secret = secrets.token_urlsafe(32)
    private(root / 'client-secret', secret)
    private(root / 'keycloak.env', 'KC_BOOTSTRAP_ADMIN_USERNAME=verification-bootstrap-admin\n'
            'KC_BOOTSTRAP_ADMIN_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    realm = {'realm': 'agentteam-verification', 'enabled': True, 'sslRequired': 'none',
             'accessTokenLifespan': 300, 'registrationAllowed': False, 'verifyEmail': False,
             'loginWithEmailAllowed': False, 'resetPasswordAllowed': False,
             'groups': [{'name': 'agentteam-' + role} for role in ('admin', 'operator', 'viewer')],
             'users': [{'username': name, 'enabled': True, 'requiredActions': [],
                        'credentials': [{'type': 'password', 'value': password, 'temporary': False}],
                        'groups': ['/agentteam-' + name.removeprefix('verification-')] if name != 'verification-unassigned' else []}
                       for name, password in users.items()],
             'clients': [{'clientId': CLIENT, 'secret': secret, 'protocol': 'openid-connect', 'enabled': True,
                          'publicClient': False, 'standardFlowEnabled': True, 'directAccessGrantsEnabled': False,
                          'redirectUris': ['http://127.0.0.1:8802/callback'], 'webOrigins': [],
                          'defaultClientScopes': ['profile'], 'optionalClientScopes': [],
                          'attributes': {'pkce.code.challenge.method': 'S256'},
                          'protocolMappers': [
                              {'name': 'api-audience', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-audience-mapper',
                               'config': {'included.custom.audience': 'agentteam-api', 'id.token.claim': 'false', 'access.token.claim': 'true'}},
                              {'name': 'groups', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-group-membership-mapper',
                               'config': {'claim.name': 'groups', 'full.path': 'true', 'id.token.claim': 'true', 'access.token.claim': 'true'}}]}]}
    private(root / 'keycloak-import/agentteam-verification-realm.json', json.dumps(realm))
    provenance = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                  'pyjwt_version': version('PyJWT'), 'origin': ORIGIN, 'issuer': ISSUER, 'client_id': CLIENT,
                  'profile_source': str(source.relative_to(REPO)), 'profile_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
                  'document_source': str(document.relative_to(REPO)), 'document_sha256': hashlib.sha256(document.read_bytes()).hexdigest(),
                  'verification_files_sha256': {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (Path(__file__), REPO / 'frontend/scripts/public-oidc.mjs', REPO / '.github/workflows/public-oidc.yml')},
                  'historical_probe_is_not_current_model_verification': True, 'model_execution': False,
                  'scope': 'real authorization-code/PKCE token acquisition and API JWT/JWKS verification',
                  'not_verified': ['OAuth2 Proxy', 'public TLS', 'MFA', 'registration', 'account recovery', 'business quality', 'human acceptance']}
    private(root / 'provenance.json', json.dumps(provenance, indent=2) + '\n')
    private(root / 'report.json', json.dumps({'status': 'NOT_RUN', 'checks': [], 'model_execution': False}) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=lambda p: Path(p).resolve(), required=True)
    prepare(parser.parse_args().root)
