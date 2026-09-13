"""Agent configuration models (mirror of schemas/agent-config.schema.json plus runtime extensions)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Driver = Literal["openai_responses", "openai_compatible_chat", "anthropic_messages", "google_genai", "ollama", "claude_cli", "fake"]
CONFIG_DRIVERS = {"openai_responses", "openai_compatible_chat", "anthropic_messages", "google_genai", "ollama", "claude_cli"}
IMPLEMENTED_DRIVERS = {"anthropic_messages", "openai_compatible_chat", "ollama", "claude_cli", "fake"}


class Defaults(BaseModel):
    connection_id: str
    model: str
    language: str = "ja"
    timezone: str = "Asia/Tokyo"
    # "team": the Master plans a DAG for Researcher/Builder/Reviewer. "single": no planning call, no review — one enabled
    # builder-role agent gets the whole request as one task with the same total budget (the single-agent baseline).
    team_mode: Literal["team", "single"] = "team"
    # Older saved profiles may intentionally omit review; fresh defaults enable this policy.
    require_independent_review: bool = False


class Connection(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    id: str
    driver: Driver
    base_url: str
    api_key_ref: str | None = None
    capability_check: Literal["not_run", "passed", "failed"] = "not_run"
    # runtime extensions (not in the blueprint schema; stripped when validating against it)
    capability_detail: dict[str, Any] | None = None
    ollama_thinking: bool | None = None  # None preserves the server default; False disables reasoning output
    refusal_fallback: bool = False  # Anthropic server-side fallback; OFF unless the user opts in
    allowed_fallback_connections: list[str] = Field(default_factory=list)

    @field_validator('api_key_ref')
    @classmethod
    def require_secret_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        kind, _, target = value.partition(':')
        valid = (kind == 'env' and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', target)) or (
            kind == 'file' and Path(target).is_absolute()) or (kind == 'keychain' and bool(target.strip()))
        if not valid or '\n' in value or '\r' in value:
            raise ValueError('use env:NAME, keychain:service/account, or file:/absolute/path; never a plaintext key')
        return value


class Limits(BaseModel):
    max_active_workers: int = 3
    max_tasks: int = 12
    max_peer_messages_per_task: int = 6
    max_revision_rounds: int = 2
    max_model_calls: int = 120
    max_tool_calls: int = 200
    timeout_seconds: int = 600
    budget_usd: float = 2.0
    max_output_tokens: int = 8000
    max_tool_output_chars: int = 12000
    max_session_cost_usd: float = 1.5  # claude_cli: --max-budget-usd per agent session
    max_session_turns: int = 40  # claude_cli: --max-turns per agent session
    max_replans: int = 2  # Master milestone sessions that may add tasks after the current DAG finishes


class Policy(BaseModel):
    external_mutation: Literal["approval"] = "approval"
    skill_install: Literal["approval"] = "approval"
    telemetry: Literal["off", "opt_in"] = "off"
    share_replay: Literal["off", "explicit_publish"] = "off"
    fallback: Literal["explicitly_approved_only"] = "explicitly_approved_only"


class AgentSpec(BaseModel):
    id: str
    role: str
    enabled: bool = True
    connection_id: str = "inherit"
    model: str = "inherit"
    system_prompt_file: str
    prompt_mode: Literal["auto_seed", "user_locked"] = "auto_seed"
    skill_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    # runtime extensions
    system_prompt_override: str | None = None  # user-edited prompt text (stored in config revision)
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None


class ModelPrice(BaseModel):
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float | None = None
    cache_write_per_mtok: float | None = None


class AgentTeamConfig(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    schema_version: Literal[1] = 1
    profile_name: str
    defaults: Defaults
    connections: list[Connection]
    limits: Limits
    policy: Policy = Field(default_factory=Policy)
    agents: list[AgentSpec]
    pricing: dict[str, ModelPrice] = Field(default_factory=dict)

    def connection(self, cid: str) -> Connection | None:
        return next((c for c in self.connections if c.id == cid), None)

    def agent(self, aid: str) -> AgentSpec | None:
        return next((a for a in self.agents if a.id == aid), None)

    def blueprint_view(self) -> dict[str, Any]:
        """Shape that validates against schemas/agent-config.schema.json (extensions removed)."""
        d = self.model_dump(mode="json")
        d.pop("pricing", None)
        d["defaults"].pop("team_mode", None)
        d["defaults"].pop("require_independent_review", None)
        for c in d["connections"]:
            for k in ("capability_detail", "refusal_fallback", "allowed_fallback_connections", "ollama_thinking"):
                c.pop(k, None)
        for a in d["agents"]:
            for k in ("system_prompt_override", "effort"):
                a.pop(k, None)
        for k in ("max_output_tokens", "max_tool_output_chars", "max_session_cost_usd", "max_session_turns", "max_replans"):
            d["limits"].pop(k, None)
        return d


class EffectiveAgentConfig(BaseModel):
    """What one agent will actually run with, frozen for a run."""
    agent_id: str
    role: str
    enabled: bool
    connection_id: str
    driver: str
    base_url: str
    model: str
    prompt_mode: str
    system_prompt: str
    system_prompt_sha256: str
    skills: list[dict[str, str]]  # {name, description, sha256, path}
    tools: list[str]
    effort: str | None = None
    api_key_ref: str | None = None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
