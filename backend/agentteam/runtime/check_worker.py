"""Bounded pure-data validation worker. Invoked by checks.py, never by model code."""
from __future__ import annotations

import base64
import json
import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
if sys.platform.startswith('linux'):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agentteam.runtime.checks import json_schema_check, regex_count

try:
    message = json.loads(sys.stdin.buffer.read(4 * 1024**2 + 1))
    data = base64.b64decode(message['data'], validate=True)
    args = message['args']
    if message['kind'] == 'json_schema':
        result = json_schema_check(data, args.get('schema'))
    elif message['kind'] == 'regex_count':
        result = regex_count(data, str(args.get('pattern') or ''), int(args.get('min_count') or 1),
                             int(args['max_count']) if args.get('max_count') is not None else None)
    else:
        raise ValueError('unsupported worker check')
    encoded = json.dumps(result, ensure_ascii=False)
    if len(encoded.encode()) > 60000:
        result = {'status': 'blocked', 'problems': ['validation result exceeds the reporting limit']}
except Exception as exc:
    result = {'status': 'blocked', 'problems': ['validation failed: ' + type(exc).__name__]}
print(json.dumps(result, ensure_ascii=False))
