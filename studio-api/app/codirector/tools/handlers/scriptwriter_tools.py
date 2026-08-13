"""M4.7 Co-Director script.* tools — reads + proposal-gated mutators."""

from __future__ import annotations

from typing import Any, Optional

from app.scriptwriter import service as sw
from app.scriptwriter.continuity import analyze_continuity
from app.scriptwriter.htmltext import document_text
from app.scriptwriter.stats import compute_stats
from app.scriptwriter.store import list_documents, load_document

from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview


def _doc_id(ctx: ToolContext, args: dict[str, Any]) -> str:
    doc_id = str(args.get("documentId") or args.get("scriptId") or "").strip()
    if not doc_id:
        docs = list_documents(ctx.db, ctx.project_id)
        if docs:
            return docs[0].id
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "No script document in this project.",
            details={"projectId": ctx.project_id},
            recoverable=True,
            recommended_action="open_scriptwriter",
        )
    doc = load_document(ctx.db, doc_id)
    if not doc or doc.projectId != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Script document not found in this project.",
            details={"documentId": doc_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return doc_id


def _load(ctx: ToolContext, args: dict[str, Any]):
    return sw.get_document(ctx.db, _doc_id(ctx, args))


async def script_inspect(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    stats = compute_stats(doc)
    text = document_text(doc)
    return {
        "documentId": doc.id,
        "title": doc.title,
        "revision": doc.revision,
        "contentType": doc.contentType,
        "contentPreview": text[:2000],
        "contentWords": len(text.split()),
        "elementCount": len(doc.elements),
        "sceneCount": sum(1 for e in doc.elements if e.type == "scene_heading"),
        "stats": stats.model_dump(mode="json"),
        "productionNumbersLocked": doc.productionNumbersLocked,
        "_summary": f"Script '{doc.title}' rev {doc.revision} ({doc.contentType}).",
        "_evidence": [{"sourceType": "script", "sourceId": doc.id, "sourceName": doc.title, "repository": "scriptwriter"}],
    }


async def script_scene_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    scene_id = str(args.get("sceneHeadingId") or "")
    block = sw._block_for_heading(doc.elements, scene_id)  # noqa: SLF001
    if not block:
        if doc.contentType == "html" or not doc.elements:
            text = document_text(doc)
            return {
                "documentId": doc.id,
                "sceneHeadingId": scene_id or None,
                "heading": None,
                "fullText": text[:4000],
                "syncStatus": "unlinked",
                "_summary": "Rich-text script — scene-block context unavailable; returning full text.",
            }
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "Scene not found.", details={"sceneHeadingId": scene_id})
    return {
        "documentId": doc.id,
        "sceneHeadingId": scene_id,
        "heading": block[0].text,
        "sceneNumber": block[0].sceneNumber,
        "elements": [e.model_dump(mode="json") for e in block],
        "syncStatus": doc.sceneSync.get(scene_id, "unlinked"),
        "_summary": f"Scene context for {block[0].text}.",
    }


async def script_character_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    if doc.contentType == "html" or not doc.elements:
        text = document_text(doc)
        return {
            "documentId": doc.id,
            "characterName": str(args.get("characterName") or "").strip() or None,
            "dialogueLines": [],
            "fullText": text[:4000],
            "voiceGuidance": "Script is in rich-text mode; structured character extraction is unavailable. Use fullText for context.",
            "_summary": "Rich-text script — returning full text for character context.",
        }
    name = str(args.get("characterName") or "").strip().upper()
    lines = []
    current_char: Optional[str] = None
    for e in sorted(doc.elements, key=lambda x: x.order):
        if e.type == "character":
            current_char = (e.text or "").strip().upper()
        elif e.type == "dialogue" and current_char and (not name or current_char == name):
            lines.append({"character": current_char, "text": e.text, "elementId": e.id})
        elif e.type == "parenthetical" and current_char and (not name or current_char == name):
            lines.append({"character": current_char, "text": f"({e.text})", "elementId": e.id})
    voice_note = (
        "Voice recommendations are descriptive of this script's dialogue patterns — not stereotypes."
    )
    return {
        "documentId": doc.id,
        "characterName": name or None,
        "dialogueLines": lines[:80],
        "voiceGuidance": voice_note,
        "_summary": f"{len(lines)} dialogue line(s) for character context.",
    }


async def script_analyze_structure(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    scenes = sw.navigator_scenes(doc)
    return {
        "documentId": doc.id,
        "actEstimate": "three-act candidate" if len(scenes) >= 6 else "short / incomplete structure",
        "scenes": scenes,
        "recommendations": [
            "Balance early setup vs later payoff.",
            "Ensure each scene advances character want or conflict.",
        ],
        "_summary": f"Structure analysis across {len(scenes)} scene(s).",
    }


async def script_analyze_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    scene_id = str(args.get("sceneHeadingId") or "")
    return sw.analyze_scene(ctx.db, doc_id, scene_id)


async def script_analyze_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    if doc.contentType == "html" or not doc.elements:
        text = document_text(doc)
        words = len(text.split())
        return {
            "documentId": doc.id,
            "dialogueCount": 0,
            "avgWordsPerLine": 0.0,
            "fullText": text[:4000],
            "recommendations": [
                "Rich-text script: structured dialogue analysis unavailable. Review fullText for voice and rhythm.",
            ],
            "_summary": "Rich-text script — dialogue analysis from full text.",
        }
    dialogue = [e for e in doc.elements if e.type == "dialogue"]
    avg = (sum(len(e.text.split()) for e in dialogue) / len(dialogue)) if dialogue else 0
    return {
        "documentId": doc.id,
        "dialogueCount": len(dialogue),
        "avgWordsPerLine": round(avg, 1),
        "recommendations": [
            "Trim on-the-nose exposition." if avg > 18 else "Dialogue length looks lean.",
            "Differentiate character voice by rhythm and vocabulary.",
        ],
        "_summary": f"Dialogue analysis for {len(dialogue)} line(s).",
    }


async def script_analyze_continuity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    findings = analyze_continuity(doc)
    return {
        "documentId": doc.id,
        "findings": findings,
        "_summary": f"{len(findings)} continuity finding(s).",
    }


async def script_suggest_revision(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    element_id = str(args.get("elementId") or "")
    if doc.contentType == "html" or not doc.elements:
        text = document_text(doc)
        return {
            "documentId": doc.id,
            "elementId": element_id or None,
            "original": None,
            "suggested": None,
            "fullText": text[:4000],
            "note": "Rich-text script: element-level suggestions unavailable. Review fullText and propose edits via script.propose_replace after review.",
            "appliesAutomatically": False,
            "_summary": "Rich-text script — returning full text for revision review.",
        }
    el = next((e for e in doc.elements if e.id == element_id), None)
    if not el:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "Element not found.", details={"elementId": element_id})
    suggested = (el.text or "").strip()
    if el.type == "dialogue" and suggested and not suggested.endswith((".", "?", "!")):
        suggested = suggested + "."
    elif el.type == "action":
        suggested = suggested[:1].upper() + suggested[1:] if suggested else suggested
    return {
        "documentId": doc.id,
        "elementId": element_id,
        "original": el.text,
        "suggested": suggested,
        "note": "Suggestion only — apply via script.propose_replace after review.",
        "appliesAutomatically": False,
        "_summary": "Revision suggestion ready for proposal.",
    }


async def script_generate_outline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    scenes = sw.navigator_scenes(doc)
    outline = [{"sceneNumber": s.get("sceneNumber"), "heading": s.get("heading"), "summary": s.get("location")} for s in scenes]
    return {"documentId": doc.id, "outline": outline, "_summary": f"Outline with {len(outline)} beat(s)."}


async def script_generate_beat_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = _load(ctx, args)
    scenes = sw.navigator_scenes(doc)
    beats = [
        {"beat": s.get("heading"), "purpose": "Scene beat", "estimatedPages": s.get("estimatedPages")}
        for s in scenes
    ]
    return {"documentId": doc.id, "beats": beats, "_summary": f"Beat sheet with {len(beats)} beat(s)."}


def _preview_mutation(summary: str, lines: list[str], document_id: str) -> ToolPreview:
    return ToolPreview(
        summary=summary,
        lines=lines,
        resourceKind="script",
        resourceId=document_id,
        warnings=["Applies only after approval via ScriptTransaction."],
    )


def preview_propose_insert(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation(
        "Propose inserting a script element.",
        [f"type={args.get('type')}", f"text={(args.get('text') or '')[:120]}"],
        doc_id,
    )


def apply_propose_insert(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    proposal = {
        "op": "insert",
        "type": args.get("type") or "action",
        "text": args.get("text") or "",
        "order": args.get("order"),
    }
    return sw.apply_codirector_proposal(ctx.db, doc_id, proposal)


def preview_propose_replace(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation(
        "Propose replacing script element text.",
        [f"elementId={args.get('elementId')}", f"text={(args.get('text') or '')[:120]}"],
        doc_id,
    )


def apply_propose_replace(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    return sw.apply_codirector_proposal(
        ctx.db,
        doc_id,
        {"op": "replace", "elementId": args.get("elementId"), "text": args.get("text") or ""},
    )


def preview_propose_delete(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation("Propose deleting a script element.", [f"elementId={args.get('elementId')}"], doc_id)


def apply_propose_delete(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    return sw.apply_codirector_proposal(ctx.db, doc_id, {"op": "delete", "elementId": args.get("elementId")})


def preview_propose_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation(
        "Propose inserting a new scene.",
        [str(args.get("heading") or "INT. LOCATION - DAY")],
        doc_id,
    )


def apply_propose_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    return sw.insert_scene(
        ctx.db,
        doc_id,
        after_order=int(args.get("afterOrder") or -1),
        heading=str(args.get("heading") or "INT. LOCATION - DAY"),
    )


def preview_convert_outline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    beats = args.get("beats") or []
    return _preview_mutation(
        f"Propose converting {len(beats)} outline beat(s) to scenes.",
        [str(b.get("title") or b.get("heading") or "beat") for b in beats[:8]],
        doc_id,
    )


def apply_convert_outline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    import json

    doc_id = _doc_id(ctx, args)
    raw = args.get("beatsJson") or args.get("beats") or "[]"
    if isinstance(raw, str):
        try:
            beats = json.loads(raw)
        except json.JSONDecodeError:
            beats = [{"title": raw}]
    else:
        beats = list(raw or [])
    return sw.convert_outline_to_scenes(ctx.db, doc_id, beats)


def preview_sync_bible(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation(
        "Propose Production Bible entity sync from script detections.",
        ["Creates Bible proposals only — never silent canon writes."],
        doc_id,
    )


def apply_sync_bible(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Create Bible proposals for detected entities; does not mutate scripture silently."""
    from app.codirector.bible.proposals import ProposalService
    from app.codirector.bible.schemas import BibleMutationSet, EntityMutation
    from app.scriptwriter.bible_detect import detect_entities

    doc = _load(ctx, args)
    candidates = detect_entities(doc)
    created = []
    for c in candidates[:20]:
        kind = "character" if c.get("kind") == "character" else "location"
        name = str(c.get("name") or "Unknown")
        mutation = EntityMutation(
            entityType=kind,  # type: ignore[arg-type]
            entityKey=f"script-{kind}-{name.lower().replace(' ', '-')[:40]}",
            displayName=name,
            data={"source": "scriptwriter", "elementId": c.get("elementId")},
        )
        out = ProposalService.create_proposal(
            ctx.db,
            project_id=ctx.project_id,
            proposal_type="entity_create",
            title=f"Add {kind}: {name}",
            summary=f"Detected in script '{doc.title}'. Requires approval.",
            payload=BibleMutationSet(entityMutations=[mutation], changeReason="script_sync_production_bible"),
            created_by="tool:script.sync_production_bible",
        )
        created.append({"proposalId": out.id, "kind": kind, "name": name})
    return {"ok": True, "proposals": created, "appliesAutomatically": False}


def preview_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    doc_id = _doc_id(ctx, args)
    return _preview_mutation(
        "Propose Timeline preparation metadata for a scene.",
        [f"sceneHeadingId={args.get('sceneHeadingId')}", "No clips auto-generated."],
        doc_id,
    )


def apply_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = _doc_id(ctx, args)
    scene_id = str(args.get("sceneHeadingId") or "")
    prep = sw.prepare_timeline(ctx.db, doc_id, scene_id)
    meta = prep.get("proposal") or {}
    applied = sw.apply_timeline_prep_metadata(ctx.db, doc_id, scene_id, meta)
    return {"ok": True, "proposal": meta, "document": applied.get("document"), "appliesClipsAutomatically": False}


async def open_scriptwriter(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "uiAction": "open_scriptwriter",
        "projectId": ctx.project_id,
        "workspaceUrl": f"/project/{ctx.project_id}?workspace=scriptwriter",
        "_evidence": {"source": "scriptwriter.ui"},
    }

