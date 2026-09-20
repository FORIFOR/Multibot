"""Master planning, exception handling and final reporting. The runtime validates everything the master proposes."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..config.loader import PKG_ROOT, SCHEMA_DIR, platform_policy_text
from ..config.voice import conversation_voice, voice_instructions
from ..contracts import TaskSpec, TaskStatus, TeamPlan
from ..providers.base import LLMRequest
from ..projections.views import artifact_review_ledger
from .checks import CHECK_KINDS
from .context import SessionContext
from .policy import PolicyEngine, PolicyViolation
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


def validate_plan(plan: TeamPlan, enabled_agent_ids: list[str], agent_roles: dict[str, str], max_tasks: int,
                  *, require_review: bool = False, required_paths: list[str] | None = None) -> list[str]:
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
        if require_review and agent_roles.get(t.owner) in ("master", "reporter"):
            errors.append(f"task {t.id}: {t.owner} coordinates or reports; assign production to a builder or researcher")
        for d in t.depends_on:
            if d not in tasks:
                errors.append(f"task {t.id}: unknown dependency {d}")
            if d == t.id:
                errors.append(f"task {t.id}: depends on itself")
        if t.write_scope in scopes:
            errors.append(f"task {t.id}: write_scope {t.write_scope} duplicates task {scopes[t.write_scope]}")
        scopes[t.write_scope] = t.id
        for p in t.output_paths:
            try:
                PolicyEngine.check_write_path(p)
            except PolicyViolation as e:
                errors.append(f"task {t.id}: invalid output path {p!r}: {e}; use a relative path inside the task workspace")
            if p in outputs:
                errors.append(f"task {t.id}: output path {p} also produced by task {outputs[p]}")
            outputs[p] = t.id
            # Acceptance identifiers are verdict keys, not deliverable paths.
            # Rejecting this common model mix-up prevents a worker from being
            # trapped trying to publish a file whose name was never requested.
            if any(c.id == p for c in t.acceptance):
                errors.append(f"task {t.id}: output path {p} duplicates an acceptance id; declare the actual file path")
        if agent_roles.get(t.owner) == "reviewer" and not t.depends_on:
            errors.append(f"task {t.id}: reviewer task must depend on the task it reviews")
        if agent_roles.get(t.owner) != "reviewer" and not t.output_paths:
            errors.append(f"task {t.id}: non-reviewer task must declare at least one output path")
    for path in required_paths or []:
        if path not in outputs:
            errors.append(f"requester delivery path {path!r} is missing from task output_paths; preserve the requested file, not separate heading files")
    if require_review:
        for t in plan.tasks:
            if agent_roles.get(t.owner) == "reviewer":
                continue
            consumers = [other for other in plan.tasks if t.id in other.depends_on]
            if not consumers:
                errors.append(f"task {t.id}: final deliverables need a reviewer task depending on {t.id}")
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


def _norm_agent(name: Any, known: list[str] | None) -> str:
    """Lenient id normalisation for weaker models: 'builder (role builder, ...)' -> 'builder'."""
    s = str(name).strip()
    if known:
        for k in known:
            if s == k or s.lower().startswith(k.lower() + " ") or s.lower().startswith(k.lower() + "("):
                return k
    return s.split()[0].strip("(),:") if s else s


def plan_from_output(data: dict[str, Any], known_agents: list[str] | None = None) -> TeamPlan:
    tasks = []
    for t in data.get("tasks", []):
        acceptance = t.get("acceptance") or []
        if isinstance(acceptance, dict):
            acceptance = [acceptance]
        for i, c in enumerate(acceptance):
            if isinstance(c, dict):
                c.setdefault("id", f"{t.get('id', 't')}a{i + 1}")
                c.setdefault("check_kind", "model_review")
        tasks.append(TaskSpec(id=str(t["id"]).strip(), owner=_norm_agent(t["owner"], known_agents), objective=t["objective"],
                              depends_on=[str(d).strip() for d in (t.get("depends_on") or [])], input_artifacts=[],
                              output_paths=[str(x).strip() for x in (t.get("output_paths") or [])], acceptance=acceptance,
                              write_scope=f"workspaces/{str(t['id']).strip()}/"))
    agents = [_norm_agent(a, known_agents) for a in (data.get("agents") or [])]
    for t in tasks:  # owners must be listed
        if t.owner not in agents:
            agents.append(t.owner)
    if known_agents:
        agents = [a for a in dict.fromkeys(agents) if a in known_agents or a in {t.owner for t in tasks}]
    return TeamPlan(goal=data["goal"], assumptions=data.get("assumptions", []), agents=agents, tasks=tasks)


def _registry_text(rt) -> str:
    lines = []
    for a in rt.enabled_agents():
        lines.append(f"- {a.agent_id} (permission class {a.role}, name {a.display_name}, specialty {a.specialty}, model {a.model}): tools {', '.join(a.tools)}; skills {', '.join(s['name'] for s in a.skills) or '-'}")
    return "\n".join(lines)


def planning_message(rt) -> str:
    inp = rt.run.inputs
    lines = [f"# Request\n{rt.run.goal}"]
    if rt.run.inputs.delivery_requirements:
        lines.append('\n## Requester-owned delivery contracts\nThe runtime independently enforces these schemas on final artifacts. '
                     'Preserve every required output and constraint when planning.\n' +
                     json.dumps([r.model_dump() for r in rt.run.inputs.delivery_requirements], ensure_ascii=False))
    if inp.text:
        lines.append(f"\n## Provided text\n{inp.text[:12000]}")
    if inp.urls:
        lines.append("\n## Provided URLs\n" + "\n".join(f"- {u}" for u in inp.urls))
    if inp.files:
        lines.append("\n## Attachments (inline user input, not published artifacts or workspace files)")
        for f in inp.files:
            content = str(f.get("content", ""))
            lines.append(f"\n### {f.get('name')}\n{content[:12000]}")
            if len(content) > 12000:
                lines.append("[Attachment truncated to 12000 characters for planning; do not assume omitted content.]")
    lines.append("\n## Available agents (enabled; you may only assign these)\n" + _registry_text(rt))
    lines.append(f"\n## Limits\nmax tasks {rt.config.limits.max_tasks}; max active workers {rt.config.limits.max_active_workers}; "
                 f"model calls {rt.config.limits.max_model_calls}; budget {rt.config.limits.budget_usd} USD; "
                 f"peer messages per task across its entire lifetime {rt.config.limits.max_peer_messages_per_task}; "
                 f"reserved revision rounds {rt.config.limits.max_revision_rounds}; "
                 f"wall clock {rt.config.limits.timeout_seconds}s. Each task costs several model calls; keep the plan small.")
    lines.append("\n## Registered programmatic checks\n" + "\n".join(f"- {k}: {v}" for k, v in CHECK_KINDS.items()))
    lines.append("\n## Example of a valid plan shape (adapt ids, owners, objectives, paths and criteria to the request)\n"
                 "{\"goal\": \"...\", \"assumptions\": [\"...\"], \"agents\": [\"master\", \"builder\", \"reviewer\"], \"tasks\": [\n"
                 "  {\"id\": \"t1\", \"owner\": \"builder\", \"objective\": \"Write index.html ...\", \"depends_on\": [], \"output_paths\": [\"index.html\"],\n"
                 "   \"acceptance\": [{\"id\": \"t1a1\", \"description\": \"html_basic passes on index.html\", \"check_kind\": \"programmatic\"}]},\n"
                 "  {\"id\": \"t2\", \"owner\": \"reviewer\", \"objective\": \"Verify t1 against its criteria\", \"depends_on\": [\"t1\"], \"output_paths\": [],\n"
                 "   \"acceptance\": [{\"id\": \"t2a1\", \"description\": \"every t1 criterion has a recorded verdict\", \"check_kind\": \"programmatic\"}]}]}")
    lines.append("\n## Default plan shape (deviate only with a reason)\n"
                 "- 1 builder task that produces all requested files, then 1 reviewer task that depends on it.\n"
                 "- Add a researcher task only when external sources must be fetched or facts must be verified before building.\n"
                 "- Split builder work into parallel tasks only when the outputs are independent AND each is large; never split one small deliverable.\n"
                 "- Keep the number of tasks stable for the same kind of request; more tasks means more model calls and cost.")
    lines.append("\n## Plan rules\n"
                 "- Task ids: t1, t2, ... Each non-reviewer task declares output_paths (relative file names, e.g. brief.md, index.html).\n"
                 "- Output paths are unique across tasks. Each task gets its own workspace; write_scope is assigned by the runtime.\n"
                 "- A reviewer task lists the task it verifies in depends_on and has no output_paths (it uses submit_review).\n"
                 "- Master plans and reports; it does not own production tasks. Assign those to builder or researcher.\n"
                 "- When a reviewer is enabled, every final production task must have a reviewer depending on it. "
                 "Intermediate work can feed another production task which is then reviewed. Do not omit final review.\n"
                 "- Preserve the recipient, audience and requested action from the user’s goal. "
                 "Reference material must not replace the goal or make unrelated internal details mandatory.\n"
                 "- Acceptance criteria must cover the user’s factual constraints, not only file format. "
                 "Check claims against original inputs; do not infer missing facts from attachment names.\n"
                 "- Acceptance criteria must be checkable; prefer programmatic where a registered check fits.\n"
                 "- Record reversible choices in assumptions instead of asking the user.\n"
                 "- Nothing is published externally; drafts only. Do not plan posting, sending or paying.")
    if inp.team_selection == 'adaptive':
        lines = [line for line in lines if not line.startswith("\n## Example of a valid plan shape")
                 and not line.startswith("\n## Default plan shape")]
        lines.append("\n## Task-specific team\nThe roster above was recommended for this request. "
                     "Assign meaningful work matching each selected specialist's expertise. Do not recreate a fixed "
                     "researcher/builder/reviewer sequence or invent those agent IDs. Preserve unique ownership of files; "
                     "specialists can contribute findings before the final producer integrates them. "
                     "Use independent review where required, and let evidence-backed findings trigger corrections.")
    return "\n".join(lines)


ANY_OUTPUT = "*"  # output_paths sentinel: "at least one artifact published by this task" (single-agent runs)


async def document_plan(rt) -> TeamPlan:
    """Explicit document workflow: compile user-owned inputs; never invent model output."""
    builder = next((a for a in rt.enabled_agents() if a.role == "builder"), None)
    reviewer = next((a for a in rt.enabled_agents() if a.role == "reviewer"), None)
    if builder is None or reviewer is None or builder.agent_id == reviewer.agent_id:
        raise PlanError("document workflow requires separate enabled builder and reviewer agents")
    path = rt.run.inputs.delivery_requirements[0].logical_path
    build = TaskSpec(id="t1", owner=builder.agent_id, objective=rt.run.goal,
                     depends_on=[], output_paths=[path], write_scope="workspaces/t1/",
                     acceptance=[
                         {"id":"document_contract", "description":"The exact published revision passes the requester-owned delivery contract.", "check_kind":"programmatic"},
                         {"id":"document_language", "description":f"Original prose uses the user-requested language, defaulting to {rt.config.defaults.language}. No unintended language switching. Verbatim quotations, names, identifiers and code preserve the source. Inspect the exact saved revision; format success is not language verification.", "check_kind":"model_review"},
                         {"id":"document_request", "description":"Every content requirement in the original request is fulfilled, including requested sections and source citations. Cite the actual output for each requirement. Repeating the writing instruction is not fulfilling it. Missing required content is a failure.", "check_kind":"model_review"},
                         {"id":"document_accuracy", "description":"The requested content preserves the supplied sources, including conditions, exceptions and operation order. Conditional actions must not become unconditional steps; unsupported claims are marked unverified.", "check_kind":"model_review"}])
    review = TaskSpec(id="t2", owner=reviewer.agent_id,
                     objective="Independently compare the exact published revision with the original request and supplied sources. Check the requester contract and factual conditions. Submit an evidence-linked verdict for each producer criterion; do not infer correctness from file existence.",
                     depends_on=[build.id], output_paths=[], write_scope="workspaces/t2/",
                     acceptance=[{"id":"document_review", "description":"Every producer criterion has an independent verdict on the exact revision, with unresolved findings retained.", "check_kind":"programmatic"}])
    plan = TeamPlan(goal=rt.run.goal, assumptions=["Requester selected document workflow: one producer followed by an independent reviewer."],
                    agents=[builder.agent_id, reviewer.agent_id], tasks=[build, review])
    errors = validate_plan(plan, plan.agents, {builder.agent_id:"builder", reviewer.agent_id:"reviewer"},
                           rt.config.limits.max_tasks, require_review=True, required_paths=[path])
    if errors:
        raise PlanError("; ".join(errors))
    await rt.events.append(rt.run_id, "plan.accepted", {"tasks":[build.id,review.id], "agents":plan.agents,
                                                        "assumptions":plan.assumptions, "mode":"document"})
    return plan


async def single_agent_plan(rt) -> TeamPlan:
    """No Master call: the whole request becomes one task for the single enabled builder-role agent."""
    solo = next((a for a in rt.enabled_agents() if a.role == "builder"), None)
    if solo is None:
        raise PlanError("single-agent mode needs one enabled agent with role builder")
    others = [a.agent_id for a in rt.enabled_agents() if a.agent_id != solo.agent_id and a.role != "reporter"]
    if others:
        raise PlanError(f"single-agent mode: disable the other agents ({', '.join(others)}) or use team mode")
    inputs = rt.run.inputs
    objective = rt.run.goal
    if inputs.text:
        objective += "\n\nInput text:\n" + inputs.text
    if inputs.urls:
        objective += "\n\nInput URLs:\n" + "\n".join(f"- {u}" for u in inputs.urls)
    task = TaskSpec(id="t1", owner=solo.agent_id, objective=objective, depends_on=[], output_paths=[ANY_OUTPUT],
                    acceptance=[{"id": "s1", "description": "every deliverable the request asks for is published as an artifact",
                                 "check_kind": "model_review"}], write_scope="workspaces/t1/")
    plan = TeamPlan(goal=rt.run.goal, assumptions=["single-agent baseline: no planning call, no independent review"],
                    agents=[solo.agent_id], tasks=[task])
    await rt.events.append(rt.run_id, "plan.accepted", {"tasks": ["t1"], "agents": plan.agents, "assumptions": plan.assumptions,
                                                        "mode": "single_agent"})
    return plan


async def plan_team(rt) -> TeamPlan:
    if rt.run.inputs.team_selection == 'adaptive' and not rt.run.config_snapshot.get('team_recommendation'):
        from .team_selection import recommend_team
        await recommend_team(rt)
    master = rt.agents.get("master") or next((a for a in rt.enabled_agents() if a.role == "master"), None)
    if master is None or not master.enabled:
        raise PlanError("no enabled master agent")
    system = platform_policy_text() + "\n---\n" + master.system_prompt + voice_instructions(conversation_voice(master.role, master.speech_style)) + "\n---\n" + TEAM_COMPILER
    ctx = SessionContext(rt=rt, agent=master, mode="plan", tools=[])
    runner = AgentRunner(ctx)
    user = planning_message(rt)
    enabled = [a.agent_id for a in rt.enabled_agents()]
    roles = {a.agent_id: a.role for a in rt.enabled_agents()}
    require_review = rt.config.defaults.require_independent_review
    if require_review and not any(role == "reviewer" for role in roles.values()):
        raise PlanError("require_independent_review needs an enabled reviewer; use single mode for an unreviewed baseline")
    output_schema = deepcopy(PLAN_OUTPUT_SCHEMA)
    output_schema["properties"]["tasks"]["items"]["properties"]["owner"]["enum"] = [
        aid for aid in enabled if roles[aid] not in ("master", "reporter")]
    messages = [{"role": "user", "content": [{"type": "text", "text": user}]}]
    last_errors: list[str] = []
    for attempt in range(3):
        req = LLMRequest(model=master.model, system=system, messages=messages, tools=[], max_tokens=rt.config.limits.max_output_tokens,
                         json_schema=output_schema, effort=master.effort, metadata={"agent_id": master.agent_id, "mode": "plan"})
        try:
            resp = await runner._call_model(req, None)
        except (WorkerFailure, PolicyViolation) as e:
            raise PlanError(f"planning call failed: {e}")
        data = None
        try:
            data = _extract_json(resp.text)
            plan = plan_from_output(data, enabled)
            last_errors = validate_plan(plan, enabled, roles, rt.config.limits.max_tasks, require_review=require_review,
                                        required_paths=[r.logical_path for r in rt.run.inputs.delivery_requirements])
            if not last_errors and rt.run.inputs.team_selection == 'adaptive':
                from .communication import communication_budget_errors
                last_errors.extend(communication_budget_errors(plan, roles, set(enabled),
                    rt.config.limits.max_peer_messages_per_task, rt.config.limits.max_revision_rounds))
        except (ValueError, KeyError, TypeError) as e:
            last_errors = [f"unparseable plan: {e}"]
            plan = None
        await rt.events.append(rt.run_id, "plan.proposed", {"attempt": attempt + 1, "plan": data if isinstance(data, dict) else None,
                                                            "errors": last_errors}, actor_id=master.agent_id, actor_kind="agent")
        if plan is not None and not last_errors:
            if rt.run.inputs.team_selection == 'adaptive':
                assigned = {t.owner for t in plan.tasks}
                unused = [a.agent_id for a in rt.enabled_agents() if a.role not in ('master', 'reporter') and a.agent_id not in assigned]
                if unused:
                    last_errors = [f'Recommended specialists need meaningful assignments: {unused}. Adapt the plan to their specialties.']
        if plan is not None and not last_errors:
            if rt.run.inputs.team_selection == 'adaptive':
                # Only plans admitted with lifecycle capacity adopt the new
                # reservation contract; old saved runs retain their semantics.
                rt.run.config_snapshot = {**rt.run.config_snapshot, 'communication_budget_version': 1}
                await rt.runs.update_run(rt.run_id, config_snapshot=rt.run.config_snapshot)
            await rt.events.append(rt.run_id, "plan.accepted", {"tasks": [t.id for t in plan.tasks], "agents": plan.agents,
                                                                "assumptions": plan.assumptions})
            return plan
        await rt.events.append(rt.run_id, "plan.rejected", {"attempt": attempt + 1, "errors": last_errors})
        messages.append({"role": "assistant", "content": [{"type": "text", "text": resp.text}]})
        messages.append({"role": "user", "content": [{"type": "text", "text": "The runtime rejected this plan:\n- " + "\n- ".join(last_errors)
                                                      + "\nReturn a corrected plan."}]})
    raise PlanError("plan rejected 3 times: " + "; ".join(last_errors))


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
    system += voice_instructions(conversation_voice(agent.role, agent.speech_style))
    ctx = SessionContext(rt=rt, agent=agent, mode="report", tools=[])
    runner = AgentRunner(ctx)
    user = ("Write the final report strictly from this evidence. Do not upgrade 'started' or 'unverified' to 'done'. "
            "Reference only artifact ids/revisions that appear in the evidence. "
            "Reviews apply only to the exact id/revision/sha256 in target_artifacts. A task's historical review "
            "does not reject or approve its newer artifacts. unreviewed means neither passed nor failed. "
            "The following runtime ledger is authoritative for current revision review coverage:\n"
            + json.dumps(artifact_review_ledger(evidence), ensure_ascii=False)
            + "\n\nEvidence (may be truncated):\n" + json.dumps(evidence, ensure_ascii=False, indent=1)[:40000])
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


async def milestone_replan(rt, round_no: int) -> dict[str, Any]:
    """After the current DAG finishes: the Master judges completeness against the goal and may add tasks.
    Returns {"added": [task ids], "verdict": str}. Runtime validation still applies to every created task."""
    master = rt.agents.get("master")
    if master is None or not master.enabled:
        return {"added": [], "verdict": "no master"}
    before = set(rt.tasks)
    ctx = SessionContext(rt=rt, agent=master, mode="milestone",
                         tools=["list_artifacts", "read_artifact", "create_task", "update_task", "read_messages", "finish_task"])
    arts = await rt.artifacts.list(rt.run_id, latest_only=True)
    lines = [f"# Milestone review {round_no} — goal: {rt.run.goal}"]
    if rt.run.plan and rt.run.plan.assumptions:
        lines.append("Assumptions: " + "; ".join(rt.run.plan.assumptions))
    lines.append("\n## Tasks")
    for t in rt.tasks.values():
        lines.append(f"- {t.spec.id} [{t.status}] {t.spec.owner}: {t.spec.objective[:160]}"
                     + (f" — result: {t.result.summary[:200]}" if t.result and t.result.summary else "")
                     + (f" — unverified: {'; '.join(t.result.unverified)[:200]}" if t.result and t.result.unverified else "")
                     + (f" — next: {'; '.join(t.result.next_steps)[:200]}" if t.result and t.result.next_steps else ""))
    lines.append("\n## Published artifacts")
    lines += [f"- {m.artifact_id} r{m.revision} ({m.media_type}, {m.size}B) by {m.agent_id}/{m.task_id}" for m in arts] or ["(none)"]
    sessions = int(rt.policy.remaining_budget() // max(rt.config.limits.max_session_cost_usd, 0.01))
    lines.append(f"\n## Remaining budget\nmodel calls {rt.config.limits.max_model_calls - rt.policy.usage.model_calls}, "
                 f"USD {rt.policy.remaining_budget():.2f} (about {sessions} agent session(s) at the per-session cap of "
                 f"{rt.config.limits.max_session_cost_usd:.2f} USD; a task with a revision round needs two), "
                 f"wall clock {int(rt.remaining_seconds())}s, task slots {rt.config.limits.max_tasks - len(rt.tasks)}.")
    lines.append("\nDecide whether the goal's deliverables are complete and verified. If something the user asked for is "
                 "missing, unverified, or a task ended partial, create the minimal additional tasks with create_task "
                 "(depends_on may reference accepted tasks; give each task acceptance criteria; add a reviewer task when "
                 "something worth verifying is produced). Only add tasks the remaining budget can finish — a task that starts and "
                 "fails on budget leaves the run partial; if the budget cannot cover the missing work, add nothing and say "
                 "so in the verdict. If every requested deliverable is accepted and only wording or polish remains, add "
                 "nothing. Do not re-do accepted work. Then call finish_task with a one-line verdict.")
    runner = AgentRunner(ctx)
    out = await runner.run("\n".join(lines))
    added = sorted(set(rt.tasks) - before)
    await rt.events.append(rt.run_id, "plan.milestone", {"round": round_no, "added_tasks": added, "verdict": out.detail[:500],
                                                          "outcome": out.kind}, actor_id=master.agent_id, actor_kind="agent")
    return {"added": added, "verdict": out.detail}
