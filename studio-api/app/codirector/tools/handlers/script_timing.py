"""Script timing estimation tools for Co-Director."""

from typing import Any

from ..definitions import ToolContext


async def read_script_timing(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Estimate script runtime and per-scene timing."""
    db = ctx.db
    project_id = ctx.project_id
    try:
        from app.scriptwriter.store import list_documents, load_document
        from app.scriptwriter.stats import compute_stats

        docs = list_documents(db, project_id)
        if not docs:
            return {"status": "no_script", "message": "No script document found for this project."}
        doc = load_document(db, docs[0].id)
        if not doc or not doc.elements:
            return {"status": "empty_script", "message": "The script document has no content."}

        stats = compute_stats(doc)

        scenes: list[dict[str, Any]] = []
        current_scene = None
        scene_elements: list = []
        for el in doc.elements:
            if el.type == "scene_heading":
                if current_scene:
                    scene_words = sum(
                        len(e.text.split())
                        for e in scene_elements
                        if e.type in ("action", "dialogue", "parenthetical")
                    )
                    scene_pages = scene_words / 180 if scene_words > 0 else 0
                    scenes.append({
                        "sceneNumber": current_scene.sceneNumber,
                        "heading": current_scene.text,
                        "elementCount": len(scene_elements),
                        "wordCount": scene_words,
                        "estimatedPages": round(scene_pages, 1),
                        "estimatedRuntimeSec": round(scene_pages * 60, 0),
                    })
                current_scene = el
                scene_elements = [el]
            else:
                scene_elements.append(el)
        # Last scene
        if current_scene:
            scene_words = sum(
                len(e.text.split())
                for e in scene_elements
                if e.type in ("action", "dialogue", "parenthetical")
            )
            scene_pages = scene_words / 180 if scene_words > 0 else 0
            scenes.append({
                "sceneNumber": current_scene.sceneNumber,
                "heading": current_scene.text,
                "elementCount": len(scene_elements),
                "wordCount": scene_words,
                "estimatedPages": round(scene_pages, 1),
                "estimatedRuntimeSec": round(scene_pages * 60, 0),
            })

        return {
            "status": "ok",
            "title": doc.title,
            "totalElements": len(doc.elements),
            "totalWords": stats.words,
            "estimatedPages": stats.pagesEstimated,
            "estimatedRuntimeMinutes": stats.runtimeMinutesEstimated,
            "sceneCount": len(scenes),
            "scenes": scenes,
            "note": "Runtime estimates use the industry guideline of ~1 page = ~1 minute. Actual runtime varies with dialogue density, action, pauses, and performance.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
