from __future__ import annotations

from agentteam.api.service import AppService
from agentteam.demo import DEMO_MARKER, seed_offline_demo


async def test_offline_demo_uses_real_stores_without_provider_calls(tmp_path, monkeypatch):
    # A regression guard: importing or constructing a provider registry would make
    # the first-proof path depend on a model/API key. The demo must not do that.
    import agentteam.providers.registry as registry

    def forbidden(*args, **kwargs):
        raise AssertionError("offline demo must not construct ProviderRegistry")

    monkeypatch.setattr(registry, "ProviderRegistry", forbidden)

    service = await AppService(tmp_path).start()
    try:
        run_id = await seed_offline_demo(service)
        run = await service.runs.get_run(run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.provider_kind == "demo"
        assert run.usage.model_calls == 0
        assert run.usage.tool_calls == 0
        assert run.final_report["demo_mode"] == DEMO_MARKER

        tasks = await service.runs.list_tasks(run_id)
        assert [task.spec.id for task in tasks] == ["draft", "review", "revise"]
        assert all(task.status == "accepted" for task in tasks)
        assert tasks[1].review is not None
        assert tasks[1].review.results[0].status == "fail"

        artifacts = await service.artifacts.list(run_id)
        assert {a.logical_path for a in artifacts} == {"release-note-draft.md", "release-note.md"}
        final = next(a for a in artifacts if a.logical_path == "release-note.md")
        final_text = service.artifacts.read_text(final)
        assert "no model provider was contacted" in final_text
        assert "no external publishing action was attempted" in final_text

        events = await service.events.list(run_id)
        assert events[0].type == "run.created"
        assert events[-1].type == "run.completed"
        assert all(event.payload.get("demo_mode") == DEMO_MARKER for event in events if "demo_mode" in event.payload)
        assert not any(event.type in {"model.called", "tool.called"} for event in events)
    finally:
        await service.stop()


async def test_offline_demo_is_idempotent_per_data_directory(tmp_path):
    service = await AppService(tmp_path).start()
    try:
        first = await seed_offline_demo(service)
        second = await seed_offline_demo(service)
        assert first == second
        runs = [r for r in await service.runs.list_runs() if r.provider_kind == "demo"]
        assert len(runs) == 1
    finally:
        await service.stop()
