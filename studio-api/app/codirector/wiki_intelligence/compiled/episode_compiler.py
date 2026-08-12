"""Episode pages from persisted script installments."""

from __future__ import annotations

from typing import Any


def compile_episode_pages(installments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for inst in installments:
        num = int(inst.get("episodeNumber") or inst.get("number") or 1)
        title = str(inst.get("title") or f"Episode {num}").strip()
        if not title.lower().startswith("episode"):
            display = f"Episode {num} — “{title}”"
        else:
            display = title
        summary = str(inst.get("summary") or inst.get("overview") or "").strip()
        scenes = inst.get("scenes") or inst.get("sceneBreakdown") or []
        if isinstance(scenes, dict):
            scenes = scenes.get("scenes") or list(scenes.values())
        scene_bullets: list[str] = []
        for sc in scenes[:20]:
            if isinstance(sc, dict):
                heading = sc.get("heading") or sc.get("slugline") or sc.get("title") or ""
                action = sc.get("summary") or sc.get("action") or ""
                line = f"{heading}: {action}".strip(": ").strip()
                if line:
                    scene_bullets.append(line[:200])
            elif isinstance(sc, str) and sc.strip():
                scene_bullets.append(sc.strip()[:200])
        chars = inst.get("characters") or []
        char_names = []
        for c in chars:
            if isinstance(c, dict):
                char_names.append(str(c.get("name") or c.get("canonicalName") or ""))
            else:
                char_names.append(str(c))
        char_names = [c for c in char_names if c]
        if not summary and scene_bullets:
            summary = scene_bullets[0]
        if not summary and char_names:
            summary = f"{display} introduces {', '.join(char_names[:3])}."
        page_id = f"page-episode-{num}"
        sections = [
            {"id": "sec-ep-overview", "title": "Overview", "body": summary, "bullets": []},
        ]
        if scene_bullets:
            sections.append(
                {"id": "sec-ep-scenes", "title": "Scenes", "body": "", "bullets": scene_bullets}
            )
        if char_names:
            sections.append(
                {
                    "id": "sec-ep-chars",
                    "title": "Characters",
                    "body": "",
                    "bullets": char_names,
                }
            )
        source = inst.get("sourceFilename") or inst.get("source") or ""
        if source:
            sections.append(
                {
                    "id": "sec-ep-source",
                    "title": "References",
                    "body": f"Source script: {source}",
                    "bullets": [],
                }
            )
        pages.append(
            {
                "pageId": page_id,
                "pageType": "EPISODE",
                "title": display,
                "summary": summary,
                "sections": sections,
                "relatedPageIds": ["page-story"],
                "sourceRecordIds": [str(inst.get("id") or page_id)],
                "canonState": "CONFIRMED",
                "questionsToExplore": [],
                "episodeNumber": num,
            }
        )
    return pages
