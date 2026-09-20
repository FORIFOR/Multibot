"""Bind a review to the exact current artifact set owned by its target task."""
from ..contracts import ArtifactRef


async def latest_task_refs(rt, task_id: str) -> list[ArtifactRef]:
    return [m.ref() for m in await rt.artifacts.list(rt.run_id, latest_only=True) if m.task_id == task_id]


def same_refs(left: list[ArtifactRef], right: list[ArtifactRef]) -> bool:
    def keys(refs):
        return {(r.artifact_id, r.revision, r.sha256) for r in refs}
    return len(left) == len(right) == len(keys(left)) and keys(left) == keys(right)
