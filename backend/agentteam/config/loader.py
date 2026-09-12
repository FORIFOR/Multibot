"""Load, validate and resolve agent configuration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .models import CONFIG_DRIVERS, AgentSpec, AgentTeamConfig, EffectiveAgentConfig, sha256_text

PKG_ROOT = Path(__file__).resolve().parent.parent  # agentteam/ (prompts, skills, schemas ship inside the package)
REPO_ROOT = PKG_ROOT.parent.parent  # repository root when running from a checkout
SCHEMA_DIR = PKG_ROOT / "schemas"
PROMPT_DIR = PKG_ROOT / "prompts"
SKILL_DIR = PKG_ROOT / "skills"

# Tools that every agent gets regardless of config; the rest is opt-in per agent.
CORE_TOOLS = ["read_skill", "finish_task"]


class ConfigError(ValueError):
    pass


def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validate_blueprint_shape(cfg: AgentTeamConfig) -> None:
    schema = _schema("agent-config.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(cfg.blueprint_view())


def load_config_text(text: str, *, allow_fake: bool = False) -> AgentTeamConfig:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    cfg = AgentTeamConfig.model_validate(raw)
    if not allow_fake:
        validate_blueprint_shape(cfg)
    validate_config(cfg, allow_fake=allow_fake)
    return cfg


def load_config_file(path: Path) -> AgentTeamConfig:
    return load_config_text(path.read_text(encoding="utf-8"))


def validate_config(cfg: AgentTeamConfig, *, allow_fake: bool = False) -> None:
    conn_ids = [c.id for c in cfg.connections]
    if len(conn_ids) != len(set(conn_ids)):
        raise ConfigError("duplicate connection ids")
    if cfg.defaults.connection_id not in conn_ids:
        raise ConfigError("defaults.connection_id is not a known connection")
    for c in cfg.connections:
        if c.driver not in CONFIG_DRIVERS and not (allow_fake and c.driver == "fake"):
            raise ConfigError(f"driver {c.driver!r} cannot be selected from config")
    ids = [a.id for a in cfg.agents]
    if len(ids) != len(set(ids)):
        raise ConfigError("duplicate agent ids")
    skills = {s["name"] for s in list_skills()}
    for a in cfg.agents:
        if a.connection_id != "inherit" and a.connection_id not in conn_ids:
            raise ConfigError(f"agent {a.id}: unknown connection {a.connection_id}")
        if not set(a.skill_ids) <= skills:
            raise ConfigError(f"agent {a.id}: unknown skill in {a.skill_ids}")
        p = (PKG_ROOT / a.system_prompt_file).resolve()
        if not p.is_relative_to(PKG_ROOT) or not p.is_file():
            raise ConfigError(f"agent {a.id}: invalid prompt path {a.system_prompt_file}")


def list_skills() -> list[dict[str, str]]:
    out = []
    for skill_md in sorted(SKILL_DIR.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        meta = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
        out.append({
            "name": str(meta.get("name") or skill_md.parent.name),
            "description": str(meta.get("description") or ""),
            "sha256": hashlib.sha256(skill_md.read_bytes()).hexdigest(),
            "path": str(skill_md.relative_to(PKG_ROOT)),
        })
    return out


def read_skill_body(name: str) -> str | None:
    for s in list_skills():
        if s["name"] == name:
            return (PKG_ROOT / s["path"]).read_text(encoding="utf-8")
    return None


def role_prompt_text(agent: AgentSpec) -> str:
    if agent.system_prompt_override is not None:
        return agent.system_prompt_override
    return (PKG_ROOT / agent.system_prompt_file).read_text(encoding="utf-8")


def platform_policy_text() -> str:
    return (PROMPT_DIR / "platform-policy.md").read_text(encoding="utf-8")


def effective_agent(cfg: AgentTeamConfig, agent: AgentSpec) -> EffectiveAgentConfig:
    cid = cfg.defaults.connection_id if agent.connection_id == "inherit" else agent.connection_id
    conn = cfg.connection(cid)
    if conn is None:
        raise ConfigError(f"agent {agent.id}: connection {cid} not found")
    model = cfg.defaults.model if agent.model == "inherit" else agent.model
    prompt = role_prompt_text(agent)
    skills = [s for s in list_skills() if s["name"] in agent.skill_ids]
    tools = list(dict.fromkeys(CORE_TOOLS + agent.tools))
    return EffectiveAgentConfig(
        agent_id=agent.id, role=agent.role, enabled=agent.enabled,
        connection_id=cid, driver=conn.driver, base_url=conn.base_url, model=model,
        prompt_mode=agent.prompt_mode, system_prompt=prompt, system_prompt_sha256=sha256_text(prompt),
        skills=skills, tools=tools, effort=agent.effort, api_key_ref=conn.api_key_ref,
    )


def effective_all(cfg: AgentTeamConfig) -> dict[str, EffectiveAgentConfig]:
    return {a.id: effective_agent(cfg, a) for a in cfg.agents}


def config_to_yaml(cfg: AgentTeamConfig) -> str:
    return yaml.safe_dump(cfg.model_dump(mode="json", exclude_none=True), allow_unicode=True, sort_keys=False)


DEFAULT_CONFIG_YAML = """# Agent Team configuration.
# API keys are references only (env:NAME, keychain:service/account, file:/path); values are never stored here.
schema_version: 1
profile_name: local-first
defaults:
  connection_id: claude_cli
  model: opus
  language: ja
  timezone: Asia/Tokyo
connections:
# Claude Code CLI on this machine (no API key; uses your `claude` login). Models: opus / sonnet / fable or a full id.
- id: claude_cli
  driver: claude_cli
  base_url: local://claude
  api_key_ref: null
  capability_check: not_run
# Anthropic API (needs a key reference). Switch defaults.connection_id to use it.
- id: anthropic
  driver: anthropic_messages
  base_url: https://api.anthropic.com
  api_key_ref: env:ANTHROPIC_API_KEY
  capability_check: not_run
limits:
  max_active_workers: 3
  max_tasks: 12
  max_peer_messages_per_task: 6
  max_revision_rounds: 2
  max_model_calls: 120   # measured: one Opus builder session ≈ 10–15 turns via claude_cli
  max_tool_calls: 200
  timeout_seconds: 600
  budget_usd: 5.0
  max_output_tokens: 8000
  max_tool_output_chars: 12000
  max_session_cost_usd: 1.5
  max_session_turns: 40
  max_replans: 2
policy:
  external_mutation: approval
  skill_install: approval
  telemetry: 'off'
  share_replay: 'off'
  fallback: explicitly_approved_only
agents:
- id: master
  role: master
  enabled: true
  connection_id: inherit
  model: inherit
  system_prompt_file: prompts/master.md
  prompt_mode: auto_seed
  skill_ids: [artifact-handoff]
  tools: [create_task, update_task, send_message, read_messages, read_artifact, list_artifacts, workspace_read, workspace_write, publish_artifact, request_approval, report_blocker]
- id: researcher
  role: researcher
  enabled: true
  connection_id: inherit
  model: inherit
  system_prompt_file: prompts/researcher.md
  prompt_mode: auto_seed
  skill_ids: [source-grounded-research, artifact-handoff]
  tools: [web_search, web_fetch, send_message, read_messages, read_artifact, list_artifacts, workspace_read, workspace_write, publish_artifact, report_blocker]
- id: builder
  role: builder
  enabled: true
  connection_id: inherit
  model: inherit
  system_prompt_file: prompts/builder.md
  prompt_mode: auto_seed
  skill_ids: [artifact-handoff]
  tools: [workspace_read, workspace_write, workspace_list, sandbox_run, run_check, send_message, read_messages, read_artifact, list_artifacts, publish_artifact, request_approval, report_blocker]
- id: reviewer
  role: reviewer
  enabled: true
  connection_id: inherit
  model: inherit
  system_prompt_file: prompts/reviewer.md
  prompt_mode: auto_seed
  skill_ids: [evidence-review, artifact-handoff]
  tools: [read_artifact, list_artifacts, run_check, sandbox_run, workspace_read, workspace_write, send_message, read_messages, publish_artifact, submit_review, report_blocker]
- id: reporter
  role: reporter
  enabled: false
  connection_id: inherit
  model: inherit
  system_prompt_file: prompts/reporter.md
  prompt_mode: auto_seed
  skill_ids: []
  tools: [read_artifact, list_artifacts, read_events, publish_artifact]
"""
