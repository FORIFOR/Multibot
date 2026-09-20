"""Requester-owned requirements; model reviews cannot override these checks."""
from __future__ import annotations

import hashlib
from .checks import isolated_check
from .policy import PolicyViolation


async def unpublished_workspace_changes(ctx):
    """Existing output drafts must match publication before either finish path.

    Missing drafts remain compatible with restored, immutable publications.
    Scratch files are not deliverables. Never follow a path outside the workspace.
    """
    if ctx.task is None or ctx.workspace is None:
        return []
    root = ctx.workspace.resolve()
    changed = []
    for artifact in await ctx.rt.artifacts.list(ctx.rt.run_id, latest_only=True):
        if artifact.task_id != ctx.task_id:
            continue
        try:
            logical = ctx.rt.policy.check_write_path(artifact.logical_path)
            path = (root / logical).resolve()
            if not path.is_relative_to(root):
                changed.append(artifact.logical_path)
                continue
            if path.exists() and (not path.is_file() or
                    hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256):
                changed.append(artifact.logical_path)
        except (OSError, RuntimeError, PolicyViolation):
            changed.append(artifact.logical_path)
    return changed


async def verify_delivery(rt, *, task_id=None, actor_id='runtime', record=True):
    requirements = rt.run.inputs.delivery_requirements
    if not requirements:
        return []
    artifacts = {a.logical_path: a for a in await rt.artifacts.list(rt.run_id, latest_only=True)}
    results = []
    for required in requirements:
        artifact = artifacts.get(required.logical_path)
        # An intermediate task need not produce all final outputs. Global
        # finalization below checks every requirement, including missing paths.
        if task_id is not None and (not artifact or artifact.task_id != task_id):
            continue
        if artifact is None:
            result = {'status': 'fail', 'problems': ['required artifact was not published']}
            target = None
        else:
            target = {'artifact_id': artifact.artifact_id, 'revision': artifact.revision, 'sha256': artifact.sha256}
            try:
                raw = rt.artifacts.read_bytes(artifact)
                if hashlib.sha256(raw).hexdigest() != artifact.sha256:
                    result = {'status': 'fail', 'problems': ['artifact checksum mismatch']}
                else:
                    result = await isolated_check('json_schema', raw, {'schema': required.json_schema, 'input_format': required.input_format})
            except OSError:
                result = {'status': 'fail', 'problems': ['artifact storage unavailable']}
        row = {'logical_path': required.logical_path, 'target': target, 'result': result,
               'schema_sha256': hashlib.sha256(required.model_dump_json().encode()).hexdigest()}
        results.append(row)
        if record:
            await rt.events.append(rt.run_id, 'delivery.checked', row, task_id=task_id, actor_id=actor_id, actor_kind='runtime')
    return results


def failures(results):
    return [f"{r['logical_path']}: " + '; '.join(r['result'].get('problems', ['required check did not pass']))
            for r in results if r['result']['status'] != 'pass']
