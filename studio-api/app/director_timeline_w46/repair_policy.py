"""Multi-range repair overlap policy — block by default."""

from __future__ import annotations

from .contracts import RepairOverlapDecision, RepairOverlapPolicy, RepairRange


def _overlaps(a: RepairRange, b: RepairRange) -> bool:
    a0, a1 = a.start, a.start + a.length
    b0, b1 = b.start, b.start + b.length
    return a0 < b1 and b0 < a1


def apply_repair_overlap_policy(
    existing: list[RepairRange],
    incoming: RepairRange,
    *,
    policy: RepairOverlapPolicy = "block",
) -> RepairOverlapDecision:
    conflicts = [r for r in existing if r.id != incoming.id and _overlaps(r, incoming)]
    if not conflicts:
        ranges = list(existing) + [incoming]
        # Deterministic layer order by start then id
        ranges.sort(key=lambda r: (r.start, r.layer, r.id))
        for i, r in enumerate(ranges):
            r.layer = i
        return RepairOverlapDecision(
            ok=True,
            policy=policy,
            ranges=ranges,
            message="Range accepted.",
        )

    if policy == "block":
        return RepairOverlapDecision(
            ok=False,
            policy=policy,
            blocked=True,
            message="Overlapping repair ranges are blocked by default. Merge Ranges or enable Advanced stacked layers.",
            ranges=list(existing),
        )

    if policy == "merge":
        starts = [incoming.start] + [c.start for c in conflicts]
        ends = [incoming.start + incoming.length] + [c.start + c.length for c in conflicts]
        merged = RepairRange(
            id=incoming.id,
            start=min(starts),
            length=max(ends) - min(starts),
            mode=incoming.mode,
            inPaintStrategy=incoming.inPaintStrategy,
            layer=0,
            status=incoming.status,
            label=incoming.label or "Merged repair",
        )
        kept = [r for r in existing if r.id not in {c.id for c in conflicts}]
        ranges = kept + [merged]
        ranges.sort(key=lambda r: (r.start, r.id))
        for i, r in enumerate(ranges):
            r.layer = i
        return RepairOverlapDecision(
            ok=True,
            policy=policy,
            merged=True,
            ranges=ranges,
            message="Overlapping ranges merged.",
        )

    # stack_advanced — allow with deterministic top layer
    top_layer = max((r.layer for r in existing), default=-1) + 1
    stacked = incoming.model_copy(update={"layer": top_layer})
    ranges = list(existing) + [stacked]
    ranges.sort(key=lambda r: (r.layer, r.start, r.id))
    return RepairOverlapDecision(
        ok=True,
        policy=policy,
        stacked=True,
        ranges=ranges,
        message=f"Stacked repair layer {top_layer} (visually on top).",
    )
