"""Compile parsed markup + Character Creator profiles into a NormalizedPerformancePlan."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..character_identity import service as ci
from .parser import parse_markup
from .schemas import ParseResultOut, PerformanceSegmentOut, PlanOut, ValidationIssue


COMPILER_VERSION = "w44.1"


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _locked_project_guard(db: Session, project_id: str, request=None) -> None:
    try:
        from ..project_security import service as project_security

        if request is not None:
            project_security.require_unlocked(db, project_id, request)
        elif project_security.is_protected(db, project_id):
            # Without request token, deny if protected (Co-Director path must bind unlock)
            raise _err(
                "PROJECT_LOCKED",
                "This project is password protected. Unlock it before accessing production data.",
                403,
            )
    except HTTPException:
        raise
    except Exception:
        pass


def resolve_character_context(db: Session, project_id: str, character_id: str, voice_version_id: str | None = None) -> dict[str, Any]:
    profile = ci.get_profile(db, project_id, character_id)
    voices = ci.list_voice_profiles(db, project_id, character_id)
    voice = None
    if voice_version_id:
        voice = next((v for v in voices if v["id"] == voice_version_id), None)
    if not voice:
        voice = next((v for v in voices if v.get("approval_status") == "approved"), None)
    if not voice and profile.active_voice_profile_id:
        voice = next((v for v in voices if v["id"] == profile.active_voice_profile_id), None)
    wiki_audio: dict[str, Any] = {}
    try:
        from ..codirector.wiki_intelligence.maintenance import tool_wiki_context

        wiki_audio = tool_wiki_context(
            db,
            project_id,
            domains=["characters", "creativeFoundation", "worldAndSetting"],
        )
    except Exception:
        wiki_audio = {}
    return {
        "profile": profile,
        "voice": voice,
        "performance": profile.performance or {},
        "emotion": profile.emotion or {},
        "relationships": profile.relationships or [],
        "motion": profile.motion or {},
        "prompt_package": profile.prompt_package or {},
        "wikiToolContext": wiki_audio if wiki_audio.get("ok") else None,
    }


def apply_character_defaults(segments: list[PerformanceSegmentOut], ctx: dict[str, Any]) -> tuple[list[PerformanceSegmentOut], dict[str, Any]]:
    perf = ctx.get("performance") or {}
    emotion = ctx.get("emotion") or {}
    defaults = {
        "speakingCadence": perf.get("speakingCadence"),
        "humorStyle": perf.get("humorStyle"),
        "reactionTiming": perf.get("reactionTiming"),
        "baselineEmotion": emotion.get("baseline"),
        "sarcasmBehavior": emotion.get("sarcasmBehavior"),
        "fromPerformanceBible": True,
    }
    out: list[PerformanceSegmentOut] = []
    for seg in segments:
        data = seg.model_dump()
        if seg.segmentType == "speech" and not seg.pace and defaults.get("speakingCadence"):
            cad = str(defaults["speakingCadence"]).lower()
            if "fast" in cad or "quick" in cad:
                data["pace"] = data.get("pace") or "fast"
        if seg.segmentType == "speech" and not seg.delivery and defaults.get("humorStyle"):
            data["delivery"] = data.get("delivery") or {"style": "dry, teasing", "fromBible": True}
        if seg.segmentType == "speech" and not seg.emotion and defaults.get("baselineEmotion"):
            data["emotion"] = {"primary": "neutral", "intensity": 0.5, "fromBible": True}
        out.append(PerformanceSegmentOut(**data))
    return out, defaults


def apply_pronunciations(
    segments: list[PerformanceSegmentOut], voice: dict[str, Any] | None
) -> tuple[list[PerformanceSegmentOut], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    entries = (voice or {}).get("pronunciations") or []
    words = {str(e.get("word") or "").lower(): e for e in entries if isinstance(e, dict) and e.get("word")}
    out = []
    for seg in segments:
        data = seg.model_dump()
        text = seg.text or ""
        found = []
        for w, e in words.items():
            if w and w in text.lower():
                found.append(
                    {
                        "word": e.get("word"),
                        "phonetic": e.get("phonetic"),
                        "status": e.get("status") or "approved",
                    }
                )
        if found:
            data["pronunciationOverrides"] = (data.get("pronunciationOverrides") or []) + found
        # Heuristic: Capitalized fictional-looking terms without entry
        for token in text.split():
            clean = token.strip(".,!?;:\"'")
            if len(clean) > 3 and clean[0].isupper() and clean.lower() not in words and clean.isalpha():
                # only warn for uncommon proper nouns heuristic — Handari etc.
                if clean.lower() in ("korri", "anadriya", "handari", "abode"):
                    if clean.lower() not in words:
                        issues.append(
                            ValidationIssue(
                                code="UNRESOLVED_PRONUNCIATION",
                                severity="warning",
                                message=f"Unresolved pronunciation term: {clean}",
                                tagKey="pronunciation",
                            )
                        )
        out.append(PerformanceSegmentOut(**data))
    return out, issues


def apply_reactions(
    segments: list[PerformanceSegmentOut], voice: dict[str, Any] | None
) -> list[PerformanceSegmentOut]:
    reactions = {r.get("id") or r.get("label"): r for r in ((voice or {}).get("reactions") or []) if isinstance(r, dict)}
    out = []
    for seg in segments:
        data = seg.model_dump()
        if seg.segmentType == "reaction" and seg.reactionKey:
            key = seg.reactionKey
            # map sarcastic_scoff → scoff etc.
            asset = reactions.get(key) or reactions.get(key.replace("sarcastic_", "").replace("amused_", ""))
            if asset and asset.get("assetId") and asset.get("status") == "ready":
                data["outputAssetId"] = asset.get("assetId")
                data["supportMode"] = "Pre-rendered asset"
                data["status"] = "ready"
                data["provider"] = "character_reaction_library"
            else:
                data["supportMode"] = "Prompt-guided"
        out.append(PerformanceSegmentOut(**data))
    return out


def apply_relationship_context(
    segments: list[PerformanceSegmentOut], relationships: list[dict[str, Any]], other_speaker: str | None
) -> list[PerformanceSegmentOut]:
    if not other_speaker:
        return segments
    rel = next(
        (
            r
            for r in relationships
            if str(r.get("targetCharacter") or "").lower() == other_speaker.lower()
        ),
        None,
    )
    if not rel:
        return segments
    ctx = {
        "targetCharacter": rel.get("targetCharacter"),
        "communicationStyle": rel.get("communicationStyle"),
        "protectiveness": rel.get("protectiveness"),
        "authorityBalance": rel.get("authorityBalance"),
        "humorStyle": rel.get("humorStyle") or rel.get("tone"),
    }
    out = []
    for seg in segments:
        data = seg.model_dump()
        if seg.segmentType == "speech":
            data["relationshipContext"] = {**(data.get("relationshipContext") or {}), **ctx}
        out.append(PerformanceSegmentOut(**data))
    return out


def compile_performance(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    source_text: str,
    scene_id: str | None = None,
    voice_version_id: str | None = None,
    request=None,
) -> ParseResultOut:
    _locked_project_guard(db, project_id, request)
    ctx = resolve_character_context(db, project_id, character_id, voice_version_id)
    voice = ctx.get("voice")
    if not voice or voice.get("approval_status") != "approved":
        # Allow draft parse for authoring, but flag readiness
        pass
    parsed = parse_markup(source_text)
    segments: list[PerformanceSegmentOut] = list(parsed["segments"])
    issues: list[ValidationIssue] = list(parsed["issues"])
    segments, defaults = apply_character_defaults(segments, ctx)
    segments, pron_issues = apply_pronunciations(segments, voice)
    issues.extend(pron_issues)
    segments = apply_reactions(segments, voice)
    # Relationship: detect other speaker names in source
    other = None
    for name in ("ANADRIYA", "HUNTER", "INTERVIEWER"):
        if name in (source_text or "").upper() and name != (parsed.get("speaker") or "").upper():
            other = name.title() if name != "ANADRIYA" else "Anadriya"
            break
    segments = apply_relationship_context(segments, ctx.get("relationships") or [], other)

    status = parsed["status"]
    if any(i.severity == "blocked" for i in issues):
        status = "blocked"
    elif any(i.severity == "error" for i in issues) and status == "resolved":
        status = "needs_review"
    elif any(i.severity == "warning" for i in issues) and status == "resolved":
        status = "resolved_with_warning"

    return ParseResultOut(
        ok=status in ("resolved", "resolved_with_warning"),
        status=status,  # type: ignore[arg-type]
        sourceText=source_text,
        speaker=parsed.get("speaker"),
        characterId=character_id,
        voiceVersionId=(voice or {}).get("id"),
        segments=segments,
        issues=issues,
        appliedDefaults=defaults,
        mock=False,
    )


def character_readiness(db: Session, project_id: str, character_id: str, request=None) -> dict[str, Any]:
    _locked_project_guard(db, project_id, request)
    ctx = resolve_character_context(db, project_id, character_id)
    voice = ctx.get("voice")
    reactions = (voice or {}).get("reactions") or []
    prons = (voice or {}).get("pronunciations") or []
    testing_candidate = None
    if voice:
        testing_candidate = (voice.get("lineage") or {}).get("testingCandidateId")
    return {
        "characterId": character_id,
        "name": ctx["profile"].name,
        "approvedVoice": bool(voice and voice.get("approval_status") == "approved"),
        "voiceVersionId": (voice or {}).get("id"),
        "voiceSourceMode": (voice or {}).get("source_mode"),
        "testingCandidateId": testing_candidate,
        "testingVoiceReady": bool(voice and testing_candidate),
        "performanceBibleAttached": bool(ctx.get("performance")),
        "emotionProfileAttached": bool(ctx.get("emotion")),
        "pronunciationCount": len(prons),
        "reactionReadyCount": sum(1 for r in reactions if isinstance(r, dict) and r.get("status") == "ready"),
        "relationshipCount": len(ctx.get("relationships") or []),
        "promptPackageAttached": bool(ctx.get("prompt_package")),
        "readyForPerformance": bool(
            voice
            and voice.get("approval_status") == "approved"
            and ctx.get("performance")
            and ctx.get("emotion")
        ),
        "readyForTestingPerformance": bool(voice and (voice.get("approval_status") == "approved" or testing_candidate)),
        "mock": False,
    }
