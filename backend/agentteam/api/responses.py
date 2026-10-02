"""Role-aware HTTP views; execution snapshots and audit storage stay unchanged.

Public agent fields are an allowlist so newly added execution configuration is
private by default. Apply these views when sending a response, including replay
of old receipts: a stored administrator response is not an authorization grant.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


AGENT_IDENTITY_FIELDS = ('id', 'agent_id', 'role', 'enabled', 'display_name', 'emoji')
AGENT_RUN_FIELDS = (*AGENT_IDENTITY_FIELDS, 'driver', 'model', 'tools', 'effort', 'system_prompt_sha256')
TOOL_EVENT_FIELDS = ('tool', 'ok', 'mode', 'attempt', 'result_chars')


def _fields(value: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {key: deepcopy(value[key]) for key in names if key in value}


def public_problems(problems: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Preflight diagnostics can contain connection names and secret file paths."""
    return [{'code': p['code'], 'message': 'Administrator setup required'} for p in problems]


def config_response(config: dict[str, Any], *, administrator: bool) -> dict[str, Any]:
    if administrator:
        return config
    return {
        'revision': config['revision'],
        'defaults': _fields(config['defaults'], ('team_mode', 'model', 'language', 'timezone')),
        'limits': _fields(config['limits'], ('budget_usd',)),
        'agents': [_fields(agent, AGENT_IDENTITY_FIELDS) for agent in config['agents']],
        'execution_summary': [_fields(item, ('driver', 'model', 'destination', 'tools'))
                              for item in config.get('execution_summary', [])],
        'problems': public_problems(config['problems']),
        # Preserve existing read-only clients' collection shapes without
        # disclosing connections, resolved prompts or installed skill paths.
        'connections': [],
        'effective_agents': {},
    }


def _snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    result = _fields(snapshot, ('provider_kind',))
    if isinstance(snapshot.get('agents'), dict):
        result['agents'] = {agent_id: _fields(agent, AGENT_RUN_FIELDS)
                            for agent_id, agent in snapshot['agents'].items() if isinstance(agent, dict)}
    recommendation = snapshot.get('team_recommendation')
    if isinstance(recommendation, dict):
        result['team_recommendation'] = _fields(recommendation, ('reason',))
        result['team_recommendation']['members'] = [
            _fields(member, ('agent_id', 'name', 'emoji', 'specialty', 'personality', 'reason'))
            for member in recommendation.get('members', []) if isinstance(member, dict)]
    return result


def run_response(payload: dict[str, Any], *, administrator: bool) -> dict[str, Any]:
    if administrator:
        return payload
    result = deepcopy(payload)
    if 'config_snapshot' in result:
        snapshot = result['config_snapshot']
        result['config_snapshot'] = _snapshot(snapshot) if isinstance(snapshot, dict) else None
    if 'problems' in result:
        result['problems'] = public_problems(result['problems'])
    # A preflight-blocked run persists the detailed operator diagnostic for
    # administrators. It is the same setup failure shown in /api/config.
    if result.get('status') == 'blocked' and result.get('plan') is None and result.get('blocked_reason'):
        result['blocked_reason'] = 'Administrator setup required'
    return result


def event_response(payload: dict[str, Any], *, administrator: bool) -> dict[str, Any]:
    if administrator:
        return payload
    result = deepcopy(payload)
    event_type = result.get('type')
    body = result.get('payload', {})
    if event_type == 'config.resolved':
        result['payload'] = _snapshot(body)
        if isinstance(body.get('limits'), dict):
            result['payload']['limits'] = _fields(body['limits'], ('budget_usd',))
    elif event_type == 'run.started' and isinstance(body.get('limits'), dict):
        result['payload']['limits'] = _fields(body['limits'], ('budget_usd',))
    elif event_type == 'run.blocked' and isinstance(body.get('problems'), list):
        result['payload']['problems'] = public_problems(body['problems'])
    elif event_type == 'run.forked':
        result['payload'] = _fields(body, ('parent_run_id', 'child_run_id', 'from_seq', 'kept_tasks'))
        result['payload']['configuration_changed'] = bool(body.get('overrides'))
    elif event_type == 'tool.called':
        # Raw tool arguments/output may include host paths, private skill text
        # and execution configuration. Keep the actual outcome visible; source
        # artifacts and check/review records remain accessible separately.
        result['payload'] = {**_fields(body, TOOL_EVENT_FIELDS), 'details_restricted': True}
    return result
