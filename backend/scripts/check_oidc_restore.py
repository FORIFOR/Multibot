"""Restore actual SSO staging data and reject a real token issued before restore.

Stop this staging API first. The actual IdP must remain reachable and the issued
browser access token must still be unexpired; no token is fabricated or modified.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.operations.backup import backup, restore


async def main(root):
    token = json.loads((root / 'issued-tokens.json').read_text())['forifor']['access_token']
    access = root / 'security/access.json'
    origin = json.loads(access.read_text())['public_origin']
    headers = {'Authorization': 'Bearer ' + token}
    source = AppService(root / 'data', access_file=access)
    app = create_app(source)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as c:
            before = (await c.get('/api/auth/me', headers=headers)).status_code
            assert before == 200, 'obtain a fresh real IdP token before this drill'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    snapshot, restored = root / ('sso-snapshot-' + stamp), root / ('sso-restored-' + stamp)
    backup(root / 'data', snapshot)
    result = restore(snapshot, restored)
    recovered = AppService(restored, access_file=access)
    app = create_app(recovered)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as c:
            after = (await c.get('/api/auth/me', headers=headers)).status_code
            assert after == 401
            admin = (root / 'forifor.key').read_text().strip()
            emergency = (await c.get('/api/auth/me', headers={'Authorization': 'Bearer ' + admin})).status_code
            assert emergency == 200
            artifact = await recovered.artifacts.get('run_1a09bfe4acdc8c36d5f', 'email.md')
            assert artifact.sha256 == '23ed248581fd6129b2f0146b10189defd71b71d8603b404174d8d085ed5e80ea'
    evidence = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'pre_restore_token_status': before,
                'same_token_after_restore_status': after, 'emergency_admin_status': emergency,
                'actual_artifact_sha256': artifact.sha256, **result}
    (root / 'oidc-restore.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


async def outage(root):
    token = json.loads((root / 'issued-tokens.json').read_text())['forifor']['access_token']
    # Timing precondition only. Trust and signature validation happen in the API.
    assert jwt.decode(token, options={'verify_signature': False})['exp'] > time.time() + 5
    access = root / 'security/access.json'
    config = json.loads(access.read_text())
    try:
        httpx.get(config['oidc']['jwks_url'], timeout=2).raise_for_status()
    except httpx.TransportError:
        pass
    else:
        raise AssertionError('stop the actual staging identity service first')
    app = create_app(AppService(root / 'data', access_file=access))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=config['public_origin']) as c:
            failed = (await c.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})).status_code
            admin = (root / 'forifor.key').read_text().strip()
            emergency = (await c.get('/api/auth/me', headers={'Authorization': 'Bearer ' + admin})).status_code
            assert failed == 503 and emergency == 200
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'real_idp_stopped': True,
              'uncached_jwks_token_status': failed, 'emergency_admin_status': emergency, 'fail_open': False}
    (root / 'oidc-outage.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--check-outage', action='store_true')
    args = p.parse_args()
    asyncio.run(outage(args.root) if args.check_outage else main(args.root))
