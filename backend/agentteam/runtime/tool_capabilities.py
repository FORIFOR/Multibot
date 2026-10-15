"""Shared tool-capability boundary used by admission and the actual gateway.

Only document reviewers have a file-only run_check. Every other role/workflow
can reach command checks, even if its configured tool list contains no
sandbox_run. Unknown workflows deliberately retain the conservative boundary.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..config.loader import CORE_TOOLS
from ..config.models import AgentTeamConfig

DOCUMENT_REVIEW_TOOLS = frozenset({
    'read_skill', 'read_input_file', 'read_artifact', 'list_artifacts', 'run_check',
    'send_message', 'read_messages', 'read_events', 'submit_review', 'finish_task', 'report_blocker',
})


def is_document_reviewer(workflow: str, role: str) -> bool:
    return workflow == 'document' and role == 'reviewer'


def allowed_tools(workflow: str, role: str, tools: Iterable[str]) -> list[str]:
    if is_document_reviewer(workflow, role):
        return [name for name in tools if name in DOCUMENT_REVIEW_TOOLS]
    return list(tools)


def requires_command_sandbox(cfg: AgentTeamConfig, workflow: str = 'team') -> bool:
    """Whether any enabled configured agent can invoke a shell-capable tool.

    Call with the effective, selected/overridden configuration that will be
    saved for execution, and that run's workflow. This is a capability check,
    not a substitute for the gateway or require_container execution guard.
    """
    for agent in cfg.agents:
        if not agent.enabled:
            continue
        names = set(allowed_tools(workflow, agent.role, [*CORE_TOOLS, *agent.tools]))
        if 'sandbox_run' in names or ('run_check' in names and not is_document_reviewer(workflow, agent.role)):
            return True
    return False
