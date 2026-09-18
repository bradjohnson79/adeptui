"""Bind approved project character voices onto H3 R2V audio slots.

A character name in the prompt is not a voice. Only an approved voice
preview or reference audio on this project may be sent as <Audio j> /
ref_audios. Do not invent, clone, or import another project's voice silently.

On Timeline H3 live generate/retake, cast authority for *pictures* remains
Direct Reference Route. This module only attaches approved *audio* refs for
characters already on that cast (identityId). It does not replace visual
refs and does not claim exact-script TTS control — H3 still runs
generator_native audio with voice timbre conditioning when refs are present.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...character_identity.models import CharacterProfileRow, VoiceProfileRow
from ...db import Asset
from ..contracts import BatchBlock
from .contracts import TimelineGenerationRequest
from .r2v import attach_canonical_r2v, merge_identity_slots


def _identity_rows_from_batch(batch: BatchBlock) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(ident: str, name: str) -> None:
        ident = str(ident or "").strip()
        if not ident or ident in seen:
            return
        seen.add(ident)
        rows.append((ident, str(name or ident).strip() or ident))

    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or "").strip().lower()
        role = str(ref.get("role") or "").strip().lower()
        if kind == "characteridentity":
            ids = list(ref.get("identityIds") or [])
            names = list(ref.get("identityNames") or [])
            for idx, ident in enumerate(ids):
                name = str(names[idx] if idx < len(names) else ident or "")
                _add(str(ident), name)
            continue
        if kind in {"entity", "character"} or role in {"character", "entity_reference", "cast"}:
            _add(str(ref.get("identityId") or ""), str(ref.get("label") or ref.get("identityName") or ""))
    for window in getattr(batch, "speechWindows", None) or []:
        if not isinstance(window, dict):
            continue
        for speaker in window.get("speakers") or []:
            if not isinstance(speaker, dict):
                continue
            _add(
                str(speaker.get("characterId") or speaker.get("speakerId") or ""),
                str(speaker.get("speakerName") or ""),
            )
    return rows


def _identity_rows(
    batch: BatchBlock,
    request: TimelineGenerationRequest | None = None,
) -> list[tuple[str, str]]:
    """Union Direct Reference cast, entity/character refs, and speech-window speakers."""
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(ident: str, name: str) -> None:
        ident = str(ident or "").strip()
        if not ident or ident in seen:
            return
        seen.add(ident)
        rows.append((ident, str(name or ident).strip() or ident))

    if request is not None:
        from .direct_reference import payload_from_request

        direct = payload_from_request(request)
        if direct is not None:
            for item in direct.characters:
                label = str(item.canonicalTag or "").lstrip("@#%*").strip() or str(item.identityId or "")
                _add(str(item.identityId or ""), label)
    for ident, name in _identity_rows_from_batch(batch):
        _add(ident, name)
    return rows


def _is_global_character(profile: Any) -> bool:
    return getattr(profile, "is_global", False) is True


def resolve_approved_voice_audio(
    db: Session,
    project_id: str,
    character_id: str,
) -> dict[str, Any] | None:
    profile = db.get(CharacterProfileRow, character_id)
    if profile is None or not profile.active_voice_profile_id:
        return None
    home = str(profile.project_id or "")
    same_project = home == str(project_id)
    if not same_project and not _is_global_character(profile):
        return None
    voice = db.get(VoiceProfileRow, profile.active_voice_profile_id)
    if voice is None or str(voice.character_profile_id or "") != str(character_id):
        return None
    if str(voice.project_id or "") not in {str(project_id), home}:
        return None
    if str(voice.approval_status or "").lower() != "approved":
        return None
    asset_id = str(voice.approved_preview_asset_id or voice.reference_asset_id or "").strip()
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    asset_project = str(getattr(asset, "project_id", "") or "")
    if asset_project not in {str(project_id), home, str(voice.project_id or "")}:
        return None
    return {
        "characterId": character_id,
        "voiceProfileId": voice.id,
        "assetId": asset_id,
        "name": profile.name or character_id,
    }


def _inject_approved_voices_into_direct_reference(
    db: Session,
    request: TimelineGenerationRequest,
    bound: list[dict[str, Any]],
) -> bool:
    """Add approved voices as DR audio items so H3 R2V sockets include ref_audios.

    Visual cast sockets stay Direct Reference. Returns True when DR was present
    and updated (even if bound is empty — clears prior approved_voice: audio).
    """
    from .direct_reference import DirectReferenceItem, _map_sockets, payload_from_request

    direct = payload_from_request(request)
    if direct is None:
        return False

    kept = [
        item
        for item in direct.audio
        if not str(item.bindingId or "").startswith("approved_voice:")
    ]
    for item in bound:
        asset = db.get(Asset, item["assetId"]) if db is not None else None
        source_path = ""
        if asset is not None:
            try:
                from ...video_runtime.comfy_asset_stage import (
                    ComfyAssetMissing,
                    resolve_library_source,
                )

                source_path = str(resolve_library_source(asset))
            except Exception:
                source_path = str(getattr(asset, "path", "") or "")
        name = str(item.get("name") or item["characterId"]).strip() or item["characterId"]
        tag = name if name.startswith(("@", "#", "%", "*")) else f"@{name}"
        kept.append(
            DirectReferenceItem(
                kind="audio",
                canonicalTag=tag,
                bindingId=f"approved_voice:{item['characterId']}",
                assetId=item["assetId"],
                assetType="audio",
                sourcePath=source_path,
                approved=True,
                identityId=item["characterId"],
                ordinal=len(kept) + 1,
            )
        )
    direct.audio = kept
    _map_sockets(direct)
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["directReferences"] = direct.model_dump()
    return True


def apply_approved_voices(
    db: Session,
    request: TimelineGenerationRequest,
    batch: BatchBlock,
    *,
    caps: Any | None = None,
) -> dict[str, Any]:
    bound: list[dict[str, Any]] = []
    missing: list[str] = []
    seen: set[str] = set()
    for ident, name in _identity_rows(batch, request):
        if ident in seen:
            continue
        seen.add(ident)
        resolved = resolve_approved_voice_audio(db, request.projectId, ident)
        if resolved is None:
            profile = db.get(CharacterProfileRow, ident)
            label = str((profile.name if profile is not None else "") or name or ident).strip()
            if label:
                missing.append(label)
            continue
        bound.append(resolved)
    kept = [
        ref
        for ref in (batch.references or [])
        if not (isinstance(ref, dict) and str(ref.get("kind") or "") == "characterVoice")
    ]
    for item in bound:
        kept.append(
            {
                "kind": "characterVoice",
                "identityId": item["characterId"],
                "identityName": item["name"],
                "label": item["name"],
                "assetId": item["assetId"],
                "voiceProfileId": item["voiceProfileId"],
                "consumed": True,
                "source": "project_character_voice",
            }
        )
    can_bind = caps is None or bool(getattr(caps, "supportsAudioReferences", False))
    if not can_bind:
        request.providerOptions = dict(request.providerOptions or {})
        request.providerOptions["characterVoices"] = {
            "applied": False,
            "voices": [],
            "missing": missing,
            "reason": "generator_has_no_audio_reference",
            "resolvedButUnbound": bound,
            "control": "voice_timbre_ref_only",
        }
        return {
            "ok": True,
            "applied": False,
            "voices": [],
            "missing": missing,
            "reason": "generator_has_no_audio_reference",
            "mock": False,
        }
    batch.references = kept
    used_direct = _inject_approved_voices_into_direct_reference(db, request, bound)
    if bound and caps is not None:
        attach_canonical_r2v(request, batch, caps, db=db)
    elif bound:
        merge_identity_slots(
            request,
            characters=[],
            place_asset_id=None,
            method=str((request.providerOptions or {}).get("reference_method") or "h3_ref2va"),
        )
    from .dialogue_authority import manifest_exact_script_dialogue

    # Timbre refs OK. Do not clobber Manifest exactScriptDialogue when locked+explicit.
    exact_script = manifest_exact_script_dialogue(request, batch)
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["characterVoices"] = {
        "applied": bool(bound),
        "voices": bound,
        "missing": missing,
        # Honesty: H3 Comfy has ref_audios sockets, not literal TTS / script lock.
        "control": "voice_timbre_ref_only",
        "exactScriptDialogue": exact_script,
        "directReferenceAudioInjected": used_direct,
    }
    return {
        "ok": True,
        "applied": bool(bound),
        "voices": bound,
        "missing": missing,
        "mock": False,
        "control": "voice_timbre_ref_only",
        "exactScriptDialogue": exact_script,
        "directReferenceAudioInjected": used_direct,
    }
