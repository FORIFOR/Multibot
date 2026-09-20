"""Task-specific roster selection. Models choose expertise, never new permissions."""
from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, Field
from ..config.loader import config_to_yaml, effective_all, load_config_text
from ..config.voice import PERSONAL_NAMES
from ..providers.base import LLMRequest
from .context import SessionContext
from .worker import AgentRunner, WorkerFailure
from .policy import PolicyViolation


class Member(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    template_id: str
    name: str = Field(min_length=1, max_length=40)
    emoji: str = Field(min_length=1, max_length=16)
    specialty: str = Field(min_length=1, max_length=200)
    personality: str = Field(min_length=1, max_length=600)
    # Optional for previously saved recommendations; new selection requires it.
    speaking_style: str = Field(default='', max_length=400)
    reason: str = Field(min_length=1, max_length=300)


class Recommendation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=600,
                        description="One or two complete sentences explaining the team size and complementary expertise. Do not repeat the request or list each member; their reasons have separate fields.")
    members: list[Member] = Field(min_length=1, max_length=6)


def compile_roster(cfg, recommendation: Recommendation):
    """Copy approved templates; only names, expertise and conversational style vary."""
    master = next((a for a in cfg.agents if a.enabled and a.role == 'master'), None)
    if master is None:
        raise ValueError('adaptive team needs an enabled coordinator')
    templates = {a.id: a for a in cfg.agents if a.enabled and a.role not in ('master', 'reporter')}
    if len(recommendation.members) > cfg.limits.max_tasks:
        raise ValueError('team exceeds the task limit')
    names = {master.display_name or 'レン'}
    reserved_ids = {a.id for a in cfg.agents}
    selected = [master.model_copy(deep=True)]
    if selected[0].prompt_mode != 'user_locked':
        selected[0].display_name = selected[0].display_name or 'レン'
    for i, member in enumerate(recommendation.members, 1):
        template = templates.get(member.template_id)
        if template is None:
            raise ValueError(f'unknown or disabled permission template: {member.template_id}')
        actual_name = (template.display_name or PERSONAL_NAMES.get(template.role, template.id)) if template.prompt_mode == 'user_locked' else member.name
        if actual_name in names or (template.prompt_mode != 'user_locked' and any(word in actual_name for word in ('係', '役', '担当'))):
            raise ValueError('use unique personal names, not duty labels')
        names.add(actual_name)
        agent = template.model_copy(deep=True)
        if agent.prompt_mode == 'user_locked':
            # A locked bot remains the same person and keeps its exact prompt.
            if any(a.id == agent.id for a in selected):
                raise ValueError('a locked member cannot be duplicated')
        else:
            suffix = i
            while f'team_{suffix}' in reserved_ids:
                suffix += 1
            agent.id = f'team_{suffix}'
            reserved_ids.add(agent.id)
            agent.display_name = member.name
            agent.emoji = member.emoji
            agent.speech_style = '\n'.join(filter(None, [member.personality, member.speaking_style]))
            agent.specialty = member.specialty
            agent.custom = True
        selected.append(agent)
    if not any(a.role != 'reviewer' for a in selected[1:]):
        raise ValueError('team needs a member who can produce the requested output')
    if cfg.defaults.require_independent_review and not any(a.role == 'reviewer' for a in selected):
        raise ValueError('independent review is required: select a distinct review-capable member')
    result = cfg.model_copy(deep=True)
    result.agents = selected
    return load_config_text(config_to_yaml(result))


def choose_roster(cfg, selected_ids: list[str]):
    """Select existing identities, never create capabilities or alter their prompts."""
    if cfg.defaults.team_mode == 'single':
        raise ValueError('Single-agent mode does not support choosing a team.')
    available = {a.id: a for a in cfg.agents if a.enabled and a.role not in ('master', 'reporter')}
    if not selected_ids or len(set(selected_ids)) != len(selected_ids) or any(i not in available for i in selected_ids):
        raise ValueError('選べる仲間から参加メンバーを選び直してください。')
    chosen = [available[i] for i in selected_ids]
    if not any(a.role != 'reviewer' for a in chosen):
        raise ValueError('成果物を作れる仲間を1人以上選んでください。')
    if cfg.defaults.require_independent_review and not any(a.role == 'reviewer' for a in chosen):
        raise ValueError('確認ができる仲間を1人以上選んでください。')
    result = cfg.model_copy(deep=True)
    # Keep disabled definitions for compatibility, but only requested workers run.
    for agent in result.agents:
        if agent.role not in ('master', 'reporter'):
            agent.enabled = agent.id in selected_ids
    return load_config_text(config_to_yaml(result))


async def recommend_team(rt):
    from .planner import PlanError, _extract_json
    master = next((a for a in rt.enabled_agents() if a.role == 'master'), None)
    if master is None:
        raise PlanError('adaptive team needs an enabled coordinator')
    templates = [a for a in rt.config.agents if a.enabled and a.role not in ('master', 'reporter')]
    schema = Recommendation.model_json_schema()
    schema['$defs']['Member']['properties']['template_id']['enum'] = [a.id for a in templates]
    schema['$defs']['Member']['required'].append('speaking_style')
    schema['$defs']['Member']['properties']['speaking_style'].update({
        'minLength': 1,
        'description': 'Concrete conversational voice: sentence endings, tone and response to a teammate. Distinct from other members; not a job description.'})
    inputs = rt.run.inputs
    prompt = json.dumps({'request': rt.run.goal, 'text': inputs.text[:12000],
                         'files': [{'name': f.get('name'), 'content': f.get('content', '')[:12000]} for f in inputs.files],
                         'urls': inputs.urls,
                         'permission_templates': [{'id': a.id, 'permission_class': a.role, 'tools': a.tools,
                                                   'locked': a.prompt_mode == 'user_locked', 'name': a.display_name,
                                                   'specialty': a.specialty} for a in templates],
                         'independent_review_required': rt.config.defaults.require_independent_review,
                         'max_members': min(6, rt.config.limits.max_tasks)}, ensure_ascii=False)
    system = ("Choose the smallest effective team for this specific request. Return JSON matching the schema. "
              "The coordinator already exists and is not included in members. Do not default to four people or one of each permission class. "
              "All members can read supplied material. Reading or extracting the supplied text alone is NOT a reason to add a researcher. "
              "For a short document based on supplied text, one producer can read and write it; add one separate reviewer when required. "
              "Add further specialists only for substantial distinct work that the producer/reviewer cannot reasonably combine. "
              "For complex design, select professions matching its actual risks and outputs; multiple specialists can use the builder template. "
              "Do not count permission classes as required jobs. State why each extra person is necessary, not merely useful. "
              "Keep the overall reason to one or two complete sentences, aiming under 250 characters. "
              "Do not quote the request or enumerate member descriptions there; use each member's reason field. "
              "Finish sentences before reaching field limits. "
              "Preserve the requested deliverable scope and exact filenames. A request to discuss implementation methods or produce a design "
              "does not authorize implementing, deploying or connecting the proposed application; describe design contributions in that case. "
              "Choose distinct task-specific expertise, for example domain analysis, accessibility, API architecture or editing, only when needed. "
              "Several specialists may inherit the same permission template; a template is not their profession. "
              "Give each bot a simple, approachable character identity: a short nickname, a recognizable animal emoji, "
              "one clear personality trait and concise speaking style. Avoid human full names, occupational person emojis, "
              "job titles, elaborate backstories, baby talk and forced animal noises. Expertise belongs in specialty, not the name. "
              "For Japanese names prefer short hiragana nicknames; names must not contain 係/役/担当. "
              "These are identity choices, not a fixed roster or fixed occupations; choose the team size and expertise for the task. "
              "Use personality for temperament and speaking_style for concrete sentence endings and how they react to another member. "
              "Keep personality and speaking_style together under 600 characters. "
              "Different people must sound different, not just have different expertise, "
              "and explain their contribution. Use the request's language. Do not invent connections, tools, permissions or verified expertise. "
              "Respect locked identities and select a reviewer template when independent review is required. "
              "The output is a proposed AI team, not real human credentials. "
              f"Write all reasons and descriptions in the user's requested language, default {rt.config.defaults.language}.")
    runner = AgentRunner(SessionContext(rt=rt, agent=master, mode='plan', tools=[]))
    messages = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}]
    for attempt in range(3):
        try:
            response = await runner._call_model(LLMRequest(model=master.model, system=system, messages=messages,
                tools=[], json_schema=schema, max_tokens=min(3000, rt.config.limits.max_output_tokens),
                effort=master.effort, metadata={'mode': 'team_selection', 'agent_id': master.agent_id}), None)
            recommendation = Recommendation.model_validate(_extract_json(response.text))
            if any(not member.speaking_style for member in recommendation.members):
                raise ValueError('each member needs speaking_style with concrete sentence endings and responses, separate from personality')
            cfg = compile_roster(rt.config, recommendation)
        except (WorkerFailure, PolicyViolation) as exc:
            raise PlanError(f'team selection failed: {exc}') from exc
        except ValueError as exc:
            await rt.events.append(rt.run_id, 'team.rejected', {'attempt': attempt + 1, 'reason': str(exc)[:1500]})
            messages.append({'role': 'user', 'content': [{'type': 'text', 'text': f'Correct the recommendation: {exc}'}]})
            continue
        rt.config = cfg
        rt.agents = effective_all(cfg)
        resolved_recommendation = {'reason': recommendation.reason, 'members': [
            {'agent_id': agent.agent_id, 'name': agent.display_name, 'emoji': agent.emoji,
             'specialty': agent.specialty or agent.role, 'personality': agent.speech_style,
             'reason': proposed.reason, 'template_id': proposed.template_id}
            for agent, proposed in zip(list(rt.agents.values())[1:], recommendation.members)]}
        snapshot = {**rt.run.config_snapshot, 'config_yaml': config_to_yaml(cfg),
                    'agents': {k: a.model_dump() for k, a in rt.agents.items() if a.enabled},
                    'team_recommendation': resolved_recommendation}
        rt.run.config_snapshot = snapshot
        await rt.runs.update_run(rt.run_id, config_snapshot=snapshot)
        await rt.events.append(rt.run_id, 'team.selected', {'reason': recommendation.reason,
            'members': [{'agent_id': a.agent_id, 'name': a.display_name, 'emoji': a.emoji,
                         'specialty': a.specialty, 'speech_style': a.speech_style} for a in rt.enabled_agents()]},
            actor_id=master.agent_id, actor_kind='agent')
        return
    raise PlanError('team recommendation rejected three times; no team was started')
