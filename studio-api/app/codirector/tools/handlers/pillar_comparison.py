"""Cross-pillar comparison tools for Co-Director."""

from typing import Any

from ..definitions import ToolContext


async def read_pillar_comparison(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Compare project pillars for consistency and coverage."""
    db = ctx.db
    project_id = ctx.project_id
    try:
        from app.codirector.project_context import retrieve_project_context

        context = retrieve_project_context(db, project_id)

        story = context.get("story")
        script = context.get("script")
        storyboard = context.get("storyboard")
        characters = context.get("characters")
        foundation = context.get("foundation")

        findings: list[dict[str, Any]] = []

        # Script vs Storyboard coverage
        if script and storyboard:
            script_scenes = len(script.get("scenes", []))
            sb_panels = storyboard.get("panelCount", 0)
            if sb_panels < script_scenes:
                findings.append({
                    "type": "coverage_gap",
                    "severity": "warning",
                    "message": f"Script has {script_scenes} scene(s) but storyboard has only {sb_panels} panel(s). Some scenes may not be storyboarded.",
                })
            elif sb_panels > script_scenes * 3:
                findings.append({
                    "type": "excess_coverage",
                    "severity": "info",
                    "message": f"Storyboard has {sb_panels} panels for {script_scenes} scene(s). Consider checking for redundant shots.",
                })
            else:
                findings.append({
                    "type": "coverage_ok",
                    "severity": "ok",
                    "message": f"Storyboard coverage appears reasonable: {sb_panels} panels for {script_scenes} scene(s).",
                })

            # Timing comparison
            if script.get("elementCount", 0) > 0 and storyboard.get("totalDurationEst", 0) > 0:
                script_minutes = script.get("estimatedRuntimeMinutes", 0)
                sb_seconds = storyboard.get("totalDurationEst", 0)
                sb_minutes = sb_seconds / 60
                if abs(script_minutes - sb_minutes) > 2:
                    findings.append({
                        "type": "timing_mismatch",
                        "severity": "warning",
                        "message": f"Script estimated runtime: ~{script_minutes:.1f}min. Storyboard estimated runtime: ~{sb_minutes:.1f}min. Difference: {abs(script_minutes - sb_minutes):.1f}min.",
                    })
        elif script and not storyboard:
            findings.append({
                "type": "missing_storyboard",
                "severity": "info",
                "message": "Script exists but no storyboard has been created. Timeline can work directly from the script.",
            })

        # Characters vs Script
        if characters and script:
            char_names = [c.get("name", "").lower() for c in characters.get("characters", [])]
            script_chars = [s.get("text", "") for s in script.get("elements", []) if s.get("type") == "character"]
            script_char_names = set(name.lower().strip() for name in script_chars if name.strip())
            known_chars = set(char_names)
            if script_char_names and known_chars:
                unmapped = script_char_names - known_chars
                if unmapped:
                    findings.append({
                        "type": "unmapped_characters",
                        "severity": "info",
                        "message": f"Script references characters not in Character Creator: {', '.join(list(unmapped)[:5])}. Consider creating profiles for them.",
                    })

        # Foundation readiness
        if foundation:
            missing = foundation.get("missing_pillars", [])
            if missing:
                findings.append({
                    "type": "incomplete_foundation",
                    "severity": "info",
                    "message": f"Missing pillars: {', '.join(missing)}. Timeline remains accessible — these are guidance, not blockers.",
                })
            else:
                findings.append({
                    "type": "foundation_ready",
                    "severity": "ok",
                    "message": "All four project pillars are established. Project is ready for Timeline.",
                })

        return {
            "status": "ok",
            "findings": findings,
            "pillarStatus": foundation,
            "hasStory": story is not None,
            "hasScript": script is not None,
            "hasStoryboard": storyboard is not None,
            "hasCharacters": characters is not None,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
