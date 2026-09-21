"""ToolGateway: the only way an agent touches the world. Every call is authorized, counted and recorded."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..config.loader import read_skill_body
from ..contracts import (Approval, ApprovalStatus, ArtifactRef, Review, ReviewResult, TaskResult, TaskSpec,
                         TaskStatus)
from ..ids import new_id, now_iso, now_utc
from ..providers.base import ToolSpec
from .checks import CHECK_KINDS, run_check
from .delivery import verify_delivery, failures, unpublished_workspace_changes
from .context import SessionContext
from .policy import PolicyViolation
from .review_targets import latest_task_refs, same_refs
from .sandbox import run_command
from .webtools import FetchDenied, web_fetch, web_search

PURPOSES = ["request", "question", "answer", "handoff", "finding", "decision"]

_REF = {"type": "object", "properties": {"artifact_id": {"type": "string"}, "revision": {"type": "integer", "minimum": 1},
                                         "sha256": {"type": "string"}}, "required": ["artifact_id", "revision"]}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


def _delivery_repair_hint(schema: dict[str, Any], result: dict[str, Any]) -> str:
    """Keep schema repair feedback actionable when a model has little context left.

    The full validator output remains recorded as evidence. This short, stable
    hint is only a prompt aid; it never changes the validator verdict.
    """
    if result.get("status") == "pass":
        return ""
    return ("Read the recorded validation problems and the requester schema. Revise only your own outputs, "
            "preserve source facts, publish a new revision and check that exact revision. "
            "Do not replace or weaken the schema. Reviewers must report findings instead of editing another task's output.")



TOOL_SPECS: dict[str, ToolSpec] = {
    'read_input_file': ToolSpec('read_input_file', 'Read an original user attachment by exact name. These are input sources, not published artifacts and have no revision. Returns source hash and a bounded character range.',
        _obj({'name': {'type': 'string'}, 'start_char': {'type': 'integer', 'minimum': 0},
              'max_chars': {'type': 'integer', 'minimum': 1, 'maximum': 20000}}, ['name'])),
    "read_skill": ToolSpec("read_skill", "Load the full body of one of your enabled skills by name.",
                           _obj({"name": {"type": "string"}}, ["name"])),
    "finish_task": ToolSpec("finish_task",
                            "Finish your current task. Call only after all output paths are published. "
                            "State what you verified and what remains unverified. Only summary is required. "
                            "verified/unverified/next_steps are arrays of strings, never review-result objects.",
                            _obj({"summary": {"type": "string"}, "verified": {"type": "array", "items": {"type": "string"}},
                                  "unverified": {"type": "array", "items": {"type": "string"}},
                                  "next_steps": {"type": "array", "items": {"type": "string"}}}, ["summary"])),
    "send_message": ToolSpec("send_message",
                             "Deliver a message to another agent's mailbox. Purposes: request, question, answer, handoff, "
                             "finding, decision. Do not send acknowledgements or encouragement. Reference artifacts by id/revision instead of pasting them. "
                             "request queues an assignment for the recipient's scheduled work; it does not start a reply or transfer task ownership. "
                             "Use question for a specific answer needed now, not to delegate rewriting your own output. "
                             "artifact_refs are only for already published revisions (1 or later). "
                             "Omit artifact_refs for original attachments and planned outputs; describe those inputs or outputs in text.",
                             _obj({"to": {"type": "string"}, "purpose": {"type": "string", "enum": PURPOSES},
                                   "text": {"type": "string"}, "task_id": {"type": "string"},
                                   "artifact_refs": {"type": "array", "items": _REF}, "reply_to": {"type": "string"}},
                                  ["to", "purpose", "text"])),
    "read_messages": ToolSpec("read_messages",
                              "Read unread messages addressed to you for your tasks. wait_seconds>0 blocks until a message arrives.",
                              _obj({"wait_seconds": {"type": "integer", "minimum": 0, "maximum": 240}})),
    "read_artifact": ToolSpec("read_artifact", "Read a published artifact revision (latest if revision omitted). Copy the full artifact_id from list_artifacts, including its file extension. For long text, use start_char/max_chars to read only the needed range; pin revision across pages. A partial read is not a full review. Omit both range fields for the complete text.",
                              _obj({"artifact_id": {"type": "string"}, "revision": {"type": "integer"},
                                    "start_char": {"type": "integer", "minimum": 0},
                                    "max_chars": {"type": "integer", "minimum": 1, "maximum": 20000}}, ["artifact_id"])),
    "list_artifacts": ToolSpec("list_artifacts", "List published artifacts in this run with their latest revision.", _obj({})),
    "workspace_write": ToolSpec("workspace_write", "Write text inside your task workspace (relative path). Supply either complete content or edit to replace one exact occurrence in an existing UTF-8 draft. For long corrections prefer edit; expected_sha256 must match the whole current draft, and old_text must occur exactly once. Publish the changed draft separately.",
                                {**_obj({"path": {"type": "string"}, "content": {"type": "string"},
                                         "edit": _obj({"expected_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                                                       "old_text": {"type": "string", "minLength": 1},
                                                       "new_text": {"type": "string"}},
                                                      ["expected_sha256", "old_text", "new_text"])}, ["path"]),
                                 "oneOf": [{"required": ["content"], "not": {"required": ["edit"]}},
                                           {"required": ["edit"], "not": {"required": ["content"]}}]}),
    "workspace_read": ToolSpec("workspace_read", "Read a text file from your task workspace.", _obj({"path": {"type": "string"}}, ["path"])),
    "workspace_list": ToolSpec("workspace_list", "List files in your task workspace.", _obj({})),
    "publish_artifact": ToolSpec("publish_artifact",
                                 "Publish a file from your workspace as an immutable artifact revision. This is the only way "
                                 "to deliver work; chat text is not a deliverable. Optionally list source URLs.",
                                 _obj({"path": {"type": "string"}, "media_type": {"type": "string"},
                                       "sources": {"type": "array", "items": {"type": "string"}}}, ["path"])),
    "sandbox_run": ToolSpec("sandbox_run", "Run a shell command inside your task workspace sandbox (no network). Returns exit code and output.",
                            _obj({"command": {"type": "string"}, "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300}}, ["command"])),
    "run_check": ToolSpec("run_check",
                          "Run a registered check against a published artifact revision (or a workspace path). Kinds: "
                          + "; ".join(f"{k}: {v}" for k, v in CHECK_KINDS.items())
                          + ". For json_schema, omitting args.schema on a published artifact or workspace path with a requester delivery requirement uses its exact schema and input format. Text schema results include the measured unicode_code_points and utf8_bytes. Use these for length verification; text_contains checks literal content, not character count. Do not reconstruct an artifact in a shell command to count it.",
                          _obj({"kind": {"type": "string", "enum": list(CHECK_KINDS)}, "artifact_id": {"type": "string"},
                                "revision": {"type": "integer"}, "path": {"type": "string"},
                                "args": {"type": "object", "additionalProperties": True}}, ["kind"])),
    "web_fetch": ToolSpec("web_fetch", "Fetch a public http(s) URL and return extracted text. Private/loopback hosts are denied.",
                          _obj({"url": {"type": "string"}, "max_chars": {"type": "integer", "minimum": 500, "maximum": 40000}}, ["url"])),
    "web_search": ToolSpec("web_search", "Search the web (best-effort). Results are hints; fetch primary sources before citing.",
                           _obj({"query": {"type": "string"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"])),
    "request_approval": ToolSpec("request_approval",
                                 "Ask the human for approval before an external or irreversible action. Blocks until resolved "
                                 "or pauses the run. Describe exactly what will be done and the expected cost.",
                                 _obj({"action": {"type": "string"}, "description": {"type": "string"},
                                       "payload": {"type": "object", "additionalProperties": True},
                                       "estimated_cost_usd": {"type": "number"}}, ["action", "description"])),
    "report_blocker": ToolSpec("report_blocker", "Stop your task because you cannot proceed. State the reason and what is needed.",
                               _obj({"reason": {"type": "string"}, "needed": {"type": "string"}}, ["reason"])),
    "submit_review": ToolSpec("submit_review",
                              "Submit your verdict for the target task: one result per acceptance criterion with status "
                              "pass/fail/unverified/blocked, evidence (what you ran/read) and a note. Do not invent problems.",
                              _obj({"target_task_id": {"type": "string"},
                                    "target_artifacts": {"type": "array", "items": _REF},
                                    "results": {"type": "array", "items": _obj({
                                        "acceptance_id": {"type": "string"},
                                        "status": {"type": "string", "enum": ["pass", "fail", "unverified", "blocked"]},
                                        "evidence": {"type": "string"}, "note": {"type": "string"}}, ["acceptance_id", "status"])},
                                    "summary": {"type": "string"}}, ["target_task_id", "results"])),
    "create_task": ToolSpec("create_task", "(Master) Add a task to the plan. Owner must be an enabled agent; depends_on must exist.",
                            _obj({"id": {"type": "string"}, "owner": {"type": "string"}, "objective": {"type": "string"},
                                  "depends_on": {"type": "array", "items": {"type": "string"}},
                                  "output_paths": {"type": "array", "items": {"type": "string"}},
                                  "acceptance": {"type": "array", "items": _obj({"id": {"type": "string"}, "description": {"type": "string"},
                                                                                "check_kind": {"type": "string", "enum": ["programmatic", "source_check", "human_review", "model_review"]}},
                                                                               ["id", "description", "check_kind"])}},
                                 ["id", "owner", "objective", "acceptance"])),
    "update_task": ToolSpec("update_task", "(Master) Decide what happens to a failed/blocked task: retry, accept_partial or cancel.",
                            _obj({"task_id": {"type": "string"}, "action": {"type": "string", "enum": ["retry", "accept_partial", "cancel"]},
                                  "note": {"type": "string"}}, ["task_id", "action"])),
    "read_events": ToolSpec("read_events", "(Reporter) Read recorded run events after a sequence number.",
                            _obj({"after_seq": {"type": "integer"}, "limit": {"type": "integer", "maximum": 200}})),
}


class ToolGateway:
    def __init__(self, ctx: SessionContext):
        self.ctx = ctx
        self.rt = ctx.rt

    @property
    def document_reviewer(self) -> bool:
        return self.rt.run.inputs.workflow == "document" and self.ctx.agent.role == "reviewer"

    def allowed_tools(self) -> list[str]:
        if not self.document_reviewer:
            return self.ctx.tools
        # A document reviewer verifies immutable producer revisions. Corrections
        # must go through submit_review and the scheduler, not another writer.
        read_review = {"read_skill", "read_input_file", "read_artifact", "list_artifacts", "run_check",
                       "send_message", "read_messages", "read_events", "submit_review", "finish_task", "report_blocker"}
        return [name for name in self.ctx.tools if name in read_review]

    def specs(self) -> list[ToolSpec]:
        from ..config.voice import conversation_voice, message_delivery_hint
        specs = [TOOL_SPECS[n] for n in self.allowed_tools() if n in TOOL_SPECS]
        # Put the user's voice beside the message the model actually generates.
        # Copy the schema: another teammate must never inherit this one's voice.
        for index, tool in enumerate(specs):
            if tool.name == "send_message":
                schema = copy.deepcopy(tool.input_schema)
                recipients = {agent.agent_id: agent.display_name or agent.agent_id for agent in self.rt.enabled_agents()}
                schema["properties"]["to"].update(
                    enum=list(recipients),
                    description="Recipient agent ID, not display name. Current team: " + json.dumps(recipients, ensure_ascii=False))
                if self.ctx.mode == 'coordination':
                    schema['required'] = list(dict.fromkeys([*schema.get('required', []), 'task_id']))
                    schema['properties']['task_id'].update(
                        enum=list(self.rt.tasks),
                        description='Required: the recipient owns this task. Task to owner: ' + json.dumps(
                            {key: task.spec.owner for key, task in self.rt.tasks.items()}, ensure_ascii=False))
                schema["properties"]["text"]["description"] = (
                    "You are " + (self.ctx.agent.display_name or self.ctx.agent.agent_id)
                    + ". Write your own message to the selected teammate. Address people by their display names "
                    "from the recipient map, not internal agent IDs. Do not speak as the recipient. "
                    "Use your configured conversation voice: "
                    + conversation_voice(self.ctx.agent.role, self.ctx.agent.speech_style)
                    + "\nApply the voice to the wording, not just the role name. Preserve facts, "
                    "uncertainty and findings. Do not invent dialogue or change artifact content."
                    + "\n" + message_delivery_hint(self.ctx.agent.role)
                )
                specs[index] = ToolSpec(tool.name, tool.description, schema)
            elif tool.name == "submit_review" and self.ctx.task:
                targets = [self.rt.tasks[t] for t in self.ctx.task.spec.depends_on if t in self.rt.tasks]
                if targets:
                    schema = copy.deepcopy(tool.input_schema)
                    schema["properties"]["target_task_id"]["enum"] = [t.spec.id for t in targets]
                    criteria = schema["properties"]["results"]["items"]["properties"]["acceptance_id"]
                    criteria["enum"] = sorted({c.id for t in targets for c in t.spec.acceptance})
                    criteria["description"] = (
                        "Use the existing ID for the selected target; put individual findings in evidence/note, "
                        "not new acceptance IDs. " + "; ".join(
                            f"{t.spec.id}: " + ", ".join(c.id for c in t.spec.acceptance) for t in targets))
                    if len(targets) == 1:
                        count = len(targets[0].spec.acceptance)
                        schema["properties"]["results"].update(minItems=count, maxItems=count)
                    # Hints mirror existing validation; the execution layer still
                    # enforces target membership, coverage, uniqueness and revisions.
                    specs[index] = ToolSpec(tool.name, tool.description, schema)
        requirements = self.rt.run.inputs.delivery_requirements
        if self.rt.run.inputs.workflow != "document" or len(requirements) != 1:
            return specs
        requirement = requirements[0]
        if requirement.input_format != "text":
            return specs
        # Put the requester's length contract beside the generated content, not
        # only in the task prompt. This is a provider hint; persisted byte checks
        # remain authoritative, and invalid drafts are still retained for repair.
        # Do not embed arbitrary schemas here: nested $ref resolution would change.
        for index, tool in enumerate(specs):
            if tool.name != "workspace_write":
                continue
            schema = copy.deepcopy(tool.input_schema)
            schema["properties"]["path"]["enum"] = [requirement.logical_path]
            content = schema["properties"]["content"]
            for bound in ("minLength", "maxLength"):
                if bound in requirement.json_schema:
                    content[bound] = requirement.json_schema[bound]
            content["description"] = "Complete document. Length counts every Unicode character, including headings, spaces and newlines. Preserve required source conditions when shortening."
            specs[index] = ToolSpec(tool.name, "Write the requested document in your task workspace. Use the declared output path.", schema)
        return specs

    async def call(self, name: str, args: dict[str, Any], *, causation_id: str | None = None) -> str:
        rt, ctx = self.rt, self.ctx
        policy = rt.policy
        try:
            policy.check_tool_allowed(self.allowed_tools(), name)
            policy.count_tool_call()
        except PolicyViolation as e:
            await rt.events.append(rt.run_id, "policy.denied", {"tool": name, "code": e.code, "message": str(e)},
                                   actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=causation_id)
            if e.fatal:
                raise
            return f"DENIED ({e.code}): {e}"
        handler = getattr(self, f"t_{name}", None)
        if handler is None:
            return f"ERROR: tool {name} is not implemented"
        ok = True
        try:
            errors = list(Draft202012Validator(TOOL_SPECS[name].input_schema).iter_errors(args))
            if errors:
                ok = False
                result = "REJECTED: invalid tool arguments: " + "; ".join(
                    f"{e.json_path}: {e.message}" for e in errors[:3])
                if name == "workspace_write" and ("content" in args) == ("edit" in args):
                    result = "REJECTED: invalid tool arguments: provide exactly one of content (complete text) or edit (expected_sha256, old_text, new_text)."
            else:
                result = await handler(args, causation_id)
                ok = not result.startswith(("ERROR", "DENIED", "REJECTED", "NOT FOUND"))
        except PolicyViolation as e:
            ok = False
            result = f"DENIED ({e.code}): {e}"
            if e.fatal:
                await self._log(name, args, result, ok, causation_id)
                raise
        except FetchDenied as e:
            ok = False
            result = f"DENIED (egress): {e}"
        except Exception as e:  # tool errors go back to the model, never crash the loop
            ok = False
            result = f"ERROR ({type(e).__name__}): {rt.redactor.text(str(e))[:500]}"
        result = rt.redactor.text(result)
        await self._log(name, args, result, ok, causation_id)
        limit = rt.config.limits.max_tool_output_chars
        if len(result) > limit:
            result = result[:limit] + f"\n...[truncated {len(result) - limit} chars; stored in full in the event log]"
        return result

    async def _log(self, name: str, args: dict[str, Any], result: str, ok: bool, causation_id: str | None) -> None:
        rt, ctx = self.rt, self.ctx
        safe_args = {k: (v if not isinstance(v, str) or len(v) < 2000 else v[:2000] + "…") for k, v in args.items()}
        await rt.events.append(rt.run_id, "tool.called",
                               {"tool": name, "args": safe_args, "ok": ok, "result_preview": result[:4000],
                                "result_chars": len(result), "mode": ctx.mode, "attempt": ctx.attempt},
                               actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=causation_id)

    # ------------------------------------------------------------------ helpers
    def _ws_path(self, rel: str) -> Path:
        ws = self.ctx.workspace
        if ws is None:
            raise PolicyViolation("no_workspace", "this session has no task workspace")
        rel = self.rt.policy.check_write_path(rel)
        p = (ws / rel).resolve()
        if not p.is_relative_to(ws.resolve()):
            raise PolicyViolation("path_scope", "path escapes workspace")
        return p

    async def _artifact(self, artifact_id: str, revision: int | None):
        m = await self.rt.artifacts.get(self.rt.run_id, artifact_id, revision)
        if m is None:
            # allow lookup by logical path too
            for cand in await self.rt.artifacts.list(self.rt.run_id, latest_only=True):
                if cand.logical_path == artifact_id:
                    return await self.rt.artifacts.get(self.rt.run_id, cand.artifact_id, revision)
        return m

    async def _artifact_lookup_hint(self, artifact_id: str) -> str:
        candidates = [c for c in await self.rt.artifacts.list(self.rt.run_id, latest_only=True)
                      if Path(c.artifact_id).stem == artifact_id]
        hint = " Copy the full artifact_id, including the file extension, from list_artifacts."
        if candidates:
            hint += " Matching IDs (latest available revisions): " + "; ".join(
                f"{c.artifact_id!r}, revision={c.revision}" for c in candidates[:5]
            ) + ". No candidate was automatically selected or read."
        return hint

    # ------------------------------------------------------------------ tools
    async def t_read_input_file(self, args, cid):
        matches = [f for f in self.rt.run.inputs.files if f.get('name') == args['name']]
        if len(matches) != 1:
            if not matches and 'read_artifact' in self.ctx.tools:
                artifact = await self._artifact(args['name'], None)
                if artifact is not None:
                    return (f"NOT FOUND: {args['name']} is a generated artifact, not an original user attachment. "
                            f"Use read_artifact(artifact_id={artifact.artifact_id!r}, revision={artifact.revision}) "
                            "to inspect it. Keep its claims separate from the original source material.")
            return 'NOT FOUND: exact unambiguous input name required. Available attachments: ' + ', '.join(f.get('name', '') for f in self.rt.run.inputs.files)
        content = matches[0].get('content', '')
        start = min(args.get('start_char', 0), len(content))
        limit = min(args.get('max_chars', 12000), max(1, self.rt.config.limits.max_tool_output_chars - 800))
        end = min(start + limit, len(content))
        metadata = {'name': args['name'], 'sha256': hashlib.sha256(content.encode()).hexdigest(),
                    'start_char': start, 'end_char': end, 'total_chars': len(content), 'more': end < len(content)}
        await self.rt.events.append(self.rt.run_id, 'input.read', metadata, actor_id=self.ctx.agent.agent_id,
                                    actor_kind='agent', task_id=self.ctx.task_id, causation_id=cid)
        return 'Original request attachment (not an artifact): ' + json.dumps(metadata, ensure_ascii=False) + '\n---\n' + content[start:end]

    async def t_read_skill(self, a, cid):
        names = [s["name"] for s in self.ctx.agent.skills]
        if a["name"] not in names:
            return f"DENIED: skill {a['name']} is not enabled for you. Enabled: {names}"
        return read_skill_body(a["name"]) or "ERROR: skill body not found"

    async def t_finish_task(self, a, cid):
        if self.ctx.mode == "coordination":
            from .communication import coordination_targets, delivered_coordination, complete_delivered_coordination
            missing = set(coordination_targets(self.ctx)) - await delivered_coordination(self.ctx)
            if missing:
                return "REJECTED: send coordinator handoffs before finishing. Missing recipients: " + ", ".join(sorted(missing))
            if await complete_delivered_coordination(self.ctx):
                # Only dispatch is proven here. Preserve the model's raw tool
                # arguments in the event log, but never adopt its claims that
                # production or review has already passed.
                return "OK"
            return "REJECTED: no verified coordinator handoffs to finish"
        if self.ctx.mode == "reply":
            if not self.ctx.replied:
                return "REJECTED: deliver an answer with send_message before finishing this reply session."
            self.ctx.finished = TaskResult(summary=a.get("summary", ""))
            return "OK: reply session finished"
        if self.ctx.task is None:
            self.ctx.finished = TaskResult(summary=a.get("summary", ""))
            return "OK"
        spec = self.ctx.task.spec
        missing = []
        if spec.output_paths == ["*"]:  # single-agent runs: any published artifact counts
            mine = [m for m in await self.rt.artifacts.list(self.rt.run_id, latest_only=True) if m.task_id == spec.id]
            if not mine and self.ctx.agent.role != "reviewer":
                return "REJECTED: nothing published yet. Write the deliverables with workspace_write, publish each with publish_artifact, then call finish_task again."
        else:
            for path in spec.output_paths:
                m = await self._artifact_for_path(path)
                if m is None or m.task_id != spec.id:
                    missing.append(path)
        if missing and self.ctx.agent.role != "reviewer":
            return ("REJECTED: these output paths are not published by this task yet: " + ", ".join(missing)
                    + ". Write them with workspace_write and publish with publish_artifact, then call finish_task again.")
        changed = await unpublished_workspace_changes(self.ctx)
        if changed:
            return ("REJECTED: unpublished workspace changes: " + ", ".join(changed)
                    + ". Publish the revised files, send their current revision references, then finish_task. "
                    "Earlier published revisions do not contain these edits.")
        required_failures = failures(await verify_delivery(self.rt, task_id=spec.id, actor_id=self.ctx.agent.agent_id))
        if required_failures:
            return ('REJECTED: requester delivery requirements failed. Revise, publish another revision and retry finish_task. '
                                        + ' | '.join(required_failures)[:6000])
        if self.ctx.agent.role == "reviewer":
            targets = [d for d in spec.depends_on if self.rt.tasks.get(d) and self.rt.agents.get(self.rt.tasks[d].spec.owner)
                       and self.rt.agents[self.rt.tasks[d].spec.owner].role != "reviewer"]
            done = {r.target_task_id for r in self.ctx.reviews}
            missing_reviews = [t for t in targets if t not in done]
            if missing_reviews:
                return ("REJECTED: call submit_review for each target task before finish_task. Missing: " + ", ".join(missing_reviews)
                        + ". Submit the verdict on the current published revisions, including fail or unverified findings. "
                        "Do not wait for corrected files before recording a failing review; the producer cannot revise "
                        "until this review session finishes. A chat finding does not replace submit_review.")
        from .communication import communication_targets
        missing_handoffs = set(communication_targets(self.ctx)) - self.ctx.communicated_to
        if missing_handoffs:
            return ("REJECTED: deliver a handoff, finding or decision with send_message for this task before finish_task. Missing recipients: "
                    + ", ".join(sorted(missing_handoffs))
                    + ". Publishing a new artifact resets earlier handoffs; submitting a review resets the handoff to its owner. "
                    "Send the current result now, referencing published artifact IDs and revisions where applicable. "
                    "Reading your inbox does not deliver a handoff; do not wait for a queued dependent task's reply.")
        self.ctx.finished = TaskResult(summary=a.get("summary", ""), verified=list(a.get("verified") or []),
                                       unverified=list(a.get("unverified") or []), next_steps=list(a.get("next_steps") or []),
                                       published=[p.ref() for p in self.ctx.published])
        return "OK: task finished"

    async def _artifact_for_path(self, logical_path: str):
        for m in await self.rt.artifacts.list(self.rt.run_id, latest_only=True):
            if m.logical_path == logical_path:
                return m
        return None

    def _pending_review_notice(self):
        ctx = self.ctx
        if ctx.task is None:
            return ""
        from .communication import communication_targets
        missing = set(communication_targets(ctx)) - ctx.communicated_to
        handoff = ("Deliver the required findings to " + ", ".join(sorted(missing)) + ", then call finish_task. "
                   if missing else
                   "Required handoffs are already delivered. Do not resend the same findings under a different purpose. "
                   "If the requested work is ready, call finish_task; it will validate publication and completion requirements. ")
        downstream = [t.spec.id for t in self.rt.tasks.values()
                      if ctx.task_id in t.spec.depends_on and t.status == "queued"]
        if downstream and ctx.agent.role != "reviewer":
            return ("Dependent tasks " + ", ".join(downstream) + " cannot start until this task finishes. "
                    "Do not wait for their replies. " + handoff
                    + "If work is incomplete, report the actual blocker instead of claiming completion.")
        if ctx.agent.role != "reviewer":
            return ""
        pending = [dep for dep in ctx.task.spec.depends_on
                   if dep in self.rt.tasks and self.rt.tasks[dep].status == "review_pending"]
        if not pending:
            return ""
        reviewed = {r.target_task_id for r in ctx.reviews}
        remaining = [task_id for task_id in pending if task_id not in reviewed]
        if not remaining:
            return ("The review is already submitted. Do not submit it again or wait for replies. "
                    + handoff + "Finish this session so the scheduler can proceed.")
        return ("Producers " + ", ".join(remaining) + " are waiting for this review and cannot revise yet. "
                "Do not wait for their replies. Submit an evidence-linked verdict with submit_review, "
                "deliver findings, then finish_task so the scheduler can run any required revision.")

    async def t_send_message(self, a, cid):
        # Reservation lookup, admission and persisted delivery form one local
        # critical section, including concurrently scheduled reply sessions.
        async with self.rt.policy.peer_message_lock:
            return await self._send_message_locked(a, cid)

    async def _send_message_locked(self, a, cid):
        rt, ctx = self.rt, self.ctx
        to = a["to"]
        if not a.get("text", "").strip():
            return "REJECTED: message text must describe the actual work or question."
        if to == ctx.agent.agent_id:
            return "REJECTED: cannot message yourself"
        if to == "user":
            return "REJECTED: there is no user mailbox. Use report_blocker for information you need from the human."
        if to not in rt.agents or not rt.agents[to].enabled:
            recipients = {agent.agent_id: agent.display_name or agent.agent_id for agent in rt.enabled_agents()}
            return f"REJECTED: unknown or disabled agent {to}. Use an agent ID, not its display name. Enabled ID to name: {json.dumps(recipients, ensure_ascii=False)}"
        task_id = a.get("task_id") or ctx.task_id
        if not task_id:
            return "REJECTED: task_id is required in this session"
        if task_id not in rt.tasks:
            return f"REJECTED: unknown task {task_id}"
        if ctx.mode == "coordination":
            from .communication import delivered_coordination
            if rt.tasks[task_id].spec.owner != to or a["purpose"] not in {"handoff", "decision"}:
                return "REJECTED: coordinator handoffs must address the task owner with purpose handoff or decision."
            if to in await delivered_coordination(ctx):
                return "ALREADY DELIVERED: coordinator handoff exists for this owner. Do not resend; finish remaining handoffs."
        refs = []
        for r in a.get("artifact_refs") or []:
            m = await self._artifact(r["artifact_id"], r.get("revision"))
            if m is None:
                return (f"REJECTED: artifact {r['artifact_id']} rev {r.get('revision')} does not exist."
                        + await self._artifact_lookup_hint(r['artifact_id']))
            refs.append(m.ref())
        message_task = rt.tasks[task_id]
        if rt.run.config_snapshot.get('communication_budget_version') == 1 and ctx.mode != 'coordination':
            from .communication import future_handoff_reserve, task_communication_targets
            future = future_handoff_reserve(rt, message_task)
            deliveries = await rt.runs.list_messages(rt.run_id, task_ids=[task_id])
            questions = {m.message_id: m for m in deliveries if m.purpose == 'question'}
            answered = {m.reply_to for m in deliveries if m.purpose == 'answer'
                        and m.reply_to in questions
                        and m.from_agent_id == questions[m.reply_to].to_agent_id
                        and m.to_agent_id == questions[m.reply_to].from_agent_id}
            pending_answers = set(questions) - answered
            question = questions.get(a.get('reply_to'))
            reserved_answer = (a['purpose'] == 'answer' and a.get('reply_to') in pending_answers
                               and question.to_agent_id == ctx.agent.agent_id and question.from_agent_id == to)
            future += len(pending_answers) - int(reserved_answer)
            targets = set(task_communication_targets(message_task.spec,
                {key: task.spec for key, task in rt.tasks.items()},
                {key: agent.role for key, agent in rt.agents.items()},
                {key for key, agent in rt.agents.items() if agent.enabled}))
            own_session = ctx.mode == 'task' and ctx.task_id == task_id and message_task.spec.owner == ctx.agent.agent_id
            needed = targets - ctx.communicated_to if own_session else targets
            pending_review = []
            if own_session and ctx.agent.role == 'reviewer':
                submitted = {review.target_task_id for review in ctx.reviews}
                pending_review = [t for t in message_task.spec.depends_on
                                  if t in rt.tasks and t not in submitted
                                  and rt.agents[rt.tasks[t].spec.owner].role != 'reviewer']
                needed.update(rt.tasks[t].spec.owner for t in pending_review)
            # Do not admit a question whose mandatory answer cannot fit.
            # Answer capacity is part of the same lifetime task budget.
            question_slots = 1 if a['purpose'] == 'question' else 0
            remaining = rt.config.limits.max_peer_messages_per_task - rt.policy.peer_messages.get(task_id, 0)
            required_now = reserved_answer or (own_session and to in needed and a['purpose'] in {'handoff', 'finding', 'decision'})
            if remaining <= future or (remaining <= future + len(needed) + question_slots and (not required_now or pending_review)):
                return ('REJECTED: remaining communication capacity is reserved for required handoffs '
                        f'and future revision sessions ({future} future messages). '
                        'Submit pending formal reviews before their handoffs. '
                        'Do not spend it on optional discussion or another task. No message was sent.')
        if (ctx.mode == "task" and (message_task.spec.owner != ctx.agent.agent_id or task_id != ctx.task_id)
                and rt.agents[message_task.spec.owner].role == "reviewer"
                and str(message_task.status) not in {"accepted", "failed", "blocked", "cancelled"}):
            owners = {rt.tasks[target].spec.owner for target in message_task.spec.depends_on
                      if target in rt.tasks and rt.agents[rt.tasks[target].spec.owner].role != "reviewer"}
            remaining = rt.config.limits.max_peer_messages_per_task - rt.policy.peer_messages.get(task_id, 0)
            if remaining > 0 and remaining <= len(owners):
                return ("REJECTED: this task's remaining message capacity is reserved for its reviewer's required handoffs. "
                        "Send information under your own task_id instead. No message was sent.")
        if ctx.mode == "task" and ctx.task and ctx.agent.role == "reviewer" and task_id == ctx.task_id:
            # A review must still reach its producer after formal submission.
            # Preserve that capacity rather than spending the final slots on
            # repeated findings or optional recipients. Never raise the limit.
            from .communication import communication_targets
            submitted = {review.target_task_id for review in ctx.reviews}
            pending = [target for target in ctx.task.spec.depends_on
                       if target in rt.tasks and target not in submitted
                       and rt.agents[rt.tasks[target].spec.owner].role != "reviewer"]
            needed = set(communication_targets(ctx)) - ctx.communicated_to
            needed.update(rt.tasks[target].spec.owner for target in pending)
            remaining = rt.config.limits.max_peer_messages_per_task - rt.policy.peer_messages.get(task_id, 0)
            if remaining > 0 and remaining <= len(needed):
                if pending:
                    return ("REJECTED: remaining message capacity is reserved for post-review handoffs. "
                            "Call submit_review for " + ", ".join(pending)
                            + " first, then send the recorded findings to the target owners. No message was sent.")
                if to not in needed or a["purpose"] not in {"handoff", "finding", "decision"}:
                    return ("REJECTED: remaining message capacity is reserved for required review handoffs to "
                            + ", ".join(sorted(needed)) + ". No message was sent.")
        # Every persisted peer delivery is charged to its task, including
        # short reply sessions. Resume reconstructs this same count from DB.
        rt.policy.count_peer_message(task_id)
        m = await rt.bus.send(from_agent_id=ctx.agent.agent_id, to_agent_id=to, task_id=task_id, purpose=a["purpose"],
                              text=a["text"], artifact_refs=refs, reply_to=a.get("reply_to"), causation_id=cid)
        if task_id == ctx.task_id and a["purpose"] in {"handoff", "finding", "decision"}:
            ctx.communicated_to.add(to)
        if a["purpose"] == "answer":
            ctx.replied = True
        if a["purpose"] == "question":
            ctx.awaiting_answer_from.add(to)
        receipt = f"DELIVERED message_id={m.message_id} to={to} task={task_id}. "
        if a["purpose"] == "request":
            receipt += ("This request is queued for the recipient's scheduled work; it does not start a reply session "
                        "or transfer ownership of your task. Continue your own assigned outputs. "
                        "Use question only for a specific answer needed to proceed, not to ask someone else to rewrite your deliverable. ")
        return receipt + (self._pending_review_notice() or
                          ("" if a["purpose"] == "request" else "Use read_messages(wait_seconds=N) to wait for a reply."))

    async def t_read_messages(self, a, cid):
        rt, ctx = self.rt, self.ctx
        wait = min(int(a.get("wait_seconds") or 0), 240, max(0, int(rt.remaining_seconds()) - 5))
        review_notice = self._pending_review_notice()
        # The notice exists so nobody waits on teammates who cannot start yet. A question this session asked is
        # different: its answer is on the way, and skipping the wait leaves that answer unread.
        if review_notice and not ctx.awaiting_answer_from:
            wait = 0
        msgs = await rt.bus.read(ctx.agent.agent_id, None, wait_seconds=wait)
        ctx.awaiting_answer_from -= {m.from_agent_id for m in msgs if m.purpose == "answer"}
        if not msgs:
            return "No new messages." + (f" (waited {wait}s)" if wait else "") + (" " + review_notice if review_notice else "")
        await rt.bus.mark_read(msgs, ctx.agent.agent_id)
        lines = []
        for m in msgs:
            refs = ", ".join(f"{r.artifact_id}@r{r.revision}" for r in m.artifact_refs) or "-"
            lines.append(f"[{m.message_id}] from={m.from_agent_id} task={m.task_id} purpose={m.purpose} reply_to={m.reply_to or '-'} "
                         f"artifacts={refs}\n{m.text}")
        return "\n\n".join(lines)

    async def t_read_artifact(self, a, cid):
        m = await self._artifact(a["artifact_id"], a.get("revision"))
        if m is None:
            if any(f.get('name') == a['artifact_id'] for f in self.rt.run.inputs.files):
                return f"NOT FOUND: {a['artifact_id']} is an original user attachment, not an artifact. Use read_input_file(name={a['artifact_id']!r}) to verify its contents."
            return f"NOT FOUND: artifact {a['artifact_id']}." + await self._artifact_lookup_hint(a['artifact_id'])
        metadata = {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256}
        range_header = ""
        if m.media_type.startswith("text/") or m.media_type in ("application/json", "image/svg+xml"):
            body = self.rt.artifacts.read_text(m)
            if "start_char" in a or "max_chars" in a:
                total = len(body)
                start = min(a.get("start_char", 0), total)
                end = min(start + a.get("max_chars", 4000), total)
                metadata.update(start_char=start, end_char=end, total_chars=total,
                                more=end < total, partial=start > 0 or end < total)
                range_header = (f" start_char={start} end_char={end} total_chars={total}"
                                f" more={str(end < total).lower()} partial={str(start > 0 or end < total).lower()}")
                body = body[start:end]
        else:
            if "start_char" in a or "max_chars" in a:
                return "REJECTED: character ranges apply only to text artifacts. Omit range fields for binary metadata."
            body = f"<binary {m.media_type}, {m.size} bytes>"
        result = (f"artifact_id={m.artifact_id} revision={m.revision} sha256={m.sha256} media_type={m.media_type} "
                f"logical_path={m.logical_path} by={m.agent_id} task={m.task_id}{range_header}\n---\n{body}")
        if range_header and len(result) > self.rt.config.limits.max_tool_output_chars:
            return ("REJECTED: requested artifact range exceeds max_tool_output_chars including metadata. "
                    "Retry with a smaller max_chars; no range was delivered.")
        await self.rt.events.append(self.rt.run_id, "artifact.read", metadata,
                                    actor_id=self.ctx.agent.agent_id, actor_kind="agent", task_id=self.ctx.task_id, causation_id=cid)
        return result

    async def t_list_artifacts(self, a, cid):
        items = await self.rt.artifacts.list(self.rt.run_id, latest_only=True)
        if not items:
            return "No artifacts published yet."
        return "\n".join(f"{m.artifact_id} r{m.revision} sha256={m.sha256[:12]} {m.media_type} {m.size}B path={m.logical_path} by={m.agent_id}/{m.task_id}"
                         for m in items)

    async def t_workspace_write(self, a, cid):
        p = self._ws_path(a["path"])
        content = a.get("content")
        if "edit" in a:
            if not p.is_file():
                return "NOT FOUND: exact replacement requires an existing workspace draft."
            raw = p.read_bytes()
            edit = a["edit"]
            current_sha = hashlib.sha256(raw).hexdigest()
            if current_sha != edit["expected_sha256"]:
                return f"REJECTED: draft SHA mismatch (current sha256={current_sha}). Read the current draft before editing; no bytes changed."
            current = raw.decode("utf-8")
            first = current.find(edit["old_text"])
            if first < 0 or first != current.rfind(edit["old_text"]):
                return "REJECTED: old_text must occur exactly once (including overlapping matches). Include enough unchanged context; no bytes changed."
            content = current.replace(edit["old_text"], edit["new_text"], 1)
        p.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        unchanged = p.is_file() and p.read_bytes() == encoded
        p.write_bytes(encoded)
        reply = (f"OK: wrote {len(content)} chars to {a['path']} (not published yet)"
                 f" sha256={hashlib.sha256(encoded).hexdigest()}")
        if unchanged:
            reply += "\nUNCHANGED: these bytes are identical to the previous draft. This did not repair any failed condition. Make a substantive correction instead of resending the same text."
        logical = p.relative_to(self.ctx.workspace.resolve()).as_posix()
        if any(r.logical_path == logical for r in self.rt.run.inputs.delivery_requirements):
            checked = await self.t_run_check({'kind': 'json_schema', 'path': a['path']}, cid)
            reply += "\nAutomatic requester delivery check (the saved draft is kept):\n" + checked
        return reply

    async def t_workspace_read(self, a, cid):
        p = self._ws_path(a["path"])
        if not p.is_file():
            if "read_artifact" in self.ctx.tools:
                published = await self._artifact(a["path"], None)
                if published is not None:
                    return (f"NOT FOUND in your task workspace: {a['path']}. A published artifact exists in this run. "
                            f"Use read_artifact(artifact_id={published.artifact_id!r}, revision={published.revision}) "
                            "to inspect that saved version. It is not an original source attachment.")
            return f"NOT FOUND: {a['path']}"
        return p.read_text(encoding="utf-8", errors="replace")

    async def t_workspace_list(self, a, cid):
        ws = self.ctx.workspace
        if ws is None:
            return "no workspace"
        files = [str(p.relative_to(ws)) for p in sorted(ws.rglob("*")) if p.is_file() and ".tmp" not in p.parts]
        return "\n".join(files) or "(empty)"

    async def t_publish_artifact(self, a, cid):
        rt, ctx = self.rt, self.ctx
        p = self._ws_path(a["path"])
        if not p.is_file():
            return f"NOT FOUND in workspace: {a['path']}. Write it first with workspace_write."
        data = p.read_bytes()
        logical = rt.policy.check_write_path(a["path"])
        # Workspaces are separate, but published logical paths share one run namespace.
        # Only the producing task may revise its own artifact, including reviewer sessions.
        existing = await self._artifact_for_path(logical)
        owner = next((t.spec.id for t in rt.tasks.values() if logical in t.spec.output_paths), None)
        if (existing and existing.task_id != ctx.task_id) or (owner and owner != ctx.task_id):
            target_id = existing.task_id if existing and existing.task_id != ctx.task_id else owner
            target = rt.tasks.get(target_id)
            if target and target.spec.owner == ctx.agent.agent_id:
                return (f"REJECTED: {logical} belongs to your separate task {target_id}, not current task {ctx.task_id}. "
                        "Finish the current task's declared outputs and handoffs; the scheduler runs the other task separately. "
                        "Do not rename this file to bypass ownership.")
            return (f"REJECTED: {logical} belongs to another task ({target_id}). Send review feedback to its owner. "
                    "Publish only your current task's declared outputs; do not rename another task's deliverable.")
        m = await rt.artifacts.publish(rt.run_id, logical, data, agent_id=ctx.agent.agent_id, task_id=ctx.task_id,
                                       media_type=a.get("media_type"), sources=list(a.get("sources") or []))
        ev = await rt.events.append(rt.run_id, "artifact.published",
                                    {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256,
                                     "media_type": m.media_type, "size": m.size, "logical_path": m.logical_path,
                                     "sources": m.sources},
                                    actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        await rt.artifacts.set_event(rt.run_id, m.artifact_id, m.revision, ev.event_id)
        ctx.published.append(m)
        ctx.communicated_to.clear()
        result = f"PUBLISHED artifact_id={m.artifact_id} revision={m.revision} sha256={m.sha256} media_type={m.media_type}"
        from .communication import communication_targets
        if communication_targets(ctx):
            result += (". After publishing all required outputs, send their exact IDs/revisions to the required recipients, "
                       "then finish_task. Messages sent before this publication do not satisfy the current handoff.")
        return result

    async def t_sandbox_run(self, a, cid):
        ws = self.ctx.workspace
        if ws is None:
            return "DENIED: no workspace in this session"
        timeout = float(a.get("timeout_seconds") or 120)
        r = await run_command(a["command"], ws, timeout=min(timeout, max(5.0, self.rt.remaining_seconds() - 5)),
                              max_output=self.rt.config.limits.max_tool_output_chars, require_container=self.rt.require_container)
        if r.denied:
            return f"DENIED: {r.reason}"
        return f"backend={r.backend} exit_code={r.exit_code} timed_out={r.timed_out}\n--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}"

    async def t_run_check(self, a, cid):
        rt, ctx = self.rt, self.ctx
        kind = a["kind"]
        if self.document_reviewer and kind == "command":
            return "DENIED: document reviewers use registered file checks, not shell commands. Read the published revision, submit_review with findings, then finish_task so its producer can revise."
        data: bytes | None = None
        target: dict[str, Any] = {}
        contract_requirement = None
        if a.get("artifact_id"):
            m = await self._artifact(a["artifact_id"], a.get("revision"))
            if m is None:
                return f"NOT FOUND: artifact {a['artifact_id']}"
            data = rt.artifacts.read_bytes(m)
            target = {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256}
            # Reviewers must be able to run the requester-owned delivery check
            # without reconstructing (and potentially corrupting) its schema.
            # Resolve it by logical path only; other checks keep their explicit
            # arguments and behavior.
            if kind == "json_schema":
                contract_requirement = next(
                    (r for r in rt.run.inputs.delivery_requirements if r.logical_path == m.logical_path),
                    None,
                )
        elif a.get("path"):
            p = self._ws_path(a["path"])
            if not p.is_file():
                return (f"NOT FOUND: {a['path']} in your task workspace. To check another task’s "
                        "published output, use artifact_id and revision from list_artifacts instead of path.")
            data = p.read_bytes()
            if kind == "json_schema":
                logical_path = p.relative_to(ctx.workspace.resolve()).as_posix()
                contract_requirement = next((r for r in rt.run.inputs.delivery_requirements if r.logical_path == logical_path), None)
            target = {"workspace_path": a["path"], "sha256": hashlib.sha256(data).hexdigest()}
        elif kind != "command":
            return "REJECTED: provide artifact_id (published revision) or path (workspace file)"
        check_args = dict(a.get("args") or {})
        if kind == "json_schema" and "schema" not in check_args and contract_requirement is not None:
            check_args["schema"] = contract_requirement.json_schema
            check_args["input_format"] = contract_requirement.input_format
        result = await run_check(kind, data, check_args, ctx.workspace, require_container=rt.require_container)
        recorded_args = dict(a.get("args") or {})
        if contract_requirement is not None and kind == "json_schema" and "schema" not in recorded_args:
            recorded_args["schema_source"] = "requester_delivery_requirement"
            recorded_args["input_format"] = contract_requirement.input_format
        await rt.events.append(rt.run_id, "check.completed", {"kind": kind, "target": target, "args": recorded_args,
                                                              "result": result},
                               actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        response = {"kind": kind, "target": target, "result": result}
        if kind in {"text_contains", "text_not_contains", "regex_count", "markdown_basic"}:
            response["interpretation"] = (
                "This result verifies only the requested literal text or structure, not meaning, source accuracy, "
                "or whether an action occurred. A mention of a future or prohibited action is not evidence it was performed. "
                "Keep requester constraints unchanged. Do not remove required concepts or reword them merely to pass "
                "a self-chosen lexical check; compare the actual statements with the request and sources for semantic review."
            )
            if kind in {"text_contains", "text_not_contains"}:
                response["interpretation"] += (
                    " Matching uses raw text, preserving Markdown markers, whitespace, case and punctuation. "
                    "A phrase visible when rendered may not be a contiguous raw substring. "
                    "For a mismatch, inspect the exact source wording and explain the difference; repeating the same "
                    "needles against the same revision cannot change the result. Do not infer a missing requirement "
                    "from that mismatch alone or change the artifact just to satisfy the search."
                )
        if contract_requirement is not None and kind == "json_schema":
            hint = _delivery_repair_hint(contract_requirement.json_schema, result)
            if hint:
                response["repair_hint"] = hint
        return json.dumps(response, ensure_ascii=False, indent=1)

    async def t_web_fetch(self, a, cid):
        r = await web_fetch(a["url"], max_chars=int(a.get("max_chars") or 12000))
        return (f"url={r['url']} status={r['status']} content_type={r['content_type']} title={r['title']!r} "
                f"truncated={r['truncated']} retrieved_at={now_iso()}\n---\n{r['text']}")

    async def t_web_search(self, a, cid):
        r = await web_search(a["query"], max_results=int(a.get("max_results") or 8))
        lines = [f"engine={r['engine']} retrieved_at={now_iso()} note={r['note']}"]
        for i, x in enumerate(r["results"], 1):
            lines.append(f"{i}. {x['title']}\n   {x['url']}\n   {x['snippet']}")
        return "\n".join(lines) if r["results"] else "No results (engine may be unavailable). Use web_fetch on known URLs."

    async def t_request_approval(self, a, cid):
        rt, ctx = self.rt, self.ctx
        payload = {"action": a["action"], "description": a["description"], "payload": a.get("payload") or {},
                   "estimated_cost_usd": a.get("estimated_cost_usd")}
        h = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        ap = Approval(approval_id=new_id("apr"), run_id=rt.run_id, task_id=ctx.task_id, agent_id=ctx.agent.agent_id,
                      action=a["action"], payload=payload, payload_hash=h, nonce=secrets.token_hex(8),
                      created_at=now_iso(), expires_at=(now_utc() + timedelta(hours=24)).isoformat().replace("+00:00", "Z"))
        await rt.runs.insert_approval(ap)
        await rt.events.append(rt.run_id, "approval.requested", {"approval_id": ap.approval_id, "action": ap.action,
                                                                 "description": a["description"], "payload_hash": h,
                                                                 "estimated_cost_usd": a.get("estimated_cost_usd")},
                               actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        ev = asyncio.Event()
        rt.approval_waiters[ap.approval_id] = ev
        try:
            await asyncio.wait_for(ev.wait(), timeout=min(rt.approval_wait_seconds, max(1.0, rt.remaining_seconds() - 5)))
        except asyncio.TimeoutError:
            ctx.approval_pending = ap
            return ("PENDING: approval not yet resolved by the human. Your task will pause until it is resolved. "
                    "Call finish_task or report_blocker now if nothing else can be done.")
        finally:
            rt.approval_waiters.pop(ap.approval_id, None)
        resolved = await rt.runs.get_approval(ap.approval_id)
        if resolved and resolved.status == ApprovalStatus.approved:
            return f"APPROVED approval_id={ap.approval_id} payload_hash={resolved.payload_hash}. Proceed with exactly the approved payload."
        if resolved and resolved.status == ApprovalStatus.edited:
            return f"APPROVED WITH EDITS approval_id={ap.approval_id}. Use this payload instead: {json.dumps(resolved.payload, ensure_ascii=False)}"
        return f"REJECTED approval_id={ap.approval_id}: {(resolved.resolution or {}).get('note', '') if resolved else ''}"

    async def t_report_blocker(self, a, cid):
        self.ctx.blocked = {"reason": a["reason"], "needed": a.get("needed", "")}
        await self.rt.events.append(self.rt.run_id, "blocker.reported", self.ctx.blocked, actor_id=self.ctx.agent.agent_id,
                                    actor_kind="agent", task_id=self.ctx.task_id, causation_id=cid)
        return "OK: blocker recorded; your session will end."

    async def t_submit_review(self, a, cid):
        rt, ctx = self.rt, self.ctx
        target = rt.tasks.get(a["target_task_id"])
        if target is None:
            return f"REJECTED: unknown task {a['target_task_id']}"
        if ctx.task and a["target_task_id"] not in ctx.task.spec.depends_on:
            return f"REJECTED: your task does not depend on {a['target_task_id']}; you may only review your declared targets"
        ids = {c.id for c in target.spec.acceptance}
        results = [ReviewResult(**r) for r in a["results"]]
        reported_ids = [r.acceptance_id for r in results]
        if len(set(reported_ids)) != len(reported_ids):
            return "REJECTED: duplicate acceptance ids; submit exactly one result for each criterion"
        unknown = [r.acceptance_id for r in results if r.acceptance_id not in ids]
        if unknown:
            return f"REJECTED: unknown acceptance ids {unknown}; valid: {sorted(ids)}"
        missing = ids - {r.acceptance_id for r in results}
        if missing:
            return f"REJECTED: missing results for acceptance ids {sorted(missing)}"
        refs = []
        for r in a.get("target_artifacts") or []:
            m = await self._artifact(r["artifact_id"], r.get("revision"))
            if m is None or (r.get("sha256") is not None and r["sha256"] != m.sha256):
                return "REJECTED: review artifact does not exist or its SHA-256 differs; read the current target revision"
            refs.append(m.ref())
        current_refs = await latest_task_refs(rt, target.spec.id)
        if not refs:  # bind to the target task's latest published artifacts
            refs = current_refs
        if not same_refs(refs, current_refs):
            return ("REJECTED: review must cover exactly the target task's latest artifacts (id, revision and SHA-256). "
                    "Read every listed revision before resubmitting; these references identify the review scope, not a verdict. "
                    "Required target_artifacts: " + json.dumps([ref.model_dump() for ref in current_refs], ensure_ascii=False))
        review = Review(target_task_id=target.spec.id, target_artifacts=refs, results=results, summary=a.get("summary", ""))
        ctx.communicated_to.discard(target.spec.owner)
        ctx.reviews = [r for r in ctx.reviews if r.target_task_id != target.spec.id] + [review]
        await rt.events.append(rt.run_id, "review.submitted", review.model_dump(), actor_id=ctx.agent.agent_id,
                               actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        remaining = [d for d in (ctx.task.spec.depends_on if ctx.task else []) if d not in {r.target_task_id for r in ctx.reviews}
                     and rt.tasks.get(d) and rt.agents[rt.tasks[d].spec.owner].role != "reviewer"]
        return "OK: review recorded." + (f" Still to review: {', '.join(remaining)}." if remaining else " Now send the review finding/decision to the target owner, then call finish_task with summary (string). "
                "Do not copy review results into verified; that optional field only accepts strings.")

    async def t_create_task(self, a, cid):
        if self.ctx.agent.role != "master" or self.rt.scheduler is None or self.ctx.mode not in ("exception", "milestone"):
            return "DENIED: only the master may create tasks, and only in exception/milestone sessions"
        spec = TaskSpec(id=a["id"], owner=a["owner"], objective=a["objective"], depends_on=list(a.get("depends_on") or []),
                        output_paths=list(a.get("output_paths") or []), acceptance=a["acceptance"],
                        write_scope=f"workspaces/{a['id']}/")
        err = await self.rt.scheduler.add_task(spec, causation_id=cid)
        return err or f"OK: task {spec.id} created"

    async def t_update_task(self, a, cid):
        if self.ctx.agent.role != "master" or self.rt.scheduler is None:
            return "DENIED: only the master may update tasks"
        err = await self.rt.scheduler.decide(a["task_id"], a["action"], a.get("note", ""), causation_id=cid)
        return err or f"OK: {a['action']} applied to {a['task_id']}"

    async def t_read_events(self, a, cid):
        evs = await self.rt.events.list(self.rt.run_id, after_seq=int(a.get("after_seq") or 0), limit=int(a.get("limit") or 100))
        return "\n".join(f"{e.seq} {e.recorded_at} {e.actor_id} {e.type} task={e.task_id or '-'} {json.dumps(e.payload, ensure_ascii=False)[:300]}"
                         for e in evs) or "(no events)"
