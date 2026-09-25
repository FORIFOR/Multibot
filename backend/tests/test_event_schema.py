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


async def test_event_list_returns_the_whole_log_unless_a_limit_is_given(tmp_path):
    from agentteam.runtime.redaction import Redactor
    from agentteam.store.db import Database
    from agentteam.store.event_store import EventStore
    db = await Database(tmp_path / "db.sqlite").connect()
    try:
        store = EventStore(db, Redactor())
        for i in range(1, 10006):
            await db.execute("INSERT INTO events(run_id,seq,event_id,recorded_at,actor_id,actor_kind,task_id,causation_id,type,payload_json) "
                             "VALUES (?,?,?,?,?,?,?,?,?,?)", ("run_big", i, f"ev{i}", "2026-09-26T00:00:00Z", "runtime", "runtime",
                                                             None, None, "tool.called", "{}"))
        events = await store.list("run_big")
        assert len(events) == 10005 and events[-1].seq == 10005
        assert [e.seq for e in await store.list("run_big", after_seq=10000, limit=2)] == [10001, 10002]
    finally:
        await db.close()
