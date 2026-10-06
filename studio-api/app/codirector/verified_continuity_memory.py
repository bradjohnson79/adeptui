"""Verified Continuity Memory — CD-owned facts for Batch N+1 refine.

HARD LAW:
- Written only after Perception Authority with parseOk=true.
- parseOk=false / UNCERTAIN / REJECTED never become canon.
- Omni never writes story/dialogue/next BatchPrompt here.
- Compile Batch N+1 may READ same project/scene/Take/revision only.
- ContinuityBridge prior_frame pixels stay Timeline Gen (not this module).
- No timeline_builder / Take / job / asset DB writes.
"""

from __future__ import annotations

import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "verified-continuity-v1"

# Perception classes that may enter canon (EXPECTED/OBSERVED only).
_CANON_OK = frozenset({"EXPECTED", "OBSERVED"})
_NEVER_CANON = frozenset({"UNEXPECTED", "UNCERTAIN", "REJECTED"})

_SPEECH_BLEED_RE = re.compile(
    r"\b(speech|speaking|spoken|dialogue|says?|said|talking|voiceover|voice-over|"
    r"gibberish|foreign language|subtitles?|whisper|muttering|camera crew|"
    r"film crew|behind the scenes|boom mic|clapper)\b",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_root() -> Path:
    override = (os.environ.get("ADEPT_VERIFIED_CONTINUITY_DIR") or "").strip()
    if override:
        return Path(override)
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or ".")
    return base / "Adept" / "VerifiedContinuityMemory"


def _key_path(
    *,
    project_id: str,
    scene_id: str,
    take_id: str,
    revision: str,
    batch_index: int,
) -> Path:
    safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "_" for c in str(s or "none"))[:80]
    return (
        memory_root()
        / safe(project_id)
        / safe(scene_id)
        / safe(take_id)
        / safe(revision)
        / f"batch_{int(batch_index)}.json"
    )


def build_verified_record(
    *,
    project_id: str,
    scene_id: str,
    take_id: str,
    revision: str,
    batch_index: int,
    facts: list[dict[str, Any]],
    source_packet_id: str = "",
    parse_ok: bool,
) -> dict[str, Any]:
    """Build a VerifiedContinuityMemory record (does not persist)."""
    verified: list[dict[str, Any]] = []
    if parse_ok:
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            klass = str(fact.get("class") or fact.get("kind") or fact.get("authority") or "").upper()
            if klass in _NEVER_CANON:
                continue
            if klass and klass not in _CANON_OK:
                # Unknown class: keep only if explicitly marked verified
                if not fact.get("verified"):
                    continue
            text = str(fact.get("text") or fact.get("summary") or fact.get("fact") or "").strip()
            if not text:
                continue
            # Speech / gibberish / foreign speech / crew-equipment never enter VCM canon.
            if _SPEECH_BLEED_RE.search(text):
                continue
            verified.append(
                {
                    "class": klass or "OBSERVED",
                    "text": text[:500],
                    "assetId": str(fact.get("assetId") or ""),
                }
            )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "projectId": project_id,
        "sceneId": scene_id,
        "takeId": take_id,
        "revision": revision,
        "batchIndex": int(batch_index),
        "parseOk": bool(parse_ok),
        "sourcePacketId": source_packet_id or "",
        "verifiedFacts": verified if parse_ok else [],
        "writtenAt": _now(),
    }


def write_verified_continuity(
    *,
    project_id: str,
    scene_id: str,
    take_id: str,
    revision: str,
    batch_index: int,
    facts: list[dict[str, Any]],
    source_packet_id: str = "",
    parse_ok: bool,
) -> dict[str, Any]:
    """Persist verified continuity. parseOk=false writes empty facts (honest record)."""
    record = build_verified_record(
        project_id=project_id,
        scene_id=scene_id,
        take_id=take_id,
        revision=revision,
        batch_index=batch_index,
        facts=facts,
        source_packet_id=source_packet_id,
        parse_ok=parse_ok,
    )
    path = _key_path(
        project_id=project_id,
        scene_id=scene_id,
        take_id=take_id,
        revision=revision,
        batch_index=batch_index,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def read_verified_continuity(
    *,
    project_id: str,
    scene_id: str,
    take_id: str,
    revision: str,
    batch_index: int,
) -> Optional[dict[str, Any]]:
    """Read memory for a prior batch. Same Take/revision only (caller supplies keys)."""
    path = _key_path(
        project_id=project_id,
        scene_id=scene_id,
        take_id=take_id,
        revision=revision,
        batch_index=batch_index,
    )
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # Fail-closed: refuse cross-key mismatches
    if str(data.get("projectId") or "") != str(project_id):
        return None
    if str(data.get("sceneId") or "") != str(scene_id):
        return None
    if str(data.get("takeId") or "") != str(take_id):
        return None
    if str(data.get("revision") or "") != str(revision):
        return None
    if not data.get("parseOk"):
        return None
    return data


def _scrub_canon_text(text: str) -> str | None:
    """Drop speech/equipment bleed from OBSERVED text before refine inject.

    Returns None when the fact is speech/crew-primary (never inject).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if _SPEECH_BLEED_RE.search(raw):
        return None
    return raw


def continuity_refine_lines(record: dict[str, Any] | None, *, limit: int = 6) -> list[str]:
    """Lines safe to inject into Batch N+1 CONTINUITY section.

    HARD: only EXPECTED/OBSERVED; UNEXPECTED/UNCERTAIN/REJECTED never inject.
    Speech / gibberish / foreign-language / crew-equipment bleed never inject.
    Always append lighting/exposure continuity for N+1 cut safety.
    """
    if not record or not record.get("parseOk"):
        return []
    lines: list[str] = []
    for fact in record.get("verifiedFacts") or []:
        if not isinstance(fact, dict):
            continue
        klass = str(fact.get("class") or "OBSERVED").upper()
        if klass in _NEVER_CANON or klass not in _CANON_OK:
            continue
        text = _scrub_canon_text(str(fact.get("text") or ""))
        if not text:
            continue
        lines.append(f"Verified continuity ({klass}): {text}")
        if len(lines) >= max(1, limit - 1):
            break
    light = (
        "Lighting continuity: same corridor practicals, exposure, and color temperature "
        "as the prior same-Take segment; no relight, no exposure flash at the cut."
    )
    if not any(light in ln for ln in lines):
        lines.append(light)
    return lines[:limit] if limit else lines


def facts_from_media_packet(packet: Any) -> list[dict[str, Any]]:
    """Extract candidate OBSERVED facts from a MediaIntelligencePacket (no canon yet)."""
    out: list[dict[str, Any]] = []
    if packet is None:
        return out
    summary = str(getattr(packet, "summary", None) or "").strip()
    if summary:
        out.append({"class": "OBSERVED", "text": summary[:400]})
    for action in getattr(packet, "characterActions", None) or []:
        label = str(getattr(action, "actionType", None) or getattr(action, "description", None) or "").strip()
        if label:
            out.append({"class": "OBSERVED", "text": f"Character action: {label}"})
    for seg in getattr(packet, "speechSegments", None) or []:
        # Speech observation is NOT dialogue authority. Unexpected / other-language /
        # gibberish speech is UNEXPECTED (never canon). Authorized speech is still
        # UNCERTAIN here — Dialogue Manifest alone may authorize lines.
        text = str(getattr(seg, "text", None) or "").strip()
        if text:
            out.append(
                {
                    "class": "UNEXPECTED",
                    "text": f"Unexpected speech (not dialogue authority; never canon): {text[:200]}",
                }
            )
    return out


def resolve_continuity_keys_from_batch(
    *,
    project_id: str,
    scene_id: str,
    batch: Any = None,
    master: Any = None,
    take_id: str = "",
    revision: str = "",
    batch_index: int | None = None,
) -> dict[str, Any]:
    """Resolve project/scene/take/revision/batchIndex for VCM keys (no DB writes).

    HARD LAW (same-Take N+1 refine):
    Prefer SceneTake id (``stk_…``) from master.activeSceneTakeId /
    currentSceneTakeId so Batch 0 and Batch 1 share one continuity key.
    Per-batch candidate ids (``take_…`` on batch.currentTakeId) are NOT the
    SceneTake — using them splits B0/B1 across folders and breaks refine.
    Fallback to batch candidate take only when no SceneTake is bound.
    """
    tid = (take_id or "").strip()
    if not tid and master is not None:
        tid = str(
            getattr(master, "activeSceneTakeId", None)
            or getattr(master, "currentSceneTakeId", None)
            or ""
        ).strip()
        # Also accept sceneTakes list member stamped on candidate takeState
        if not tid:
            try:
                from app.director_timeline_w46.scene_takes import (
                    active_scene_take,
                    current_scene_take,
                )

                st = active_scene_take(master) or current_scene_take(master)
                if st is not None:
                    tid = str(getattr(st, "id", "") or "").strip()
            except Exception:
                pass
    if not tid and batch is not None:
        # Last resort: per-batch candidate (does NOT prove same-Take refine alone)
        tid = str(
            getattr(batch, "currentTakeId", None)
            or getattr(batch, "activeTakeId", None)
            or ""
        ).strip()
    rev = (revision or "").strip()
    if not rev and master is not None:
        rev = str(getattr(master, "revision", None) or "").strip()
    if not rev:
        rev = "1"
    if batch_index is None:
        if batch is not None and getattr(batch, "order", None) is not None:
            batch_index = int(getattr(batch, "order", 0) or 0)
        else:
            batch_index = 0
    return {
        "project_id": str(project_id or "").strip(),
        "scene_id": str(scene_id or "").strip(),
        "take_id": tid or "unknown-take",
        "revision": rev,
        "batch_index": int(batch_index),
    }


def packet_parse_ok(packet: Any) -> bool:
    """True only when Perception Authority allows canon."""
    if packet is None:
        return False
    if hasattr(packet, "parseOk"):
        try:
            if packet.parseOk is True:
                return True
            if packet.parseOk is False:
                return False
        except Exception:
            pass
    try:
        if callable(getattr(packet, "is_ready", None)):
            return bool(packet.is_ready())
    except Exception:
        return False
    return False



def continuity_advance_allowed(*, batch: Any = None, dialogue_qc: dict | None = None) -> bool:
    """False while dialogue QC pending/retry/content-fail — no raw/stale VCM promotion."""
    try:
        from app.codirector.dialogue_authority import dialogue_qc_blocks_vcm_advance
        return not dialogue_qc_blocks_vcm_advance(batch, dialogue_qc)
    except Exception:
        if batch is not None and getattr(batch, "status", None) in (
            "QC_Pending",
            "QC_RetryRequired",
            "NeedsDialogueRetake",
        ):
            return False
        return True

def record_verified_continuity_from_packet(
    packet: Any,
    *,
    project_id: str,
    scene_id: str,
    batch: Any = None,
    master: Any = None,
    take_id: str = "",
    revision: str = "",
    batch_index: int | None = None,
) -> dict[str, Any] | None:
    """CD helper for live Gen Omni continuity path.

    Call after media_analyze.analyze_asset / save_packet when Take context exists.
    parseOk=false → empty verifiedFacts (never canon). No Take/job/asset DB writes.
    """
    if not continuity_advance_allowed(batch=batch):
        return None
    keys = resolve_continuity_keys_from_batch(
        project_id=project_id,
        scene_id=scene_id,
        batch=batch,
        master=master,
        take_id=take_id,
        revision=revision,
        batch_index=batch_index,
    )
    if not keys["project_id"] or not keys["scene_id"]:
        return None
    parse_ok = packet_parse_ok(packet)
    source_id = str(getattr(packet, "packetId", None) or "")
    return write_verified_continuity(
        project_id=keys["project_id"],
        scene_id=keys["scene_id"],
        take_id=keys["take_id"],
        revision=keys["revision"],
        batch_index=keys["batch_index"],
        facts=facts_from_media_packet(packet) if parse_ok else [],
        source_packet_id=source_id,
        parse_ok=parse_ok,
    )
