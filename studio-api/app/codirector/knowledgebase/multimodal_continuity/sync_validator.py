"""Synchronization validator — JSON, English, and Chinese must agree."""

from __future__ import annotations

from .panels import panel_includes_occupied
from .schema import CanonicalContinuity, ContinuityCompileError, HARD_FACT_STATUSES, InstructionPacket
from .terminology import GLOSSARY


def fact_pairs(facts: CanonicalContinuity) -> list[tuple[str, str, str]]:
    """Return (fact_id, english_token, chinese_token) for hard constraints."""
    pairs: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add(fid: str) -> None:
        if fid in seen or fid not in GLOSSARY:
            return
        seen.add(fid)
        en, zh = GLOSSARY[fid]
        pairs.append((fid, en, zh))

    add("preserve_environment")
    add("only_camera")
    include_actors = panel_includes_occupied(facts.cameraTask.panelTask)
    for actor in facts.actors:
        if not include_actors:
            break
        if str(actor.factStatus) not in HARD_FACT_STATUSES:
            continue
        if actor.relativePosition == "behind_service_counter":
            add("behind_service_counter")
        if actor.landmark == "espresso_station":
            add("espresso_station")
        if actor.barrierSide == "employee_side":
            add("employee_side")
        if "front_of_counter" in actor.forbiddenZones:
            add("front_of_counter")
        if "customer_seating" in actor.forbiddenZones:
            add("customer_seating")
    if facts.fixedArchitecture.get("serviceCounterOrBar"):
        add("service_counter")
    return pairs


def validate_sync(packet: InstructionPacket) -> None:
    conflicts: list[str] = []
    english = packet.englishPrompt or ""
    chinese = packet.chinesePrompt or ""
    for fid, en, zh in fact_pairs(packet.continuityJson):
        if en.lower() not in english.lower():
            conflicts.append(f"{fid}: english missing '{en}'")
        if zh not in chinese:
            conflicts.append(f"{fid}: chinese missing '{zh}'")
        # Opposite-side leak: behind in JSON/English but 前方 in Chinese.
        if fid == "behind_service_counter" and GLOSSARY["front_of_counter"][1] in chinese:
            if GLOSSARY["behind_service_counter"][1] not in chinese:
                conflicts.append("behind_service_counter: chinese says 吧台前方")
        if fid == "behind_service_counter" and GLOSSARY["front_of_counter"][0].lower() in english.lower():
            if "do not place" not in english.lower() and "not" not in english.lower():
                conflicts.append("behind_service_counter: english asserts in front of the counter")
    if conflicts:
        raise ContinuityCompileError(
            "The English and Chinese instructions disagree. Generation was blocked "
            "so the model would not receive conflicting placement rules.",
            field="sync",
            conflicts=conflicts,
        )
    packet.syncOk = True
    packet.syncConflicts = []
