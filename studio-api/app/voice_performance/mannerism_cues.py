"""Controlled mannerism-cue vocabulary for Voice Performance (local IndexTTS2 / QwenEmotion).

Dialogue text = what the character speaks.
Mannerism cues = direction metadata + discrete local vocal-event layer.
Cue WORDS are NEVER spoken TTS text. Discrete audible events are stitched
separately (see mannerism_events.py); IndexTTS2 keeps dialogue/tone only.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

MannerismPosition = Literal["before", "during", "after"]
MannerismIntensity = Literal["light", "medium", "strong"]

# Controlled vocabulary — ids are stable; labels are UI-facing.
SUPPORTED_MANNERISMS: tuple[dict[str, str], ...] = (
    {"id": "sigh", "label": "Sigh", "aliases": "sigh,sighs,sighed"},
    {"id": "chuckle", "label": "Chuckle", "aliases": "chuckle,chuckles,chuckled"},
    {"id": "laugh", "label": "Laugh", "aliases": "laugh,laughs,laughed,laughter"},
    {"id": "soft_laugh", "label": "Soft Laugh", "aliases": "soft laugh,soft_laugh,softlaugh,giggle,giggles"},
    {"id": "gasp", "label": "Gasp", "aliases": "gasp,gasps,gasped"},
    {"id": "breath_in", "label": "Breath In", "aliases": "breath in,breath_in,inhale,inhaling,intake"},
    {"id": "breath_out", "label": "Breath Out", "aliases": "breath out,breath_out,exhale,exhaling"},
    {"id": "whisper", "label": "Whisper", "aliases": "whisper,whispers,whispered,whispering"},
    {"id": "pause", "label": "Pause", "aliases": "pause,pauses,paused,beat"},
    {"id": "hesitate", "label": "Hesitate", "aliases": "hesitate,hesitates,hesitated,hesitation,hesitant"},
    {"id": "scoff", "label": "Scoff", "aliases": "scoff,scoffs,scoffed"},
    {"id": "nervous_breath", "label": "Nervous Breath", "aliases": "nervous breath,nervous_breath,nervousbreath"},
)

_ALIAS_TO_ID: dict[str, str] = {}
_LABEL_BY_ID: dict[str, str] = {}
for _m in SUPPORTED_MANNERISMS:
    _LABEL_BY_ID[_m["id"]] = _m["label"]
    _ALIAS_TO_ID[_m["id"]] = _m["id"]
    _ALIAS_TO_ID[_m["label"].lower()] = _m["id"]
    for _a in _m["aliases"].split(","):
        _ALIAS_TO_ID[_a.strip().lower()] = _m["id"]

# Honest engine capability map — IndexTTS2 has no native non-speech audio events.
# Approximations ride QwenEmotion emo_text (+ optional structural ellipsis for pause/hesitate).
_CAPABILITY: dict[str, dict[str, Any]] = {
    "sigh": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a soft weary sigh before speaking, gently resigned",
            "medium": "a clear sigh of weariness or resignation before the line",
            "strong": "a heavy, audible sigh of deep resignation before speaking",
        },
    },
    "chuckle": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a light amused chuckle coloring the delivery",
            "medium": "an amused chuckle before the line",
            "strong": "a hearty chuckle breaking into the line",
        },
    },
    "laugh": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a quiet laugh energy in the delivery",
            "medium": "an open laugh before speaking the line",
            "strong": "a full laugh bursting before the line",
        },
    },
    "soft_laugh": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a barely-there soft laugh under the words",
            "medium": "a soft quiet laugh before the line",
            "strong": "a warm soft laugh clearly before speaking",
        },
    },
    "gasp": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a small surprised intake before speaking",
            "medium": "a sharp gasp of surprise before the line",
            "strong": "a startled gasp, breath caught hard before speaking",
        },
    },
    "breath_in": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a soft breath in before the first word",
            "medium": "an audible breath in before speaking",
            "strong": "a deep preparatory breath in before the line",
        },
    },
    "breath_out": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a soft breath out releasing into the line",
            "medium": "an audible breath out before speaking",
            "strong": "a heavy breath out before the line",
        },
    },
    "whisper": {
        "native": False,
        "mode": "emo_text",
        "emo_text": {
            "light": "soft near-whisper intimate delivery",
            "medium": "whispered intimate delivery throughout the line",
            "strong": "very close whispered hush, almost secret",
        },
    },
    "pause": {
        "native": False,
        "mode": "structural_pause",
        "emo_text": {
            "light": "a brief held beat before continuing",
            "medium": "a clear dramatic pause before the line",
            "strong": "a long held silence before speaking",
        },
        "leading_mark": {  # optional structural cue in spoken text (not a cue WORD)
            "light": "… ",
            "medium": "… ",
            "strong": "…… ",
        },
    },
    "hesitate": {
        "native": False,
        "mode": "structural_pause",
        "emo_text": {
            "light": "slight hesitation before committing to the words",
            "medium": "hesitant delivery, searching for the next word",
            "strong": "strong hesitation, almost unwilling to continue",
        },
        "leading_mark": {
            "light": "… ",
            "medium": "… ",
            "strong": "… ",
        },
    },
    "scoff": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a light dismissive scoff in the tone",
            "medium": "a contemptuous scoff before the line",
            "strong": "a sharp scornful scoff before speaking",
        },
    },
    "nervous_breath": {
        "native": False,
        "mode": "vocal_event",
        "emo_text": {
            "light": "a small nervous breath under the words",
            "medium": "a nervous shallow breath before speaking",
            "strong": "tight nervous breathing clearly before the line",
        },
    },
}

# Bracket tags: [sigh] [Sigh] [soft laugh] [reaction: sigh] [mannerism: chuckle]
_BRACKET = re.compile(r"\[([^\]]+)\]")
# Tag-shaped unknown: single token / short phrase inside brackets, not dialogue-like
_TAG_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9 _\-]{0,40}$")

# Natural-language CD patterns (Law #39 — structured result only; never dump to chat)
_CD_PATTERNS: tuple[tuple[re.Pattern[str], str, MannerismPosition], ...] = (
    (re.compile(r"\b(?:have|make|let)\s+\w+\s+sigh\b", re.I), "sigh", "before"),
    (re.compile(r"\bsigh\s+before\s+(?:saying|speaking|the\s+line)\b", re.I), "sigh", "before"),
    (re.compile(r"\bwith\s+a\s+sigh\b", re.I), "sigh", "before"),
    (re.compile(r"\bchuckle\s+before\b", re.I), "chuckle", "before"),
    (re.compile(r"\b(?:have|make|let)\s+\w+\s+chuckle\b", re.I), "chuckle", "before"),
    (re.compile(r"\bsoft\s+laugh\b", re.I), "soft_laugh", "before"),
    (re.compile(r"\b(?:have|make|let)\s+\w+\s+laugh\b", re.I), "laugh", "before"),
    (re.compile(r"\blaugh\s+before\b", re.I), "laugh", "before"),
    (re.compile(r"\bgasp\s+before\b", re.I), "gasp", "before"),
    (re.compile(r"\b(?:have|make|let)\s+\w+\s+gasp\b", re.I), "gasp", "before"),
    (re.compile(r"\bwhisper(?:s|ed|ing)?\b", re.I), "whisper", "during"),
    (re.compile(r"\bpause\s+before\b", re.I), "pause", "before"),
    (re.compile(r"\bhesitat(?:e|es|ed|ion)\b", re.I), "hesitate", "before"),
    (re.compile(r"\bscoff\s+before\b", re.I), "scoff", "before"),
    (re.compile(r"\b(?:have|make|let)\s+\w+\s+scoff\b", re.I), "scoff", "before"),
    (re.compile(r"\bnervous\s+breath\b", re.I), "nervous_breath", "before"),
    (re.compile(r"\bbreath(?:e)?\s+in\b", re.I), "breath_in", "before"),
    (re.compile(r"\bbreath(?:e)?\s+out\b", re.I), "breath_out", "before"),
)


def resolve_mannerism_id(raw: str) -> Optional[str]:
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if not key:
        return None
    if key in _ALIAS_TO_ID:
        return _ALIAS_TO_ID[key]
    # reaction: sigh / mannerism: chuckle / cue: gasp
    for prefix in ("reaction:", "mannerism:", "cue:", "action:"):
        if key.startswith(prefix):
            return resolve_mannerism_id(key[len(prefix) :].strip())
    return None


def normalize_intensity(raw: str | None) -> MannerismIntensity:
    v = (raw or "medium").strip().lower()
    if v in ("light", "low", "soft", "subtle"):
        return "light"
    if v in ("strong", "high", "heavy", "hard"):
        return "strong"
    return "medium"


def normalize_position(raw: str | None) -> MannerismPosition:
    v = (raw or "before").strip().lower().replace("-", " ").replace("_", " ")
    if v in ("during", "during line", "mid", "middle"):
        return "during"
    if v in ("after", "after line", "end"):
        return "after"
    return "before"


def make_cue(
    cue_id: str,
    *,
    position: MannerismPosition = "before",
    intensity: MannerismIntensity = "medium",
    source: str = "structured",
) -> dict[str, Any]:
    cap = _CAPABILITY.get(cue_id) or {}
    return {
        "id": cue_id,
        "label": _LABEL_BY_ID.get(cue_id, cue_id),
        "position": position,
        "intensity": intensity,
        "source": source,
        "nativeSupport": bool(cap.get("native")),
        "approximationMode": cap.get("mode") or "strip_only",
        "approximationNote": (
            "Discrete local vocal-event layer (DSP), stitched into the take; not IndexTTS2 emo_text alone."
            if (cap.get("mode") == "vocal_event")
            else (
                "No native IndexTTS2 non-speech audio; approximated via QwenEmotion emo_text / delivery."
                if not cap.get("native")
                else "Native engine support."
            )
        ),
    }


def _parse_bracket_body(body: str) -> tuple[Optional[str], bool]:
    """Return (cue_id_or_None, is_tag_shaped)."""
    raw = (body or "").strip()
    if not raw:
        return None, False
    # intensity suffix: sigh:strong / sigh|strong
    base = raw
    intensity_hint = None
    for sep in (":", "|", "/"):
        if sep in raw and not raw.lower().startswith(("http", "emotion", "delivery", "pace", "volume")):
            left, _, right = raw.partition(sep)
            # Keep emotion:/delivery: etc. out of mannerism path — those are performance tags
            if left.strip().lower() in (
                "emotion",
                "delivery",
                "pace",
                "volume",
                "pitch",
                "pause",
                "beat",
                "silence",
                "emphasis",
                "pronunciation",
                "relationship_tone",
                "timing",
                "breath",
            ):
                # pause/breath as performance tags may ALSO be mannerisms when value empty or duration
                if left.strip().lower() == "pause":
                    # [pause] or [pause: 280ms] — treat bare / word pause as mannerism; numeric as timing tag (leave)
                    if not right.strip() or right.strip().lower() in ("short", "medium", "long", "beat"):
                        return "pause", True
                    return None, True  # duration pause — not our mannerism strip (legacy parser owns it)
                if left.strip().lower() == "breath":
                    bid = resolve_mannerism_id(right) or resolve_mannerism_id("breath " + right)
                    if bid:
                        return bid, True
                    return None, True
                return None, True  # known non-mannerism performance tag — strip? leave to markup; M410 doesn't use it
            base, intensity_hint = left, right
            break
    cue_id = resolve_mannerism_id(base)
    if cue_id:
        return cue_id, True
    # reaction: sigh already handled in resolve
    if _TAG_SHAPE.match(raw) and " " not in raw.strip()[:1]:
        # clearly tag-shaped single token unknown
        if _TAG_SHAPE.match(raw):
            return None, True
    if _TAG_SHAPE.match(raw) and len(raw.split()) <= 3:
        return None, True
    return None, False


def extract_mannerisms_from_text(source_text: str) -> dict[str, Any]:
    """Parse bracketed cues from dialogue; return spoken text + structured cues + notices."""
    text = source_text or ""
    cues: list[dict[str, Any]] = []
    notices: list[str] = []
    spoken_parts: list[str] = []
    pos = 0
    for m in _BRACKET.finditer(text):
        spoken_parts.append(text[pos : m.start()])
        body = m.group(1)
        cue_id, tag_shaped = _parse_bracket_body(body)
        intensity = "medium"
        # intensity from body if present
        for sep in (":", "|", "/"):
            if sep in body:
                left, _, right = body.partition(sep)
                if resolve_mannerism_id(left) and right.strip():
                    intensity = normalize_intensity(right)
                break
        if cue_id:
            # Default position: leading cue → before; trailing → after; else during
            before = "".join(spoken_parts).strip()
            after_probe = text[m.end() :].lstrip()
            if not before:
                position: MannerismPosition = "before"
            elif not after_probe or after_probe.startswith("\n"):
                position = "after"
            else:
                position = "during"
            cues.append(make_cue(cue_id, position=position, intensity=intensity, source="bracket"))
            # Strip from spoken — do not append cue text
        elif tag_shaped:
            notices.append(f"Unsupported mannerism cue [{body.strip()}] was removed from spoken dialogue.")
            # Strip unknown tag-shaped brackets from TTS
        else:
            # Looks like ordinary dialogue characters inside brackets — keep
            spoken_parts.append(m.group(0))
        pos = m.end()
    spoken_parts.append(text[pos:])
    spoken = "".join(spoken_parts)
    # Collapse leftover whitespace from stripped tags
    spoken = re.sub(r"[ \t]{2,}", " ", spoken)
    spoken = re.sub(r" *\n *", "\n", spoken)
    spoken = spoken.strip()
    return {
        "spokenText": spoken,
        "mannerismCues": cues,
        "notices": notices,
        "sourceText": source_text,
    }


def merge_structured_cues(
    existing: list[dict[str, Any]] | None,
    extracted: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge UI/CD structured cues with bracket-extracted cues (dedupe by id+position)."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for src in (existing or [], extracted or []):
        for raw in src:
            if not isinstance(raw, dict):
                continue
            cue_id = resolve_mannerism_id(str(raw.get("id") or raw.get("cue") or raw.get("label") or ""))
            if not cue_id:
                continue
            position = normalize_position(str(raw.get("position") or "before"))
            intensity = normalize_intensity(str(raw.get("intensity") or "medium"))
            key = (cue_id, position)
            if key in seen:
                continue
            seen.add(key)
            cue = make_cue(
                cue_id,
                position=position,
                intensity=intensity,
                source=str(raw.get("source") or "structured"),
            )
            out.append(cue)
    return out


def apply_structural_marks(spoken_text: str, cues: list[dict[str, Any]]) -> str:
    """For pause/hesitate, optionally prepend ellipsis — never append cue WORDS."""
    text = spoken_text or ""
    prefix = ""
    for cue in cues:
        if cue.get("position") != "before":
            continue
        cap = _CAPABILITY.get(str(cue.get("id")) or "") or {}
        marks = cap.get("leading_mark") or {}
        intensity = normalize_intensity(str(cue.get("intensity") or "medium"))
        mark = marks.get(intensity) if isinstance(marks, dict) else None
        if mark and not text.lstrip().startswith("…") and not text.lstrip().startswith("..."):
            prefix = mark
            break
    return f"{prefix}{text}".strip() if prefix else text


def build_mannerism_emo_text(cues: list[dict[str, Any]]) -> str:
    """Compose QwenEmotion emo_text fragments for delivery-only mannerisms.

    Discrete vocal-event cues (sigh/chuckle/gasp/...) are NOT pushed into emo_text;
    they are rendered by mannerism_events and stitched into the take.
    """
    parts: list[str] = []
    for cue in cues:
        cue_id = str(cue.get("id") or "")
        cap = _CAPABILITY.get(cue_id) or {}
        if cap.get("mode") == "vocal_event":
            continue  # discrete audible event layer owns these
        emo_map = cap.get("emo_text") or {}
        intensity = normalize_intensity(str(cue.get("intensity") or "medium"))
        fragment = emo_map.get(intensity) if isinstance(emo_map, dict) else None
        if not fragment:
            continue
        position = normalize_position(str(cue.get("position") or "before"))
        if position == "after":
            fragment = fragment.replace("before the line", "after the line").replace(
                "before speaking", "as the line ends"
            )
        elif position == "during":
            fragment = fragment.replace("before the line", "during the line").replace(
                "before speaking", "while speaking"
            )
        parts.append(fragment)
    return "; ".join(parts).strip()


def sanitize_for_tts(
    dialogue_text: str,
    *,
    structured_cues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mandatory pre-synthesis sanitation.

    Returns spokenText (safe for IndexTTS text field), mannerismCues, notices, emoTextSupplement.
    """
    extracted = extract_mannerisms_from_text(dialogue_text or "")
    cues = merge_structured_cues(structured_cues, extracted["mannerismCues"])
    spoken = apply_structural_marks(extracted["spokenText"], cues)
    # Final safety: never allow recognized cue words as lone bracket leftovers
    emo = build_mannerism_emo_text(cues)
    return {
        "spokenText": spoken,
        "mannerismCues": cues,
        "notices": list(extracted["notices"]),
        "emoTextSupplement": emo,
        "originalText": dialogue_text,
    }


def extract_mannerisms_from_direction(text: str) -> list[dict[str, Any]]:
    """Parse Co-Director natural language into structured cues (no technical syntax required)."""
    raw = text or ""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern, cue_id, position in _CD_PATTERNS:
        if pattern.search(raw) and cue_id not in seen:
            seen.add(cue_id)
            found.append(make_cue(cue_id, position=position, intensity="medium", source="codirector"))
    # Also honor any brackets CD might have quoted
    bracketed = extract_mannerisms_from_text(raw)
    return merge_structured_cues(found, bracketed["mannerismCues"])


def vocabulary_snapshot() -> dict[str, Any]:
    return {
        "cues": [
            {
                "id": m["id"],
                "label": m["label"],
                "nativeSupport": bool((_CAPABILITY.get(m["id"]) or {}).get("native")),
                "approximationMode": (_CAPABILITY.get(m["id"]) or {}).get("mode"),
            }
            for m in SUPPORTED_MANNERISMS
        ],
        "positions": ["before", "during", "after"],
        "intensities": ["light", "medium", "strong"],
        "engine": "index-tts2-local dialogue + local vocal-event layer (DSP stitch)",
        "policyUnknownTagShapedBrackets": "strip_from_tts_with_notice",
        "mock": False,
    }
