"""Repeat real repository-to-enterprise-readiness work with an actual local LLM.

Uses the secured production API in-process, the durable queue, original source
files and real credentials. No synthetic business inputs or model replacements.
Run from a clean immutable checkout, with a new root for each changed series.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.config.loader import config_to_yaml, load_config_file
from agentteam.ids import new_id
from agentteam.providers.registry import ProviderRegistry
from agentteam.runtime.checks import json_schema_check
from agentteam.security.accounts import issue_key

SOURCES = ['docs/PRODUCTION_PLAN.md', 'docs/evidence/operations-2026-09-14/README.md']
GOAL = '''企業の導入担当者に渡す、Multibotの本番化現状を整理してください。添付は実際のプロジェクト資料です。
成果物は readiness.json の1ファイル。Markdownコードフェンスで囲まずJSONをそのまま公開してください。
トップレベルは product（文字列Multibot）、production_ready（真偽値。資料のL3判定に従う）、deployment（文字列dedicated-single-host）、summary（日本語の要約）、areas（配列）です。
areasには PRODUCTION_PLAN.md の表にある全8領域を1回ずつ、同じ順番で含めてください。各行は area（元の領域名）、implemented（実装・検証済みの内容を日本語で要約）、remaining（残る受入条件を日本語で要約）、source_file（PRODUCTION_PLAN.md）、evidence_quote（その行のRemaining acceptance work列の原文を省略せず逐語引用）の5項目です。`remaining` は必ず日本語の要約にし、英語原文をコピーしないでください。`evidence_quote` だけは英語原文をそのまま残します。
日本語の要約は資料から確認できる事実だけに限定してください。テスト件数を本番導入可能やSLA達成に読み替えず、未検証・未達・顧客側の条件を残してください。
技術固有名は英字のまま保持してください。例えば暗号化ツールageを「年齢」に訳さず、readinessは「準備状況」、actor-scopedは「操作主体ごとの」としてください。
意味を確認できないカタカナ語や途中で切れた英単語を作らないでください（例：アイデムpotent、リクエストャ、アバター、パーラン、サイントニック、オデータ、アクトアード、カーソリストリーム、デリル、アドバザリ、ステール、リカスケル、マニファクト）。Executionのimplementedには `idempotent` または「冪等性」を、Dataのimplementedには暗号化ツール名 `age` をそのまま含めてください。
用語は次の正確な日本語を優先してください：per-run＝「ランごとの」、artifact＝「アーティファクト」、actor-scoped idempotent acceptance＝「操作主体ごとの冪等な受入」、requester-owned artifact requirements＝「依頼者所有のアーティファクト要件」、synthetic＝「合成」、auditor＝「監査者」、cursor＝「カーソル」、drill＝「ドリル」、advisory＝「アドバイザリ」、stale＝「陳腐化」、resumable＝「再開可能」。これらを意味不明なカタカナへ変換しないでください。
提供資料だけで完結する業務です。外部検索や架空企業のデータは不要です。Builderが作成し、Reviewerが全8領域、引用と原資料の一致、日本語要約の事実性、L3の未達判定を確認してください。'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as f:
        json.dump(value, f, indent=2, ensure_ascii=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    temporary.replace(path)


def source_rows(text):
    if '**L3 remains unachieved.**' not in text:
        raise ValueError('source readiness conclusion changed; review this acceptance workflow')
    rows = []
    for line in text.splitlines():
        if line.startswith('| ') and not line.startswith('| Area'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) == 3 and cells[0] != '---':
                rows.append(cells)
    if len(rows) != 8:
        raise ValueError('source table changed; review the workflow before a new series')
    return rows


def grade(raw, expected):
    problems = []
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return {'mechanical_pass': False, 'problems': ['readiness.json missing or invalid JSON'], 'semantic_review': 'pending'}
    if not isinstance(doc, dict):
        return {'mechanical_pass': False, 'problems': ['top level must be an object'], 'semantic_review': 'pending'}
    if doc.get('product') != 'Multibot' or doc.get('production_ready') is not False or doc.get('deployment') != 'dedicated-single-host':
        problems.append('product/deployment/L3 conclusion disagrees with the source and request')
    if not isinstance(doc.get('summary'), str) or not re.search(r'[ぁ-んァ-ン一-龯]', doc.get('summary', '')):
        problems.append('Japanese summary missing')
    areas = doc.get('areas')
    if not isinstance(areas, list) or len(areas) != len(expected):
        problems.append('all eight source areas required exactly once')
    else:
        for index, (area, _, remaining) in enumerate(expected):
            row = areas[index]
            if not isinstance(row, dict):
                problems.append(f'{area}: invalid row'); continue
            if row.get('area') != area or row.get('source_file') != 'PRODUCTION_PLAN.md' or row.get('evidence_quote') != remaining:
                problems.append(f'{area}: area/source/exact quote mismatch')
            for name in ('implemented', 'remaining'):
                if not isinstance(row.get(name), str) or not re.search(r'[ぁ-んァ-ン一-龯]', row.get(name, '')):
                    problems.append(f'{area}: Japanese {name} summary missing')
    # Re-run the exact requester contract in the evidence collector. This
    # keeps campaign grading aligned with the runtime's immutable delivery
    # decision, including translation-drift and copied-quote guards.
    contract = json_schema_check(raw.encode(), delivery_schema(expected))
    if contract['status'] != 'pass':
        problems.extend('delivery contract: ' + p for p in contract.get('problems', []))
    return {'mechanical_pass': not problems, 'problems': problems, 'semantic_review': 'pending',
            'delivery_contract': contract}


def delivery_schema(expected):
    """Requester rules derived from the actual source, independent of the model plan."""
    # These are concrete translation failures observed in the preserved v1/v2
    # and v3 local-model attempts. They are rejected at the delivery boundary
    # so a Japanese-character regex cannot turn a garbled summary into a pass.
    forbidden_translation_fragments = (
        '年齢|アイデム|イデム|potent|リクエストャ|リクエストャー|アバター|'
        'パーラン|サイントニック|オデータ|アクトアード|カーソリストリーム|'
        'デリル|アドバザリ|ステール|リカスケル|マニファクト|'
        'バイントーリング|レジャーリー|アデュータ|コッレクター|レタード|'
        '演算主体|アクター監査|actor-scoped|per-run|requester-owned|'
        'resumable|synthetic|auditor|cursor|drill|stale|artifact|advisory'
    )
    japanese = {'type': 'string', 'description': 'Japanese summary required. Do not copy the English source quotation.',
                'minLength': 1, 'maxLength': 4000, 'pattern': '[ぁ-んァ-ン一-龯]',
                'not': {'pattern': forbidden_translation_fragments}}
    row = {'type': 'object', 'additionalProperties': False,
           'required': ['area', 'implemented', 'remaining', 'source_file', 'evidence_quote'],
           'properties': {'area': {'type': 'string'}, 'implemented': japanese, 'remaining': japanese,
                          'source_file': {'const': 'PRODUCTION_PLAN.md'},
                          'evidence_quote': {'type': 'string', 'description': 'Exact English source quotation; do not translate or alter.'}}}
    technical_constraints = {
        # Keep terms whose meaning is unsafe to infer from a loose katakana
        # transliteration. The Japanese alternatives are explicit and narrow.
        # These are requester terms, rather than a model's free-form review.
        'Isolation': {'implemented': {'pattern': 'アーティファクト'}},
        'Execution': {'implemented': {'pattern': '(?:idempotent|冪等|べき等)'}},
        'Data': {'implemented': {'allOf': [{'pattern': 'age'}, {'pattern': '再開可能'}]}},
        'Audit / monitoring': {'implemented': {'allOf': [{'pattern': '監査者'}, {'pattern': 'カーソル'}]}},
        'Deployment': {'implemented': {'pattern': 'アドバイザリ'}},
    }
    def row_constraints(area, remaining):
        properties = {
            'area': {'const': area},
            'evidence_quote': {'const': remaining},
            # Do not allow a Japanese prefix/suffix to hide a copied English
            # acceptance quote in the `remaining` summary.
            'remaining': {'allOf': [japanese, {'not': {'pattern': re.escape(remaining)}}]},
        }
        for name, constraint in technical_constraints.get(area, {}).items():
            properties[name] = {'allOf': [japanese, constraint]}
        return properties
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'additionalProperties': False,
            'required': ['product', 'production_ready', 'deployment', 'summary', 'areas'], '$defs': {'row': row},
            'properties': {'product': {'const': 'Multibot'}, 'production_ready': {'const': False},
                           'deployment': {'const': 'dedicated-single-host'}, 'summary': japanese,
                                     'areas': {'type': 'array', 'minItems': len(expected), 'maxItems': len(expected),
                                     'prefixItems': [{'allOf': [{'$ref': '#/$defs/row'}, {'properties': row_constraints(area, remaining)}]}
                                                    for area, _, remaining in expected]}}}


async def main(root, repeat, profile_path):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (root / 'workflow.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT.parent, text=True).strip():
        raise ValueError('use a clean, fixed checkout')
    source = {Path(name).name: (ROOT.parent / name).read_text() for name in SOURCES}
    expected = source_rows(source['PRODUCTION_PLAN.md'])
    required = [{'logical_path': 'readiness.json', 'json_schema': delivery_schema(expected)}]
    cfg = load_config_file(ROOT.parent / profile_path)
    cfg.profile_name = 'production-readiness-source-workflow'
    cfg.limits.max_tasks = 4; cfg.limits.max_model_calls = 40; cfg.limits.max_tool_calls = 80
    cfg.limits.max_replans = 0; cfg.limits.max_session_turns = 18; cfg.limits.max_output_tokens = 5000
    cfg.limits.max_active_workers = 1
    # v1/v2 consumed their 600/900s windows while revising the failed output.
    # Record a separate fixed 1200s series with room for a real correction and
    # independent review; this is not a latency or SLA claim.
    cfg.limits.timeout_seconds = 1200
    next(a for a in cfg.agents if a.id == 'researcher').enabled = False
    async with httpx.AsyncClient(timeout=10, trust_env=False) as local:
        version = (await local.get('http://127.0.0.1:11434/api/version')).json()['version']
        models = (await local.get('http://127.0.0.1:11434/api/tags')).json()['models']
    model = next(m for m in models if m['name'] in (cfg.defaults.model, cfg.defaults.model + ':latest'))
    fingerprint = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT.parent, text=True).strip(),
                   'source_sha256': {name: sha(value.encode()) for name, value in source.items()},
                   'goal_sha256': sha(GOAL.encode()), 'config_sha256': sha(config_to_yaml(cfg).encode()),
                   'delivery_requirements_sha256': sha(json.dumps(required, sort_keys=True, ensure_ascii=False).encode()),
                   'model': cfg.defaults.model, 'model_digest': model['digest'], 'ollama_version': version, 'target_runs': repeat}
    manifest = root / 'fingerprint.json'
    if manifest.exists() and json.loads(manifest.read_text()) != fingerprint:
        raise ValueError('code, source, model or configuration changed; use a new series')
    if not manifest.exists():
        write_json(manifest, fingerprint)
        (root / 'inputs').mkdir(mode=0o700)
        for name, value in source.items():
            (root / 'inputs' / name).write_text(value)
        (root / 'goal.txt').write_text(GOAL)
        write_json(root / 'delivery-requirements.json', required)
    access = root / 'access.json'
    if not access.exists():
        issue_key(access, 'forifor', 'admin', root / 'forifor.key', organization='FORIFOR/Multibot', public_origin='https://localhost')
        settings = json.loads(access.read_text()); settings.update(max_active_runs=1, max_pending_runs=1)
        write_json(access, settings); access.chmod(0o600)
    svc = AppService(root / 'data', config_yaml=config_to_yaml(cfg), access_file=access)
    app = create_app(svc)
    attempts_path = root / 'attempts.json'
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
    def status(state, **extra):
        write_json(root / 'status.json', {'state': state, 'updated_at': datetime.now(timezone.utc).isoformat(), 'target_runs': repeat, **extra})
    try:
        async with app.router.lifespan_context(app):
            if svc.config.connections[0].capability_check != 'passed':
                registry = ProviderRegistry(svc.config)
                try:
                    result = await registry.adapter('ollama').probe(cfg.defaults.model)
                finally:
                    await registry.aclose()
                write_json(root / 'probe.json', asdict(result))
                if not result.ok:
                    raise ValueError('actual local capability probe failed')
                passed = svc.config.model_copy(deep=True)
                passed.connections[0].capability_check = 'passed'
                passed.connections[0].capability_detail = {'model_reported': result.model_reported, 'error': result.error}
                await svc.save_config(passed, 'actual local probe before production workflow')
            def normalized(configuration):
                value = configuration.model_dump(mode='json')
                for connection in value['connections']:
                    connection.pop('capability_check', None); connection.pop('capability_detail', None)
                return value
            if normalized(svc.config) != normalized(cfg):
                raise ValueError('persisted workflow configuration changed; use a new series')
            (root / 'probed-agents.yaml').write_text(config_to_yaml(svc.config))
            token = (root / 'forifor.key').read_text().strip()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://localhost',
                                        headers={'Authorization': 'Bearer ' + token}, timeout=30) as client:
                body = {'goal': GOAL, 'inputs': {'files': [{'name': name, 'content': text} for name, text in source.items()],
                                               'delivery_requirements': required}, 'start': True}
                for rep in range(1, repeat + 1):
                    if (root / 'STOP').exists():
                        status('paused', reason='STOP requested; prior attempts preserved'); return
                    attempt = next((a for a in attempts if a['rep'] == rep), None)
                    if attempt and attempt.get('result'):
                        continue
                    async with httpx.AsyncClient(timeout=10, trust_env=False) as local:
                        current_version = (await local.get('http://127.0.0.1:11434/api/version')).json()['version']
                        current_models = (await local.get('http://127.0.0.1:11434/api/tags')).json()['models']
                    current_model = next(m for m in current_models if m['name'] in (cfg.defaults.model, cfg.defaults.model + ':latest'))
                    if current_version != version or current_model['digest'] != model['digest']:
                        raise ValueError('local model changed during the series')
                    if attempt is None:
                        attempt = {'rep': rep, 'request_key': new_id('workflow')}; attempts.append(attempt); write_json(attempts_path, attempts)
                    status('running', rep=rep)
                    if not attempt.get('run_id'):
                        response = await client.post('/api/runs', json=body, headers={'Idempotency-Key': attempt['request_key']})
                        if response.status_code != 202:
                            raise ValueError('production API refused workflow admission: ' + str(response.status_code))
                        attempt['run_id'] = response.json()['run_id']; write_json(attempts_path, attempts)
                    run_id = attempt['run_id']; status('running', rep=rep, run_id=run_id)
                    async with asyncio.timeout(cfg.limits.timeout_seconds + 180):
                        while True:
                            detail = (await client.get('/api/runs/' + run_id)).json()
                            if detail['status'] not in ('queued', 'planning', 'running'):
                                break
                            await asyncio.sleep(1)
                    evidence = root / 'evidence' / f'{rep:02d}-{run_id}'; evidence.mkdir(parents=True, exist_ok=True)
                    write_json(evidence / 'run.json', detail)
                    raw_events = await client.get(f'/api/runs/{run_id}/export')
                    (evidence / 'events.jsonl').write_bytes(raw_events.content)
                    events = [json.loads(line) for line in raw_events.text.splitlines() if line.strip()]
                    artifacts = {}; inventory = []
                    for index, metadata in enumerate(sorted(detail['artifacts'], key=lambda m: m['revision'])):
                        raw = await client.get(f'/api/artifacts/{run_id}/{quote(metadata["artifact_id"], safe="")}/versions/{metadata["revision"]}/raw')
                        raw.raise_for_status()
                        if sha(raw.content) != metadata['sha256']:
                            raise ValueError('published artifact checksum mismatch')
                        filename = f'artifact-{index:03d}.bin'; (evidence / filename).write_bytes(raw.content)
                        inventory.append({**metadata, 'evidence_file': filename})
                        artifacts[metadata['logical_path']] = raw.text
                    write_json(evidence / 'artifacts.json', inventory)
                    graded = grade(artifacts.get('readiness.json'), expected)
                    review = [e for e in events if e['type'] == 'review.submitted']
                    result = {'rep': rep, 'run_id': run_id, 'status': detail['status'], **graded,
                              'false_completion_by_mechanical_checks': detail['status'] == 'completed' and not graded['mechanical_pass'],
                              'model_actors': sorted({e.get('actor_id') for e in events if e['type'] == 'model.called'}),
                              'review_submissions': len(review), 'usage': detail['usage'], 'evidence_dir': str(evidence)}
                    attempt['result'] = result; write_json(attempts_path, attempts)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
        status('completed_mechanical_trials', completed=len(attempts), semantic_review='pending', production_ready=False)
    except BaseException as exc:
        status('stopped', error_type=type(exc).__name__, message='inspect retained run and private process log; no automatic success claim')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=10)
    parser.add_argument('--profile', default='docs/config/local-qwen35-9b-team.yaml',
                        help='repository-relative team profile; the model and digest are fingerprinted')
    args = parser.parse_args()
    if not 1 <= args.repeat <= 100:
        parser.error('--repeat must be 1–100')
    asyncio.run(main(args.root.resolve(), args.repeat, args.profile))
