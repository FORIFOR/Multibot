"""Actual primary-site HTTPS, redirect and bounded-download checks; no fake server."""
import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentteam.runtime.webtools import web_fetch, MAX_BYTES


async def main(output):
    commit = '2a46e209f102f7cb094484aa24d099135e27cbc6'
    path = 'docs/PRODUCTION_PLAN.md'
    original = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT.parent)
    result = await web_fetch(f'https://raw.githubusercontent.com/FORIFOR/Multibot/{commit}/{path}', max_chars=50000)
    assert result['status'] == 200 and result['text'].encode() == original and not result['truncated']
    redirect = await web_fetch('http://docs.python.org/3/whatsnew/3.12.html', max_chars=500)
    assert redirect['status'] == 200 and redirect['url'].startswith('https://docs.python.org/')
    large = await web_fetch('https://www.python.org/ftp/python/3.12.12/Python-3.12.12.tgz', max_chars=16)
    assert large['status'] == 200 and large['body_limit_reached'] and large['bytes'] == MAX_BYTES
    record = {'recorded_at': datetime.now(timezone.utc).isoformat(),
              'checks': ['HTTPS certificate validation and original-host routing preserve exact published source bytes',
                         'actual HTTP-to-HTTPS redirect is followed through the same guarded transport',
                         'actual Python source archive download stops at the two-million-byte body limit'],
              'source_url': result['url'], 'source_sha256': hashlib.sha256(original).hexdigest(),
              'redirect': {k: v for k, v in redirect.items() if k != 'text'},
              'bounded_download': {k: v for k, v in large.items() if k != 'text'}, 'mocked_responses': False}
    output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'passed': len(record['checks']), 'evidence': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args().output))
