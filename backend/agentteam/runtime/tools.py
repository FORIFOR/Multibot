"""ToolGateway: the only way an agent touches the world. Every call is authorized, counted and recorded."""
from __future__ import annotations

import asyncio
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
from .context import SessionContext
from .policy import PolicyViolation
from .sandbox import run_command
from .webtools import FetchDenied, web_fetch, web_search

PURPOSES = ["request", "question", "answer", "handoff", "finding", "decision"]

_REF = {"type": "object", "properties": {"artifact_id": {"type": "string"}, "revision": {"type": "integer"},
                                         "sha256": {"type": "string"}}, "required": ["artifact_id", "revision"]}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


TOOL_SPECS: dict[str, ToolSpec] = {
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
                             "finding, decision. Do not send acknowledgements or encouragement. Reference artifacts by id/revision "
                             "instead of pasting them.",
                             _obj({"to": {"type": "string"}, "purpose": {"type": "string", "enum": PURPOSES},
                                   "text": {"type": "string"}, "task_id": {"type": "string"},
                                   "artifact_refs": {"type": "array", "items": _REF}, "reply_to": {"type": "string"}},
                                  ["to", "purpose", "text"])),
    "read_messages": ToolSpec("read_messages",
                              "Read unread messages addressed to you for your tasks. wait_seconds>0 blocks until a message arrives.",
                              _obj({"wait_seconds": {"type": "integer", "minimum": 0, "maximum": 240}})),
    "read_artifact": ToolSpec("read_artifact", "Read a published artifact revision (latest if revision omitted).",
                              _obj({"artifact_id": {"type": "string"}, "revision": {"type": "integer"}}, ["artifact_id"])),
    "list_artifacts": ToolSpec("list_artifacts", "List published artifacts in this run with their latest revision.", _obj({})),
    "workspace_write": ToolSpec("workspace_write", "Write a text file inside your task workspace (relative path).",
                                _obj({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])),
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
                          + "; ".join(f"{k}: {v}" for k, v in CHECK_KINDS.items()),
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

    def specs(self) -> list[ToolSpec]:
        return [TOOL_SPECS[n] for n in self.ctx.tools if n in TOOL_SPECS]

    async def call(self, name: str, args: dict[str, Any], *, causation_id: str | None = None) -> str:
        rt, ctx = self.rt, self.ctx
        policy = rt.policy
        try:
            policy.check_tool_allowed(ctx.tools, name)
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

    # ------------------------------------------------------------------ tools
    async def t_read_skill(self, a, cid):
        names = [s["name"] for s in self.ctx.agent.skills]
        if a["name"] not in names:
            return f"DENIED: skill {a['name']} is not enabled for you. Enabled: {names}"
        return read_skill_body(a["name"]) or "ERROR: skill body not found"

    async def t_finish_task(self, a, cid):
        if self.ctx.mode == "reply":
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
        if self.ctx.agent.role == "reviewer":
            targets = [d for d in spec.depends_on if self.rt.tasks.get(d) and self.rt.agents.get(self.rt.tasks[d].spec.owner)
                       and self.rt.agents[self.rt.tasks[d].spec.owner].role != "reviewer"]
            done = {r.target_task_id for r in self.ctx.reviews}
            missing_reviews = [t for t in targets if t not in done]
            if missing_reviews:
                return ("REJECTED: call submit_review for each target task before finish_task. Missing: " + ", ".join(missing_reviews))
        self.ctx.finished = TaskResult(summary=a.get("summary", ""), verified=list(a.get("verified") or []),
                                       unverified=list(a.get("unverified") or []), next_steps=list(a.get("next_steps") or []),
                                       published=[p.ref() for p in self.ctx.published])
        return "OK: task finished"

    async def _artifact_for_path(self, logical_path: str):
        for m in await self.rt.artifacts.list(self.rt.run_id, latest_only=True):
            if m.logical_path == logical_path:
                return m
        return None

    async def t_send_message(self, a, cid):
        rt, ctx = self.rt, self.ctx
        to = a["to"]
        if to == ctx.agent.agent_id:
            return "REJECTED: cannot message yourself"
        if to == "user":
            return "REJECTED: there is no user mailbox. Use report_blocker for information you need from the human."
        if to not in rt.agents or not rt.agents[to].enabled:
            return f"REJECTED: unknown or disabled agent {to}. Enabled: {[x.agent_id for x in rt.enabled_agents()]}"
        task_id = a.get("task_id") or ctx.task_id
        if not task_id:
            return "REJECTED: task_id is required in this session"
        if task_id not in rt.tasks:
            return f"REJECTED: unknown task {task_id}"
        refs = []
        for r in a.get("artifact_refs") or []:
            m = await self._artifact(r["artifact_id"], r.get("revision"))
            if m is None:
                return f"REJECTED: artifact {r['artifact_id']} rev {r.get('revision')} does not exist; publish first"
            refs.append(m.ref())
        if ctx.mode == "task" and ctx.task is not None:
            rt.policy.count_peer_message(task_id)
        m = await rt.bus.send(from_agent_id=ctx.agent.agent_id, to_agent_id=to, task_id=task_id, purpose=a["purpose"],
                              text=a["text"], artifact_refs=refs, reply_to=a.get("reply_to"), causation_id=cid)
        if a["purpose"] == "answer":
            ctx.replied = True
        return f"DELIVERED message_id={m.message_id} to={to} task={task_id}. Use read_messages(wait_seconds=N) to wait for a reply."

    async def t_read_messages(self, a, cid):
        rt, ctx = self.rt, self.ctx
        wait = min(int(a.get("wait_seconds") or 0), 240, max(0, int(rt.remaining_seconds()) - 5))
        msgs = await rt.bus.read(ctx.agent.agent_id, None if ctx.mode != "task" else ctx.owned_task_ids(), wait_seconds=wait)
        if not msgs:
            return "No new messages." + (f" (waited {wait}s)" if wait else "")
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
            return f"NOT FOUND: artifact {a['artifact_id']}"
        await self.rt.events.append(self.rt.run_id, "artifact.read", {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256},
                                    actor_id=self.ctx.agent.agent_id, actor_kind="agent", task_id=self.ctx.task_id, causation_id=cid)
        if m.media_type.startswith("text/") or m.media_type in ("application/json", "image/svg+xml"):
            body = self.rt.artifacts.read_text(m)
        else:
            body = f"<binary {m.media_type}, {m.size} bytes>"
        return (f"artifact_id={m.artifact_id} revision={m.revision} sha256={m.sha256} media_type={m.media_type} "
                f"logical_path={m.logical_path} by={m.agent_id} task={m.task_id}\n---\n{body}")

    async def t_list_artifacts(self, a, cid):
        items = await self.rt.artifacts.list(self.rt.run_id, latest_only=True)
        if not items:
            return "No artifacts published yet."
        return "\n".join(f"{m.artifact_id} r{m.revision} sha256={m.sha256[:12]} {m.media_type} {m.size}B path={m.logical_path} by={m.agent_id}/{m.task_id}"
                         for m in items)

    async def t_workspace_write(self, a, cid):
        p = self._ws_path(a["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(a["content"], encoding="utf-8")
        return f"OK: wrote {len(a['content'])} chars to {a['path']}"

    async def t_workspace_read(self, a, cid):
        p = self._ws_path(a["path"])
        if not p.is_file():
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
        m = await rt.artifacts.publish(rt.run_id, logical, data, agent_id=ctx.agent.agent_id, task_id=ctx.task_id,
                                       media_type=a.get("media_type"), sources=list(a.get("sources") or []))
        ev = await rt.events.append(rt.run_id, "artifact.published",
                                    {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256,
                                     "media_type": m.media_type, "size": m.size, "logical_path": m.logical_path,
                                     "sources": m.sources},
                                    actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        await rt.artifacts.set_event(rt.run_id, m.artifact_id, m.revision, ev.event_id)
        ctx.published.append(m)
        return f"PUBLISHED artifact_id={m.artifact_id} revision={m.revision} sha256={m.sha256} media_type={m.media_type}"

    async def t_sandbox_run(self, a, cid):
        ws = self.ctx.workspace
        if ws is None:
            return "DENIED: no workspace in this session"
        timeout = float(a.get("timeout_seconds") or 120)
        r = await run_command(a["command"], ws, timeout=min(timeout, max(5.0, self.rt.remaining_seconds() - 5)),
                              max_output=self.rt.config.limits.max_tool_output_chars)
        if r.denied:
            return f"DENIED: {r.reason}"
        return f"backend={r.backend} exit_code={r.exit_code} timed_out={r.timed_out}\n--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}"

    async def t_run_check(self, a, cid):
        rt, ctx = self.rt, self.ctx
        kind = a["kind"]
        data: bytes | None = None
        target: dict[str, Any] = {}
        if a.get("artifact_id"):
            m = await self._artifact(a["artifact_id"], a.get("revision"))
            if m is None:
                return f"NOT FOUND: artifact {a['artifact_id']}"
            data = rt.artifacts.read_bytes(m)
            target = {"artifact_id": m.artifact_id, "revision": m.revision, "sha256": m.sha256}
        elif a.get("path"):
            p = self._ws_path(a["path"])
            if not p.is_file():
                return (f"NOT FOUND: {a['path']} in your task workspace. To check another task’s "
                        "published output, use artifact_id and revision from list_artifacts instead of path.")
            data = p.read_bytes()
            target = {"workspace_path": a["path"], "sha256": hashlib.sha256(data).hexdigest()}
        elif kind != "command":
            return "REJECTED: provide artifact_id (published revision) or path (workspace file)"
        result = await run_check(kind, data, dict(a.get("args") or {}), ctx.workspace)
        await rt.events.append(rt.run_id, "check.completed", {"kind": kind, "target": target, "args": a.get("args") or {},
                                                              "result": result},
                               actor_id=ctx.agent.agent_id, actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        return json.dumps({"kind": kind, "target": target, "result": result}, ensure_ascii=False, indent=1)

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
        unknown = [r.acceptance_id for r in results if r.acceptance_id not in ids]
        if unknown:
            return f"REJECTED: unknown acceptance ids {unknown}; valid: {sorted(ids)}"
        missing = ids - {r.acceptance_id for r in results}
        if missing:
            return f"REJECTED: missing results for acceptance ids {sorted(missing)}"
        refs = []
        for r in a.get("target_artifacts") or []:
            m = await self._artifact(r["artifact_id"], r.get("revision"))
            if m:
                refs.append(m.ref())
        if not refs:  # bind to the target task's latest published artifacts
            for m in await rt.artifacts.list(rt.run_id, latest_only=True):
                if m.task_id == target.spec.id:
                    refs.append(m.ref())
        review = Review(target_task_id=target.spec.id, target_artifacts=refs, results=results, summary=a.get("summary", ""))
        ctx.reviews = [r for r in ctx.reviews if r.target_task_id != target.spec.id] + [review]
        await rt.events.append(rt.run_id, "review.submitted", review.model_dump(), actor_id=ctx.agent.agent_id,
                               actor_kind="agent", task_id=ctx.task_id, causation_id=cid)
        remaining = [d for d in (ctx.task.spec.depends_on if ctx.task else []) if d not in {r.target_task_id for r in ctx.reviews}
                     and rt.tasks.get(d) and rt.agents[rt.tasks[d].spec.owner].role != "reviewer"]
        return "OK: review recorded." + (f" Still to review: {', '.join(remaining)}." if remaining else " Now call finish_task with summary (string). "
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
