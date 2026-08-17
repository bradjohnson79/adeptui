"""Assemble one instruction packet + fingerprint from Spatial Map, intent, and canon."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .chinese import compile_chinese
from .english import compile_english
from .panels import occlusion_notes
from .schema import (
    COMPILER_VERSION,
    CameraTask,
    CanonicalContinuity,
    InstructionPacket,
)
from .semantic_placement import translate_placements
from .source_authority import assert_canon_matches_pixels, resolve_source_authority
from .sync_validator import validate_sync
from .terminology import GLOSSARY


def _canon_dict(canon: Any | None) -> dict[str, Any]:
    if canon is None:
        return {}
    dump = getattr(canon, "model_dump", None)
    if callable(dump):
        return dump()
    if isinstance(canon, dict):
        return dict(canon)
    return {}


def _blocking_invariants(blocking: Any) -> list[str]:
    if blocking is None:
        return []
    if isinstance(blocking, dict):
        return [str(x).strip() for x in (blocking.get("invariants") or []) if str(x).strip()]
    values = getattr(blocking, "invariants", None) or []
    return [str(x).strip() for x in values if str(x).strip()]


def compile_facts(
    *,
    scene_title: str = "",
    location_type: str = "",
    original_asset_id: str = "",
    atlas_asset_id: str = "",
    lineage_fingerprint: str = "",
    canon: Any | None = None,
    characters: list[Any] | None = None,
    props: list[Any] | None = None,
    blocking: Any | None = None,
    panel_task: str = "whole_sheet",
    extra_invariants: list[str] | None = None,
) -> CanonicalContinuity:
    source = resolve_source_authority(
        original_asset_id=original_asset_id,
        atlas_asset_id=atlas_asset_id,
        lineage_fingerprint=lineage_fingerprint,
    )
    assert_canon_matches_pixels(source=source, canon=canon)
    cd = _canon_dict(canon)
    availability = str(cd.get("availability") or "")
    identity = dict(cd.get("identity") or {}) if isinstance(cd.get("identity"), dict) else {}
    geometry = dict(cd.get("geometry") or {}) if isinstance(cd.get("geometry"), dict) else {}
    architecture = (
        dict(cd.get("fixedArchitecture") or {}) if isinstance(cd.get("fixedArchitecture"), dict) else {}
    )
    furniture = dict(cd.get("furniture") or {}) if isinstance(cd.get("furniture"), dict) else {}
    materials = dict(cd.get("materials") or identity.get("materials") or {})
    lighting = dict(cd.get("lighting") or identity.get("lighting") or {})
    spatial = [str(x) for x in (cd.get("spatialRelationships") or []) if str(x).strip()]
    canon_hard = [str(x) for x in (cd.get("hardInvariants") or []) if str(x).strip()]
    forbidden = [str(x) for x in (cd.get("forbiddenChanges") or []) if str(x).strip()]
    uncertainties = [str(x) for x in (cd.get("uncertainty") or []) if str(x).strip()]
    if availability and availability != "available":
        uncertainties.append("Visual Canon is unavailable; architecture is not invented from vision.")
    actors, prop_rows = translate_placements(characters, props, canon=cd)
    hard: list[str] = []
    hard.extend(_blocking_invariants(blocking))
    hard.extend(canon_hard)
    hard.extend(extra_invariants or [])
    for actor in actors:
        if actor.relativePosition == "behind_service_counter":
            hard.append(
                f"{actor.actor} stays {GLOSSARY['behind_service_counter'][0]}, "
                f"{GLOSSARY['employee_side'][0]}."
            )
            forbidden.append("move characters to customer seating")
            forbidden.append("place characters in front of the service counter")
        if actor.landmark == "espresso_station":
            hard.append(f"{actor.actor} remains beside the {GLOSSARY['espresso_station'][0]}.")
    forbidden.extend(
        [
            "redesign the room",
            "mirror the architecture",
            "change window count",
            "relocate the main entrance",
        ]
    )
    facts = CanonicalContinuity(
        environmentIdentity=identity,
        geometry=geometry,
        fixedArchitecture=architecture,
        persistentFurniture=furniture,
        materials=materials if isinstance(materials, dict) else {},
        lighting=lighting if isinstance(lighting, dict) else {},
        spatialRelationships=spatial,
        actors=actors,
        props=prop_rows,
        hardInvariants=list(dict.fromkeys(hard)),
        forbiddenChanges=list(dict.fromkeys(forbidden)),
        uncertainties=uncertainties,
        factStatus=dict(cd.get("factStatus") or {}) if isinstance(cd.get("factStatus"), dict) else {},
        cameraTask=CameraTask(panelTask=panel_task or "whole_sheet", view=str(panel_task or "whole_sheet")),
        sourceAuthority=source,
        occlusionNotes=occlusion_notes(
            CanonicalContinuity(persistentFurniture=furniture, fixedArchitecture=architecture),
            panel_task,
        ),
        sceneTitle=scene_title,
        locationType=location_type,
    )
    if not facts.occlusionNotes:
        facts.occlusionNotes = occlusion_notes(facts, panel_task)
    return facts


def packet_fingerprint(
    facts: CanonicalContinuity,
    *,
    english: str,
    chinese: str,
    panel_task: str,
) -> str:
    payload = {
        "v": COMPILER_VERSION,
        "source": facts.sourceAuthority.model_dump(),
        "actors": [a.model_dump() for a in facts.actors],
        "props": [p.model_dump() for p in facts.props],
        "hard": facts.hardInvariants,
        "forbidden": facts.forbiddenChanges,
        "canon_identity": facts.environmentIdentity,
        "geometry": facts.geometry,
        "architecture": facts.fixedArchitecture,
        "furniture": facts.persistentFurniture,
        "panel": panel_task,
        "en": english,
        "zh": chinese,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def compile_packet(
    *,
    scene_title: str = "",
    location_type: str = "",
    original_asset_id: str = "",
    atlas_asset_id: str = "",
    lineage_fingerprint: str = "",
    canon: Any | None = None,
    characters: list[Any] | None = None,
    props: list[Any] | None = None,
    blocking: Any | None = None,
    panel_task: str = "whole_sheet",
    extra_invariants: list[str] | None = None,
    provider: str = "",
) -> InstructionPacket:
    facts = compile_facts(
        scene_title=scene_title,
        location_type=location_type,
        original_asset_id=original_asset_id,
        atlas_asset_id=atlas_asset_id,
        lineage_fingerprint=lineage_fingerprint,
        canon=canon,
        characters=characters,
        props=props,
        blocking=blocking,
        panel_task=panel_task,
        extra_invariants=extra_invariants,
    )
    english = compile_english(facts)
    chinese = compile_chinese(facts)
    packet = InstructionPacket(
        compilerVersion=COMPILER_VERSION,
        referenceImage={
            "assetId": facts.sourceAuthority.assetId,
            "type": str(facts.sourceAuthority.type),
        },
        continuityJson=facts,
        englishPrompt=english,
        chinesePrompt=chinese,
        hardInvariants=list(facts.hardInvariants),
        forbiddenChanges=list(facts.forbiddenChanges),
        panelTask=panel_task or "whole_sheet",
        provider=provider,
    )
    packet.fingerprint = packet_fingerprint(
        facts, english=english, chinese=chinese, panel_task=str(packet.panelTask)
    )
    validate_sync(packet)
    from .providers.gpt_image2 import render_gpt_image2
    from .providers.krea2 import render_krea2
    from .providers.qwen import render_qwen

    family = str(provider or "").lower()
    if "krea2" in family:
        packet.providerPrompt = render_krea2(packet)
    elif "qwen" in family:
        packet.providerPrompt = render_qwen(packet)
    elif "gpt" in family:
        packet.providerPrompt = render_gpt_image2(packet)
    else:
        packet.providerPrompt = english
    return packet
