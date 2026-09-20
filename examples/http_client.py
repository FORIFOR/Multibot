"""Small stdlib HTTP example, not a stable SDK. Never automatically repeats mutations.

Read a run: python examples/http_client.py --url http://127.0.0.1:8787 --run-id RUN_ID
Save selected files: add --save chosen.zip (fails if the destination already exists).
Creation/adoption methods below are explicit caller actions; read docs/quality/integration.md.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import zipfile


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward credentials or repeat a command at another URL.


class AgentTeamHTTP:
    def __init__(self, base_url: str, token: str | None = None):
        parsed = urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('use a base URL without credentials, query or fragment')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('use HTTPS, or loopback HTTP for local mode')
        self.base_url = base_url.rstrip('/')
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.token = token

    def request(self, method: str, path: str, body=None, *, key: str | None = None):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if key:
            headers['Idempotency-Key'] = key
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        # Let HTTPError/TimeoutError propagate. The caller keeps the same key/body
        # and reconciles the result instead of assuming that no action occurred.
        with self.opener.open(Request(self.base_url + path, data=data, headers=headers, method=method), timeout=30) as response:
            return response.read()

    def create(self, goal: str, source: Path, *, key: str, start: bool = False, adaptive_team: bool = False):
        return json.loads(self.request('POST', '/api/runs', {
            'goal': goal, 'inputs': {'team_selection': 'adaptive' if adaptive_team else 'fixed', 'files': [{'name': source.name, 'content': source.read_text()}]},
            'start': start,
        }, key=key))

    def run(self, run_id: str):
        return json.loads(self.request('GET', '/api/runs/' + quote(run_id, safe='')))

    def adopt(self, run_id: str, artifact_id: str, revision: int, expected: int):
        path = f'/api/artifacts/{quote(run_id, safe="")}/{quote(artifact_id, safe="")}/adopt'
        return json.loads(self.request('POST', path, {'revision': revision, 'expected_selected_revision': expected}))

    def save_selected(self, run_id: str, destination: Path):
        data = self.request('GET', '/api/runs/' + quote(run_id, safe='') + '/export?fmt=zip&selection=adopted')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            if manifest['schema_version'] != 1 or manifest['selection'] != 'adopted' or manifest['run_id'] != run_id:
                raise ValueError('unexpected export contract')
            for artifact in manifest['artifacts']:
                if hashlib.sha256(archive.read(artifact['path'])).hexdigest() != artifact['sha256']:
                    raise ValueError('artifact hash mismatch')
        # No archive extraction and no overwrite of an existing local file.
        with destination.open('xb') as output:
            output.write(data)
        return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--save', type=Path)
    args = parser.parse_args()
    client = AgentTeamHTTP(args.url, args.token_file.read_text().strip() if args.token_file else None)
    result = client.save_selected(args.run_id, args.save) if args.save else client.run(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
