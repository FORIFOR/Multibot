"""Recheck retained v61 bytes/provenance; does not grade semantics or call a model."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = HERE.parents[3]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify():
    fingerprint = json.loads((HERE / 'fingerprint.json').read_text())
    review = json.loads((HERE / 'review.json').read_text())
    source = (HERE / 'PRODUCTION_PLAN.md').read_bytes()
    sources = {
        'PRODUCTION_PLAN.md': ('PRODUCTION_PLAN.md', 'docs/PRODUCTION_PLAN.md'),
        'README.md': ('operations-README.md', 'docs/evidence/operations-2026-09-14/README.md'),
    }
    for original, (snapshot, git_path) in sources.items():
        raw = (HERE / snapshot).read_bytes()
        assert digest(raw) == fingerprint['source_sha256'][original], snapshot
        committed = subprocess.check_output(
            ['git', 'show', f"{fingerprint['commit']}:{git_path}"], cwd=REPO)
        assert raw == committed, f'{snapshot}: fixed checkout mismatch'
    request = (HERE / 'request.txt').read_bytes()
    assert digest(request) == fingerprint['goal_sha256']
    changed = subprocess.check_output(
        ['git', 'diff', '--name-only', review['implementation_change_commit'],
         fingerprint['commit']], cwd=REPO, text=True).splitlines()
    assert changed and all(path.startswith('docs/') for path in changed)
    rows = []
    for line in source.decode().splitlines():
        if line.startswith('| ') and not line.startswith(('| Area', '| ---')):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            if len(cells) == 3:
                rows.append(cells)
    assert len(rows) == 8
    files = sorted(EVIDENCE.glob('*-draft-r1.json'))
    assert len(files) == 10
    recorded = {item['file']: item for item in review['artifacts']}
    actual_hashes = set()
    for path in files:
        raw = path.read_bytes()
        actual_hashes.add(digest(raw))
        assert digest(raw) == recorded[path.name]['sha256']
        assert len(raw) == recorded[path.name]['bytes']
        doc = json.loads(raw)
        assert doc['production_ready'] is False
        assert len(doc['areas']) == 8
        for output, (area, _, remaining) in zip(doc['areas'], rows):
            assert output['area'] == area
            assert output['source_file'] == 'PRODUCTION_PLAN.md'
            assert output['evidence_quote'] == remaining
            # Each entire Japanese field was supplied in the fixed request.
            for field in ('implemented', 'remaining'):
                assert output[field] in request.decode()
        business = doc['areas'][6]['implemented']
        assert review['finding']['source_text'] in rows[6][1]
        assert review['finding']['output_text'] in business
        assert business in request.decode()
    assert len(actual_hashes) == 1
    attempts = json.loads((EVIDENCE / 'attempts.json').read_text())
    assert len(attempts) == 10
    assert sum(a['result']['status'] == 'completed' for a in attempts) == 9
    assert sum(a['result']['status'] == 'interrupted' for a in attempts) == 1
    assert sum(a['result']['review_submissions'] for a in attempts) == 9
    assert review['accepted_runs'] == 0 and review['production_ready'] is False
    return {
        'status': 'PASS',
        'method': 'Retained-byte, exact-quote, example-origin and Git provenance checks only',
        'source_hashes_verified': 2, 'request_hash_verified': True,
        'artifact_hashes_verified': 10, 'distinct_artifact_hashes': len(actual_hashes),
        'exact_row_quotes_verified': 80, 'supplied_japanese_fields_verified': 160,
        'recorded_reviews': 9, 'semantic_finding': 'V61-SEM-01 remains FAIL',
        'accepted_runs': 0, 'production_ready': False,
    }


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
