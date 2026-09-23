"""Data contracts shared by the runtime, the API and the UI.

These mirror docs/blueprint schemas (team-plan, event, agent-config) and add the
runtime-owned objects (task state, message, artifact manifest, approval, run).
"""
from __future__ import annotations

from enum import StrEnum
import json
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator

MessagePurpose = Literal["request", "question", "answer", "handoff", "finding", "decision"]
CheckKind = Literal["programmatic", "source_check", "human_review", "model_review"]


class ArtifactRef(BaseModel):
    artifact_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AcceptanceCriterion(BaseModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    check_kind: CheckKind


class TaskSpec(BaseModel):
    id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    input_artifacts: list[ArtifactRef] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    acceptance: list[AcceptanceCriterion] = Field(min_length=1)
    write_scope: str = Field(min_length=1)

    @field_validator("depends_on", "output_paths")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate entries")
        return v


class TeamPlan(BaseModel):
    schema_version: Literal[1] = 1
    goal: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    agents: list[str]
    tasks: list[TaskSpec] = Field(min_length=1)


class TaskStatus(StrEnum):
    queued = "queued"
    ready = "ready"
    running = "running"
    waiting = "waiting"
    review_pending = "review_pending"
    accepted = "accepted"
    blocked = "blocked"
    approval_required = "approval_required"
    interrupted = "interrupted"
    failed = "failed"
    cancelled = "cancelled"
    partial = "partial"


TERMINAL_TASK_STATES = {TaskStatus.accepted, TaskStatus.failed, TaskStatus.cancelled, TaskStatus.partial}
# a dependency's outputs are usable once published; review_pending means the work is done and only verification is open
DONE_FOR_DEPENDENTS = {TaskStatus.accepted, TaskStatus.partial, TaskStatus.review_pending}


class RunStatus(StrEnum):
    created = "created"
    queued = "queued"
    planning = "planning"
    running = "running"
    approval_required = "approval_required"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"
    interrupted = "interrupted"
    blocked = "blocked"


RUN_TERMINAL = {RunStatus.completed, RunStatus.partial, RunStatus.failed, RunStatus.cancelled}


class EventType(StrEnum):
    # blueprint minimum
    run_started = "run.started"
    task_started = "task.started"
    task_blocked = "task.blocked"
    message_sent = "message.sent"
    artifact_published = "artifact.published"
    check_completed = "check.completed"
    approval_requested = "approval.requested"
    run_completed = "run.completed"
    run_failed = "run.failed"
    run_cancelled = "run.cancelled"
    config_resolved = "config.resolved"
    # extensions (superset; see docs/IMPLEMENTATION_PLAN.md)
    run_created = "run.created"
    run_partial = "run.partial"
    run_interrupted = "run.interrupted"
    run_resumed = "run.resumed"
    run_forked = "run.forked"
    run_blocked = "run.blocked"
    plan_proposed = "plan.proposed"
    plan_rejected = "plan.rejected"
    plan_accepted = "plan.accepted"
    plan_milestone = "plan.milestone"
    task_created = "task.created"
    task_updated = "task.updated"
    task_ready = "task.ready"
    task_waiting = "task.waiting"
    task_review_pending = "task.review_pending"
    task_accepted = "task.accepted"
    task_partial = "task.partial"
    task_failed = "task.failed"
    task_cancelled = "task.cancelled"
    task_interrupted = "task.interrupted"
    model_called = "model.called"
    model_failed = "model.failed"
    tool_called = "tool.called"
    message_read = "message.read"
    artifact_read = "artifact.read"
    review_submitted = "review.submitted"
    approval_resolved = "approval.resolved"
    blocker_reported = "blocker.reported"
    checkpoint_saved = "checkpoint.saved"
    report_generated = "report.generated"
    budget_exceeded = "budget.exceeded"
    policy_denied = "policy.denied"
    instruction_received = "instruction.received"
    artifact_adopted = "artifact.adopted"


class Event(BaseModel):
    schema_version: Literal[1] = 1
    event_id: str
    run_id: str
    seq: int = Field(ge=1)
    recorded_at: str
    actor_id: str
    actor_kind: Literal["runtime", "agent", "human"]
    task_id: str | None = None
    causation_id: str | None = None
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    message_id: str
    run_id: str
    seq: int
    from_agent_id: str
    to_agent_id: str
    task_id: str
    purpose: MessagePurpose
    text: str = Field(min_length=1)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    reply_to: str | None = None
    recorded_at: str
    read_at: str | None = None


class ArtifactManifest(BaseModel):
    run_id: str
    artifact_id: str
    revision: int
    sha256: str
    media_type: str
    size: int
    logical_path: str
    storage_path: str
    task_id: str | None
    agent_id: str
    created_at: str
    event_id: str | None = None
    sources: list[str] = Field(default_factory=list)

    def ref(self) -> ArtifactRef:
        return ArtifactRef(artifact_id=self.artifact_id, revision=self.revision, sha256=self.sha256)


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    edited = "edited"


class Approval(BaseModel):
    approval_id: str
    run_id: str
    task_id: str | None
    agent_id: str
    action: str
    payload: dict[str, Any]
    payload_hash: str
    nonce: str
    status: ApprovalStatus = ApprovalStatus.pending
    created_at: str
    expires_at: str
    resolved_at: str | None = None
    resolution: dict[str, Any] | None = None


class ReviewResult(BaseModel):
    acceptance_id: str
    status: Literal["pass", "fail", "unverified", "blocked"]
    evidence: str = ""
    note: str = ""


class Review(BaseModel):
    target_task_id: str
    target_artifacts: list[ArtifactRef] = Field(default_factory=list)
    results: list[ReviewResult] = Field(min_length=1)
    summary: str = ""


class TaskResult(BaseModel):
    summary: str = ""
    verified: list[str] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    published: list[ArtifactRef] = Field(default_factory=list)


class Usage(BaseModel):
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    reserved_usd: float = 0.0
    wall_seconds: float = 0.0


class TaskState(BaseModel):
    run_id: str
    spec: TaskSpec
    status: TaskStatus = TaskStatus.queued
    attempt: int = 0
    revision_round: int = 0
    result: TaskResult | None = None
    blocked_reason: str | None = None
    updated_at: str
    review: Review | None = None


class DeliveryRequirement(BaseModel):
    logical_path: str = Field(min_length=1, max_length=256)
    json_schema: dict[str, Any]
    input_format: Literal["json", "text"] = "json"

    @model_serializer(mode="wrap")
    def compatible_dump(self, handler):
        data = handler(self)
        if self.input_format == "json":
            data.pop("input_format", None)  # preserve existing receipt/evidence hashes
        return data

    @field_validator('logical_path')
    @classmethod
    def valid_path(cls, value):
        path = PurePosixPath(value)
        if not path.parts or path.is_absolute() or '..' in path.parts or str(path) != value or '\\' in value or value == 'final-report.md':
            raise ValueError('delivery path must be a normalized relative artifact path')
        return value

    @field_validator('json_schema')
    @classmethod
    def bounded_schema(cls, value):
        if not value or len(json.dumps(value).encode()) > 64000:
            raise ValueError('delivery schema must be nonempty and at most 64KB')
        return value


class RunInputs(BaseModel):
    text: str = ""
    urls: list[str] = Field(default_factory=list)
    files: list[dict[str, str]] = Field(default_factory=list)  # {name, content} small text attachments
    delivery_requirements: list[DeliveryRequirement] = Field(default_factory=list, max_length=10)
    workflow: Literal["team", "document"] = "team"
    team_selection: Literal["fixed", "adaptive"] = "fixed"

    selected_agent_ids: list[str] | None = Field(default=None, min_length=1, max_length=32)

    @model_serializer(mode="wrap")
    def compatible_dump(self, handler):
        data = handler(self)
        if self.selected_agent_ids is None:
            data.pop("selected_agent_ids", None)
        if self.workflow == "team":
            data.pop("workflow", None)
        if self.team_selection == "fixed":
            data.pop("team_selection", None)
        return data

    @model_validator(mode="after")
    def document_inputs(self):
        if self.selected_agent_ids is not None:
            if self.team_selection != "fixed" or len(set(self.selected_agent_ids)) != len(self.selected_agent_ids):
                raise ValueError("selected_agent_ids requires fixed selection and unique IDs")
        if self.workflow == "document" and (
            self.urls or not (self.text.strip() or any(f.get("content", "").strip() for f in self.files))
            or len(self.delivery_requirements) != 1
        ):
            raise ValueError('document workflow requires supplied text/files, no URL inputs, and exactly one delivery contract')
        return self

    @field_validator('delivery_requirements')
    @classmethod
    def unique_delivery_paths(cls, value):
        if len({r.logical_path for r in value}) != len(value):
            raise ValueError('delivery paths must be unique')
        return value


class Run(BaseModel):
    run_id: str
    status: RunStatus
    goal: str
    inputs: RunInputs
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    config_snapshot: dict[str, Any] | None = None
    plan: TeamPlan | None = None
    usage: Usage = Field(default_factory=Usage)
    parent_run_id: str | None = None
    fork_from_seq: int | None = None
    final_report: dict[str, Any] | None = None
    blocked_reason: str | None = None
    provider_kind: str = "real"  # "real" | "fake" (tests only)


    def can_receive_instruction(self) -> bool:
        """Saving a direction never starts work or reopens accepted tasks."""
        return self.status in (RunStatus.created, RunStatus.queued, RunStatus.planning, RunStatus.running) or (
            self.plan is not None and self.status in (
                RunStatus.interrupted, RunStatus.partial, RunStatus.failed, RunStatus.cancelled, RunStatus.approval_required
            )
        )
