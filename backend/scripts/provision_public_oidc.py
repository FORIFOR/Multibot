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
import traceback

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'backend'))

ORIGIN = 'http://127.0.0.1:8798'
ISSUER = 'http://127.0.0.1:8801/realms/agentteam-verification'
CLIENT = 'agentteam-verification-login'


def private(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(value.encode() if isinstance(value, str) else value)


def prepare(root, report):
    report['stage'] = 'issue_emergency_key'
    from agentteam.security.accounts import issue_key

    access = root / 'security/access.json'
    issue_key(access, 'verification-emergency-admin', 'admin', root / 'emergency-admin.key',
              organization='FORIFOR/Multibot', public_origin=ORIGIN)
    report['stage'] = 'configure_oidc'
    config = json.loads(access.read_text())
    config['oidc'] = {'issuer': ISSUER, 'jwks_url': ISSUER + '/protocol/openid-connect/certs',
                      'audience': 'agentteam-api', 'client_id': CLIENT,
                      'group_roles': {'/agentteam-' + role: role for role in ('admin', 'operator', 'viewer')}}
    access.write_text(json.dumps(config) + '\n')
    report['stage'] = 'copy_recorded_profile_and_document'
    source = REPO / 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-run.json'
    profile = json.loads(source.read_text())['config_snapshot']['config_yaml']
    private(root / 'data/agents.yaml', profile)
    document = REPO / 'docs/PRODUCTION_PLAN.md'
    private(root / 'source.md', document.read_bytes())
    report['stage'] = 'prepare_technical_accounts'
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
    report['stage'] = 'record_provenance'
    provenance = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True, stderr=subprocess.PIPE).strip(),
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


def main(root):
    os.umask(0o077)
    created = False
    report = {'status': 'NOT_RUN', 'checks': [], 'model_execution': False, 'stage': 'github_runner_guard'}
    try:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            raise RuntimeError('this verification is restricted to disposable GitHub Actions runners')
        report['stage'] = 'create_private_root'
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        created = True
        # Persist before imports, credentials or evidence processing can fail.
        # Existing roots are never modified, even when reporting a failure.
        report['stage'] = 'initialize_report'
        private(root / 'report.json', json.dumps(report, indent=2) + '\n')
        prepare(root, report)
        report['stage'] = 'prepared'
        report['provision_status'] = 'PREPARED'
        (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        return 0
    except BaseException as error:
        report['status'] = 'FAILED'
        report['failure_stage'] = report.pop('stage')
        report['error_type'] = type(error).__name__
        if created:
            try:
                private(root / 'provision-failure.private.log', traceback.format_exc())
            except OSError:
                report['private_log_write_failed'] = True
            try:
                (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            except OSError:
                report['report_write_failed'] = True
        # No exception message, credential, traceback or subprocess output is
        # emitted. Failure before a new root exists is console-only and safe.
        print(json.dumps({'status': 'FAILED', 'failure_stage': report['failure_stage'], 'error_type': report['error_type']}))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=lambda p: Path(p).resolve(), required=True)
    raise SystemExit(main(parser.parse_args().root))
