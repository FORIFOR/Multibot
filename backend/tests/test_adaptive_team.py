"""Compile actual local-model recommendations; no stub provider or generated chat."""
import json
from pathlib import Path
import pytest
from agentteam.config.loader import load_config_text, config_to_yaml, effective_all
from agentteam.runtime.team_selection import Recommendation, compile_roster

SOURCE = Path(__file__).resolve().parents[2] / 'docs/evidence/adaptive-team-2026-09-20/real-recommendation.json'


def actual():
    record = json.loads(SOURCE.read_text())
    return load_config_text(record['original_config_yaml']), Recommendation.model_validate(record['recommendation'])


def test_actual_recommendation_preserves_capabilities_and_survives_reload():
    cfg, proposal = actual()
    compiled = compile_roster(cfg, proposal)
    restored = load_config_text(config_to_yaml(compiled))
    assert len(restored.agents) == len(proposal.members) + 1
    assert restored.connections == cfg.connections
    assert restored.limits == cfg.limits and restored.policy == cfg.policy
    for member, agent in zip(proposal.members, restored.agents[1:]):
        original = cfg.agent(member.template_id)
        for field in ['tools', 'connection_id', 'model', 'skill_ids', 'role', 'system_prompt_file', 'system_prompt_override']:
            assert getattr(agent, field) == getattr(original, field)
        assert agent.display_name == member.name
        assert agent.specialty == member.specialty
        assert agent.speech_style == member.personality
    assert len(effective_all(restored)) == len(restored.agents)


def test_locked_identity_collision_cannot_replace_a_selected_person():
    cfg, proposal = actual()
    locked = cfg.agent(proposal.members[0].template_id)
    locked.id = 'team_2'  # Collision with the original automatic numbering.
    locked.prompt_mode = 'user_locked'
    proposal.members[0].template_id = locked.id
    original = locked.model_dump()
    compiled = compile_roster(cfg, proposal)
    assert compiled.agent('team_2').model_dump() == original
    assert len(effective_all(compiled)) == len(proposal.members) + 1
    assert load_config_text(config_to_yaml(compiled)).agent('team_2').model_dump() == original


def test_recommendation_cannot_enable_tools_or_a_disabled_template():
    cfg, proposal = actual()
    raw = proposal.model_dump()
    raw['members'][0]['tools'] = cfg.agents[0].tools
    with pytest.raises(ValueError):
        Recommendation.model_validate(raw)
    cfg.agent(proposal.members[0].template_id).enabled = False
    with pytest.raises(ValueError, match='disabled permission template'):
        compile_roster(cfg, proposal)


def test_required_review_cannot_be_dropped():
    cfg, proposal = actual()
    proposal.members = [m for m in proposal.members if cfg.agent(m.template_id).role != 'reviewer']
    assert cfg.defaults.require_independent_review
    with pytest.raises(ValueError, match='independent review'):
        compile_roster(cfg, proposal)


def test_actual_explicit_voices_survive_configuration_roundtrip():
    record = json.loads(SOURCE.with_name('explicit-voice-recommendation.json').read_text())
    cfg = load_config_text(record['original_config_yaml'])
    proposal = Recommendation.model_validate(record['recommendation'])
    restored = load_config_text(config_to_yaml(compile_roster(cfg, proposal)))
    for member, agent in zip(proposal.members, restored.agents[1:]):
        assert member.speaking_style and member.personality
        assert member.speaking_style in agent.speech_style
        assert member.personality in agent.speech_style
        assert agent.tools == cfg.agent(member.template_id).tools
    assert len({a.speech_style for a in restored.agents[1:]}) == len(proposal.members)


def test_user_selection_preserves_real_identities_permissions_and_roundtrip():
    from agentteam.runtime.team_selection import choose_roster
    from agentteam.contracts import RunInputs
    cfg, _ = actual()
    ids = [a.id for a in cfg.agents if a.enabled and a.role in ('builder', 'reviewer')]
    restored = load_config_text(config_to_yaml(choose_roster(cfg, ids)))
    assert {a.id for a in restored.agents if a.enabled and a.role not in ('master', 'reporter')} == set(ids)
    for identifier in ids:
        assert restored.agent(identifier).model_dump() == cfg.agent(identifier).model_dump()
    assert restored.limits == cfg.limits and restored.connections == cfg.connections
    assert restored.policy == cfg.policy
    assert 'selected_agent_ids' not in RunInputs().model_dump()
    assert RunInputs(selected_agent_ids=ids).model_dump()['selected_agent_ids'] == ids
    with pytest.raises(ValueError):
        RunInputs(team_selection='adaptive', selected_agent_ids=ids)
    with pytest.raises(ValueError):
        RunInputs(selected_agent_ids=ids + ids)
    with pytest.raises(ValueError):
        choose_roster(cfg, [cfg.agents[0].id])
    with pytest.raises(ValueError):
        choose_roster(cfg, [a.id for a in cfg.agents if a.enabled and a.role == 'builder'])
    cfg.agent(ids[0]).enabled = False
    with pytest.raises(ValueError):
        choose_roster(cfg, ids)
