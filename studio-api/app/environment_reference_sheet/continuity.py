"""Truthful metadata-based continuity checks for ERS."""

from __future__ import annotations

from .contracts import (
    ContinuityFinding,
    ContinuityValidationReport,
    DirectionalViewRecord,
    EnvironmentReferenceSheet,
)

_EXPECTED_DIRECTIONS = ("north", "east", "south", "west")


def _view_by_direction(sheet: EnvironmentReferenceSheet) -> dict[str, DirectionalViewRecord]:
    return {view.direction: view for view in sheet.directionalViews}


def validate_sheet(sheet: EnvironmentReferenceSheet) -> ContinuityValidationReport:
    findings: list[ContinuityFinding] = []
    preserved: list[str] = []
    views = _view_by_direction(sheet)

    if sheet.spatialMap is None:
        # Adept UI v1.1: Spatial Map is optional enrichment (shelved). ERS remains
        # environment authority without a map document — soft advisory only.
        findings.append(
            ContinuityFinding(
                severity="warning",
                code="spatial_map_missing",
                title="Place layout not attached",
                message="No place-layout document is linked. Directional north-lock enrichment is unavailable; ERS package/sheet/composite remains authoritative.",
                recommendedAction="Optional later: attach a place-layout document for geometry enrichment. Not required for Environment Creator ERS.",
            )
        )

    for direction in _EXPECTED_DIRECTIONS:
        view = views.get(direction)
        if view is None:
            findings.append(
                ContinuityFinding(
                    severity="error",
                    code="direction_missing",
                    title=f"{direction.title()} view missing",
                    message=f"The {direction.title()} direction has not been planned yet.",
                    affectedDirections=[direction],  # type: ignore[list-item]
                    recommendedAction="Create the missing directional plan from the north-locked map.",
                )
            )
            continue
        if view.status in {"approved", "ready"} and view.approvedAssetId:
            preserved.append(direction)
        elif view.status in {"planned", "queued", "missing"}:
            findings.append(
                ContinuityFinding(
                    severity="warning",
                    code="direction_unapproved",
                    title=f"{direction.title()} view still needs approval",
                    message=f"The {direction.title()} direction exists, but it has not reached an approved asset yet.",
                    affectedDirections=[direction],  # type: ignore[list-item]
                    recommendedAction="Review candidates for this direction and approve the keeper.",
                )
            )
        elif view.status == "blocked":
            findings.append(
                ContinuityFinding(
                    severity="error",
                    code="direction_blocked",
                    title=f"{direction.title()} view blocked",
                    message=f"The {direction.title()} direction is currently blocked and cannot be treated as stable coverage.",
                    affectedDirections=[direction],  # type: ignore[list-item]
                    recommendedAction="Repair or regenerate only this blocked direction unless the creator asks for a wider rebuild.",
                )
            )

    if sheet.spatialMap and sheet.spatialMap.warnings:
        findings.append(
            ContinuityFinding(
                severity="warning",
                code="spatial_map_warnings",
                title="Place layout has open warnings",
                message="The linked place-layout document still reports staging warnings that may affect environment continuity.",
                recommendedAction="Clear those layout warnings before final approval when possible.",
            )
        )

    has_error = any(item.severity == "error" for item in findings)
    summary = (
        "Directional continuity is ready for review."
        if not findings
        else "Continuity review found issues that should be repaired before final approval."
    )
    return ContinuityValidationReport(
        status="blocked" if has_error else ("warning" if findings else "ready"),
        summary=summary,
        findings=findings,
        repairStrategy="preserve_approved_views",
        preservedDirections=preserved,  # type: ignore[arg-type]
        note="Continuity findings are metadata-based in this foundation pass; no pixel-level vision claim is made.",
    )
