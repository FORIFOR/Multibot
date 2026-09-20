"""Required task handoffs, shared by model instructions and the tool boundary."""
from .context import SessionContext


def task_communication_targets(spec, tasks, roles, enabled) -> list[str]:
    """One dependency rule for planning feasibility and actual delivery."""
    if roles.get(spec.owner) == "reviewer":
        peers = {tasks[t].owner for t in spec.depends_on if t in tasks}
    else:
        peers = {t.owner for t in tasks.values() if spec.id in t.depends_on}
        if not peers:
            peers = {tasks[t].owner for t in spec.depends_on if t in tasks}
    return sorted(p for p in peers if p != spec.owner and p in enabled)


def communication_budget_errors(plan, roles, enabled, limit, revision_rounds) -> list[str]:
    """Reserve compulsory deliveries, without increasing an approved limit.

    One coordinator delivery may be charged to any task of an owner. Reserve
    one there conservatively. Optional questions/findings need further capacity.
    """
    tasks = {t.id: t for t in plan.tasks}
    errors = []
    for spec in plan.tasks:
        targets = task_communication_targets(spec, tasks, roles, enabled)
        reviewer = roles.get(spec.owner) == 'reviewer'
        reviewed = any(
            spec.id in t.depends_on and roles.get(t.owner) == 'reviewer' for t in plan.tasks)
        # Targets can fail in different rounds; do not assume their revisions
        # will always be batched into the same review session.
        rounds = (revision_rounds * sum(
            t in tasks and roles.get(tasks[t].owner) != 'reviewer'
            for t in spec.depends_on)) if reviewer else (revision_rounds if reviewed else 0)
        sessions = 1 + rounds
        required = 1 + len(targets) * sessions
        if required > limit:
            errors.append(f'task {spec.id}: communication budget {limit} cannot cover '
                          f'{required} reserved messages (1 coordinator delivery + '
                          f'{len(targets)} recipients x {sessions} sessions). '
                          'Simplify the dependency/owner plan within the configured budget; '
                          'do not omit required reviews, change limits, or claim completion.')
    return errors


def communication_targets(ctx: SessionContext) -> list[str]:
    if ctx.mode != "task" or ctx.task is None:
        return []
    return task_communication_targets(ctx.task.spec,
        {key: task.spec for key, task in ctx.rt.tasks.items()},
        {key: agent.role for key, agent in ctx.rt.agents.items()},
        {key for key, agent in ctx.rt.agents.items() if agent.enabled})


def future_handoff_reserve(rt, task) -> int:
    """Compulsory deliveries after this session, using persisted round usage."""
    spec = task.spec
    roles = {key: agent.role for key, agent in rt.agents.items()}
    tasks = {key: value.spec for key, value in rt.tasks.items()}
    targets = task_communication_targets(spec, tasks, roles,
        {key for key, agent in rt.agents.items() if agent.enabled})
    def remaining(task_id):
        return max(0, rt.config.limits.max_revision_rounds - rt.policy.revision_rounds.get(task_id, 0))
    if roles.get(spec.owner) == 'reviewer':
        rounds = sum(remaining(t) for t in spec.depends_on
                     if t in tasks and roles.get(tasks[t].owner) != 'reviewer')
    else:
        reviewed = any(spec.id in t.depends_on and roles.get(t.owner) == 'reviewer' for t in tasks.values())
        rounds = remaining(spec.id) if reviewed else 0
    return len(targets) * rounds


def coordination_targets(ctx: SessionContext) -> list[str]:
    return sorted({t.spec.owner for t in ctx.rt.tasks.values()
                   if t.spec.owner != ctx.agent.agent_id
                   and t.spec.owner in ctx.rt.agents and ctx.rt.agents[t.spec.owner].enabled})


async def delivered_coordination(ctx: SessionContext) -> set[str]:
    """Use persisted deliveries, not a claimed finish or an in-memory flag."""
    messages = await ctx.rt.runs.list_messages(ctx.rt.run_id)
    return {m.to_agent_id for m in messages
            if m.from_agent_id == ctx.agent.agent_id
            and m.purpose in {'handoff', 'decision'}
            and m.task_id in ctx.rt.tasks
            and ctx.rt.tasks[m.task_id].spec.owner == m.to_agent_id}


async def complete_delivered_coordination(ctx: SessionContext) -> bool:
    """End only the dispatch phase when its actual persisted deliveries exist.

    A model's extra acknowledgement is not required after sending every handoff.
    This does not finish any production task or judge an artifact's correctness.
    """
    if ctx.mode != 'coordination' or ctx.blocked or ctx.approval_pending:
        return False
    targets = set(coordination_targets(ctx))
    if not targets or targets - await delivered_coordination(ctx):
        return False
    from ..contracts import TaskResult
    ctx.finished = TaskResult(summary='Coordinator handoffs verified in persisted delivery records')
    return True


async def coordinate_team(rt):
    from .worker import AgentRunner, SessionOutcome
    import json
    master = next((a for a in rt.enabled_agents() if a.role == 'master'), None)
    if master is None:
        return SessionOutcome('blocked', 'communication_configuration: no enabled coordinator')
    tools = [name for name in ('send_message', 'finish_task', 'report_blocker') if name in master.tools]
    ctx = SessionContext(rt, master, 'coordination', tools=tools)
    remaining = set(coordination_targets(ctx)) - await delivered_coordination(ctx)
    if not remaining:
        return SessionOutcome('finished', 'Existing coordinator deliveries verified')
    if 'send_message' not in tools or 'finish_task' not in tools:
        return SessionOutcome('blocked', 'communication_configuration: coordinator needs send_message and finish_task')
    tasks = [{'task_id': t.spec.id, 'owner': t.spec.owner, 'status': str(t.status),
              'objective': t.spec.objective, 'depends_on': t.spec.depends_on,
              'output_paths': t.spec.output_paths} for t in rt.tasks.values()]
    prompt = ('計画の担当者へ、あなたの話し方で短い依頼を届けてください。新しい計画や成果物は作りません。'
              'あなたは依頼を配る立場です。受信者の一人称を演じず、相手の個人名を使って仕事を依頼してください。'
              '各宛先へsend_messageを1回使い、purpose=handoff、task_idはその宛先が担当する実在の作業IDにしてください。'
              '担当する結果、依存する入力、未確認事項と次の行動を具体的に伝えます。完了した作業をやり直すよう命じないでください。'
              '原添付は各担当の作業入力へ渡されます。この依頼配布で添付を読み直す必要はありません。'
              '原添付と予定成果物の名前は本文に記載し、未公開ファイルやrevision=0をartifact_refsへ入れないでください。'
              '全員へ送信したらfinish_task。返信待ちや挨拶だけの発言は不要です。複数の送信を同じ応答で呼べます。\n'
              + '未送信の宛先: ' + ', '.join(sorted(remaining)) + '\n依頼: ' + rt.run.goal
              + '\n確定計画: ' + json.dumps(tasks, ensure_ascii=False))
    await rt.events.append(rt.run_id, 'task.updated', {'mode': 'coordination', 'state': 'started', 'recipients': sorted(remaining)}, actor_id=master.agent_id, actor_kind='agent')
    outcome = await AgentRunner(ctx).run(prompt)
    await rt.events.append(rt.run_id, 'task.updated', {'mode': 'coordination', 'state': outcome.kind, 'detail': outcome.detail}, actor_id=master.agent_id, actor_kind='agent')
    return outcome
