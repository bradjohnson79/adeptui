from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import settings
from .validation import ensure_asset_lineage_fields, parse_sequence

DEFAULT_TRACKS = [
    ("video", "V1"),
    ("video", "V2"),
    ("video", "V3"),
    ("image", "I1"),
    ("image", "I2"),
    ("audio", "A1"),
    ("audio", "A2"),
    ("audio", "A3"),
    ("text", "T1"),
    ("fx", "FX"),
    ("mask", "M"),
    ("adjustment", "ADJ"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seq_dir(project_id: str) -> Path:
    return Path(settings.data_dir) / "magi" / "sequences" / project_id


def _seq_path(project_id: str) -> Path:
    return _seq_dir(project_id) / "sequence.json"


def empty_sequence(project_id: str, frame_rate: int = 24) -> dict[str, Any]:
    tracks = [
        {
            "id": f"trk_{label.lower()}_{uuid.uuid4().hex[:6]}",
            "kind": kind,
            "label": label,
            "order": index,
        }
        for index, (kind, label) in enumerate(DEFAULT_TRACKS)
    ]
    return {
        "id": f"seq_{uuid.uuid4().hex[:10]}",
        "projectId": project_id,
        "frameRate": frame_rate,
        "durationFrames": frame_rate * 60,
        "playheadFrame": 0,
        "tracks": tracks,
        "clips": [],
        "markers": [],
        "snapEnabled": True,
        "revision": 1,
        "updatedAt": _now(),
        "recipeId": None,
        "exportLedger": {},
        "finishing": {},
    }


def get_sequence(project_id: str) -> dict[str, Any]:
    """Read the sequence for a project without any write side-effect.

    A missing or corrupt file yields a fresh in-memory empty sequence; nothing
    is persisted on read (P2 fix from the m1 audit). The first PUT creates the
    file.
    """
    path = _seq_path(project_id)
    if not path.is_file():
        return empty_sequence(project_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_sequence(project_id)
    if not isinstance(raw, dict):
        return empty_sequence(project_id)
    # Validate shape of what we already have; if it no longer conforms, serve a
    # fresh empty sequence rather than a broken document. Never persists here.
    try:
        return parse_sequence(raw).model_dump()
    except ValueError:
        return empty_sequence(project_id)


def has_saved_sequence(project_id: str) -> bool:
    """Whether the project has a persisted MAGI sequence document.

    The m8 CLIP_NOT_FOUND contract applies only once a sequence is authoritative
    on the server; a never-saved project keeps the legacy asset-placement path.
    """
    return _seq_path(project_id).is_file()


def record_export_ledger(
    project_id: str,
    batch_block_id: str,
    clips: list[dict[str, Any]],
    *,
    scene_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Append m5 export provenance to ``sequence.json.exportLedger``.

    Server-owned bookkeeping only (B3): this merges the ledger into the
    canonical sequence document WITHOUT bumping ``revision``/``updatedAt``, so a
    MAGI export never forces a spurious optimistic-concurrency conflict for an
    in-flight client autosave. The ledger survives reload through normal
    sequence persistence and does not touch the frozen W46 contract.
    """
    current = get_sequence(project_id)
    ledger = dict(current.get("exportLedger") or {})
    existing = dict(ledger.get(batch_block_id) or {})
    existing_clips = list(existing.get("clips") or [])
    existing_clips.extend(clips)
    ledger[batch_block_id] = {
        **existing,
        "batchBlockId": batch_block_id,
        "sceneId": scene_id,
        "label": label,
        "clips": existing_clips,
    }
    path = _seq_path(project_id)
    document = {
        **current,
        "exportLedger": ledger,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return ledger


def save_sequence(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist a sequence payload (whole-document replace).

    Raises ``ValueError`` for schema-invalid payloads (never ``setdefault``-fills
    garbage). Backward-compatible defaults fill only fields missing from older
    empty sequence files. ``projectId``/``revision``/``updatedAt`` are forced.
    """
    path = _seq_path(project_id)
    current: dict[str, Any]
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    else:
        current = {}

    payload = dict(body or {})
    if not isinstance(payload, dict):
        raise ValueError("sequence payload must be an object")

    # Force project ownership + stable identity + revision (server is source of
    # truth for revision; mirrors the m1 audit P2 note on last-writer-wins).
    payload["projectId"] = project_id
    payload["id"] = payload.get("id") or current.get("id") or f"seq_{uuid.uuid4().hex[:10]}"
    payload["revision"] = int(current.get("revision") or 0) + 1
    payload["updatedAt"] = _now()

    # Backward-compatible migration for existing empty sequence files: carry
    # over defaults the client may not yet send. Only applied to genuinely
    # missing keys, never to invalid values (validation catches those below).
    payload.setdefault("frameRate", current.get("frameRate") or 24)
    payload.setdefault("durationFrames", current.get("durationFrames") or 24 * 60)
    payload.setdefault("playheadFrame", current.get("playheadFrame") or 0)
    payload.setdefault("snapEnabled", True)
    if "tracks" not in payload or not isinstance(payload.get("tracks"), list):
        payload["tracks"] = current.get("tracks") or empty_sequence(project_id)["tracks"]
    payload.setdefault("clips", [])
    payload.setdefault("markers", [])
    payload.setdefault("recipeId", None)
    payload.setdefault("exportLedger", current.get("exportLedger") or {})
    payload.setdefault("finishing", current.get("finishing") or {})

    # Strict schema + reference validation (rejects cross-track and malformed
    # payloads instead of persisting them).
    validated = parse_sequence(payload)

    # Preserve optional lineage fields on clips through serialization.
    clips = [
        ensure_asset_lineage_fields(clip) for clip in validated.model_dump()["clips"]
    ]

    document = {
        **validated.model_dump(exclude={"clips"}),
        "clips": clips,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return document
