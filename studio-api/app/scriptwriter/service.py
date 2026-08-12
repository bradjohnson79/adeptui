"""High-level Scriptwriter Studio service."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from .bible_detect import detect_entities
from .continuity import analyze_continuity
from .errors import (
    SCRIPT_LOAD_FAILED,
    SCRIPT_REVISION_LOCKED,
    SCRIPT_SCENE_SYNC_CONFLICT,
    ScriptwriterError,
)
from .fountain import parse_fountain, to_fountain
from .migration import preview_migration, run_migration
from .models import (
    DEFAULT_REVISION_COLORS,
    ScriptDocument,
    ScriptElement,
    ScriptRevisionSnapshot,
    SceneSyncStatus,
)
from .stats import compute_stats
from .store import (
    clear_recovery,
    ensure_scriptwriter_tables,
    get_recovery,
    list_documents,
    list_revisions,
    load_document,
    load_revision,
    save_document,
    save_revision,
    set_recovery,
)
from .transactions import commit_transaction, history, undo_last
from .transitions import cycle_type, next_on_enter


def ensure_ready() -> None:
    ensure_scriptwriter_tables()


def get_or_create_document(db: Session, project_id: str, *, title: str = "Untitled Script") -> ScriptDocument:
    ensure_ready()
    docs = list_documents(db, project_id)
    if docs:
        return docs[0]
    # try migrate first
    mig = run_migration(db, project_id)
    if mig.get("document"):
        return ScriptDocument.model_validate(mig["document"])
    doc = ScriptDocument(
        id=str(uuid.uuid4()),
        projectId=project_id,
        title=title,
        elements=[
            ScriptElement(id=str(uuid.uuid4()), type="scene_heading", text="INT. LOCATION - DAY", order=0, sceneNumber="1"),
            ScriptElement(id=str(uuid.uuid4()), type="action", text="", order=1),
        ],
    )
    return save_document(db, doc)


def get_document(db: Session, document_id: str) -> ScriptDocument:
    doc = load_document(db, document_id)
    if not doc:
        raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Script document not found.", recovery_action="reload")
    return doc


def autosave_elements(
    db: Session,
    document_id: str,
    elements: list[dict[str, Any]],
    *,
    expected_revision: Optional[int] = None,
) -> dict[str, Any]:
    doc = get_document(db, document_id)
    if expected_revision is not None and expected_revision != doc.revision:
        set_recovery(db, document_id, {"elements": elements, "expectedRevision": expected_revision})
        raise ScriptwriterError(
            "SCRIPT_CONFLICT",
            "Document revision conflict.",
            details={"serverRevision": doc.revision, "clientRevision": expected_revision},
            recovery_action="reload_or_recover",
        )

    def mutate(d: ScriptDocument) -> list[str]:
        d.elements = [ScriptElement.model_validate(e) for e in elements]
        return [e.id for e in d.elements]

    doc, tx = commit_transaction(db, doc, kind="autosave_batch", source="creator", mutate=mutate, reversible=True)
    clear_recovery(db, document_id)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json"), "saveState": "saved"}


def insert_scene(db: Session, document_id: str, *, after_order: int = -1, heading: str = "INT. LOCATION - DAY") -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        els = sorted(d.elements, key=lambda e: e.order)
        insert_at = after_order + 1 if after_order >= 0 else len(els)
        scene_num = _next_scene_number(d)
        heading_el = ScriptElement(
            id=str(uuid.uuid4()), type="scene_heading", text=heading.upper(), order=insert_at, sceneNumber=scene_num
        )
        action_el = ScriptElement(id=str(uuid.uuid4()), type="action", text="", order=insert_at + 1)
        for e in els:
            if e.order >= insert_at:
                e.order += 2
        d.elements = els + [heading_el, action_el]
        return [heading_el.id, action_el.id]

    doc, tx = commit_transaction(db, doc, kind="insert_scene", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def delete_scene(db: Session, document_id: str, scene_heading_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        els = sorted(d.elements, key=lambda e: e.order)
        start = next((i for i, e in enumerate(els) if e.id == scene_heading_id), None)
        if start is None:
            raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Scene heading not found.")
        end = len(els)
        for i in range(start + 1, len(els)):
            if els[i].type == "scene_heading":
                end = i
                break
        affected = [e.id for e in els[start:end]]
        if d.productionNumbersLocked:
            for e in els[start:end]:
                e.omitted = True
            d.elements = els
        else:
            d.elements = els[:start] + els[end:]
        return affected

    doc, tx = commit_transaction(db, doc, kind="delete_scene", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def move_scene(db: Session, document_id: str, scene_heading_id: str, *, to_index: int) -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        blocks = _scene_blocks(d.elements)
        idx = next((i for i, b in enumerate(blocks) if b[0].id == scene_heading_id), None)
        if idx is None:
            raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Scene not found.")
        block = blocks.pop(idx)
        to_index_clamped = max(0, min(to_index, len(blocks)))
        blocks.insert(to_index_clamped, block)
        flat: list[ScriptElement] = []
        order = 0
        for b in blocks:
            for e in b:
                e.order = order
                flat.append(e)
                order += 1
        d.elements = flat
        return [e.id for e in block]

    doc, tx = commit_transaction(db, doc, kind="move_scene", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def create_revision_set(db: Session, document_id: str, *, name: str, color: str = "Blue", note: str = "") -> dict[str, Any]:
    doc = get_document(db, document_id)
    set_id = doc.revisionSetId or str(uuid.uuid4())
    doc.revisionSetId = set_id
    save_document(db, doc)
    color_final = color if color in DEFAULT_REVISION_COLORS else "Blue"
    snap = ScriptRevisionSnapshot(
        id=str(uuid.uuid4()),
        documentId=doc.id,
        revisionSetId=set_id,
        name=name or f"Revision {doc.revision}",
        color=color_final,
        note=note,
        revision=doc.revision,
        elements=list(doc.elements),
    )
    save_revision(db, snap)
    doc.activeRevision = snap.id
    save_document(db, doc)
    return {"ok": True, "revision": snap.model_dump(mode="json"), "document": doc.model_dump(mode="json")}


def compare_revisions(db: Session, document_id: str, revision_a: str, revision_b: str) -> dict[str, Any]:
    a = load_revision(db, revision_a)
    b = load_revision(db, revision_b)
    if not a or not b:
        raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Revision not found.")
    map_a = {e.order: e for e in a.elements}
    map_b = {e.order: e for e in b.elements}
    changed = []
    for order in sorted(set(map_a) | set(map_b)):
        ea, eb = map_a.get(order), map_b.get(order)
        if not ea or not eb or ea.text != eb.text or ea.type != eb.type:
            changed.append({"order": order, "a": ea.model_dump(mode="json") if ea else None, "b": eb.model_dump(mode="json") if eb else None})
    return {"ok": True, "changed": changed, "a": a.model_dump(mode="json"), "b": b.model_dump(mode="json")}


def restore_revision(db: Session, document_id: str, revision_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)
    snap = load_revision(db, revision_id)
    if not snap:
        raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Revision not found.")

    def mutate(d: ScriptDocument) -> list[str]:
        d.elements = [e.model_copy(deep=True) for e in snap.elements]
        d.activeRevision = revision_id
        return [e.id for e in d.elements]

    doc, tx = commit_transaction(db, doc, kind="restore_revision", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def import_text(db: Session, document_id: str, text: str, *, fmt: str = "fountain") -> dict[str, Any]:
    doc = get_document(db, document_id)
    elements = parse_fountain(text)

    def mutate(d: ScriptDocument) -> list[str]:
        d.elements = elements
        _assign_scene_numbers(d)
        return [e.id for e in d.elements]

    doc, tx = commit_transaction(db, doc, kind="import_document", source="import", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json"), "format": fmt}


def export_fountain(db: Session, document_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)
    return {"ok": True, "fountain": to_fountain(doc.elements, title=doc.title), "title": doc.title}


def export_pdf_file(db: Session, document_id: str, out_dir: Path) -> dict[str, Any]:
    from .pdf_export import export_pdf

    doc = get_document(db, document_id)
    path = out_dir / f"{doc.id}.pdf"
    try:
        export_pdf(doc, path)
        return {"ok": True, "path": str(path)}
    except ScriptwriterError as exc:
        return {"ok": False, "error": exc.to_dict()}


def apply_codirector_proposal(db: Session, document_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    doc = get_document(db, document_id)
    op = str(proposal.get("op") or "replace")
    element_id = str(proposal.get("elementId") or "")
    text = str(proposal.get("text") or "")
    new_elements = proposal.get("elements")

    def mutate(d: ScriptDocument) -> list[str]:
        if new_elements and isinstance(new_elements, list):
            d.elements = [ScriptElement.model_validate(e) for e in new_elements]
            return [e.id for e in d.elements]
        affected: list[str] = []
        if op == "replace" and element_id:
            for e in d.elements:
                if e.id == element_id:
                    if e.locked:
                        raise ScriptwriterError(SCRIPT_REVISION_LOCKED, "Element locked.")
                    e.text = text
                    affected.append(e.id)
        elif op == "insert":
            etype = str(proposal.get("type") or "action")
            order = int(proposal.get("order") or len(d.elements))
            el = ScriptElement(id=str(uuid.uuid4()), type=etype, text=text, order=order)  # type: ignore[arg-type]
            for e in d.elements:
                if e.order >= order:
                    e.order += 1
            d.elements.append(el)
            affected.append(el.id)
        elif op == "delete" and element_id:
            d.elements = [e for e in d.elements if e.id != element_id]
            affected.append(element_id)
        return affected

    doc, tx = commit_transaction(db, doc, kind="apply_codirector_proposal", source="codirector", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def convert_outline_to_scenes(db: Session, document_id: str, beats: list[dict[str, Any]]) -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        created: list[str] = []
        order = max((e.order for e in d.elements), default=-1) + 1
        for beat in beats:
            heading = str(beat.get("heading") or beat.get("title") or "INT. LOCATION - DAY")
            if not heading.upper().startswith(("INT.", "EXT.", "I/E.")):
                heading = f"INT. {heading.upper()} - DAY"
            h = ScriptElement(
                id=str(uuid.uuid4()),
                type="scene_heading",
                text=heading.upper(),
                order=order,
                sceneNumber=_next_scene_number(d),
            )
            a = ScriptElement(
                id=str(uuid.uuid4()),
                type="action",
                text=str(beat.get("description") or beat.get("notes") or ""),
                order=order + 1,
            )
            d.elements.extend([h, a])
            created.extend([h.id, a.id])
            order += 2
        return created

    doc, tx = commit_transaction(db, doc, kind="convert_outline_to_scenes", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def link_scene(db: Session, document_id: str, scene_heading_id: str, project_scene_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        affected: list[str] = []
        in_scene = False
        for e in sorted(d.elements, key=lambda x: x.order):
            if e.id == scene_heading_id:
                in_scene = True
            elif e.type == "scene_heading" and in_scene:
                break
            if in_scene:
                e.sceneId = project_scene_id
                affected.append(e.id)
        d.sceneSync[scene_heading_id] = "linked"
        return affected

    doc, tx = commit_transaction(db, doc, kind="edit_elements", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json"), "syncStatus": "linked"}


def prepare_timeline(db: Session, document_id: str, scene_heading_id: str) -> dict[str, Any]:
    """Build a Timeline preparation proposal (does not apply clips)."""
    doc = get_document(db, document_id)
    block = _block_for_heading(doc.elements, scene_heading_id)
    if not block:
        raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Scene not found.")
    heading = block[0]
    characters = [e.text for e in block if e.type == "character"]
    dialogue_els = [e for e in block if e.type == "dialogue"]
    dialogue = []
    for idx, e in enumerate(dialogue_els):
        prev_el = dialogue_els[idx - 1] if idx > 0 else None
        next_el = dialogue_els[idx + 1] if idx + 1 < len(dialogue_els) else None
        parenthetical = None
        # Parenthetical immediately before dialogue in the scene block
        try:
            abs_idx = block.index(e)
            if abs_idx > 0 and block[abs_idx - 1].type == "parenthetical":
                parenthetical = block[abs_idx - 1].text
        except ValueError:
            parenthetical = None
        dialogue.append(
            {
                "elementId": e.id,
                "scriptDocumentId": document_id,
                "sceneHeadingId": scene_heading_id,
                "speaker": (e.metadata or {}).get("speaker"),
                "text": e.text,
                "parenthetical": parenthetical,
                "previousLine": prev_el.text if prev_el else None,
                "nextLine": next_el.text if next_el else None,
                "revisionVersion": getattr(e, "revisionVersion", None) or getattr(doc, "revision", None),
            }
        )
    action = [e.text for e in block if e.type == "action"]
    viz_prompt = (
        f"Cinematic scene: {heading.text}. "
        + (" ".join(action[:2]) if action else "")
        + " Medium shot, production-ready lighting."
    ).strip()
    proposal = {
        "sceneHeadingId": scene_heading_id,
        "sceneHeading": heading.text,
        "sceneNumber": heading.sceneNumber,
        "summary": action[0] if action else heading.text,
        "characters": characters,
        "dialogue": dialogue,
        "actionBeats": action,
        "shotList": [
            {"shot": "Wide establishing", "notes": heading.text},
            {"shot": "Medium coverage", "notes": "Primary action"},
            {"shot": "Close-up", "notes": "Emotional beat" if dialogue else "Detail"},
        ],
        "audioRequirements": ["dialogue track"] if dialogue else ["ambience"],
        "lipSyncNeeded": bool(dialogue),
        "visualizationPrompt": viz_prompt,
        "requiresUserReview": True,
        "appliesClipsAutomatically": False,
    }
    return {"ok": True, "proposal": proposal, "status": "proposed"}


def apply_timeline_prep_metadata(db: Session, document_id: str, scene_heading_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    doc = get_document(db, document_id)

    def mutate(d: ScriptDocument) -> list[str]:
        for e in d.elements:
            if e.id == scene_heading_id:
                e.metadata = {**(e.metadata or {}), "timelinePrep": metadata}
                d.sceneSync[scene_heading_id] = "synced"
                return [e.id]
        raise ScriptwriterError(SCRIPT_LOAD_FAILED, "Scene heading not found.")

    doc, tx = commit_transaction(db, doc, kind="apply_timeline_prep_metadata", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def analyze_scene(db: Session, document_id: str, scene_heading_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)
    block = _block_for_heading(doc.elements, scene_heading_id)
    action = " ".join(e.text for e in block if e.type == "action")
    dialogue = [e.text for e in block if e.type == "dialogue"]
    chars = [e.text for e in block if e.type == "character"]
    return {
        "ok": True,
        "analysis": {
            "scenePurpose": (action[:180] + "…") if len(action) > 180 else (action or "Unspecified"),
            "characters": chars,
            "dialogueLines": len(dialogue),
            "conflict": "Possible opposition present" if len(chars) >= 2 else "Single-character or empty scene",
            "visualStorytelling": "Action lines present" if action else "Dialogue-heavy / thin action",
            "productionComplexity": "moderate" if len(block) > 8 else "low",
            "recommendations": [
                "Clarify character objective in action." if not action else "Consider a strong exit image.",
            ],
        },
    }


def lock_production_numbers(db: Session, document_id: str, locked: bool = True) -> dict[str, Any]:
    doc = get_document(db, document_id)
    doc.productionNumbersLocked = locked
    if locked:
        _assign_scene_numbers(doc)
    save_document(db, doc)
    return {"ok": True, "document": doc.model_dump(mode="json")}


def navigator_scenes(doc: ScriptDocument) -> list[dict[str, Any]]:
    out = []
    for block in _scene_blocks(doc.elements):
        h = block[0]
        words = sum(len((e.text or "").split()) for e in block)
        out.append(
            {
                "sceneHeadingId": h.id,
                "sceneNumber": h.sceneNumber or "",
                "heading": h.text,
                "location": _location_from_heading(h.text),
                "timeOfDay": _tod_from_heading(h.text),
                "estimatedPages": round(max(0.1, words / 180.0), 2),
                "draftStatus": doc.draftStatus,
                "continuityWarningCount": 0,
                "productionStatus": doc.sceneSync.get(h.id, "unlinked"),
                "omitted": h.omitted,
            }
        )
    return out


def document_bundle(db: Session, document_id: str) -> dict[str, Any]:
    doc = get_document(db, document_id)
    return {
        "ok": True,
        "document": doc.model_dump(mode="json"),
        "stats": compute_stats(doc).model_dump(mode="json"),
        "navigator": navigator_scenes(doc),
        "continuity": analyze_continuity(doc),
        "bibleCandidates": detect_entities(doc),
        "revisions": [r.model_dump(mode="json") for r in list_revisions(db, document_id)],
        "transactions": [t.model_dump(mode="json") for t in history(db, document_id, limit=20)],
        "transitions": {
            "nextOnEnter": {k: next_on_enter(k) for k in ("scene_heading", "action", "character", "dialogue", "parenthetical", "transition")},  # type: ignore[arg-type]
            "cycle": [cycle_type("action"), cycle_type("action", reverse=True)],
        },
        "recovery": get_recovery(db, document_id),
        "paginationMode": "estimated",
    }


def undo(db: Session, document_id: str) -> dict[str, Any]:
    doc, tx = undo_last(db, document_id)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


def propose_bible_entities(db: Session, project_id: str, document_id: str) -> dict[str, Any]:
    """Create Production Bible proposals from detected script entities (never silent write)."""
    from ..codirector.bible.proposals import ProposalService
    from ..codirector.bible.schemas import BibleMutationSet, EntityMutation

    doc = get_document(db, document_id)
    created = []
    for c in detect_entities(doc)[:20]:
        kind = "character" if c.get("kind") == "character" else "location"
        name = str(c.get("name") or "Unknown")
        mutation = EntityMutation(
            entityType=kind,  # type: ignore[arg-type]
            entityKey=f"script-{kind}-{name.lower().replace(' ', '-')[:40]}",
            displayName=name,
            data={"source": "scriptwriter", "elementId": c.get("elementId")},
        )
        out = ProposalService.create_proposal(
            db,
            project_id=project_id,
            proposal_type="entity_create",
            title=f"Add {kind}: {name}",
            summary=f"Detected in script '{doc.title}'. Requires approval.",
            payload=BibleMutationSet(entityMutations=[mutation], changeReason="scriptwriter_bible_propose"),
            created_by="scriptwriter",
        )
        created.append({"proposalId": out.id, "kind": kind, "name": name})
    return {"ok": True, "proposals": created, "appliesAutomatically": False}


def search_replace(
    db: Session,
    document_id: str,
    *,
    find: str,
    replace: str,
    element_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    doc = get_document(db, document_id)
    types = set(element_types or [])

    def mutate(d: ScriptDocument) -> list[str]:
        affected: list[str] = []
        for e in d.elements:
            if types and e.type not in types:
                continue
            if find and find in (e.text or ""):
                e.text = (e.text or "").replace(find, replace)
                affected.append(e.id)
        return affected

    doc, tx = commit_transaction(db, doc, kind="search_replace", source="creator", mutate=mutate)
    return {"ok": True, "document": doc.model_dump(mode="json"), "transaction": tx.model_dump(mode="json")}


# helpers

def _scene_blocks(elements: list[ScriptElement]) -> list[list[ScriptElement]]:
    blocks: list[list[ScriptElement]] = []
    current: list[ScriptElement] = []
    for e in sorted(elements, key=lambda x: x.order):
        if e.type == "scene_heading":
            if current:
                blocks.append(current)
            current = [e]
        else:
            if not current:
                current = [e]
            else:
                current.append(e)
    if current:
        blocks.append(current)
    return blocks


def _block_for_heading(elements: list[ScriptElement], heading_id: str) -> list[ScriptElement]:
    for b in _scene_blocks(elements):
        if b and b[0].id == heading_id:
            return b
    return []


def _next_scene_number(doc: ScriptDocument) -> str:
    if not doc.productionNumbersLocked:
        nums = []
        for e in doc.elements:
            if e.type == "scene_heading" and e.sceneNumber and e.sceneNumber.isdigit():
                nums.append(int(e.sceneNumber))
        return str((max(nums) + 1) if nums else 1)
    # suffix mode: find max base and add A/B
    bases: dict[str, int] = {}
    for e in doc.elements:
        if e.type != "scene_heading" or not e.sceneNumber:
            continue
        m = e.sceneNumber.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        suf = e.sceneNumber[len(m) :]
        bases[m] = max(bases.get(m, 0), (ord(suf[-1]) - 64) if suf else 0)
    if not bases:
        return "1"
    last = sorted(bases.keys(), key=lambda x: int(x) if x.isdigit() else 0)[-1]
    n = bases[last] + 1
    return f"{last}{chr(64 + n)}" if n > 0 else last


def _assign_scene_numbers(doc: ScriptDocument) -> None:
    n = 1
    for e in sorted(doc.elements, key=lambda x: x.order):
        if e.type == "scene_heading" and not e.omitted:
            if not doc.productionNumbersLocked or not e.sceneNumber:
                e.sceneNumber = str(n)
                n += 1


def _location_from_heading(text: str) -> str:
    t = (text or "").upper()
    for p in ("INT.", "EXT.", "INT./EXT.", "EXT./INT.", "I/E."):
        if t.startswith(p):
            rest = t[len(p) :].strip()
            return rest.split("-")[0].strip()
    return ""


def _tod_from_heading(text: str) -> str:
    if "-" in (text or ""):
        return text.split("-")[-1].strip()
    return ""
