"""Movement Segments — discrete blocking states on a Spatial Map.

State-based inheritance is non-negotiable. Creating M2 from M1 copies
character/prop/attachment/continuity snapshots. Prompt text is beat
direction only — it is never the inheritance mechanism.

document.characters / document.props / document.cameras are the live
working buffer for the ACTIVE segment. Cameras are free entities with
per-movement pose snapshots (cameraStates), same as characters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .errors import SpatialMapErrorCode, raise_http_error
from .schemas import (
    MovementAction,
    MovementContinuity,
    MovementCreateBody,
    MovementDialogue,
    MovementSegment,
    MovementUpdateBody,
    SpatialCamera,
    SpatialCharacterPlacement,
    SpatialMapDocument,
    SpatialPropPlacement,
)

MOVEMENT_MIN = 1
MOVEMENT_MAX = 5


def movement_alias(segment_number: int) -> str:
    return f"M{int(segment_number)}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _copy_characters(items: list[Any]) -> list[SpatialCharacterPlacement]:
    out: list[SpatialCharacterPlacement] = []
    for item in items or []:
        if isinstance(item, SpatialCharacterPlacement):
            out.append(item.model_copy(deep=True))
        else:
            out.append(SpatialCharacterPlacement.model_validate(item))
    return out


def _copy_props(items: list[Any]) -> list[SpatialPropPlacement]:
    out: list[SpatialPropPlacement] = []
    for item in items or []:
        if isinstance(item, SpatialPropPlacement):
            out.append(item.model_copy(deep=True))
        else:
            out.append(SpatialPropPlacement.model_validate(item))
    return out


def camera_refs(document: SpatialMapDocument) -> list[str]:
    return [str(c.id) for c in (document.cameras or []) if getattr(c, "id", None)]


def _copy_cameras(items: list[Any]) -> list[SpatialCamera]:
    out: list[SpatialCamera] = []
    for item in items or []:
        if isinstance(item, SpatialCamera):
            out.append(item.model_copy(deep=True))
        else:
            out.append(SpatialCamera.model_validate(item))
    return out


def camera_refs_from_states(items: list[Any]) -> list[str]:
    return [str(c.id) for c in (items or []) if getattr(c, "id", None)]


def seed_missing_camera_states(document: SpatialMapDocument) -> bool:
    """Legacy reconnect for empty cameraStates.

    Never copy the live (active) buffer onto *inactive* empty segments -- that
    poisoned M1 with M2 poses whenever the doc loaded while M2 was active.
    Rules:
    - Active empty segment: seed from live cameras.
    - Inactive empty segment: inherit from the previous segment's snapshot
      (by segmentNumber); if none, leave empty until that movement is used.
    """
    live = _copy_cameras(document.cameras)
    active_id = str(document.activeMovementSegmentId or "").strip()
    changed = False
    ordered = sorted(
        document.movementSegments or [],
        key=lambda s: int(getattr(s, "segmentNumber", 0) or 0),
    )
    prev_states: list[SpatialCamera] | None = None
    for segment in ordered:
        existing = list(getattr(segment, "cameraStates", None) or [])
        if existing:
            if not segment.cameraStateRefs:
                segment.cameraStateRefs = camera_refs_from_states(existing)
                changed = True
            prev_states = existing
            continue
        is_active = active_id and str(segment.id) == active_id
        if is_active and live:
            donor = live
        elif prev_states is not None:
            donor = prev_states
        else:
            # Inactive + no prior snapshot: do not invent poses from live.
            continue
        segment.cameraStates = _copy_cameras(donor)
        segment.cameraStateRefs = camera_refs_from_states(segment.cameraStates)
        prev_states = list(segment.cameraStates)
        changed = True
    return changed


def add_camera_to_all_segments(document: SpatialMapDocument, camera: SpatialCamera) -> None:
    wanted = str(getattr(camera, "id", "") or "")
    if not wanted:
        return
    for segment in document.movementSegments or []:
        states = list(getattr(segment, "cameraStates", None) or [])
        if any(str(getattr(c, "id", "")) == wanted for c in states):
            continue
        states.append(camera.model_copy(deep=True))
        segment.cameraStates = states
        segment.cameraStateRefs = camera_refs_from_states(states)


def remove_camera_from_all_segments(document: SpatialMapDocument, camera_id: str) -> None:
    wanted = str(camera_id or "")
    if not wanted:
        return
    for segment in document.movementSegments or []:
        states = [
            c
            for c in (getattr(segment, "cameraStates", None) or [])
            if str(getattr(c, "id", "")) != wanted
        ]
        segment.cameraStates = states
        segment.cameraStateRefs = camera_refs_from_states(states)


def seed_movement_one(document: SpatialMapDocument) -> MovementSegment:
    """Seed M1 with a deterministic ID derived from the document ID.
    
    Legacy documents stored without movementSegments get a stable M1 UUID
    (uuid5 from document.id) so that every parse produces the same segment ID.
    Once saved, the persisted JSON carries the id and the factory is never
    invoked again.
    """
    now = _now()
    doc_id = str(document.id) if document.id else "unknown"
    seg_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"spatial-map/{doc_id}/movement-1"))
    return MovementSegment(
        id=seg_id,
        segmentNumber=1,
        beatName="",
        characterStates=_copy_characters(document.characters),
        propStates=_copy_props(document.props),
        cameraStateRefs=camera_refs(document),
        cameraStates=_copy_cameras(document.cameras),
        createdAt=now,
        updatedAt=now,
        revision=1,
    )


def find_segment(document: SpatialMapDocument, segment_id: str) -> MovementSegment:
    wanted = (segment_id or "").strip()
    if not wanted:
        raise raise_http_error(
            SpatialMapErrorCode.MOVEMENT_SEGMENT_NOT_FOUND,
            "Choose a Movement Segment.",
        )
    for segment in document.movementSegments or []:
        if str(segment.id) == wanted:
            return segment
    raise raise_http_error(
        SpatialMapErrorCode.MOVEMENT_SEGMENT_NOT_FOUND,
        "That movement no longer exists. Choose another movement.",
        movementSegmentId=wanted,
    )


def find_segment_by_number(document: SpatialMapDocument, number: int) -> MovementSegment:
    for segment in document.movementSegments or []:
        if int(segment.segmentNumber) == int(number):
            return segment
    raise raise_http_error(
        SpatialMapErrorCode.MOVEMENT_SEGMENT_NOT_FOUND,
        f"Movement {int(number)} no longer exists. Choose another movement.",
        segmentNumber=int(number),
    )


def active_segment(document: SpatialMapDocument) -> MovementSegment:
    hydrate_movement_segments(document)
    sid = str(document.activeMovementSegmentId or "").strip()
    if sid:
        return find_segment(document, sid)
    return find_segment_by_number(document, 1)


def next_segment_number(document: SpatialMapDocument) -> int:
    used = {int(s.segmentNumber) for s in (document.movementSegments or [])}
    for number in range(MOVEMENT_MIN, MOVEMENT_MAX + 1):
        if number not in used:
            return number
    raise raise_http_error(
        SpatialMapErrorCode.MOVEMENT_LIMIT_REACHED,
        "A scene can have at most five movements.",
    )


def inherit_segment(source: MovementSegment, segment_number: int) -> MovementSegment:
    """Copy production STATE from source. Do not copy beat prose."""
    now = _now()
    return MovementSegment(
        segmentNumber=segment_number,
        beatName="",
        characterStates=_copy_characters(source.characterStates),
        propStates=_copy_props(source.propStates),
        cameraStateRefs=list(source.cameraStateRefs or camera_refs_from_states(source.cameraStates)),
        cameraStates=_copy_cameras(source.cameraStates),
        userDirection="",
        productionPrompt="",
        actions=[],
        dialogue=[],
        continuity=source.continuity.model_copy(deep=True)
        if source.continuity
        else MovementContinuity(),
        timingHintSeconds=source.timingHintSeconds,
        revision=1,
        createdAt=now,
        updatedAt=now,
    )


def hydrate_live_from_segment(document: SpatialMapDocument, segment: MovementSegment) -> None:
    """Restore live working buffers from a segment snapshot.

    Characters/props always swap. Cameras swap when cameraStates is present.
    When cameraStates is empty we deliberately do *not* leave the previous
    movement's live cameras in place for write-through -- that made M1 appear
    to "not stick" after visiting M2. Empty states keep identity via refs when
    possible; otherwise live cameras are left unchanged (legacy global cams).
    """
    document.characters = _copy_characters(segment.characterStates)
    document.props = _copy_props(segment.propStates)
    states = list(getattr(segment, "cameraStates", None) or [])
    if states:
        document.cameras = _copy_cameras(states)
        return
    refs = [str(r) for r in (segment.cameraStateRefs or []) if r]
    if not refs:
        return
    by_id = {str(getattr(c, "id", "")): c for c in (document.cameras or [])}
    restored = [
        by_id[rid].model_copy(deep=True)
        for rid in refs
        if rid in by_id
    ]
    if restored:
        document.cameras = restored


def write_through_active(document: SpatialMapDocument) -> None:
    """Flush live placements into the active segment snapshot.

    Resolves the active segment *without* calling hydrate/seed so an outgoing
    movement's poses are never overwritten by seed-from-live before flush.
    """
    if not document.movementSegments:
        return
    sid = str(document.activeMovementSegmentId or "").strip()
    segment = None
    if sid:
        for candidate in document.movementSegments:
            if str(candidate.id) == sid:
                segment = candidate
                break
    if segment is None:
        segment = find_segment_by_number(document, 1)
    next_chars = _copy_characters(document.characters)
    next_props = _copy_props(document.props)
    next_cam_states = _copy_cameras(document.cameras)
    next_cams = camera_refs_from_states(next_cam_states)
    prev_cam_states = getattr(segment, "cameraStates", None) or []
    changed = (
        [c.model_dump() for c in segment.characterStates] != [c.model_dump() for c in next_chars]
        or [p.model_dump() for p in segment.propStates] != [p.model_dump() for p in next_props]
        or [c.model_dump() for c in prev_cam_states] != [c.model_dump() for c in next_cam_states]
        or list(segment.cameraStateRefs or []) != next_cams
    )
    segment.characterStates = next_chars
    segment.propStates = next_props
    segment.cameraStates = next_cam_states
    segment.cameraStateRefs = next_cams
    segment.updatedAt = _now()
    if changed:
        segment.revision = int(segment.revision or 1) + 1
        document.movementSegmentRevision = int(document.movementSegmentRevision or 0) + 1


def hydrate_movement_segments(document: SpatialMapDocument) -> bool:
    """Ensure M1 exists. Legacy maps become Movement 1 from current live state."""
    changed = False
    if not document.movementSegments:
        m1 = seed_movement_one(document)
        document.movementSegments = [m1]
        document.activeMovementSegmentId = m1.id
        if not document.movementSegmentRevision:
            document.movementSegmentRevision = 1
        return True
    if not document.activeMovementSegmentId or not any(
        str(s.id) == str(document.activeMovementSegmentId) for s in document.movementSegments
    ):
        first = sorted(document.movementSegments, key=lambda s: int(s.segmentNumber))[0]
        document.activeMovementSegmentId = first.id
        changed = True
    if seed_missing_camera_states(document):
        changed = True
    return changed


def compact_index(document: SpatialMapDocument) -> dict[str, Any]:
    hydrate_movement_segments(document)
    active_id = str(document.activeMovementSegmentId or "")
    rows = []
    for segment in sorted(document.movementSegments, key=lambda s: int(s.segmentNumber)):
        rows.append(
            {
                "id": segment.id,
                "segmentNumber": segment.segmentNumber,
                "alias": movement_alias(segment.segmentNumber),
                "beatName": segment.beatName or "",
                "active": str(segment.id) == active_id,
                "revision": int(segment.revision or 1),
                "characterCount": len(segment.characterStates or []),
                "hasDialogue": bool(segment.dialogue),
                "hasDirection": bool((segment.userDirection or "").strip()),
            }
        )
    return {
        "activeMovementId": active_id,
        "movementCount": len(rows),
        "movementSegmentRevision": int(document.movementSegmentRevision or 0),
        "movements": rows,
    }


def _placement_key(item: Any) -> str:
    return str(
        getattr(item, "characterId", None)
        or getattr(item, "propId", None)
        or getattr(item, "id", None)
        or getattr(item, "label", "")
        or ""
    )


def _coord_tuple(item: Any) -> tuple[Any, ...]:
    return (
        getattr(item, "normalizedX", None),
        getattr(item, "normalizedY", None),
        getattr(item, "gridRow", None),
        getattr(item, "gridColumn", None),
        getattr(item, "x", None),
        getattr(item, "z", None),
        getattr(item, "visible", True),
        getattr(item, "yawDegrees", None),
        getattr(item, "placementMode", None),
        getattr(item, "attachmentPoint", None),
        getattr(item, "attachedCharacterId", None),
    )


def compute_transition(start: MovementSegment, end: MovementSegment) -> dict[str, Any]:
    """Derived M1 → M2 facts. Not persisted as authority."""
    start_chars = {_placement_key(c): c for c in start.characterStates}
    end_chars = {_placement_key(c): c for c in end.characterStates}
    start_props = {_placement_key(p): p for p in start.propStates}
    end_props = {_placement_key(p): p for p in end.propStates}
    changed: list[str] = []
    unchanged: list[str] = []
    for key, before in start_chars.items():
        after = end_chars.get(key)
        label = str(getattr(before, "label", None) or getattr(before, "tag", None) or key)
        if after is None:
            changed.append(f"{label} left the scene")
        elif _coord_tuple(before) != _coord_tuple(after):
            changed.append(f"{label} moved")
        else:
            unchanged.append(f"{label} position")
    for key, before in start_props.items():
        after = end_props.get(key)
        label = str(getattr(before, "label", None) or getattr(before, "tag", None) or key)
        if after is None:
            changed.append(f"{label} removed")
        elif _coord_tuple(before) != _coord_tuple(after):
            changed.append(f"{label} changed")
        else:
            unchanged.append(f"{label} identity")
    unchanged.extend(["environment", "cameras", "ERS"])
    return {
        "fromId": start.id,
        "toId": end.id,
        "fromAlias": movement_alias(start.segmentNumber),
        "toAlias": movement_alias(end.segmentNumber),
        "fromRevision": int(start.revision or 1),
        "toRevision": int(end.revision or 1),
        "unchanged": unchanged,
        "changed": changed,
        "startingState": {
            "segmentNumber": start.segmentNumber,
            "beatName": start.beatName,
            "characters": [c.model_dump() for c in start.characterStates],
            "props": [p.model_dump() for p in start.propStates],
            "userDirection": start.userDirection,
            "dialogue": [d.model_dump() for d in start.dialogue],
        },
        "endingState": {
            "segmentNumber": end.segmentNumber,
            "beatName": end.beatName,
            "characters": [c.model_dump() for c in end.characterStates],
            "props": [p.model_dump() for p in end.propStates],
            "userDirection": end.userDirection,
            "dialogue": [d.model_dump() for d in end.dialogue],
        },
    }


def previous_segment(document: SpatialMapDocument, segment: MovementSegment) -> Optional[MovementSegment]:
    prior = [
        s
        for s in document.movementSegments
        if int(s.segmentNumber) < int(segment.segmentNumber)
    ]
    if not prior:
        return None
    return max(prior, key=lambda s: int(s.segmentNumber))


def compute_arrows(
    document: SpatialMapDocument,
    *,
    selected_character_id: str | None = None,
) -> list[dict[str, Any]]:
    """Deterministic overlay legs from saved character coordinates."""
    hydrate_movement_segments(document)
    ordered = sorted(document.movementSegments, key=lambda s: int(s.segmentNumber))
    if len(ordered) < 2:
        return []
    active = active_segment(document)
    focus_id = (selected_character_id or "").strip()
    legs: list[dict[str, Any]] = []
    pairs = list(zip(ordered, ordered[1:]))
    if not focus_id:
        prev = previous_segment(document, active)
        if prev is not None:
            pairs = [(prev, active)]
    for start, end in pairs:
        by_id = {_placement_key(c): c for c in start.characterStates}
        for dest in end.characterStates:
            key = _placement_key(dest)
            origin = by_id.get(key)
            if origin is None:
                continue
            if focus_id and key != focus_id and str(getattr(dest, "id", "")) != focus_id:
                if str(getattr(dest, "characterId", "")) != focus_id:
                    continue
            if _coord_tuple(origin) == _coord_tuple(dest):
                continue
            legs.append(
                {
                    "characterId": str(getattr(dest, "characterId", "") or key),
                    "label": str(getattr(dest, "label", None) or getattr(dest, "tag", None) or key),
                    "fromAlias": movement_alias(start.segmentNumber),
                    "toAlias": movement_alias(end.segmentNumber),
                    "from": {
                        "normalizedX": origin.normalizedX,
                        "normalizedY": origin.normalizedY,
                        "gridRow": origin.gridRow,
                        "gridColumn": origin.gridColumn,
                    },
                    "to": {
                        "normalizedX": dest.normalizedX,
                        "normalizedY": dest.normalizedY,
                        "gridRow": dest.gridRow,
                        "gridColumn": dest.gridColumn,
                    },
                }
            )
    return legs


def create_inherited_movement(
    document: SpatialMapDocument,
    body: MovementCreateBody | None = None,
) -> MovementSegment:
    hydrate_movement_segments(document)
    write_through_active(document)
    if len(document.movementSegments) >= MOVEMENT_MAX:
        raise raise_http_error(
            SpatialMapErrorCode.MOVEMENT_LIMIT_REACHED,
            "A scene can have at most five movements.",
        )
    body = body or MovementCreateBody()
    inherit_from_id = (body.inheritFromId or document.activeMovementSegmentId or "").strip()
    source = find_segment(document, inherit_from_id) if inherit_from_id else active_segment(document)
    created = inherit_segment(source, next_segment_number(document))
    created.beatName = (body.beatName or "").strip()
    created.userDirection = (body.userDirection or "").strip()
    created.productionPrompt = (body.productionPrompt or "").strip()
    if body.dialogue:
        created.dialogue = [d if isinstance(d, MovementDialogue) else MovementDialogue.model_validate(d) for d in body.dialogue]
    if body.actions:
        created.actions = [a if isinstance(a, MovementAction) else MovementAction.model_validate(a) for a in body.actions]
    document.movementSegments.append(created)
    document.activeMovementSegmentId = created.id
    document.movementSegmentRevision = int(document.movementSegmentRevision or 0) + 1
    hydrate_live_from_segment(document, created)
    return created


def _snapshot_camera_donor(document: SpatialMapDocument, exclude_id: str) -> list[SpatialCamera] | None:
    """Camera poses from another segment snapshot. Never uses the live buffer."""
    wanted = str(exclude_id or "")
    ordered = sorted(
        document.movementSegments or [],
        key=lambda s: int(getattr(s, "segmentNumber", 0) or 0),
    )
    target_num = 0
    for seg in ordered:
        if str(seg.id) == wanted:
            target_num = int(getattr(seg, "segmentNumber", 0) or 0)
            break
    prev: list[SpatialCamera] | None = None
    later: list[SpatialCamera] | None = None
    for seg in ordered:
        if str(seg.id) == wanted:
            continue
        states = list(getattr(seg, "cameraStates", None) or [])
        if not states:
            continue
        if int(getattr(seg, "segmentNumber", 0) or 0) < target_num:
            prev = states
        elif later is None:
            later = states
    return prev or later


def activate_segment(document: SpatialMapDocument, segment_id: str) -> MovementSegment:
    """Switch active movement: flush current live -> old segment, then hydrate.

    Write-through runs *before* legacy seed so we never lose the outgoing
    movement's latest camera/character/prop poses to a seed-from-live pass.

    Incoming empty cameraStates inherit from another segment snapshot, never
    from live. Live still holds the outgoing movement until hydrate; seeding
    after set-active copied M2 cameras onto empty M1 (Korri live NO-GO).
    """
    if document.movementSegments and document.activeMovementSegmentId:
        write_through_active(document)
    hydrate_movement_segments(document)
    write_through_active(document)
    segment = find_segment(document, segment_id)
    incoming = list(getattr(segment, "cameraStates", None) or [])
    if not incoming:
        donor = _snapshot_camera_donor(document, segment.id)
        if donor:
            segment.cameraStates = _copy_cameras(donor)
            segment.cameraStateRefs = camera_refs_from_states(segment.cameraStates)
    document.activeMovementSegmentId = segment.id
    hydrate_live_from_segment(document, segment)
    document.movementSegmentRevision = int(document.movementSegmentRevision or 0) + 1
    return segment


def update_segment_narrative(
    document: SpatialMapDocument,
    segment_id: str,
    body: MovementUpdateBody,
) -> MovementSegment:
    hydrate_movement_segments(document)
    write_through_active(document)
    segment = find_segment(document, segment_id)
    updates = body.model_dump(exclude_unset=True)
    if "beatName" in updates and updates["beatName"] is not None:
        segment.beatName = str(updates["beatName"] or "").strip()
    if "userDirection" in updates and updates["userDirection"] is not None:
        segment.userDirection = str(updates["userDirection"] or "")
    if "productionPrompt" in updates and updates["productionPrompt"] is not None:
        segment.productionPrompt = str(updates["productionPrompt"] or "")
    if "dialogue" in updates and updates["dialogue"] is not None:
        segment.dialogue = [
            d if isinstance(d, MovementDialogue) else MovementDialogue.model_validate(d)
            for d in (updates["dialogue"] or [])
        ]
    if "actions" in updates and updates["actions"] is not None:
        segment.actions = [
            a if isinstance(a, MovementAction) else MovementAction.model_validate(a)
            for a in (updates["actions"] or [])
        ]
    if "continuity" in updates and updates["continuity"] is not None:
        segment.continuity = MovementContinuity.model_validate(updates["continuity"])
    if "timingHintSeconds" in updates:
        segment.timingHintSeconds = updates["timingHintSeconds"]
    segment.updatedAt = _now()
    segment.revision = int(segment.revision or 1) + 1
    document.movementSegmentRevision = int(document.movementSegmentRevision or 0) + 1
    return segment


def delete_segment(document: SpatialMapDocument, segment_id: str) -> MovementSegment:
    hydrate_movement_segments(document)
    segment = find_segment(document, segment_id)
    if int(segment.segmentNumber) == 1:
        raise raise_http_error(
            SpatialMapErrorCode.MOVEMENT_CANNOT_DELETE,
            "Movement 1 cannot be removed.",
            movementSegmentId=segment.id,
        )
    document.movementSegments = [s for s in document.movementSegments if str(s.id) != str(segment.id)]
    if str(document.activeMovementSegmentId) == str(segment.id):
        remaining = sorted(document.movementSegments, key=lambda s: int(s.segmentNumber))
        nxt = remaining[-1] if remaining else seed_movement_one(document)
        if nxt not in document.movementSegments:
            document.movementSegments = [nxt]
        document.activeMovementSegmentId = nxt.id
        hydrate_live_from_segment(document, nxt)
    document.movementSegmentRevision = int(document.movementSegmentRevision or 0) + 1
    return segment


def resolve_movement_ref(document: SpatialMapDocument, ref: str) -> dict[str, Any]:
    """Resolve M1 / Movement 2 / beat name / next / previous / current.

    Never guesses when two beats share a name. Never falls back to M1 silently.
    """
    hydrate_movement_segments(document)
    text = (ref or "").strip()
    if not text:
        return {"matched": [], "ambiguous": False, "note": "empty reference"}
    import re

    lowered = text.lower()
    ordered = sorted(document.movementSegments, key=lambda s: int(s.segmentNumber))
    active = active_segment(document)

    if re.search(r"\b(current|this|active)\s+movement\b", lowered) or lowered in {"current", "this movement"}:
        return {"matched": [active.model_dump()], "ambiguous": False, "note": "active movement"}
    if re.search(r"\bnext\s+movement\b", lowered) or lowered == "the next movement":
        later = [s for s in ordered if int(s.segmentNumber) > int(active.segmentNumber)]
        if not later:
            return {"matched": [], "ambiguous": False, "note": "no next movement"}
        return {"matched": [later[0].model_dump()], "ambiguous": False, "note": "next movement"}
    if re.search(r"\b(previous|last|prior)\s+movement\b", lowered):
        earlier = [s for s in ordered if int(s.segmentNumber) < int(active.segmentNumber)]
        if not earlier:
            return {"matched": [], "ambiguous": False, "note": "no previous movement"}
        return {"matched": [earlier[-1].model_dump()], "ambiguous": False, "note": "previous movement"}

    number = None
    m = re.search(r"(?i)\bm\s*(\d)\b", text)
    if m:
        number = int(m.group(1))
    else:
        m = re.search(r"(?i)\bmovement\s+(\d)\b", text)
        if m:
            number = int(m.group(1))
    if number is not None:
        hits = [s for s in ordered if int(s.segmentNumber) == number]
        if not hits:
            return {
                "matched": [],
                "ambiguous": False,
                "note": f"Movement {number} no longer exists. Choose another movement.",
            }
        return {"matched": [hits[0].model_dump()], "ambiguous": False, "note": movement_alias(number)}

    name_hits = [
        s
        for s in ordered
        if s.beatName and s.beatName.strip().lower() in lowered
    ]
    if len(name_hits) == 1:
        return {"matched": [name_hits[0].model_dump()], "ambiguous": False, "note": name_hits[0].beatName}
    if len(name_hits) > 1:
        return {
            "matched": [s.model_dump() for s in name_hits],
            "ambiguous": True,
            "note": "more than one movement matches that beat name",
        }
    return {"matched": [], "ambiguous": False, "note": "unrecognized movement reference"}


def compact_segment_json(segment: MovementSegment) -> dict[str, Any]:
    return {
        "id": segment.id,
        "segmentNumber": segment.segmentNumber,
        "alias": movement_alias(segment.segmentNumber),
        "beatName": segment.beatName,
        "revision": int(segment.revision or 1),
        "userDirection": segment.userDirection,
        "productionPrompt": segment.productionPrompt,
        "actions": [a.model_dump() for a in segment.actions],
        "dialogue": [d.model_dump() for d in segment.dialogue],
        "continuity": segment.continuity.model_dump() if segment.continuity else {},
        "timingHintSeconds": segment.timingHintSeconds,
        "characterStates": [c.model_dump() for c in segment.characterStates],
        "propStates": [p.model_dump() for p in segment.propStates],
        "cameraStateRefs": list(segment.cameraStateRefs or []),
        "cameraStates": [c.model_dump() for c in (getattr(segment, "cameraStates", None) or [])],
    }
