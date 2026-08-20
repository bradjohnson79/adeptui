"""Co-Director importance filter — raw detections are not production objects."""

from __future__ import annotations

import re
from typing import Iterable

from .contracts import (
    MAX_CAMERA_SLOTS,
    MAX_CHARACTER_SLOTS,
    MAX_PROP_SLOTS,
    PerceptionEntity,
    UnusedDetection,
)

_WALL_LINT = re.compile(
    r"\b(poster|painting|picture frame|wall art|outlet|switch|vent|tile|brick|"
    r"wallpaper|nail|screw|sticker|decoration|ornament|doily|coaster)\b",
    re.IGNORECASE,
)

_FILM_PROP = re.compile(
    r"\b(counter|bar|table|chair|stool|door|window|espresso|machine|register|"
    r"cup|mug|lamp|sofa|couch|desk|stairs|vehicle|car|tree|plant|shelf|"
    r"cabinet|display|case|menu|board|sink|oven|grinder|pastry|bag)\b",
    re.IGNORECASE,
)

_ARCHITECTURE = re.compile(
    r"\b(wall|door|window|entrance|doorway|ceiling|floor|column|stairs)\b",
    re.IGNORECASE,
)


def is_wall_lint(label: str) -> bool:
    return bool(_WALL_LINT.search(label or ""))


def is_filmmaking_entity(entity: PerceptionEntity) -> bool:
    label = entity.label or ""
    if entity.kindHint == "character":
        return True
    if is_wall_lint(label):
        return False
    if entity.kindHint in {"prop", "architecture"}:
        return True
    return bool(_FILM_PROP.search(label) or _ARCHITECTURE.search(label))


def filter_entities(
    entities: Iterable[PerceptionEntity],
) -> tuple[list[PerceptionEntity], list[UnusedDetection]]:
    kept: list[PerceptionEntity] = []
    unused: list[UnusedDetection] = []
    for entity in entities:
        if is_filmmaking_entity(entity):
            kept.append(entity)
        else:
            unused.append(
                UnusedDetection(
                    label=entity.label,
                    kindHint=entity.kindHint,
                    perceptionEntityId=entity.id,
                    reason="not_important_to_blocking",
                )
            )
    return kept, unused


def cap_slot_counts(
    characters: list,
    props: list,
    cameras: list,
) -> tuple[list, list, list, list[UnusedDetection]]:
    overflow: list[UnusedDetection] = []

    def _trim(items: list, limit: int, kind: str) -> list:
        if len(items) <= limit:
            return items
        extra = items[limit:]
        for item in extra:
            overflow.append(
                UnusedDetection(
                    label=getattr(item, "label", "") or kind,
                    kindHint="character" if kind == "character" else "prop",
                    perceptionEntityId=getattr(item, "perceptionEntityId", "")
                    or getattr(item, "id", ""),
                    reason="overflow_or_low_importance",
                )
            )
        return items[:limit]

    return (
        _trim(characters, MAX_CHARACTER_SLOTS, "character"),
        _trim(props, MAX_PROP_SLOTS, "prop"),
        _trim(cameras, MAX_CAMERA_SLOTS, "camera"),
        overflow,
    )
