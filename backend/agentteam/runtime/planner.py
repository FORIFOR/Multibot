"""Master planning, exception handling and final reporting. The runtime validates everything the master proposes."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..config.loader import PKG_ROOT, SCHEMA_DIR, platform_policy_text
from ..contracts import TaskSpec, TaskStatus, TeamPlan
from ..providers.base import LLMRequest
from .checks import CHECK_KINDS
from .context import SessionContext
from .policy import PolicyViolation
from .worker import AgentRunner, WorkerFailure

TEAM_COMPILER = (PKG_ROOT / "prompts" / "team-compiler.md").read_text(encoding="utf-8")

# Structured-output schema for the model (subset of JSON Schema features). Strict validation happens afterwards.
PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "agents": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "owner": {"type": "string"},
                "objective": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "output_paths": {"type": "array", "items": {"type": "string"}},
                "acceptance": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "description": {"type": "string"},
                                   "check_kind": {"type": "string", "enum": ["programmatic", "source_check", "human_review", "model_review"]}},
                    "required": ["id", "description", "check_kind"], "additionalProperties": False}},
            },
            "required": ["id", "owner", "objective", "depends_on", "output_paths", "acceptance"],
            "additionalProperties": False}},
    },
    "required": ["goal", "assumptions", "agents", "tasks"],
    "additionalProperties": False,
}

REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "deliverables": {"type": "array", "items": {"type": "object", "properties": {
            "artifact_id": {"type": "string"}, "revision": {"type": "integer"}, "note": {"type": "string"}},
            "required": ["artifact_id", "revision", "note"], "additionalProperties": False}},
        "verified": {"type": "array", "items": {"type": "string"}},
        "unresolved": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "deliverables", "verified", "unresolved", "next_steps"],
    "additionalProperties": False,
}


class PlanError(ValueError):
    pass


def _strict_schema() -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / "team-plan.schema.json").read_text(encoding="utf-8"))


def validate_plan(plan: TeamPlan, enabled_agent_ids: list[str], agent_roles: dict[str, str], max_tasks: int) -> list[str]:
    errors: list[str] = []
    v = Draft202012Validator(_strict_schema(), format_checker=FormatChecker())
    for e in v.iter_errors(plan.model_dump(mode="json")):
        errors.append(f"schema: {e.message} at {'/'.join(str(p) for p in e.path)}")
    tasks = {t.id: t for t in plan.tasks}
    if len(tasks) != len(plan.tasks):
        errors.append("duplicate task ids")
    if len(plan.tasks) > max_tasks:
        errors.append(f"too many tasks ({len(plan.tasks)} > {max_tasks})")
    for a in plan.agents:
        if a not in enabled_agent_ids:
            errors.append(f"agent {a} is not enabled")
    scopes: dict[str, str] = {}
    outputs: dict[str, str] = {}
    for t in plan.tasks:
        if t.owner not in enabled_agent_ids:
            errors.append(f"task {t.id}: unknown or disabled owner {t.owner}")
        if t.owner not in plan.agents:
            errors.append(f"task {t.id}: owner {t.owner} not listed in plan.agents")
        for d in t.depends_on:
            if d not in tasks:
                errors.append(f"task {t.id}: unknown dependency {d}")
            if d == t.id:
                errors.append(f"task {t.id}: depends on itself")
        if t.write_scope in scopes:
            errors.append(f"task {t.id}: write_scope {t.write_scope} duplicates task {scopes[t.write_scope]}")
        scopes[t.write_scope] = t.id
        for p in t.output_paths:
            if p in outputs:
                errors.append(f"task {t.id}: output path {p} also produced by task {outputs[p]}")
            outputs[p] = t.id
        if agent_roles.get(t.owner) == "reviewer" and not t.depends_on:
            errors.append(f"task {t.id}: reviewer task must depend on the task it reviews")
        if agent_roles.get(t.owner) != "reviewer" and not t.output_paths:
            errors.append(f"task {t.id}: non-reviewer task must declare at least one output path")
    # cycles
    state: dict[str, int] = {}

    def visit(tid: str) -> None:
        if state.get(tid) == 1:
            raise PlanError(f"cyclic dependency at {tid}")
        if state.get(tid) == 2:
            return
        state[tid] = 1
        for d in tasks[tid].depends_on:
            if d in tasks:
                visit(d)
        state[tid] = 2

    try:
        for tid in tasks:
            visit(tid)
    except PlanError as e:
        errors.append(str(e))
    return errors


def plan_from_output(data: dict[str, Any]) -> TeamPlan:
    tasks = []
    for t in data.get("tasks", []):
        tasks.append(TaskSpec(id=t["id"], owner=t["owner"], objective=t["objective"], depends_on=t.get("depends_on", []),
                              input_artifacts=[], output_paths=t.get("output_paths", []), acceptance=t["acceptance"],
                              write_scope=f"workspaces/{t['id']}/"))
    return TeamPlan(goal=data["goal"], assumptions=data.get("assumptions", []), agents=data.get("agents", []), tasks=tasks)


def _registry_text(rt) -> str:
    lines = []
    for a in rt.enabled_agents():
        lines.append(f"- {a.agent_id} (role {a.role}, model {a.model}): tools {', '.join(a.tools)}; skills {', '.join(s['name'] for s in a.skills) or '-'}")
    return "\n".join(lines)


def planning_message(rt) -> str:
    inp = rt.run.inputs
    lines = [f"# Request\n{rt.run.goal}"]
    if inp.text:
        lines.append(f"\n## Provided text\n{inp.text[:12000]}")
    if inp.urls:
        lines.append("\n## Provided URLs\n" + "\n".join(f"- {u}" for u in inp.urls))
    if inp.files:
        lines.append("\n## Attachments\n" + "\n".join(f"- {f.get('name')} ({len(str(f.get('content','')))} chars)" for f in inp.files))
    lines.append("\n## Available agents (enabled; you may only assign these)\n" + _registry_text(rt))
    lines.append(f"\n## Limits\nmax tasks {rt.config.limits.max_tasks}; max active workers {rt.config.limits.max_active_workers}; "
                 f"model calls {rt.config.limits.max_model_calls}; budget {rt.config.limits.budget_usd} USD; "
                 f"wall clock {rt.config.limits.timeout_seconds}s. Each task costs several model calls; keep the plan small.")
    lines.append("\n## Registered programmatic checks\n" + "\n".join(f"- {k}: {v}" for k, v in CHECK_KINDS.items()))
    lines.append("\n## Plan rules\n"
                 "- Task ids: t1, t2, ... Each non-reviewer task declares output_paths (relative file names, e.g. brief.md, index.html).\n"
                 "- Output paths are unique across tasks. Each task gets its own workspace; write_scope is assigned by the runtime.\n"
                 "- A reviewer task lists the task it verifies in depends_on and has no output_paths (it uses submit_review).\n"
                 "- Use the reviewer only when there is something worth verifying. For a trivial request use one task.\n"
                 "- Acceptance criteria must be checkable; prefer programmatic where a registered check fits.\n"
                 "- Record reversible choices in assumptions instead of asking the user.\n"
                 "- Nothing is published externally; drafts only. Do not plan posting, sending or paying.")
    return "\n".join(lines)


async def plan_team(rt) -> TeamPlan:
    master = rt.agents.get("master") or next((a for a in rt.enabled_agents() if a.role == "master"), None)
    if master is None or not master.enabled:
        raise PlanError("no enabled master agent")
    system = platform_policy_text() + "\n---\n" + master.system_prompt + "\n---\n" + TEAM_COMPILER
    ctx = SessionContext(rt=rt, agent=master, mode="plan", tools=[])
    runner = AgentRunner(ctx)
    user = planning_message(rt)
    enabled = [a.agent_id for a in rt.enabled_agents()]
    roles = {a.agent_id: a.role for a in rt.enabled_agents()}
    messages = [{"role": "user", "content": [{"type": "text", "text": user}]}]
    last_errors: list[str] = []
    for attempt in range(2):
        req = LLMRequest(model=master.model, system=system, messages=messages, tools=[], max_tokens=rt.config.limits.max_output_tokens,
                         json_schema=PLAN_OUTPUT_SCHEMA, effort=master.effort, metadata={"agent_id": master.agent_id, "mode": "plan"})
        try:
            resp = await runner._call_model(req, None)
        except (WorkerFailure, PolicyViolation) as e:
            raise PlanError(f"planning call failed: {e}")
        try:
            data = _extract_json(resp.text)
            plan = plan_from_output(data)
            last_errors = validate_plan(plan, enabled, roles, rt.config.limits.max_tasks)
        except (ValueError, KeyError, TypeError) as e:
            last_errors = [f"unparseable plan: {e}"]
            plan = None
        await rt.events.append(rt.run_id, "plan.proposed", {"attempt": attempt + 1, "plan": data if isinstance(data, dict) else None,
                                                            "errors": last_errors}, actor_id=master.agent_id, actor_kind="agent")
        if plan is not None and not last_errors:
            await rt.events.append(rt.run_id, "plan.accepted", {"tasks": [t.id for t in plan.tasks], "agents": plan.agents,
                                                                "assumptions": plan.assumptions})
            return plan
        await rt.events.append(rt.run_id, "plan.rejected", {"attempt": attempt + 1, "errors": last_errors})
        messages.append({"role": "assistant", "content": [{"type": "text", "text": resp.text}]})
        messages.append({"role": "user", "content": [{"type": "text", "text": "The runtime rejected this plan:\n- " + "\n- ".join(last_errors)
                                                      + "\nReturn a corrected plan."}]})
    raise PlanError("plan rejected twice: " + "; ".join(last_errors))


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


async def handle_exception(rt, task, outcome_kind: str, detail: str) -> str | None:
    """Master decides what to do with a failed/blocked task via create_task/update_task. Returns a summary."""
    master = rt.agents.get("master")
    if master is None or not master.enabled:
        return None
    ctx = SessionContext(rt=rt, agent=master, mode="exception", tools=["update_task", "create_task", "send_message",
                                                                        "read_messages", "read_artifact", "list_artifacts",
                                                                        "finish_task"], causation_id=None)
    published = [m for m in await rt.artifacts.list(rt.run_id, latest_only=True)]
    msg = (f"# Exception on task {task.spec.id} (owner {task.spec.owner}, attempt {task.attempt})\n"
           f"Outcome: {outcome_kind}\nDetail: {detail}\n\nObjective: {task.spec.objective}\n"
           f"Task states: " + ", ".join(f"{t.spec.id}={t.status}" for t in rt.tasks.values()) + "\n"
           f"Published artifacts: " + (", ".join(f"{m.artifact_id}@r{m.revision}" for m in published) or "none") + "\n"
           f"Remaining: model calls {rt.config.limits.max_model_calls - rt.policy.usage.model_calls}, "
           f"budget {rt.config.limits.budget_usd - rt.policy.usage.cost_usd:.3f} USD, wall clock {int(rt.remaining_seconds())}s.\n\n"
           "Decide with ONE update_task call (retry / accept_partial / cancel) and optionally create_task, then finish_task. "
           "Do not retry the same failure without a change; if information from the human is required, accept_partial and say what is needed.")
    runner = AgentRunner(ctx)
    out = await runner.run(msg)
    return out.detail


async def final_report(rt, evidence: dict[str, Any]) -> dict[str, Any] | None:
    reporter = rt.agents.get("reporter")
    agent = reporter if (reporter and reporter.enabled) else rt.agents.get("master")
    if agent is None or not agent.enabled:
        return None
    if rt.config.limits.max_model_calls - rt.policy.usage.model_calls < 1:
        return None
    system = platform_policy_text() + "\n---\n" + (agent.system_prompt if agent.role == "reporter" else
                                                 (PKG_ROOT / "prompts" / "reporter.md").read_text(encoding="utf-8"))
    ctx = SessionContext(rt=rt, agent=agent, mode="report", tools=[])
    runner = AgentRunner(ctx)
    user = ("Write the final report strictly from this evidence. Do not upgrade 'started' or 'unverified' to 'done'. "
            "Reference only artifact ids/revisions that appear in the evidence.\n\n" + json.dumps(evidence, ensure_ascii=False, indent=1)[:40000])
    req = LLMRequest(model=agent.model, system=system, messages=[{"role": "user", "content": [{"type": "text", "text": user}]}],
                     tools=[], max_tokens=4000, json_schema=REPORT_SCHEMA, effort="low" if agent.effort is None else agent.effort,
                     metadata={"agent_id": agent.agent_id, "mode": "report"})
    try:
        resp = await runner._call_model(req, None)
        data = _extract_json(resp.text)
    except (WorkerFailure, PolicyViolation, ValueError) as e:
        await rt.events.append(rt.run_id, "model.failed", {"stage": "report", "message": str(e)}, actor_id=agent.agent_id, actor_kind="agent")
        return None
    known = {(m.artifact_id, m.revision) for m in await rt.artifacts.list(rt.run_id)}
    data["deliverables"] = [d for d in data.get("deliverables", []) if (d.get("artifact_id"), d.get("revision")) in known]
    data["author"] = agent.agent_id
    return data
