"""Deterministic Co-Director replies for leftover J22 situational cases.

Routing and runtime truth — not conversational cover-up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy.orm import Session

from .implied_references import (
    ImpliedResolution,
    resolve_implied_references,
    spoken_implied_resolution,
)


_CANCEL_RE = re.compile(
    r"\b(?:cancel(?:\s+that|\s+it|\s+the(?:\s+current)?\s+generation)?|"
    r"stop(?:\s+that|\s+it|\s+the(?:\s+current)?\s+generation)?|"
    r"never\s+mind)\b",
    re.I,
)
_TRY_AGAIN_RE = re.compile(
    r"\b(?:try\s+again|retry(?:\s+that)?|use\s+the\s+previous\s+one(?:\s+instead)?|"
    r"do\s+that\s+again(?!\s+but\s+with))\b",
    re.I,
)
_EXPLAIN_RE = re.compile(
    r"\b(?:how\s+will|what\s+changes\s+if|can\s+\w+\s+use|why\s+isn'?t|explain\s+honestly|"
    r"how\s+(?:minimax|h3|ltx|seedance)|compile\s+those\s+bindings)\b",
    re.I,
)
_SELECT_GEN_RE = re.compile(
    r"^\s*(?:please\s+)?(?:use|switch\s+to|let'?s\s+use|make\s+it)\s+"
    r"(?:the\s+)?(h3 base optimized|faster local h3|standard h3|"
    r"hunyuan(?:\s*video)?\s*1\.?5\s*distilled|"
    r"minimax(?:\s*-?\s*h3)?|\bh3\b|ltx(?:\s*-?\s*2(?:[.\s]*[35])?)?|"
    r"seedance(?:\s+kie)?|see\s*dance|kling|wan|hunyuan)\b"
    r"(?:\s+for\s+this(?:\s+scene)?|\s+as\s+the\s+generator)?\s*[.!]?\s*$",
    re.I,
)
_NAMED_GEN_RE = re.compile(
    r"\b(h3 base optimized|faster local h3|standard h3|"
    r"hunyuan(?:\s*video)?\s*1\.?5\s*distilled|"
    r"minimax(?:\s*-?\s*h3)?|\bh3\b|ltx(?:\s*-?\s*2(?:[.\s]*[35])?)?|"
    r"seedance(?:\s*-?\s*(?:fal|kie|api))?|see\s*dance|kling|wan|hunyuan|"
    r"maximin|seedanse|ltx\s*9)\b",
    re.I,
)
_GENERATE_RE = re.compile(
    r"\b(?:create|generate|render|run|enqueue|make|add)\b.+\b"
    r"(?:shot|clip|video|take|image|crs|sheet|footsteps?|footfalls?|sfx|sound|music|ambience|foley|audio)\b"
    r"|\bgenerate\s+(?:this|the|that|next)\b",
    re.I,
)
_ATTACHED_RE = re.compile(r"\b(?:what i attached|the attached|use what i attached)\b", re.I)
_SAME_SCENE_RE = re.compile(
    r"\b(?:stay(?:\s+on)?|keep(?:\s+us)?(?:\s+on|\s+in)?|lock|use)\s+"
    r"(?:the\s+)?(?:same|this|current)\s+scene\b"
    r"|\b(?:the\s+)?same\s+scene\b"
    r"|\bdon'?t\s+(?:switch|change|borrow)\s+(?:scenes?|the\s+scene)\b",
    re.I,
)
_INVENTORY_RE = re.compile(
    r"\b(?:what do we (?:already )?have|what(?:'s| is) already (?:here|made|produced)|"
    r"what have we (?:already )?(?:got|made|produced)|what(?:'s| is) in (?:the )?(?:library|scene))\b"
    r"|\balready have for (?:this|the) scene\b",
    re.I,
)
_PREV_GEN_RE = re.compile(
    r"\b(?:the\s+)?(?:previous|last|same)\s+generator\b|\bgenerator\s+as\s+last\s+time\b",
    re.I,
)
_AGAIN_WITH_RE = re.compile(r"\bdo\s+that\s+again\s+but\s+with\s+([A-Za-z][A-Za-z0-9_-]*)\b", re.I)
_DURATION_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*-?\s*seconds?\b", re.I)
_PASTE_FORBIDDEN = re.compile(r"\b(?:copy|paste|text model|drop this into|type this into)\b", re.I)


_AVATAR_STUDIO_RETIRED_RE = re.compile(
    r"\b(?:avatar\s*studio|infinite\s*talk|infinitetalk|long\s*cat|longcat|night\s*cat|"
    r"meigen|wan\s*avatar|talking\s*avatar|avatar\s*lip\s*sync|animate\s+\w+\s+with\s+avatar|"
    r"use\s+avatar(?:\s*studio)?\s+to)\b",
    re.I,
)


_GENERATOR_IDS = {
    "minimax": "minimax-h3",
    "minimax h3": "minimax-h3",
    "minimax-h3": "minimax-h3",
    "h3": "minimax-h3",
    "h3 base optimized": "minimax-h3-base-optimized",
    "minimax h3 base optimized": "minimax-h3-base-optimized",
    "faster local h3": "minimax-h3-base-optimized",
    "standard h3": "minimax-h3-i2v-local",
    "ltx": "ltx-2.5-distilled",
    "ltx 2.5": "ltx-2.5-distilled",
    "ltx-2.5": "ltx-2.5-distilled",
    "ltx 2.3": "ltx-local",
    "ltx-2.3": "ltx-local",
    "ltx-local": "ltx-local",
    "wan": "wan-local",
    "wan 2.2": "wan-local",
    "wan-local": "wan-local",
    "hunyuanvideo 1.5 distilled": "hunyuan-video-1.5-distilled",
    "hunyuan video 1.5 distilled": "hunyuan-video-1.5-distilled",
    "hunyuan": "hunyuan-video-1.5-local",
    "hunyuan-video-1.5-local": "hunyuan-video-1.5-local",
    "hunyuan-video-13b-local": "hunyuan-video-13b-local",
    "seedance": "seedance-2.0",
    "see dance": "seedance-2.0",
    "seedance 2.0": "seedance-2.0",
    "seedance-2.0": "seedance-2.0",
    "seedance-fal": "seedance-2.0",
    "seedance-api": "seedance-2.0",
    "fal_seedance": "seedance-2.0",
    "seedance 2.5": "seedance-2.5",
    "seedance-2.5": "seedance-2.5",
    "fal_seedance_25": "seedance-2.5",
    "seedance kie": "seedance-kie",
    "seedance-kie": "seedance-kie",
    "kling": "kling-fal",
}

_GENERATOR_LABELS = {
    "minimax-h3": "MiniMax H3",
    "minimax-h3-i2v-local": "MiniMax H3 — Local",
    "minimax-h3-base-optimized": "MiniMax H3 Base Optimized",
    "hunyuan-video-1.5-distilled": "HunyuanVideo 1.5 Distilled",
    "ltx-2.5-distilled": "LTX 2.5",
    "seedance-2.0": "Seedance 2.0",
    "seedance-2.5": "Seedance 2.5",
    "seedance-fal": "Seedance 2.0",
    "seedance-kie": "Seedance (Kie)",
    "kling-fal": "Kling",
    "ltx-local": "LTX 2.3",
    "wan-local": "WAN",
    "hunyuan-video-1.5-local": "Hunyuan Video",
    "hunyuan-video-13b-local": "Hunyuan Video 13B",
}

# Generators that are retired in Adept UI v1.1. Selecting one must fail honestly
# and redirect to MiniMax H3 or LTX 2.5 — never silently switch or pretend to run.
_RETIRED_GENERATORS = frozenset({
    "wan-local",
    "hunyuan-video-1.5-local",
    "hunyuan-video-13b-local",
    "ltx-local",
})

_KNOWN_GENERATOR_TOKENS = frozenset(_GENERATOR_IDS)
_UNKNOWN_LOOKALIKES = frozenset({"maximin", "seedanse", "ltx 9", "ltx9"})

ACTIVE_JOB = frozenset(
    {"queued", "running", "pending", "in_progress", "preparing", "cancel_requested", "cancelling"}
)
TERMINAL_OK = frozenset({"done", "completed", "succeeded"})
TERMINAL_STOP = frozenset({"cancelled", "canceled", "failed", "error"})


@dataclass
class SituationalTurn:
    spoken: str = ""
    block: bool = False
    kind: str = ""
    resolution: ImpliedResolution | None = None
    generator_id: str = ""
    job_status: str = ""


def canonical_generator_id(raw: str | None) -> str:
    token = re.sub(r"\s+", " ", (raw or "").strip().lower())
    token = token.replace("see dance", "seedance").replace("mini-max", "minimax")
    return _GENERATOR_IDS.get(token, "")


def generator_label(generator_id: str) -> str:
    return _GENERATOR_LABELS.get(generator_id, generator_id or "this generator")


def named_generators(text: str) -> list[str]:
    found: list[str] = []
    for match in _NAMED_GEN_RE.finditer(text or ""):
        raw = match.group(1)
        token = re.sub(r"\s+", " ", raw.strip().lower())
        if token in _UNKNOWN_LOOKALIKES:
            found.append(f"?{token}")
            continue
        resolved = canonical_generator_id(token)
        if resolved and resolved not in found:
            found.append(resolved)
    return found


def _scene_generator_id(db: Session, project_id: str, scene_id: str | None) -> str:
    if not project_id or not scene_id:
        return ""
    try:
        from ...director_timeline_w46.store import load_master

        master = load_master(db, project_id, scene_id)
        batches = ((master.get("master") or {}).get("batchBlocks") or []) if isinstance(master, dict) else []
        live = next((str(b.get("generatorId") or "") for b in batches if b.get("generatorId")), "")
        return live
    except Exception:
        return ""


def _scene_name(db: Session, scene_id: str | None) -> str:
    if not scene_id:
        return ""
    try:
        from ...db import Scene

        row = db.get(Scene, scene_id)
        return str(getattr(row, "name", "") or "") if row is not None else ""
    except Exception:
        return ""


_ARTIFACT_SPOKEN = {
    "image": "image",
    "video": "video",
    "audio": "sound",
}

_PACK_STATUS_SPOKEN = {
    "completed": "ready",
    "done": "ready",
    "succeeded": "ready",
    "running": "still generating",
    "queued": "queued",
    "preparing": "starting",
    "preview": "waiting for approval",
    "failed": "couldn't finish",
    "cancelled": "stopped",
    "canceled": "stopped",
}


def _clip_brief(text: str, limit: int = 90) -> str:
    brief = " ".join((text or "").split())
    if len(brief) <= limit:
        return brief
    return brief[: limit - 1].rstrip() + "…"


def _scene_production_inventory(db: Session, project_id: str, scene_id: str | None) -> str:
    """Speak from canonical production memory for the current scene."""

    scene = _scene_name(db, scene_id) or "this scene"
    if not project_id:
        return f"I do not have stored production work for {scene} yet."
    try:
        from ..generation_memory.store import list_generation_requests

        rows = list_generation_requests(db, project_id)
    except Exception:
        return f"I could not read what is already produced for {scene}."

    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for pack, req in rows:
        pack_scene = str(getattr(pack, "scene_id", "") or "")
        if scene_id and pack_scene and pack_scene != scene_id:
            continue
        brief = (req.originalUserInstructions or "").strip()
        if not brief:
            continue
        family = str(req.artifactType or pack.capability or "").split(".")[0] or "image"
        key = (family, brief[:120].lower())
        if key in seen:
            continue
        seen.add(key)
        kind = _ARTIFACT_SPOKEN.get(family, family)
        status = _PACK_STATUS_SPOKEN.get(str(getattr(pack, "status", "") or "").lower(), "")
        suffix = f" ({status})" if status else ""
        lines.append(f"- {kind}: {_clip_brief(brief)}{suffix}")
        if len(lines) >= 6:
            break
    if not lines:
        return f"I do not have stored images, video, or sound for {scene} yet."
    return f"Here is what I already have for {scene}:\n" + "\n".join(lines)


def _jobs_for_project(db: Session, project_id: str) -> list[Any]:
    if not project_id:
        return []
    try:
        from ...db import Job

        return (
            db.query(Job)
            .filter(Job.project_id == project_id)
            .order_by(Job.updated_at.desc())
            .limit(12)
            .all()
        )
    except Exception:
        return []


def _job_bucket(status: str) -> str:
    token = (status or "").strip().lower()
    if token in ACTIVE_JOB:
        return "active" if token not in {"queued", "pending"} else "queued"
    if token in TERMINAL_OK:
        return "completed"
    if token in TERMINAL_STOP:
        return "stopped"
    return "none"


def cancel_or_retry_reply(db: Session, project_id: str, text: str) -> SituationalTurn | None:
    message = text or ""
    wants_cancel = bool(_CANCEL_RE.search(message))
    wants_retry = bool(_TRY_AGAIN_RE.search(message))
    if not wants_cancel and not wants_retry:
        return None
    bare_never_mind = bool(re.match(r"^\s*never\s+mind[.!]?\s*$", message, re.I))
    jobs = _jobs_for_project(db, project_id)
    active = [j for j in jobs if _job_bucket(getattr(j, "status", "")) in {"active", "queued"}]
    latest = jobs[0] if jobs else None
    latest_status = str(getattr(latest, "status", "") or "") if latest is not None else ""
    bucket = _job_bucket(latest_status) if latest is not None else "none"

    if wants_cancel:
        if active:
            job = active[0]
            return SituationalTurn(
                spoken=(
                    f"There is a live generation ({job.id[:8]}…, {job.status}). "
                    "Cancel it from the job row if you want it stopped. I will not pretend it already stopped."
                ),
                block=True,
                kind="cancel_live",
                job_status=str(job.status),
            )
        if bare_never_mind:
            return SituationalTurn(
                spoken="Okay. Nothing is running. I did not cancel a job.",
                block=True,
                kind="never_mind",
                job_status=latest_status or "none",
            )
        if bucket == "completed":
            return SituationalTurn(
                spoken="The last generation already finished. There is nothing running to cancel.",
                block=True,
                kind="cancel_completed",
                job_status=latest_status,
            )
        if bucket == "stopped":
            return SituationalTurn(
                spoken=(
                    f"The last generation is already {latest_status}. "
                    "There is no live job to cancel."
                ),
                block=True,
                kind="cancel_already_stopped",
                job_status=latest_status,
            )
        return SituationalTurn(
            spoken="There is no generation running on this project. Nothing was cancelled.",
            block=True,
            kind="cancel_none",
            job_status="none",
        )

    if bucket in {"active", "queued"}:
        return SituationalTurn(
            spoken=(
                "A generation is still running. I will not start another one beside it. "
                "Cancel the live job first, or wait for it to finish."
            ),
            block=True,
            kind="retry_blocked_live",
            job_status=latest_status,
        )
    # Terminal or missing jobs are not an interview. Canonical production memory
    # plus the dispatcher own retry / inherit. Chat must not override that.
    return None


def _readiness_line(generator_id: str) -> tuple[str, str, bool]:
    try:
        from ...production_control.video_readiness import collect_video_facts, derive_video_readiness

        locality = (
            "hosted"
            if generator_id
            in {
                "seedance-2.0",
                "seedance-2.5",
                "seedance-fal",
                "seedance-kie",
                "kling-fal",
            }
            else "local"
        )
        facts = collect_video_facts(generator_id, locality=locality)
        return derive_video_readiness(facts)
    except Exception:
        return "Unsupported", "I could not read this generator's readiness.", False


def _creator_compile_line(generator_id: str) -> str:
    from ..knowledgebase.video_generators import load_video_generator_knowledge

    label = generator_label(generator_id)
    # Retired generators: honest retirement notice, not a compile card.
    if generator_id in _RETIRED_GENERATORS:
        return (
            f"{label} is retired in Adept UI v1.1. I will not compile references for it. "
            "Use Timeline MiniMax H3 or LTX 2.5 for Reference-to-Video."
        )
    kb = load_video_generator_knowledge(generator_id)
    if not kb.loaded:
        return f"{label} has no Adept generator card. I will not invent how it uses references."
    contract = kb.compile
    dialect = contract.dialect or "unmapped"
    if dialect == "unavailable" or generator_id == "seedance-kie":
        return (
            f"{label} is listed in Production Control but is not a Timeline submit path. "
            "I will not compile fal @Image tokens for it and I will not silently switch to Seedance fal."
        )
    if dialect == "h3_picture_tokens":
        return (
            f"{label} uses Character and Environment sheets as pictures in order: "
            "characters, then place, then props. Both characters and the corridor can ride together. "
            "Adept compiles the picture tags. You do not type them yourself."
        )
    if dialect == "ltx23_ingredients":
        return (
            f"{label} uses Ingredients: character and place sheets are guide images, "
            "not MiniMax picture tags and not a single start frame that drops extras."
        )
    if dialect == "ltx25_single_cond":
        return (
            f"{label} can condition only one start picture. Extra characters stay named in the prompt; "
            "they are not separate picture slots the way MiniMax H3 uses them."
        )
    if dialect == "seedance_at_tokens":
        return (
            f"{label} can take up to {contract.max_images or 4} images"
            + (" and one motion video" if contract.max_videos else "")
            + ". Characters and the environment become those images only when Seedance is Ready. "
            "Adept will not emit MiniMax picture tags for it."
        )
    return f"{label} compiles with the {dialect or contract.mechanism or 'authoritative'} contract from its generator card."


def generator_explain_reply(
    text: str,
    *,
    resolution: ImpliedResolution | None = None,
    current_generator_id: str = "",
) -> SituationalTurn | None:
    message = text or ""
    if not (
        _EXPLAIN_RE.search(message)
        or re.search(r"\bcompile\b.+\b(?:minimax|h3|ltx|seedance|kie)\b", message, re.I)
        or re.search(r"\b(?:minimax|h3|ltx|seedance|kie)\b.+\bcompile\b", message, re.I)
    ):
        return None
    wanted = named_generators(message)
    if "?ltx 9" in wanted or any(item.startswith("?") for item in wanted):
        unknown = next(item[1:] for item in wanted if item.startswith("?"))
        return SituationalTurn(
            spoken=f"I do not have a generator called {unknown}. I will not invent a compile contract for it.",
            block=True,
            kind="unknown_generator",
        )
    if "h3" in message.lower() and "ltx" in message.lower():
        wanted = ["minimax-h3", "ltx-2.5-distilled"]
    if not wanted:
        if current_generator_id:
            wanted = [canonical_generator_id(current_generator_id) or current_generator_id]
        else:
            wanted = ["minimax-h3"]
    retired = [item for item in wanted if item in _RETIRED_GENERATORS]
    if retired:
        labels = ", ".join(generator_label(item) for item in retired)
        return SituationalTurn(
            spoken=(
                f"{labels} is retired in Adept UI v1.1. I will not compile references for it. "
                "Use Timeline MiniMax H3 or LTX 2.5 for Reference-to-Video. "
                "I have not started a generation."
            ),
            block=True,
            kind="retired_generator",
            generator_id=retired[0],
        )
    lines = [_creator_compile_line(item) for item in wanted]
    if resolution and resolution.resolved:
        lines.append(
            "On this project that means: "
            + ", ".join(item.token for item in resolution.resolved)
            + "."
        )
    elif resolution and resolution.missing:
        lines.append(" ".join(resolution.missing))
    if re.search(r"why\s+isn'?t\s+this\s+prop", message, re.I):
        props = [item for item in (resolution.inventory if resolution else []) if item.kind == "prs"]
        if not props:
            lines.append(
                "No prop sheet is bound, so Adept will not send a prop picture. "
                "I will not invent a PRS."
            )
    lines.append("I have not started a generation.")
    return SituationalTurn(
        spoken=" ".join(lines),
        block=True,
        kind="generator_explain",
        generator_id=wanted[0] if wanted else "",
        resolution=resolution,
    )


def generator_select_reply(
    text: str,
    *,
    current_generator_id: str = "",
) -> SituationalTurn | None:
    message = (text or "").strip()
    match = _SELECT_GEN_RE.search(message)
    if not match:
        return None
    if _GENERATE_RE.search(message):
        return None
    raw = match.group(1)
    generator_id = canonical_generator_id(raw)
    if not generator_id:
        return SituationalTurn(
            spoken=f"I do not have a generator called {raw}. I will not invent one or switch silently.",
            block=True,
            kind="unknown_generator",
        )
    label = generator_label(generator_id)
    # Retired generators: fail honestly and redirect to current local video.
    if generator_id in _RETIRED_GENERATORS:
        return SituationalTurn(
            spoken=(
                f"{label} is retired in Adept UI v1.1. I will not start a shot with it. "
                "Use Timeline MiniMax H3 or LTX 2.5 for Reference-to-Video. "
                "I have not started a shot."
            ),
            block=True,
            kind="retired_generator",
            generator_id=generator_id,
        )
    current = canonical_generator_id(current_generator_id) or current_generator_id
    current_label = generator_label(current) if current else ""
    readiness, reason, executable = _readiness_line(generator_id)
    extra = ""
    if current and current != generator_id and current_label:
        extra = (
            f" This scene's current Timeline generator is {current_label}. "
            f"I'll treat {label} as the generator for this request. I have not changed the scene default."
        )
    ready_bit = f" {label} is {readiness}" + (f" — {reason}" if reason else ".")
    if not reason:
        ready_bit = f" {label} is {readiness}."
    spoken = (
        f"I'll use {label} on this project's Timeline. Adept already owns that route — "
        f"you do not copy or paste anything into another app.{extra}{ready_bit} "
        "I have not started a shot."
    )
    if _PASTE_FORBIDDEN.search(spoken):
        spoken = spoken.replace("copy or paste", "hand off")
    return SituationalTurn(
        spoken=spoken,
        block=True,
        kind="generator_select",
        generator_id=generator_id,
    )


def unready_generate_reply(text: str) -> SituationalTurn | None:
    message = text or ""
    if not _GENERATE_RE.search(message):
        return None
    # A Timeline scene-preparation request IS the Timeline path — the handoff
    # reply exists for chat-side "generate a shot with <generator>" asks, not
    # for scene production that names a generator in its runtime settings
    # ("...using MiniMax H3"). Blocking here would swallow the production
    # request before the dispatcher ever sees it.
    try:
        from .generation_authority import classify_generation_authority

        authority = classify_generation_authority(message)
        if authority is not None and str(getattr(authority, "kind", "") or "") == "timeline_scene_prepare":
            return None
    except Exception:
        pass
    named = named_generators(message)
    if any(item.startswith("?") for item in named):
        unknown = next(item[1:] for item in named if item.startswith("?"))
        return SituationalTurn(
            spoken=f"I do not have a generator called {unknown}. I did not start a shot and I will not guess.",
            block=True,
            kind="unknown_generator",
        )
    if not named:
        return None
    lines: list[str] = []
    any_blocked = False
    for generator_id in named:
        label = generator_label(generator_id)
        # Retired generators: honest retirement notice, not a readiness probe.
        if generator_id in _RETIRED_GENERATORS:
            lines.append(
                f"{label} is retired in Adept UI v1.1. Use Timeline MiniMax H3 or LTX 2.5."
            )
            any_blocked = True
            continue
        readiness, reason, executable = _readiness_line(generator_id)
        detail = f" — {reason}" if reason else ""
        lines.append(f"{label} is {readiness}{detail}.")
        if not executable:
            any_blocked = True
    if any_blocked:
        lines.append("I will not silently switch to another generator and I have not started a shot.")
        return SituationalTurn(
            spoken=" ".join(lines),
            block=True,
            kind="generator_unready",
            generator_id=named[0],
        )
    lines.append(
        "Timeline owns that reference-to-video shot. I have not started a generation from chat."
    )
    return SituationalTurn(
        spoken=" ".join(lines),
        block=True,
        kind="generator_named_handoff",
        generator_id=named[0],
    )


def _duration_conflict(text: str) -> str:
    values = [float(m.group(1)) for m in _DURATION_RE.finditer(text or "")]
    unique = {round(v, 3) for v in values}
    if len(unique) > 1:
        shown = " and ".join(f"{int(v) if v.is_integer() else v}s" for v in sorted(unique))
        return f"That asks for {shown} at once. Which duration should I keep?"
    return ""


def _misspelled_character(text: str, inventory: Iterable[Any]) -> str:
    names = [getattr(item, "name", "") for item in inventory if getattr(item, "kind", "") == "crs"]
    if not names:
        return ""
    import difflib

    words = re.findall(r"\b[A-Z][A-Za-z]{2,}\b", text or "")
    known = {name.lower() for name in names}
    known_tokens = {token for name in known for token in name.split() if len(token) > 2}
    # Platform/generator vocabulary and common sentence-start verbs are never
    # character misspellings. Project-specific names come from the live
    # inventory above — never from a hardcoded franchise list.
    generic_skip = {"minimax", "seedance", "create", "generate", "timeline", "scene"}
    for word in words:
        if word.lower() in known:
            continue
        if word.lower() in known_tokens:
            # Partial mention of a known multi-word character ("Meridian" of
            # "Dax Meridian", a dialogue speaker prefix) is not a misspelling.
            continue
        if word.lower() in generic_skip:
            continue
        hits = difflib.get_close_matches(word, names, n=1, cutoff=0.78)
        if hits and word.lower() != hits[0].lower():
            return f"I do not have a character named {word}. Did you mean {hits[0]}?"
    return ""


def memory_or_error_reply(
    db: Session,
    project_id: str,
    scene_id: str | None,
    text: str,
    *,
    attachment_ids: Iterable[str] | None = None,
    resolution: ImpliedResolution | None = None,
) -> SituationalTurn | None:
    message = text or ""
    attached = [str(item).strip() for item in (attachment_ids or []) if str(item).strip()]
    if _ATTACHED_RE.search(message):
        if not attached:
            return SituationalTurn(
                spoken="Nothing was attached on this turn. I did not look at a picture.",
                block=True,
                kind="no_attachment",
                resolution=resolution,
            )
        return SituationalTurn(
            spoken=f"I'll use the attachment from this turn ({attached[0][:8]}…). I have not started a generation.",
            block=True,
            kind="use_attachment",
            resolution=resolution,
        )

    duration = _duration_conflict(message)
    if duration:
        return SituationalTurn(spoken=duration, block=True, kind="duration_conflict", resolution=resolution)

    miss = _misspelled_character(message, (resolution.inventory if resolution else []))
    if miss:
        return SituationalTurn(spoken=miss, block=True, kind="unknown_character", resolution=resolution)

    if _INVENTORY_RE.search(message):
        spoken = _scene_production_inventory(db, project_id, scene_id)
        return SituationalTurn(
            spoken=spoken,
            block=True,
            kind="scene_inventory",
            resolution=resolution,
        )

    if _SAME_SCENE_RE.search(message) and not _GENERATE_RE.search(message) and not _INVENTORY_RE.search(message):
        name = _scene_name(db, scene_id) or "the current scene"
        return SituationalTurn(
            spoken=f"I'll stay on {name} in this project. I am not borrowing another scene or project.",
            block=True,
            kind="same_scene",
            resolution=resolution,
        )

    if _PREV_GEN_RE.search(message) and not _GENERATE_RE.search(message):
        current = _scene_generator_id(db, project_id, scene_id)
        if not current:
            return SituationalTurn(
                spoken="I do not have a stored previous generator for this scene. I will not guess one from another project.",
                block=True,
                kind="previous_generator_unknown",
            )
        return SituationalTurn(
            spoken=f"The generator on this scene is {generator_label(canonical_generator_id(current) or current)}. I have not started a shot.",
            block=True,
            kind="previous_generator",
            generator_id=current,
        )

    again = _AGAIN_WITH_RE.search(message)
    if again:
        who = again.group(1)
        hits = [
            item
            for item in (resolution.inventory if resolution else [])
            if item.kind == "crs" and item.name.lower() == who.lower()
        ]
        if not hits:
            return SituationalTurn(
                spoken=f"I do not have a character named {who} on this project. I will not invent one.",
                block=True,
                kind="unknown_character",
                resolution=resolution,
            )
        return SituationalTurn(
            spoken=(
                f"I can repeat the last request with {hits[0].token} only if we have a last valid generation on this project. "
                "I have not started that retry."
            ),
            block=True,
            kind="retry_with_character",
            resolution=resolution,
        )
    return None


def posecraft_product_reply(db: Session, project_id: str, text: str) -> SituationalTurn | None:
    """Product answers that must not depend on Local AI Runtime being online.

    Adept UI v1.1: PoseCraft is shelved — do not advertise or route into it.
    """
    try:
        from .v11_spatial_shelf import is_posecraft_creator_execution_gated

        if is_posecraft_creator_execution_gated():
            return None
    except Exception:
        return None
    raw = text or ""
    if re.search(
        r"\bwhat\s+is\s+posecraft(?:\s+used\s+for)?\b|\bwhat(?:'s| is)\s+posecraft\s+for\b",
        raw,
        re.I,
    ):
        return SituationalTurn(
            spoken=(
                "PoseCraft is the 3D staging workspace. Use it to place figures, set poses, "
                "and build a visual staging reference before Image Pipeline or Storyboard. "
                "It is not a final rendered frame."
            ),
            block=True,
            kind="posecraft_what",
        )
    if re.search(r"\bwho\s+is\s+(?:currently\s+)?on\s+(?:the\s+)?stage\b|\bwho(?:'s| is)\s+on\s+stage\b", raw, re.I):
        names: list[str] = []
        if project_id:
            try:
                from ..production_state.posecraft_slice import build_posecraft_slice

                slice_ = build_posecraft_slice(db, project_id)
                names = [fig.name for fig in slice_.figures if (fig.name or "").strip()]
            except Exception:  # noqa: BLE001
                names = []
        if names:
            spoken = f"On the PoseCraft stage right now: {', '.join(names)}."
        else:
            spoken = "No figures are on the PoseCraft stage yet."
        return SituationalTurn(spoken=spoken, block=True, kind="posecraft_who")
    if re.search(r"\bwhat\s+character\s+identity\s+should\s+posecraft\s+use\b", raw, re.I):
        return SituationalTurn(
            spoken=(
                "PoseCraft should use the character identity already bound on the stage figure, "
                "or the project character you name. I will not invent a different identity."
            ),
            block=True,
            kind="posecraft_identity",
        )
    open_match = re.search(r"\bopen\s+([A-Za-z][\w'-]*)\s+in\s+posecraft\b", raw, re.I)
    if open_match:
        who = open_match.group(1)
        return SituationalTurn(
            spoken=(
                f"I can open {who} in PoseCraft once the PoseCraft workspace navigation is wired. "
                "That navigation action is a PoseCraft product fix, not a Local AI Runtime failure."
            ),
            block=True,
            kind="posecraft_open",
        )
    return None


_AVAIL_RE = re.compile(
    r"\bwhich\s+local\s+video\s+generators?\s+are\s+available"
    r"|\bwhat\s+local\s+video\s+generators?\s+(?:are\s+)?(?:available|ready)"
    r"|\bwhich\s+video\s+generators?\s+(?:are|can i use)",
    re.I,
)
_WAN_T2V_RE = re.compile(
    r"\bwhy\s+can(?:'?t|\s+not)?\s+wan(?:\s+not)?\b.+\btext[- ]to[- ]video\b"
    r"|\bwan\b.+\btext[- ]to[- ]video\b.+\b(?:can'?t|cannot|won'?t|unavailable|offline|not)\b"
    r"|\btext[- ]to[- ]video\b.+\bwan\b",
    re.I,
)
_LTX_SHOT_RE = re.compile(
    r"\bcan\s+ltx\b.+\b(?:this\s+kind\s+of\s+shot|text[- ]to[- ]video|this\s+shot)\b"
    r"|\bltx\b.+\bcreate\s+this\s+(?:kind\s+of\s+)?shot\b",
    re.I,
)
_APPROPRIATE_GEN_RE = re.compile(
    r"\buse\s+the\s+appropriate\s+video\s+generator\b"
    r"|\b(?:pick|choose|select)\s+the\s+(?:right|correct|appropriate)\s+(?:video\s+)?generator\b",
    re.I,
)


def _mode_line(gen: Any) -> str:
    t2v = bool(getattr(gen, "supportsTextToVideo", False))
    last = bool(getattr(gen, "requiresLastFrame", False))
    i2v = bool(getattr(gen, "supportsImageToVideo", False))
    if last:
        return "first and last frame only — use 3 Frame or Timeline, not Text-to-Video or 1 Frame"
    if t2v:
        return "Text-to-Video"
    if i2v:
        return "Reference / Image-to-Video — 1 Frame or Timeline"
    return "Reference-to-Video on Timeline — not Text-to-Video and not start-only 1 Frame"


def _availability_spoken_from_rows(rows: list[Any]) -> str:
    skip = {"optional-wan", "wan-local", "wan", "wan_2_2"}
    locals_ = [
        g
        for g in rows
        if str(getattr(g, "locality", "")) == "local"
        and str(getattr(g, "id", "")) not in skip
    ]
    if not locals_:
        return (
            "I could not read the local video generator list from Production Control. "
            "That is a catalog read failure, not proof that every engine is offline."
        )
    lines: list[str] = []
    for gen in locals_:
        label = str(getattr(gen, "label", None) or getattr(gen, "id", "generator"))
        readiness = str(getattr(gen, "readiness", "") or "")
        reason = str(getattr(gen, "disabledReason", "") or "")
        executable = bool(getattr(gen, "executable", False))
        mode = _mode_line(gen)
        if executable and readiness == "Ready":
            state = f"Ready — {mode}"
        elif readiness == "Testing":
            state = f"installed, but not certified for normal use — {mode}"
            if reason:
                state = f"{state} ({reason})"
        elif readiness in {"Requires Setup", "Unsupported"} and "not installed" in reason.lower():
            state = f"not installed — {reason}"
        elif readiness == "Runtime Offline":
            state = f"runtime is down — {reason or 'the video host is not ready'}"
        elif readiness == "Requires Setup":
            state = f"requires setup — {reason or mode}"
        else:
            state = f"{readiness or 'unknown'} — {reason or mode}"
        lines.append(f"{label}: {state}.")
    return (
        "Local video generators right now: "
        + " ".join(lines)
        + " Gray does not always mean offline — mode, install, and runtime are different."
    )


def generator_availability_reply(text: str) -> SituationalTurn | None:
    message = text or ""
    if _WAN_T2V_RE.search(message):
        return SituationalTurn(
            spoken=(
                "WAN is retired in Adept UI v1.1. It is not a Text-to-Video path and "
                "it is not restored for first-and-last-frame shots. Use Timeline MiniMax H3 "
                "or LTX 2.5. I have not started a generation."
            ),
            block=True,
            kind="wan_retired",
            generator_id="wan-local",
        )
    if _LTX_SHOT_RE.search(message):
        wants_t2v = bool(re.search(r"\btext[- ]to[- ]video\b|\bno references\b", message, re.I))
        if wants_t2v:
            spoken = (
                "LTX cannot create a Text-to-Video shot. It needs a start picture "
                "on 1 Frame or Timeline. That is mode compatibility, not LTX being offline. "
                "I have not started a generation."
            )
        else:
            spoken = (
                "Yes — LTX 2.5 can create this kind of shot when you give it a start picture "
                "on 1 Frame or Timeline. It is Reference/Image-to-Video, not Text-to-Video. "
                "I have not started a generation."
            )
        return SituationalTurn(
            spoken=spoken,
            block=True,
            kind="ltx_mode",
            generator_id="ltx-2.5-distilled",
        )
    if _APPROPRIATE_GEN_RE.search(message):
        wants_t2v = bool(re.search(r"\btext[- ]to[- ]video\b|\bno references\b", message, re.I))
        if wants_t2v:
            spoken = (
                "For Text-to-Video, use MiniMax H3 or LTX 2.5 when Ready, or a hosted row such as Seedance. "
                "WAN is retired in v1.1. I have not started a generation or switched the scene."
            )
        else:
            spoken = (
                "For a reference shot, use a Ready local generator: MiniMax H3 Timeline or LTX 2.5. "
                "WAN is retired in v1.1. I have not started a generation or switched the scene."
            )
        return SituationalTurn(
            spoken=spoken,
            block=True,
            kind="appropriate_generator",
        )
    if not _AVAIL_RE.search(message):
        return None
    try:
        from ...production_control.generator_authority import timeline_generator_snapshot

        rows = timeline_generator_snapshot()
    except Exception:
        rows = []
    spoken = _availability_spoken_from_rows(rows)
    spoken = (
        spoken
        + " Avatar Studio is not part of the current production build (temporarily retired)."
    )
    return SituationalTurn(
        spoken=spoken,
        block=True,
        kind="generator_availability",
    )


def _persist_timeline_model(db: Session, project_id: str, scene_id: str | None, generator_id: str) -> bool:
    """Save an explicit model choice on the open Timeline shot. Never starts a job."""

    if db is None or not project_id or not scene_id or not generator_id:
        return False
    if generator_id in _RETIRED_GENERATORS:
        return False
    try:
        from ...film_timeline.orchestrator import set_shot_generator
        from ...film_timeline.store import require_film

        film = require_film(db, project_id, scene_id)
        if not film.shots:
            return False
        shot = film.shots[-1]
        set_shot_generator(db, project_id, scene_id, shot.id, generator_id)
        return True
    except Exception:
        return False


def resolve_situational_turn(
    db: Session,
    project_id: str,
    text: str,
    *,
    scene_id: str | None = None,
    attachment_ids: Iterable[str] | None = None,
) -> SituationalTurn:
    resolution = (
        resolve_implied_references(db, project_id, text, scene_id=scene_id)
        if project_id
        else ImpliedResolution()
    )
    current = _scene_generator_id(db, project_id, scene_id)

    cancel = cancel_or_retry_reply(db, project_id, text)
    if cancel:
        cancel.resolution = resolution
        return cancel

    # Avatar Studio temporarily retired from current Adept UI (InfiniteTalk/Wan unsuitable).
    if _AVATAR_STUDIO_RETIRED_RE.search(text or ""):
        return SituationalTurn(
            spoken=(
                "Avatar Studio is not available in this version. "
                "It has been temporarily retired from the current Adept UI production build "
                "(InfiniteTalk / Wan are not part of the current production direction). "
                "I will not open Avatar Studio or start avatar generation. "
                "Voice Creator remains available. Existing Avatar Library outputs remain valid. "
                "Future direction: cloud Avatar for Adept UI v1.2 — no delivery date. "
                "For video now, use Timeline MiniMax H3 or LTX 2.5."
            ),
            block=True,
            kind="avatar_studio_retired",
            resolution=resolution,
        )

    availability = generator_availability_reply(text)
    if availability:
        availability.resolution = resolution
        return availability

    explain = generator_explain_reply(text, resolution=resolution, current_generator_id=current)
    if explain:
        return explain

    if re.search(r"lower[-\s]?vram", text or "", re.I) and re.search(r"\b(?:use|switch|recommend)\b", text or "", re.I):
        return SituationalTurn(
            spoken=(
                "HunyuanVideo 1.5 Distilled is the lower-VRAM local option for Text to Video and Start Frame. "
                "I have not switched the Timeline model. Say \"Use HunyuanVideo 1.5 Distilled\" if you want that model."
            ),
            block=True,
            kind="generator_recommend",
            resolution=resolution,
        )

    select = generator_select_reply(text, current_generator_id=current)
    if select:
        select.resolution = resolution
        if select.kind == "generator_select" and _persist_timeline_model(db, project_id, scene_id, select.generator_id):
            label = generator_label(select.generator_id)
            select.spoken = f"Timeline is now using {label}. I have not started a shot."
        return select

    unready = unready_generate_reply(text)
    if unready:
        unready.resolution = resolution
        return unready

    if re.search(
        r"\b(?:ordinary|plain|standard)\s+i2v\b|\bsingle start frame only\b|"
        r"\btext-to-video\b.+\bno references\b|\bno references\b.+\btext-to-video\b",
        text or "",
        re.I,
    ) and re.search(r"\b(?:timeline|i2v|t2v|text-to-video)\b", text or "", re.I):
        return SituationalTurn(
            spoken=(
                "Timeline shots are Reference-to-Video, not ordinary I2V from one start frame "
                "and not empty text-to-video. I have not started a shot."
            ),
            block=True,
            kind="timeline_r2v_reframe",
            resolution=resolution,
        )

    posecraft = posecraft_product_reply(db, project_id, text)
    if posecraft:
        posecraft.resolution = resolution
        return posecraft

    if re.search(r"\bcrs\b|character reference sheet", text or "", re.I) and re.search(
        r"^\s*(?:should we|should i|do you think|would creating|what is|what's a)\b",
        text or "",
        re.I,
    ):
        return SituationalTurn(
            spoken=(
                "CRS means Character Reference Sheet — a Character Creator action, not a relationship map. "
                "Name the character and say create it if you want that action. I have not started a sheet."
            ),
            block=True,
            kind="crs_question",
            resolution=resolution,
        )

    if re.search(r"\bltx\s*-?\s*2(?:[.\s]*5)\b", text or "", re.I) and re.search(
        r"\b(?:both character|three separate|separate (?:image )?cond|the way minimax)\b",
        text or "",
        re.I,
    ):
        return SituationalTurn(
            spoken=(
                "LTX 2.5 is text-to-video, a start frame, or a start frame and an end frame. "
                "It does not take character, place, or prop references, and it does not take a middle frame. "
                "I have not started a shot."
            ),
            block=True,
            kind="ltx25_one_cond",
            generator_id="ltx-2.5-distilled",
            resolution=resolution,
        )

    memory = memory_or_error_reply(
        db,
        project_id,
        scene_id,
        text,
        attachment_ids=attachment_ids,
        resolution=resolution,
    )
    if memory:
        return memory

    if re.search(r"\b(?:mug|coffee mug|glass mug|this prop|the prop)\b", text or "", re.I):
        props = [item for item in resolution.inventory if item.kind == "prs"]
        if not props:
            return SituationalTurn(
                spoken=(
                    "There is no bound prop sheet for that prop. "
                    "I will not invent one. Bind a prop reference sheet first; it stays unbound."
                ),
                block=True,
                kind="unbound_prop",
                resolution=resolution,
            )

    if (
        resolution.bind_only
        or (resolution.has_question and resolution.requested)
        or "change_only" in resolution.requested
        or "keep_except_environment" in resolution.requested
    ):
        spoken = spoken_implied_resolution(resolution)
        if spoken:
            return SituationalTurn(
                spoken=spoken,
                block=True,
                kind="implied_references",
                resolution=resolution,
            )

    return SituationalTurn(spoken="", block=False, kind="continue", resolution=resolution)
