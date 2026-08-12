"""Directed acyclic dependency graph validation for plan steps."""

from __future__ import annotations

from .schemas import DependencyValidationResult, ProductionPlanStep


def validate_dependencies(steps: list[ProductionPlanStep]) -> DependencyValidationResult:
    ids = {s.stepId for s in steps}
    self_deps: list[str] = []
    missing: list[str] = []
    for s in steps:
        for dep in s.dependsOn or []:
            if dep == s.stepId:
                self_deps.append(s.stepId)
            elif dep not in ids:
                missing.append(f"{s.stepId}->{dep}")

    # Cycle detection (DFS)
    graph = {s.stepId: list(s.dependsOn or []) for s in steps}
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                idx = stack.index(node)
                cycles.append(stack[idx:] + [node])
            return
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt in graph:
                dfs(nxt)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for sid in graph:
        dfs(sid)

    # Unreachable: steps with no path from roots (no deps) — warn only if orphaned after deps missing
    roots = [s.stepId for s in steps if not s.dependsOn]
    reachable: set[str] = set()
    reverse = {s.stepId: [] for s in steps}
    for s in steps:
        for dep in s.dependsOn or []:
            if dep in reverse:
                reverse[dep].append(s.stepId)

    queue = list(roots)
    while queue:
        cur = queue.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        queue.extend(reverse.get(cur, []))

    unreachable = [s.stepId for s in steps if s.stepId not in reachable and s.dependsOn]

    warnings: list[str] = []
    if unreachable:
        warnings.append(f"{len(unreachable)} step(s) unreachable from roots.")

    valid = not cycles and not missing and not self_deps
    return DependencyValidationResult(
        valid=valid,
        cycles=cycles,
        missingDependencies=missing,
        selfDependencies=self_deps,
        unreachableSteps=unreachable,
        warnings=warnings,
    )


def compute_step_readiness(steps: list[ProductionPlanStep], open_blocker_step_ids: set[str]) -> list[ProductionPlanStep]:
    """Return steps with state adjusted from dependencies/blockers (non-terminal only)."""
    by_id = {s.stepId: s.model_copy(deep=True) for s in steps}
    completed = {sid for sid, s in by_id.items() if s.state in {"completed", "skipped"}}
    for s in by_id.values():
        if s.state in {"completed", "failed", "skipped", "cancelled", "in_progress", "unsupported"}:
            continue
        if s.executionAvailability in {"deferred", "unsupported", "unconfigured"}:
            s.state = "deferred" if s.executionAvailability != "unsupported" else "unsupported"
            continue
        if s.stepId in open_blocker_step_ids or any(b for b in s.blockedBy):
            s.state = "blocked"
            continue
        deps = s.dependsOn or []
        if deps and not all(d in completed for d in deps):
            s.state = "pending"
            continue
        if s.requiresApproval and s.state != "awaiting_approval":
            # leave awaiting_approval if already set
            if s.state != "awaiting_approval":
                s.state = "ready"
        else:
            s.state = "ready"
    return [by_id[s.stepId] for s in steps]
