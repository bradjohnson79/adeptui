"""Storyboard timing estimation tools for Co-Director."""

from typing import Any

from ..definitions import ToolContext


async def read_storyboard_timing(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Estimate storyboard runtime from panel durations."""
    db = ctx.db
    project_id = ctx.project_id
    try:
        from app.codirector.project_context import _get_storyboard

        sb = _get_storyboard(db, project_id)
        if not sb:
            return {"status": "no_storyboard", "message": "No storyboard document found for this project."}

        panels = sb.get("panels", [])
        if not panels:
            return {"status": "empty_storyboard", "message": "The storyboard has no panels."}
        total_duration = sb.get("totalDurationEst", 0)

        # Per-panel breakdown
        panel_timings: list[dict[str, Any]] = []
        for i, p in enumerate(panels):
            dur = p.get("durationEst")
            has_dur = dur is not None
            panel_timings.append({
                "index": i + 1,
                "label": p.get("label") or f"Panel {i + 1}",
                "durationSec": dur if has_dur else 3.0,
                "shotSize": p.get("shotSize"),
                "hasDuration": has_dur,
            })

        # Identify missing durations
        missing_count = sum(1 for p in panel_timings if not p["hasDuration"])

        return {
            "status": "ok",
            "panelCount": len(panels),
            "totalDurationSec": total_duration,
            "totalDurationFormatted": (
                f"{int(total_duration // 60)}m {int(total_duration % 60)}s"
                if total_duration
                else "0s"
            ),
            "panels": panel_timings,
            "missingDurationCount": missing_count,
            "note": (
                "Durations are estimates (default 3.0s per panel) where explicit durations are not set."
                if missing_count > 0
                else "All panels have explicit durations."
            ),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
