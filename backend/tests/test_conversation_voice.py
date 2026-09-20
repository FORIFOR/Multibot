"""Actual configuration/API persistence; no provider responses or generated messages."""
from pathlib import Path
import httpx
from agentteam.api.app import create_app
from agentteam.api.service import AppService
from agentteam.config.loader import effective_all
from agentteam.config.voice import ROLE_VOICES
from agentteam.runtime.context import SessionContext
from agentteam.runtime.worker import build_system_prompt
from agentteam.runtime.tools import ToolGateway, TOOL_SPECS

ROOT = Path(__file__).resolve().parents[2]
PROFILE = (ROOT / "docs/config/local-qwen35-9b-team.yaml").read_text()

async def test_voice_save_conflict_snapshot_reset_and_restart(tmp_path):
    service = AppService(tmp_path, config_yaml=PROFILE)
    app = create_app(service)
    async with app.router.lifespan_context(app):
        initial = effective_all(service.config)
        assert len({a.speech_style for a in initial.values()}) == len(initial)
        original_prompt = initial["builder"].system_prompt
        original_tools = initial["builder"].tools
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            revision = service.config_revision
            style = ROLE_VOICES["reviewer"]
            saved = await client.patch("/api/agents/builder", json={"expected_revision": revision, "speech_style": style})
            assert saved.status_code == 200
            assert saved.json()["agent"]["speech_style"] == style
            conflict = await client.patch("/api/agents/builder", json={"expected_revision": revision, "speech_style": ""})
            assert conflict.status_code == 409
            invalid = await client.patch("/api/agents/builder", json={"expected_revision": service.config_revision, "speech_style": (ROOT / "README.md").read_text()[:601]})
            assert invalid.status_code == 422
            current = effective_all(service.config)["builder"]
            assert current.system_prompt == original_prompt
            assert current.tools == original_tools
            assert current.speech_style == style
            run, _ = await service.manager.create_run((ROOT / "docs/design/brief.md").read_text())
            runtime = service.manager._build_runtime(run, service.config)
            prompt = build_system_prompt(SessionContext(runtime, runtime.agents["builder"], "task", tools=current.tools))
            assert prompt.count(style) == 1
            assert "性格を理由に事実、検証結果、権限、完了条件を変えてはいけません" in prompt
            original_schema = TOOL_SPECS['send_message'].input_schema
            import copy
            before_schema = copy.deepcopy(original_schema)
            for agent in runtime.agents.values():
                gateway = ToolGateway(SessionContext(runtime, agent, 'task', tools=agent.tools))
                specs = gateway.specs()
                assert [t.name for t in specs] == agent.tools
                messages = [t for t in specs if t.name == 'send_message']
                assert bool(messages) == ('send_message' in agent.tools)
                if messages:
                    recipients = messages[0].input_schema['properties']['to']
                    assert recipients['enum'] == [a.agent_id for a in runtime.enabled_agents()]
                    for teammate in runtime.enabled_agents():
                        assert (teammate.display_name or teammate.agent_id) in recipients['description']
                    assert agent.speech_style in messages[0].input_schema['properties']['text']['description']
                    assert messages[0].input_schema['required'] == original_schema['required']
            assert original_schema == before_schema  # no voice leaks across teammates/runs
            assert "speech_style:" in run.config_snapshot["config_yaml"]
            frozen = run.config_snapshot["config_yaml"]
    reopened = AppService(tmp_path)
    app = create_app(reopened)
    async with app.router.lifespan_context(app):
        assert effective_all(reopened.config)["builder"].speech_style == style
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            reset = await client.patch("/api/agents/builder", json={"expected_revision": reopened.config_revision, "speech_style": ""})
            assert reset.status_code == 200
            assert effective_all(reopened.config)["builder"].speech_style == ROLE_VOICES["builder"]
            detail = (await client.get(f"/api/runs/{run.run_id}")).json()
            assert detail["config_snapshot"]["config_yaml"] == frozen
