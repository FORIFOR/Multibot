"""Deterministic, provider-free demo data for the first 30 seconds.

The demo writes through the same RunStore, EventStore and ArtifactStore used by
real runs.  It never constructs a provider registry and never starts execution.
That keeps the first-run experience truthful: the UI is real; the work record is
synthetic and explicitly labelled as such.
"""
from __future__ import annotations

from .contracts import (
    AcceptanceCriterion,
    Review,
    ReviewResult,
    Run,
    RunInputs,
    RunStatus,
    TaskResult,
    TaskSpec,
    TaskState,
    TaskStatus,
    TeamPlan,
    Usage,
)
from .ids import new_id, now_iso

DEMO_GOAL = "Turn a short release brief into a reviewed launch note."
DEMO_MARKER = "synthetic_offline_demo"


async def seed_offline_demo(service) -> str:
    """Create one completed synthetic run and return its id.

    Reuses an existing demo run in the same data directory so repeated
    `agentteam demo` launches stay quiet and predictable.
    """
    for existing in await service.runs.list_runs(limit=100):
        if existing.provider_kind == "demo" and existing.final_report and existing.final_report.get("demo_mode") == DEMO_MARKER:
            return existing.run_id

    run_id = new_id("demo")
    ts = now_iso()
    draft_spec = TaskSpec(
        id="draft",
        owner="writer",
        objective="Draft a concise release note from the supplied brief.",
        output_paths=["release-note-draft.md"],
        acceptance=[AcceptanceCriterion(id="clear", description="Explains the change and the boundary without invented claims.", check_kind="human_review")],
        write_scope="artifacts only",
    )
    review_spec = TaskSpec(
        id="review",
        owner="reviewer",
        objective="Review the draft against the acceptance criterion.",
        depends_on=["draft"],
        acceptance=[AcceptanceCriterion(id="evidence", description="Every claim is supported by the supplied brief.", check_kind="human_review")],
        write_scope="review only",
    )
    revise_spec = TaskSpec(
        id="revise",
        owner="writer",
        objective="Apply the review and publish the final note.",
        depends_on=["review"],
        output_paths=["release-note.md"],
        acceptance=[AcceptanceCriterion(id="final", description="The final note keeps the review correction.", check_kind="human_review")],
        write_scope="artifacts only",
    )
    plan = TeamPlan(schema_version=1, goal=DEMO_GOAL, assumptions=["Synthetic offline demonstration; no model was called."], agents=["writer", "reviewer"], tasks=[draft_spec, review_spec, revise_spec])
    run = Run(
        run_id=run_id,
        status=RunStatus.completed,
        goal=DEMO_GOAL,
        inputs=RunInputs(text="Synthetic brief: announce a local-first demo. Do not claim customer adoption or production deployment."),
        created_at=ts,
        started_at=ts,
        finished_at=ts,
        plan=plan,
        usage=Usage(model_calls=0, tool_calls=0, cost_usd=0.0),
        provider_kind="demo",
        final_report={
            "demo_mode": DEMO_MARKER,
            "summary": "A synthetic brief was drafted, reviewed, corrected and published without contacting a model provider.",
            "verified": ["No provider/model call was made by the demo seeder.", "The final artifact includes the requested limitation."],
            "unverified": ["No external publishing or customer workflow was attempted."],
        },
    )
    await service.runs.create_run(run)
    await service.events.append(run_id, "run.created", {"demo_mode": DEMO_MARKER, "provider_calls": 0, "external_actions": 0})
    await service.events.append(run_id, "run.started", {"demo_mode": DEMO_MARKER})
    await service.events.append(run_id, "plan.accepted", {"task_ids": ["draft", "review", "revise"], "demo_mode": DEMO_MARKER})

    await service.runs.upsert_task(TaskState(run_id=run_id, spec=draft_spec, status=TaskStatus.accepted, attempt=1, result=TaskResult(summary="Draft produced from the synthetic brief."), updated_at=ts))
    await service.events.append(run_id, "task.started", {"attempt": 1, "demo_mode": DEMO_MARKER}, actor_id="writer", actor_kind="agent", task_id="draft")
    draft = await service.artifacts.publish(
        run_id,
        "release-note-draft.md",
        b"# Agent Team demo\n\nA local-first demo shows the draft -> review -> revise work record.\n\nThis is a synthetic example.\n",
        agent_id="writer",
        task_id="draft",
        sources=["synthetic-demo-brief"],
    )
    draft_event = await service.events.append(run_id, "artifact.published", {"artifact_id": draft.artifact_id, "revision": draft.revision, "sha256": draft.sha256, "logical_path": draft.logical_path, "demo_mode": DEMO_MARKER}, actor_id="writer", actor_kind="agent", task_id="draft")
    await service.artifacts.set_event(run_id, draft.artifact_id, draft.revision, draft_event.event_id)
    await service.events.append(run_id, "task.accepted", {"artifact_refs": [draft.ref().model_dump()], "demo_mode": DEMO_MARKER}, actor_id="runtime", task_id="draft")

    review = Review(
        target_task_id="draft",
        target_artifacts=[draft.ref()],
        results=[ReviewResult(acceptance_id="clear", status="fail", evidence="The first draft did not explicitly say that no external publishing occurred.", note="Add the execution boundary before publishing the final note.")],
        summary="One boundary statement is missing; revise before accepting the deliverable.",
    )
    await service.runs.upsert_task(TaskState(run_id=run_id, spec=review_spec, status=TaskStatus.accepted, attempt=1, result=TaskResult(summary="Review found one concrete boundary omission."), review=review, updated_at=ts))
    await service.events.append(run_id, "task.started", {"attempt": 1, "demo_mode": DEMO_MARKER}, actor_id="reviewer", actor_kind="agent", task_id="review")
    await service.events.append(run_id, "review.submitted", {"target_task_id": "draft", "results": [r.model_dump() for r in review.results], "summary": review.summary, "demo_mode": DEMO_MARKER}, actor_id="reviewer", actor_kind="agent", task_id="review")
    await service.events.append(run_id, "task.accepted", {"demo_mode": DEMO_MARKER}, task_id="review")

    final_text = (
        "# Agent Team demo\n\n"
        "A local-first demo shows the draft -> review -> revise work record in the real Agent Team UI.\n\n"
        "This record is synthetic: no model provider was contacted and no external publishing action was attempted.\n"
    ).encode()
    final = await service.artifacts.publish(run_id, "release-note.md", final_text, agent_id="writer", task_id="revise", sources=[f"artifact:{draft.artifact_id}:r{draft.revision}", "review:clear"])
    await service.runs.upsert_task(TaskState(run_id=run_id, spec=revise_spec, status=TaskStatus.accepted, attempt=1, revision_round=1, result=TaskResult(summary="Review correction applied.", verified=["Execution boundary is explicit."], published=[final.ref()]), updated_at=ts))
    await service.events.append(run_id, "task.started", {"attempt": 1, "revision_round": 1, "demo_mode": DEMO_MARKER}, actor_id="writer", actor_kind="agent", task_id="revise")
    final_event = await service.events.append(run_id, "artifact.published", {"artifact_id": final.artifact_id, "revision": final.revision, "sha256": final.sha256, "logical_path": final.logical_path, "sources": final.sources, "demo_mode": DEMO_MARKER}, actor_id="writer", actor_kind="agent", task_id="revise")
    await service.artifacts.set_event(run_id, final.artifact_id, final.revision, final_event.event_id)
    await service.events.append(run_id, "check.completed", {"acceptance_id": "final", "status": "pass", "evidence": "Final artifact explicitly states the execution boundary.", "demo_mode": DEMO_MARKER}, actor_id="reviewer", actor_kind="agent", task_id="revise")
    await service.events.append(run_id, "task.accepted", {"artifact_refs": [final.ref().model_dump()], "demo_mode": DEMO_MARKER}, task_id="revise")
    await service.events.append(run_id, "report.generated", {"verified": 2, "unverified": 1, "model_calls": 0, "external_actions": 0, "demo_mode": DEMO_MARKER})
    await service.events.append(run_id, "run.completed", {"status": "completed", "demo_mode": DEMO_MARKER})
    return run_id
