"""Every event the runtime records must validate against schemas/event.schema.json (blueprint contract, extended enum)."""
import json

from jsonschema import Draft202012Validator, FormatChecker

from agentteam.config.loader import SCHEMA_DIR


async def test_recorded_events_validate_against_schema(harness):
    schema = json.loads((SCHEMA_DIR / "event.schema.json").read_text())
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    async with harness() as h:
        run = await h.run_goal()
        events = await h.events.list(run.run_id)
        assert len(events) > 50
        for e in events:
            v.validate(e.model_dump())
        # message.sent payloads follow the blueprint's strict sub-schema
        msgs = [e for e in events if e.type == "message.sent"]
        assert msgs and all(set(m.payload) == {"from_agent_id", "to_agent_id", "task_id", "purpose", "text", "artifact_refs", "reply_to"} for m in msgs)
