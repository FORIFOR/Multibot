"""Custom identity persistence through the actual API, without real model calls."""
import yaml
from tests.test_api import client  # reuse the deterministic AppService fixture


async def test_custom_bot_roundtrip_and_frozen_snapshot(client):
    before = (await client.get('/api/config')).json()
    body = {'expected_revision': before['revision'], 'id': 'qa-panda', 'display_name': '確認パンダ',
            'emoji': '🐼', 'role': 'specialist', 'system_prompt': 'Use supplied evidence only.'}
    response = await client.post('/api/agents', json=body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['revision'] > before['revision']
    current = (await client.get('/api/config')).json()
    spec = next(a for a in current['agents'] if a['id'] == 'qa-panda')
    assert spec['display_name'] == '確認パンダ' and spec['emoji'] == '🐼' and spec['custom']
    assert spec['connection_id'] == 'inherit' and spec['model'] == 'inherit'
    assert not set(spec['tools']) & {'sandbox_run', 'web_fetch', 'create_task'}
    effective = (await client.get('/api/agents/qa-panda/effective-config')).json()
    assert effective['emoji'] == '🐼' and effective['system_prompt'] == body['system_prompt']
    created = await client.post('/api/runs', json={'goal': 'Snapshot only, no model execution', 'start': False})
    assert created.status_code == 202, created.text
    run_id = created.json()['run_id']
    assert (await client.patch('/api/agents/qa-panda', json={'expected_revision': current['revision'], 'display_name': '新しい名前', 'emoji': '👩🏽‍💻'})).status_code == 200
    run = (await client.get(f'/api/runs/{run_id}')).json()
    # Before execution the frozen configuration is YAML; effective agents are resolved on start.
    frozen = yaml.safe_load(run['config_snapshot']['config_yaml'])
    original = next(a for a in frozen['agents'] if a['id'] == 'qa-panda')
    assert original['emoji'] == '🐼'
    assert original['display_name'] == '確認パンダ'
    latest = (await client.get('/api/agents/qa-panda/effective-config')).json()
    assert latest['emoji'] == '👩🏽‍💻' and latest['display_name'] == '新しい名前'


async def test_custom_bot_duplicate_and_stale_revision_do_not_overwrite(client):
    rev = (await client.get('/api/config')).json()['revision']
    body = {'expected_revision': rev, 'id': 'unique-bot', 'display_name': 'Bot', 'emoji': '🇯🇵', 'system_prompt': 'Read only.'}
    first = await client.post('/api/agents', json=body)
    assert first.status_code == 201
    assert (await client.post('/api/agents', json=body)).status_code == 409
    body['expected_revision'] = first.json()['revision']
    assert (await client.post('/api/agents', json=body)).status_code == 409
    agents = (await client.get('/api/agents')).json()
    assert len([a for a in agents if a['id'] == 'unique-bot']) == 1
