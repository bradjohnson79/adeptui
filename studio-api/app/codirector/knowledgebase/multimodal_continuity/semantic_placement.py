"""Spatial Map placements → visually meaningful relationships.

Does not add zone/landmark columns to SpatialPlacement. Translates miniPrompt,
notes, grid cell, and optional Visual Canon landmarks.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.spatial_map.ers_projection import grid_cell_label
from .schema import ActorPlacement, HARD_FACT_STATUSES, PropPlacement


def _as_dict(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, dict):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dump()
    return {
        key: getattr(item, key)
        for key in ("characterId", "propId", "label", "tag", "miniPrompt", "notes", "gridColumn", "gridRow")
        if hasattr(item, key)
    }


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "").strip() for p in parts if str(p or "").strip()).lower()


def translate_actor(placement: Any, *, canon: dict[str, Any] | None = None) -> ActorPlacement:
    data = _as_dict(placement)
    name = (
        str(data.get("label") or "").strip()
        or str(data.get("tag") or "").lstrip("@").strip()
        or str(data.get("characterId") or "").strip()
        or "Character"
    )
    mini = str(data.get("miniPrompt") or data.get("notes") or "").strip()
    text = _blob(mini, name)
    cell = grid_cell_label(data.get("gridColumn"), data.get("gridRow"))
    actor = ActorPlacement(
        actor=name,
        characterId=str(data.get("characterId") or "").strip(),
        miniPrompt=mini,
        gridCell=cell,
        factStatus="uncertain",
    )
    behind_bar = "behind" in text and any(
        k in text for k in ("bar", "counter", "barista", "service")
    )
    espresso = any(k in text for k in ("espresso", "barista station", "coffee machine", "coffee maker"))
    if behind_bar:
        actor.relativePosition = "behind_service_counter"
        actor.zone = "staff"
        actor.barrierSide = "employee_side"
        actor.facing = "customer_side"
        actor.forbiddenZones = ["front_of_counter", "customer_seating"]
        actor.factStatus = "creator_confirmed" if mini else "spatial_map_authoritative"
    if espresso:
        actor.landmark = "espresso_station"
        if actor.factStatus == "uncertain":
            actor.factStatus = "creator_confirmed" if mini else "inferred"
    if any(k in text for k in ("staff", "employee")):
        actor.barrierSide = "employee_side"
        actor.zone = actor.zone or "staff"
        if actor.factStatus == "uncertain":
            actor.factStatus = "creator_confirmed"
    if not actor.relativePosition and cell:
        actor.relativePosition = f"grid_{cell}"
        actor.factStatus = "spatial_map_authoritative"
    _apply_canon_landmarks(actor, canon)
    return actor


def translate_prop(placement: Any) -> PropPlacement:
    data = _as_dict(placement)
    name = (
        str(data.get("label") or "").strip()
        or str(data.get("tag") or "").lstrip("#").strip()
        or str(data.get("propId") or "").strip()
        or "Prop"
    )
    cell = grid_cell_label(data.get("gridColumn"), data.get("gridRow"))
    attached = str(data.get("placementMode") or "") == "attached"
    host = str(data.get("attachedCharacterId") or "").strip()
    return PropPlacement(
        prop=name,
        propId=str(data.get("propId") or data.get("prop_id") or "").strip(),
        gridCell=cell,
        attachedTo=host if attached else "",
        relativePosition="attached" if attached else (f"grid_{cell}" if cell else ""),
        factStatus="spatial_map_authoritative" if (cell or attached) else "uncertain",
    )


def translate_placements(
    characters: Iterable[Any] | None = None,
    props: Iterable[Any] | None = None,
    *,
    canon: dict[str, Any] | None = None,
) -> tuple[list[ActorPlacement], list[PropPlacement]]:
    actors = [translate_actor(c, canon=canon) for c in (characters or [])]
    prop_rows = [translate_prop(p) for p in (props or [])]
    return actors, prop_rows


def hard_actors(actors: list[ActorPlacement]) -> list[ActorPlacement]:
    return [a for a in actors if str(a.factStatus) in HARD_FACT_STATUSES]


def _apply_canon_landmarks(actor: ActorPlacement, canon: dict[str, Any] | None) -> None:
    if not canon:
        return
    arch = canon.get("fixedArchitecture") if isinstance(canon.get("fixedArchitecture"), dict) else {}
    bar = arch.get("serviceCounterOrBar") if isinstance(arch.get("serviceCounterOrBar"), dict) else {}
    if actor.relativePosition == "behind_service_counter" and bar.get("location"):
        actor.zone = actor.zone or "staff"
    furniture = canon.get("furniture") if isinstance(canon.get("furniture"), dict) else {}
    couch = furniture.get("couch") if isinstance(furniture.get("couch"), dict) else {}
    if couch.get("present") is True and "east" in (actor.occludedFrom or []):
        return
