"""Check actual HTTP authorization and live key rotation; no fake service/provider."""
import argparse
import json
import sys
import time
import secrets
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentteam.security.accounts import issue_key


def check(root, base, operator_key_file=None):
    admin = {'Authorization': 'Bearer ' + (root / 'forifor.key').read_text().strip()}
    old = (operator_key_file or root / 'verification-operator.key').read_text().strip()
    operator = {'Authorization': 'Bearer ' + old}
    run_id = json.loads((ROOT.parent / 'docs/evidence/local-fixes-2026-09-14/thinking-interruption.json').read_text())['run_id']
    with httpx.Client(base_url=base, timeout=10) as c:
        results = {'anonymous_runs': c.get('/api/runs').status_code,
                   'admin_runs': c.get('/api/runs', headers=admin).status_code,
                   'operator_run': c.get('/api/runs/' + run_id, headers=operator).status_code,
                   'operator_artifact': c.get('/api/artifacts/' + run_id + '/email.md/versions/1/raw', headers=operator).status_code,
                   'operator_config_write': c.put('/api/limits', headers=operator, json={}).status_code}
        assert results == {'anonymous_runs': 401, 'admin_runs': 200, 'operator_run': 404, 'operator_artifact': 404, 'operator_config_write': 403}, results
        login = c.post('/api/auth/login', headers={'Origin': base}, json={'token': old})
        assert login.status_code == 200, login.text
        assert c.get('/api/auth/me').status_code == 200
        rotated = root / ('verification-operator-rotated-' + secrets.token_hex(4) + '.key')
        started = time.monotonic()
        issue_key(root / 'security/access.json', 'verification-operator', 'operator', rotated)
        # Host-to-VM bind mounts can briefly cache directory entries. Measure propagation explicitly.
        while True:
            results['revoked_cookie'] = c.get('/api/auth/me').status_code
            results['revoked_bearer'] = c.get('/api/auth/me', headers=operator).status_code
            if results['revoked_cookie'] == results['revoked_bearer'] == 401:
                break
            if time.monotonic() - started > 5:
                raise AssertionError('credential revocation did not propagate within five seconds')
            time.sleep(0.1)
        results['revocation_observed_seconds'] = round(time.monotonic() - started, 3)
        current = rotated.read_text().strip()
        assert c.get('/api/auth/me', headers={'Authorization': 'Bearer ' + current}).status_code == 200
        results['rotated_key'] = 200
        readiness = c.get('/api/admin/ready', headers=admin)
        assert readiness.status_code == 503  # saved profile has not been probed on this installation
        results['readiness'] = readiness.json()
        assert 'capability_check' in results['readiness']['configuration_problems']
        assert results['readiness']['sandbox_backend'] == 'none'  # no host Docker socket is exposed
        results['liveness'] = c.get('/api/health/live').status_code
        assert results['liveness'] == 200
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': results,
              'transport': 'real HTTP against secured service', 'model_inference': 'none; saved real run used for access checks'}
    (root / 'http-smoke.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--base', default='http://127.0.0.1:8796')
    p.add_argument('--operator-key-file', type=Path)
    args = p.parse_args()
    check(args.root.resolve(), args.base.rstrip('/'), args.operator_key_file)
