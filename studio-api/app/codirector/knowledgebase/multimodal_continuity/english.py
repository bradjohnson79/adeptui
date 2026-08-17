"""English compiled view of CanonicalContinuity. Not an independent truth."""

from __future__ import annotations

from .panels import emphasis_lines, occlusion_notes, panel_includes_occupied
from .schema import CanonicalContinuity, HARD_FACT_STATUSES
from .terminology import GLOSSARY


def compile_english(facts: CanonicalContinuity) -> str:
    title = facts.sceneTitle or "this environment"
    src = facts.sourceAuthority
    lines: list[str] = []
    if src.assetId:
        lines.append(
            f"{GLOSSARY['preserve_environment'][0]} ({title}). "
            f"Source asset {src.assetId}."
        )
    else:
        lines.append(f"Generate the locked environment {title}.")
    preserve: list[str] = []
    if facts.fixedArchitecture.get("serviceCounterOrBar"):
        preserve.append("service counter")
    if any(a.landmark == "espresso_station" for a in facts.actors):
        preserve.append("espresso station")
    preserve.extend(
        p
        for p, ok in (
            ("pastry case", bool(facts.persistentFurniture.get("displayCases"))),
            ("storefront windows", bool((facts.geometry or {}).get("windowLocations"))),
            ("main entrance", bool((facts.geometry or {}).get("doorOrEntranceLocations"))),
            ("lounge couch", _couch_present(facts)),
        )
        if ok
    )
    if preserve:
        lines.append("Preserve the " + ", ".join(preserve) + ", materials, and room orientation.")
    else:
        lines.append(
            "Preserve architecture, materials, color palette, and room orientation from the reference."
        )
    for actor in facts.actors:
        if not panel_includes_occupied(facts.cameraTask.panelTask):
            break
        if str(actor.factStatus) not in HARD_FACT_STATUSES:
            continue
        bits = [f"{actor.actor} stands"]
        if actor.relativePosition == "behind_service_counter":
            bits.append(GLOSSARY["behind_service_counter"][0])
        if actor.landmark == "espresso_station":
            bits.append("beside the " + GLOSSARY["espresso_station"][0])
        if actor.barrierSide == "employee_side":
            bits.append("on the " + GLOSSARY["employee_side"][0])
        line = " ".join(bits) + "."
        if actor.forbiddenZones:
            bans = []
            if "front_of_counter" in actor.forbiddenZones:
                bans.append(GLOSSARY["front_of_counter"][0])
            if "customer_seating" in actor.forbiddenZones:
                bans.append("the " + GLOSSARY["customer_seating"][0])
            if bans:
                line += " Keep them there. Do not place them " + " or in ".join(bans) + "."
        lines.append(line)
    for inv in facts.hardInvariants:
        if not inv.strip():
            continue
        if not panel_includes_occupied(facts.cameraTask.panelTask) and _mentions_actor(inv, facts):
            continue
        lines.append(inv.strip())
    for ban in facts.forbiddenChanges:
        if not ban.strip():
            continue
        if not panel_includes_occupied(facts.cameraTask.panelTask) and _character_ban(ban):
            continue
        lines.append(ban.strip() if ban.strip().lower().startswith("do not") else f"Do not {ban.strip()}.")
    for note in occlusion_notes(facts, facts.cameraTask.panelTask):
        lines.append(note)
    lines.extend(emphasis_lines(facts.cameraTask.panelTask))
    lines.append(GLOSSARY["only_camera"][0] + ".")
    return "\n\n".join(lines)


def _couch_present(facts: CanonicalContinuity) -> bool:
    couch = facts.persistentFurniture.get("couch")
    if isinstance(couch, dict):
        return bool(couch.get("present") is True or couch.get("location"))
    return False


def _mentions_actor(text: str, facts: CanonicalContinuity) -> bool:
    return any(a.actor and a.actor in text for a in facts.actors)


def _character_ban(text: str) -> bool:
    blob = text.lower()
    return any(k in blob for k in ("character", "seating", "place characters"))
