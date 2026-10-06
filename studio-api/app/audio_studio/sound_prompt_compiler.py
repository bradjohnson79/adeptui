"""Deterministic Sound Prompt Compiler for Audio Studio / Co-Director.

ORDER 14 Gen — structured SFX intent → provider prompt string + metadata.
Systems adapter consumes to_dict() fields; FE refine chips call mutate_sfx_intent.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence, Union

COMPILER_VERSION = "order14-sfx-compiler-v1.2"

# --- Intensity lexicon -------------------------------------------------------

BOLD_CUES = (
    "heavy", "loud", "hard", "forceful", "powerful", "massive", "violent",
    "slamming", "bang", "thunderous", "intense", "bold", "huge", "crash",
)
SOFT_CUES = (
    "soft", "quiet", "gentle", "light", "faint", "muted", "slight", "subtle",
    "whisper", "delicate",
)

INTENSITY_CFG = {
    "subtle": 3.6,
    "soft": 3.8,
    "normal": 4.5,
    "bold": 5.2,
    "huge": 5.6,
}

INTENSITY_PHRASE = {
    "subtle": "very soft subtle intensity, restrained transient",
    "soft": "soft gentle intensity, low-energy transient",
    "normal": "balanced natural intensity, clear readable transient",
    "bold": "bold heavy intensity, close and loud",
    "huge": "huge high-energy intensity, close and overwhelming",
}

# --- Refine ops (CONTRACT v1.2) ---------------------------------------------

OWNER_REFINE_OPS = frozenset({
    "too_soft", "too_loud", "too_short", "too_long",
    "wrong_material", "wrong_sound",
    "more_impacts", "fewer_impacts",
    "more_reverb", "less_reverb",
    "more_aggressive", "more_subtle",
    "regenerate_similar",
    # aliases
    "more_material", "less_ambience",
})

# UI "Too Soft" means the result was soft → patch LOUDER (contract § table).
_INTENSITY_UP = {"subtle": "soft", "soft": "normal", "normal": "bold", "bold": "huge", "huge": "huge"}
_INTENSITY_DOWN = {"huge": "bold", "bold": "normal", "normal": "soft", "soft": "subtle", "subtle": "subtle"}

_EVENT_ALIASES = {
    "door_slam": "door_slam",
    "doorslam": "door_slam",
    "slam": "door_slam",
    "door close": "door_slam",
    "door_close": "door_slam",
    "soft_close": "door_slam",
    "footsteps": "footsteps",
    "footstep": "footsteps",
    "steps": "footsteps",
    "walk": "footsteps",
    "knock": "knock",
    "knocks": "knock",
    "latch": "latch",
}

_MATERIAL_WORDS = (
    "steel", "metal", "iron", "wood", "wooden", "plastic", "glass", "concrete",
    "stone", "leather", "rubber", "ceramic", "aluminum", "aluminium",
)


@dataclass
class TemporalIntent:
    eventCount: Optional[int] = None
    pace: Optional[str] = None  # slow|medium|fast|or free text
    durationSec: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventCount": self.eventCount,
            "pace": self.pace,
            "durationSec": self.durationSec,
        }


@dataclass
class SoundCompileResult:
    """Compile result: provider prompt + structured intent for Systems/FE."""

    compiled_prompt: str
    physicalEvent: str = "generic"
    material: Optional[str] = None
    context: Optional[str] = None
    temporal: TemporalIntent = field(default_factory=TemporalIntent)
    negatives: list[str] = field(default_factory=list)
    refinementOps: list[str] = field(default_factory=list)
    # legacy / adapter helpers
    intensity_key: str = "normal"
    cfg_strength: float = 4.5
    event_key: str = "generic"
    variation_clause: Optional[str] = None
    compiler_version: str = COMPILER_VERSION
    warnings: list[str] = field(default_factory=list)
    raw_prompt: str = ""

    def to_dict(self, *, camel_compiled_prompt: bool = True) -> dict[str, Any]:
        """Systems adapter contract. Emits structured fields + compiled prompt.

        Always includes snake_case ``compiled_prompt``. When camel_compiled_prompt
        is True (default), also emits ``compiledPrompt`` for API camelCase.
        """
        neg_joined = ", ".join(self.negatives) if self.negatives else ""
        out: dict[str, Any] = {
            "physicalEvent": self.physicalEvent,
            "material": self.material,
            "context": self.context,
            "temporal": self.temporal.to_dict(),
            "negatives": list(self.negatives),
            "refinementOps": list(self.refinementOps),
            "compiled_prompt": self.compiled_prompt,
            "intensity_key": self.intensity_key,
            "cfg_strength": self.cfg_strength,
            "event_key": self.event_key,
            "variation_clause": self.variation_clause,
            "compiler_version": self.compiler_version,
            "warnings": list(self.warnings),
            "raw_prompt": self.raw_prompt,
            # service.py / Systems compat aliases
            "event_type": self.physicalEvent or self.event_key,
            "negative_prompt": neg_joined,
            "negativePrompt": neg_joined,
        }
        if camel_compiled_prompt:
            out["compiledPrompt"] = self.compiled_prompt
        return out

    def as_intent(self) -> dict[str, Any]:
        """Mutable intent dict suitable for mutate_sfx_intent input."""
        return {
            "physicalEvent": self.physicalEvent,
            "material": self.material,
            "context": self.context,
            "temporal": self.temporal.to_dict(),
            "negatives": list(self.negatives),
            "refinementOps": list(self.refinementOps),
            "intensity_key": self.intensity_key,
            "raw_prompt": self.raw_prompt,
            "event_key": self.event_key,
        }


# --- Helpers -----------------------------------------------------------------

def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _word_hit(text: str, words: Iterable[str]) -> bool:
    t = f" {_norm(text)} "
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in words)


def _infer_intensity(raw: str, explicit: Optional[str]) -> str:
    """Prefer explicit non-default intensity; else scan raw cues."""
    ex = _norm(explicit)
    mapping = {
        "subtle": "subtle", "soft": "soft", "quiet": "soft", "gentle": "soft",
        "normal": "normal", "natural": "normal", "medium": "normal",
        "bold": "bold", "loud": "bold", "heavy": "bold", "hard": "bold",
        "huge": "huge", "massive": "huge", "violent": "huge",
    }
    if ex and ex in mapping and mapping[ex] != "normal":
        return mapping[ex]
    if ex in mapping:
        # explicit normal — still allow raw cue override for slam/heavy language
        key = mapping[ex]
    else:
        key = "normal"
    if _word_hit(raw, BOLD_CUES):
        # door_slam + slam/bang/crash/heavy → bold unless user chose soft/subtle
        if key in ("soft", "subtle"):
            return key
        if _word_hit(raw, ("huge", "massive", "violent", "thunderous")):
            return "huge"
        return "bold"
    if _word_hit(raw, SOFT_CUES):
        if key in ("bold", "huge"):
            return key
        return "soft" if not _word_hit(raw, ("subtle", "whisper", "faint")) else "subtle"
    return key if ex else "normal"


def _infer_material(raw: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    t = _norm(raw)
    if "heavy steel" in t or "thick steel" in t:
        return "heavy steel"
    for w in _MATERIAL_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", t):
            if w in ("wood", "wooden"):
                return "wood"
            if w in ("metal", "iron", "steel", "aluminum", "aluminium"):
                return "steel" if "steel" in t or w == "steel" else w
            return w
    return None


def _infer_event(raw: str, explicit: Optional[str] = None, category: Optional[str] = None) -> str:
    if explicit:
        key = _norm(explicit).replace("-", "_").replace(" ", "_")
        return _EVENT_ALIASES.get(key, key)
    t = _norm(raw)
    # soft close before generic slam
    if re.search(r"\b(soft|gentle|quiet)\b.*\b(door|close|closing)\b", t) or \
       re.search(r"\b(door|close|closing)\b.*\b(soft|gentle|quiet)\b", t) or \
       "soft close" in t or "wooden door close" in t:
        return "door_slam"  # same event class; intensity/material discriminate
    if re.search(r"\b(door\s*slam|slam(?:ming)?\s+door|doorslam)\b", t) or \
       (re.search(r"\bslam\b", t) and re.search(r"\bdoor\b", t)):
        return "door_slam"
    if re.search(r"\b(footsteps?|foot\s*steps?|steps?\b|walking)\b", t):
        return "footsteps"
    if re.search(r"\bknock", t):
        return "knock"
    if re.search(r"\blatch\b", t):
        return "latch"
    if category:
        cat = _norm(category)
        if cat in _EVENT_ALIASES:
            return _EVENT_ALIASES[cat]
    return "generic"


def _footstep_count(duration_sec: float) -> int:
    """Intentional duration→step count. ORDER 14: max(3,min(12,round(duration*1.8)))."""
    try:
        d = float(duration_sec)
    except (TypeError, ValueError):
        d = 3.0
    return max(3, min(12, int(round(d * 1.8))))


def _pace_from_count(count: int, duration_sec: float) -> str:
    if duration_sec <= 0:
        return "medium"
    rate = count / max(duration_sec, 0.1)
    if rate < 1.2:
        return "slow"
    if rate > 2.2:
        return "fast"
    return "medium"


def _duration_hint(event_key: str, duration_sec: Optional[float], event_count: Optional[int]) -> tuple[str, TemporalIntent]:
    """Build temporal phrase + TemporalIntent."""
    dur = float(duration_sec) if duration_sec is not None else None
    temporal = TemporalIntent(durationSec=dur, eventCount=event_count)

    if event_key == "footsteps":
        d = dur if dur is not None else 3.0
        n = event_count if event_count is not None else _footstep_count(d)
        temporal.eventCount = n
        temporal.pace = _pace_from_count(n, d)
        # Explicit readable mapping in compiled prompt
        phrase = (
            f"{n} distinct footsteps over {d:g} seconds "
            f"(pace {temporal.pace}, ~{n / max(d, 0.1):.1f} steps/sec)"
        )
        return phrase, temporal

    if event_key == "door_slam":
        d = dur if dur is not None else 2.5
        temporal.eventCount = 1
        temporal.pace = "single"
        temporal.durationSec = d
        phrase = (
            f"single slam near the start of the {d:g}-second clip, "
            f"short residual only — one impact event"
        )
        return phrase, temporal

    if event_key == "knock":
        d = dur if dur is not None else 3.0
        n = event_count if event_count is not None else max(2, min(5, int(round(d))))
        temporal.eventCount = n
        temporal.pace = _pace_from_count(n, d)
        phrase = f"{n} distinct knocks spaced over {d:g} seconds"
        return phrase, temporal

    if dur is not None:
        temporal.eventCount = event_count or 1
        phrase = f"fit clearly within {dur:g} seconds"
        return phrase, temporal

    temporal.eventCount = event_count or 1
    return "clear finite event", temporal


def _door_slam_body(intensity_key: str, material: Optional[str], raw: str) -> str:
    """Bold/heavy steel vs soft wooden close — mutually exclusive language."""
    mat = _norm(material or "")
    soft = intensity_key in ("soft", "subtle") or _word_hit(raw, SOFT_CUES)
    steel = "steel" in mat or "metal" in mat or _word_hit(raw, ("steel", "metal", "iron"))
    wood = "wood" in mat or _word_hit(raw, ("wood", "wooden"))

    if soft or (wood and not steel and intensity_key not in ("bold", "huge")):
        # Subtle / soft wooden close — ≠ slam/crash/metal boom
        return (
            "soft wooden door close: soft wood settle into the frame, "
            "gentle latch catch after the settle, faint hinge whisper — "
            "quiet closure, not a slam, not a crash, not a metal boom"
        )

    if intensity_key in ("bold", "huge") or (steel and not soft):
        # Bold / heavy steel — latch AFTER mass impact; ≠ knock / light latch
        return (
            "heavy steel door slam: thick steel slab and frame boom, "
            "deep low-frequency mass impact first, then latch crash AFTER the mass hit — "
            "forceful metallic body slam, brief ringing decay, close and loud — "
            "not a knock, not a knuckle tap, not a light latch-only tick"
        )

    # normal default (metal-leaning slam, not knock)
    return (
        "forceful door slam impact, heavy door mass hitting frame, "
        "metallic boom, latch crash after the mass impact, short ringing residual — "
        "isolated slam, not a knock"
    )


def _footsteps_body(temporal_phrase: str, material: Optional[str], intensity_key: str) -> str:
    surface = material or "hard floor"
    weight = {
        "subtle": "very light soft footfalls",
        "soft": "light soft footfalls",
        "normal": "clear natural footfalls",
        "bold": "heavy solid footfalls",
        "huge": "very heavy pounding footfalls",
    }.get(intensity_key, "clear natural footfalls")
    return (
        f"footsteps event: {temporal_phrase}; {weight} on {surface}, "
        f"each step a distinct transient, keep event identity as footsteps only"
    )


def _generic_body(raw: str) -> str:
    base = (raw or "").strip() or "cinematic sound effect"
    # strip trailing period clutter
    return base.rstrip(".")


def _door_slam_negatives() -> list[str]:
    return [
        "knock", "knuckle", "light tap", "latch-only tick", "plastic click",
        "whoosh", "wind", "multiple doors", "footsteps",
        "gunshot", "explosion", "music", "melody", "speech",
    ]


def _soft_close_negatives() -> list[str]:
    return [
        "slam", "crash", "metal boom", "bang", "violent impact",
        "knock", "gunshot", "explosion", "music", "melody", "whoosh", "wind",
    ]


def _footsteps_negatives() -> list[str]:
    return [
        "door slam", "knock", "music", "melody", "speech", "ambience bed",
        "whoosh", "wind howl", "crowd",
    ]


def _variation_clause(event_key: str, intensity_key: str, variation_index: Optional[int]) -> Optional[str]:
    if variation_index is None or int(variation_index) <= 0:
        return None
    idx = int(variation_index) % 3
    if event_key == "door_slam":
        if intensity_key in ("soft", "subtle"):
            opts = (
                "slightly closer wood settle, same soft single close",
                "a touch more hinge whisper, same soft single close",
                "gentler latch after settle, same soft single close",
            )
        else:
            opts = (
                "heavier door mass, closer metallic body slam, same single slam",
                "more metallic boom body, same single slam",
                "deeper LF thud then latch, same single slam",
            )
        return opts[idx]
    if event_key == "footsteps":
        opts = (
            "slightly closer mic, same step count and pace",
            "a touch heavier each step, same step count",
            "drier room, same distinct step count",
        )
        return opts[idx]
    opts = (
        "slightly closer perspective, same event",
        "sharper transient, same event",
        "drier room, same event",
    )
    return opts[idx]


def _assemble_negatives(event_key: str, intensity_key: str, extra: Optional[Sequence[str]]) -> list[str]:
    if event_key == "door_slam" and intensity_key in ("soft", "subtle"):
        base = _soft_close_negatives()
    elif event_key == "door_slam":
        base = _door_slam_negatives()
    elif event_key == "footsteps":
        base = _footsteps_negatives()
    else:
        base = ["music", "melody", "speech", "gunshot", "explosion"]
    out: list[str] = []
    seen = set()
    for item in list(base) + list(extra or []):
        s = str(item).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _context_phrase(raw: str, explicit: Optional[str]) -> Optional[str]:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    # light scrape of "in <place>" from raw
    m = re.search(r"\bin\s+([^,.;]{3,80})", raw or "", flags=re.I)
    if m:
        return m.group(0).strip()
    return None


# --- Public API --------------------------------------------------------------

def compile_sound_prompt(
    prompt: str,
    *,
    duration_seconds: Optional[float] = None,
    intensity: Optional[str] = None,
    category: Optional[str] = None,
    event: Optional[str] = None,
    physicalEvent: Optional[str] = None,
    material: Optional[str] = None,
    context: Optional[str] = None,
    pace: Optional[str] = None,
    event_count: Optional[int] = None,
    eventCount: Optional[int] = None,
    negatives: Optional[Sequence[str]] = None,
    refinement_ops: Optional[Sequence[str]] = None,
    refinementOps: Optional[Sequence[str]] = None,
    variation_index: Optional[int] = None,
    intent: Optional[Mapping[str, Any]] = None,
    **_: Any,
) -> SoundCompileResult:
    """Compile creator prompt (+ optional structured intent) → provider prompt.

    Keeps legacy kwargs; also accepts contract camelCase from Systems adapter.
    """
    intent = dict(intent or {})
    raw = str(prompt or intent.get("raw_prompt") or "").strip()
    material = material or intent.get("material")
    context = context or intent.get("context")
    physicalEvent = physicalEvent or event or intent.get("physicalEvent") or intent.get("event_key")
    intensity = intensity or intent.get("intensity_key") or intent.get("intensity")
    duration_seconds = (
        duration_seconds
        if duration_seconds is not None
        else (intent.get("temporal") or {}).get("durationSec")
        if isinstance(intent.get("temporal"), dict)
        else intent.get("durationSec")
    )
    event_count = (
        eventCount
        if eventCount is not None
        else event_count
        if event_count is not None
        else (intent.get("temporal") or {}).get("eventCount")
        if isinstance(intent.get("temporal"), dict)
        else intent.get("eventCount")
    )
    if pace is None and isinstance(intent.get("temporal"), dict):
        pace = intent.get("temporal", {}).get("pace")
    neg_in = list(negatives or intent.get("negatives") or [])
    ref_ops = list(refinementOps or refinement_ops or intent.get("refinementOps") or [])

    event_key = _infer_event(raw, physicalEvent, category)
    intensity_key = _infer_intensity(raw, intensity)
    mat = _infer_material(raw, material)
    ctx = _context_phrase(raw, context)

    # Apply pending refinement ops onto a scratch intent before body assemble
    scratch = {
        "physicalEvent": event_key,
        "material": mat,
        "context": ctx,
        "temporal": {
            "eventCount": event_count,
            "pace": pace,
            "durationSec": duration_seconds,
        },
        "negatives": neg_in,
        "refinementOps": [],
        "intensity_key": intensity_key,
        "raw_prompt": raw,
        "event_key": event_key,
    }
    for op in ref_ops:
        scratch = mutate_sfx_intent(scratch, op)
    event_key = str(scratch.get("physicalEvent") or event_key)
    intensity_key = str(scratch.get("intensity_key") or intensity_key)
    mat = scratch.get("material") if scratch.get("material") is not None else mat
    ctx = scratch.get("context") if scratch.get("context") is not None else ctx
    temporal_in = scratch.get("temporal") or {}
    duration_seconds = temporal_in.get("durationSec", duration_seconds)
    event_count = temporal_in.get("eventCount", event_count)
    pace = temporal_in.get("pace", pace)
    neg_in = list(scratch.get("negatives") or neg_in)
    applied_ops = list(scratch.get("refinementOps") or ref_ops)

    temporal_phrase, temporal = _duration_hint(event_key, duration_seconds, event_count)
    if pace:
        temporal.pace = pace

    if event_key == "door_slam":
        body = _door_slam_body(intensity_key, mat, raw)
    elif event_key == "footsteps":
        body = _footsteps_body(temporal_phrase, mat, intensity_key)
    elif event_key == "knock":
        body = f"door knock pattern: {temporal_phrase}, knuckle on solid door, not a slam"
    else:
        body = _generic_body(raw)

    parts: list[str] = [body]
    if ctx:
        parts.append(ctx)
    if mat and event_key != "footsteps":
        # footsteps already embeds surface; door embeds material in body
        if event_key not in ("door_slam",) and mat.lower() not in body.lower():
            parts.append(f"{mat} material")
    if event_key != "footsteps":
        parts.append(temporal_phrase)
    parts.append(INTENSITY_PHRASE.get(intensity_key, INTENSITY_PHRASE["normal"]))

    if event_key == "door_slam":
        parts.append("isolated door slam, not a gunshot, not an explosion")
    elif event_key == "footsteps":
        parts.append("isolated footsteps only, not a crowd, not a door")

    neg_list = _assemble_negatives(event_key, intensity_key, neg_in)
    if neg_list:
        parts.append("avoid: " + ", ".join(neg_list))

    var = _variation_clause(event_key, intensity_key, variation_index)
    if var:
        parts.append(var)

    compiled = ", ".join(p.strip().rstrip(",") for p in parts if p and str(p).strip())

    return SoundCompileResult(
        compiled_prompt=compiled,
        physicalEvent=event_key,
        material=mat,
        context=ctx,
        temporal=temporal,
        negatives=neg_list,
        refinementOps=applied_ops,
        intensity_key=intensity_key,
        cfg_strength=float(INTENSITY_CFG.get(intensity_key, 4.5)),
        event_key=event_key,
        variation_clause=var,
        raw_prompt=raw,
    )


def mutate_sfx_intent(
    intent: Union[Mapping[str, Any], SoundCompileResult],
    op: str,
    *,
    materialHint: Optional[str] = None,
    physicalEventHint: Optional[str] = None,
    **hints: Any,
) -> dict[str, Any]:
    """Patch structured SFX intent for a refine op (CONTRACT v1.2).

    UI labels describe the *problem* with the last result:
      too_soft  → make LOUDER
      too_loud  → make SOFTER
      too_short → lengthen duration / more time for events
      too_long  → shorten duration
    """
    if isinstance(intent, SoundCompileResult):
        base = intent.as_intent()
    else:
        base = copy.deepcopy(dict(intent))

    temporal = dict(base.get("temporal") or {})
    if "eventCount" not in temporal and base.get("eventCount") is not None:
        temporal["eventCount"] = base.get("eventCount")
    if "durationSec" not in temporal and base.get("durationSec") is not None:
        temporal["durationSec"] = base.get("durationSec")
    if "pace" not in temporal and base.get("pace") is not None:
        temporal["pace"] = base.get("pace")

    negatives = list(base.get("negatives") or [])
    ops = list(base.get("refinementOps") or [])
    intensity = str(base.get("intensity_key") or base.get("intensity") or "normal")
    material = base.get("material")
    physical = str(base.get("physicalEvent") or base.get("event_key") or "generic")

    key = _norm(op).replace("-", "_").replace(" ", "_")
    materialHint = materialHint or hints.get("material_hint") or hints.get("materialHint")
    physicalEventHint = physicalEventHint or hints.get("physical_event_hint") or hints.get("physicalEventHint")

    if key not in OWNER_REFINE_OPS:
        # unknown op: record warning-style no-op but still append for traceability
        ops.append(key)
        base["refinementOps"] = ops
        base["temporal"] = temporal
        base["warnings"] = list(base.get("warnings") or []) + [f"unknown_refine_op:{key}"]
        return base

    if key == "too_soft":
        intensity = _INTENSITY_UP.get(intensity, "bold")
    elif key == "too_loud":
        intensity = _INTENSITY_DOWN.get(intensity, "soft")
    elif key == "too_short":
        d = float(temporal.get("durationSec") or 3.0)
        temporal["durationSec"] = round(min(20.0, d * 1.35 + 0.5), 3)
        if physical == "footsteps":
            temporal["eventCount"] = _footstep_count(float(temporal["durationSec"]))
    elif key == "too_long":
        d = float(temporal.get("durationSec") or 3.0)
        temporal["durationSec"] = round(max(1.0, d * 0.7), 3)
        if physical == "footsteps":
            temporal["eventCount"] = _footstep_count(float(temporal["durationSec"]))
    elif key == "wrong_material":
        if materialHint:
            material = str(materialHint).strip()
        else:
            # nudge: flip common steel/wood pair for door events
            m = _norm(str(material or ""))
            if "wood" in m:
                material = "heavy steel"
            elif "steel" in m or "metal" in m:
                material = "wood"
            else:
                material = "steel"
    elif key == "wrong_sound":
        if physicalEventHint:
            physical = _infer_event("", str(physicalEventHint))
        # else leave physical; Systems should pass hint
    elif key == "more_impacts":
        n = int(temporal.get("eventCount") or (1 if physical == "door_slam" else 4))
        temporal["eventCount"] = min(12, n + 2)
        if physical == "door_slam" and temporal["eventCount"] > 1:
            # door stays single-impact identity unless explicitly reclassed
            temporal["eventCount"] = 1
            negatives = _uniq(negatives + ["multiple doors", "repeated slams"])
    elif key == "fewer_impacts":
        n = int(temporal.get("eventCount") or 4)
        temporal["eventCount"] = max(1, n - 2)
        if physical == "footsteps":
            temporal["eventCount"] = max(3, temporal["eventCount"])
    elif key == "more_reverb":
        ctx = str(base.get("context") or "")
        if "reverb" not in ctx.lower():
            base["context"] = (ctx + ", more room reverb, longer tail").strip(", ")
    elif key == "less_reverb":
        ctx = str(base.get("context") or "")
        base["context"] = (ctx + ", dry close mic, minimal reverb").strip(", ")
        negatives = _uniq(negatives + ["long reverb", "hall wash"])
    elif key == "more_aggressive":
        intensity = _INTENSITY_UP.get(intensity, "bold")
        if intensity == "bold":
            intensity = "huge"
    elif key == "more_subtle":
        intensity = _INTENSITY_DOWN.get(intensity, "soft")
        if intensity == "soft":
            intensity = "subtle"
    elif key == "regenerate_similar":
        # no structural change — seed/variation handled by service
        pass
    elif key == "more_material":
        # alias → material presence nudge
        if materialHint:
            material = str(materialHint).strip()
        elif material:
            material = f"{material}, more pronounced material character"
        else:
            material = "more pronounced material character"
    elif key == "less_ambience":
        negatives = _uniq(negatives + ["ambience bleed", "room tone bed", "background wash", "music"])

    # re-sync footsteps count if duration changed and count not explicitly from more/fewer
    if physical == "footsteps" and key in ("too_short", "too_long"):
        temporal["eventCount"] = _footstep_count(float(temporal.get("durationSec") or 3.0))
        temporal["pace"] = _pace_from_count(
            int(temporal["eventCount"]), float(temporal.get("durationSec") or 3.0)
        )

    ops.append(key)
    base["physicalEvent"] = physical
    base["event_key"] = physical
    base["material"] = material
    base["temporal"] = temporal
    base["negatives"] = negatives
    base["refinementOps"] = ops
    base["intensity_key"] = intensity
    return base


def _uniq(items: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for x in items:
        k = str(x).strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(str(x).strip())
    return out


def compile_from_intent(intent: Mapping[str, Any], *, variation_index: Optional[int] = None) -> SoundCompileResult:
    """Provider-aware entry: structured intent → SoundCompileResult."""
    return compile_sound_prompt(
        str(intent.get("raw_prompt") or intent.get("prompt") or ""),
        intent=intent,
        variation_index=variation_index,
    )




def variation_clause(event: str | None, index: int = 0) -> str:
    """Legacy helper used by audio_studio.service._variation_hint path.

    Returns a short variation phrase; empty string if none.
    """
    key = _EVENT_ALIASES.get(_norm(event or ""), _norm(event or "") or "generic")
    clause = _variation_clause(key, "normal", int(index) if index is not None else None)
    return clause or ""

__all__ = [
    "COMPILER_VERSION",
    "OWNER_REFINE_OPS",
    "TemporalIntent",
    "SoundCompileResult",
    "compile_sound_prompt",
    "compile_from_intent",
    "mutate_sfx_intent",
    "_footstep_count",
]
