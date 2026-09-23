"""Universal scene understanding — Layer B extraction from a creator request.

Two paths, one contract:

- LLM path: the project's active Co-Director provider receives a strict
  JSON-only extraction brief. Output is parsed and schema-validated; nothing
  is trusted without validation.
- Deterministic fallback: a universal cinematic extractor built from generic
  film grammar (camera moves, beat cues, reveal phrases, dialogue patterns,
  exclusion language). It contains no franchise- or project-specific tokens.

Both paths return `SceneUnderstanding`. Asset *names* are extracted here;
authoritative resolution/canonical tags stay with `reference_resolver`.
Runtime metadata (generator, seconds, aspect, megapixels, batches) is never
part of the understanding — `intent_parser` owns it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from .instruction_copy import strip_instruction_copy

logger = logging.getLogger(__name__)

LlmFn = Callable[[str, str], str]

BEAT_KINDS = (
    "establish",
    "approach",
    "impact",
    "pause",
    "escalation",
    "reveal",
    "dialogue",
    "reaction",
    "exit",
    "hold",
    "transition",
    "action",
)


class UnderstandingAsset(BaseModel):
    name: str = ""
    hinted_type: str = ""  # character | prop | environment | vehicle | ""


class UnderstandingBeat(BaseModel):
    kind: str = "action"
    description: str = ""
    subjects: list[str] = Field(default_factory=list)
    camera: str = ""
    hold_seconds: Optional[float] = None
    vfx: str = ""


class UnderstandingDialogue(BaseModel):
    speaker: str = ""
    line: str = ""
    delivery: str = ""
    voice_characteristics: str = ""
    filtering: str = ""
    after_beat: Optional[int] = None


class UnderstandingReveal(BaseModel):
    subject: str = ""
    hidden_until: str = ""
    reveal_order: list[str] = Field(default_factory=list)
    condition: str = ""


class UnderstandingCamera(BaseModel):
    shot_type: str = ""
    movement: str = ""
    framing: str = ""
    target: str = ""
    evolution: str = ""


class SceneUnderstanding(BaseModel):
    """Schema-validated Layer B extraction target. All creative, no runtime."""

    scene_type: str = ""
    purpose: str = ""
    mood: str = ""
    environment_name: str = ""
    assets: list[UnderstandingAsset] = Field(default_factory=list)
    beats: list[UnderstandingBeat] = Field(default_factory=list)
    reveals: list[UnderstandingReveal] = Field(default_factory=list)
    dialogue: list[UnderstandingDialogue] = Field(default_factory=list)
    camera: UnderstandingCamera = Field(default_factory=UnderstandingCamera)
    spatial: list[str] = Field(default_factory=list)
    continuity: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    subtitle_policy: str = ""
    opening_state: str = ""
    end_state: str = ""


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the scene-understanding engine inside a film co-director system.
Read the creator's request and output ONLY a JSON object matching this schema:

{
  "scene_type": "short cinematic classification, e.g. establishing | suspense_reveal | dialogue | action | vfx_reveal | multi_beat_cinematic",
  "purpose": "one sentence: what this scene is for dramatically",
  "mood": "mood words from the request",
  "environment_name": "the named setting/place reference, or empty",
  "assets": [{"name": "exact asset name as the creator wrote it", "hinted_type": "character|prop|environment|vehicle"}],
  "beats": [{"kind": "establish|approach|impact|pause|escalation|reveal|dialogue|reaction|exit|hold|transition|action",
             "description": "one on-screen event in cinematic present tense",
             "subjects": ["asset names involved"], "camera": "beat-specific camera note or empty",
             "hold_seconds": null, "vfx": "effect name or empty"}],
  "reveals": [{"subject": "who/what stays hidden", "hidden_until": "the event that ends the hiding",
               "reveal_order": ["staged parts in order, e.g. eyes, silhouette, full body"], "condition": "raw condition"}],
  "dialogue": [{"speaker": "exact speaker name", "line": "the EXACT spoken line, verbatim, never paraphrased",
                "delivery": "delivery style", "voice_characteristics": "voice qualities", "filtering": "audio filtering or empty",
                "after_beat": null}],
  "camera": {"shot_type": "", "movement": "semantic movement, e.g. slow forward dolly", "framing": "",
             "target": "what the camera frames or moves toward", "evolution": "how the camera changes across the scene"},
  "spatial": ["spatial/scale/occlusion/positioning rules"],
  "continuity": ["hard continuity rules from the creator"],
  "exclusions": ["every 'no ...' / 'do not ...' constraint"],
  "subtitle_policy": "none when the creator forbids subtitles/on-screen text, else empty",
  "opening_state": "the scene's opening state",
  "end_state": "the required final state"
}

LAWS:
- Output JSON only. No markdown, no commentary.
- Beats are ordered on-screen events. Preserve the creator's event order exactly.
- Never invent assets, characters, or events the creator did not name or describe.
- "assets" lists ONLY named, reusable reference assets the creator explicitly invokes
  as references: reference-sheet names, @/#/% tags, "X as the setting",
  "Character reference of X". Descriptive scenery, weather, and background
  elements (mountains, fog, water, sky, light) are NEVER assets — they belong
  to beats and mood, not to reference verification.
- Dialogue lines are verbatim. Never paraphrase, never drop.
- Reveal gating ("do not reveal X before Y", "not yet visible", "eyes appear first")
  must appear in reveals, and the beats must respect it.
- Ignore runtime/execution settings (generator names, seconds, aspect ratios,
  megapixels, batch counts). They are handled elsewhere — never put them in beats.
- "exclusions" are on-screen cinematic prohibitions only ("no extra characters",
  "no subtitles", "no costume changes"). NEVER emit meta-instructions about
  runtime settings, generator names, aspect ratios, durations, or batch counts
  as exclusions — those are not cinematic constraints.
- Ignore meta instructions ("build a scene in Timeline", "use this reference sheet").
  Extract only what happens on screen.
- "Image 1" / "Image 2" style tokens are reference bindings, not prompt language.
  Translate them into the named asset they describe when the request names one."""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    blob = (text or "").strip()
    if not blob:
        return None
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob)
        blob = re.sub(r"\s*```$", "", blob)
    start = blob.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(blob)):
        char = blob[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(blob[start : index + 1])
                except Exception:
                    return None
                return data if isinstance(data, dict) else None
    return None


def _sanitize_text(value: str) -> str:
    return strip_instruction_copy(re.sub(r"\s+", " ", (value or "").strip()))


_REF_DECL_RE = re.compile(
    r"\s*\b(?:character|prop|environment|vehicle)\s+reference(?:\s+(?:sheet|package|set))?\b(?:\s+of\s+)?",
    re.I,
)


def _clean_cinematic_field(value: str) -> str:
    """Reference-declaration language ("prop reference sheet", "character
    reference of") is request chrome, not cinematic content. Strip it from
    descriptive fields so it can never leak into prompt sections — the asset
    NAME stays, the reference-operation words go."""
    cleaned = _REF_DECL_RE.sub("", _sanitize_text(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip(" ;,.")


def _sanitize_understanding(data: SceneUnderstanding) -> SceneUnderstanding:
    data.purpose = _sanitize_text(data.purpose)
    data.opening_state = _sanitize_text(data.opening_state)
    data.end_state = _sanitize_text(data.end_state)
    data.mood = _sanitize_text(data.mood)
    data.camera.shot_type = _clean_cinematic_field(data.camera.shot_type)
    data.camera.movement = _clean_cinematic_field(data.camera.movement)
    data.camera.framing = _clean_cinematic_field(data.camera.framing)
    data.camera.target = _clean_cinematic_field(data.camera.target)
    data.camera.evolution = _clean_cinematic_field(data.camera.evolution)
    for beat in data.beats:
        # Beat descriptions are on-screen staging statements: instruction copy
        # is stripped and creator/LLM imperatives become declarative cinematic
        # prose ("Hold for one second" -> "The shot holds for one second").
        beat.description = _cinematicize_beat_sentence(beat.description)
        # A timed hold must verbalize its duration — when the LLM sets
        # hold_seconds but paraphrases the prose without duration language,
        # the compiled prompt would silently lose the staged hold length.
        if beat.hold_seconds and not _HOLD_RE.search(beat.description or ""):
            beat.description = _verbalize_hold_duration(
                beat.description, float(beat.hold_seconds)
            )
        beat.camera = _clean_cinematic_field(beat.camera)
        beat.kind = (beat.kind or "action").strip().lower()
        if beat.kind not in BEAT_KINDS:
            beat.kind = "action"
    data.beats = [beat for beat in data.beats if beat.description]
    for line in data.dialogue:
        line.line = (line.line or "").strip().strip("“”")
        line.delivery = _sanitize_text(line.delivery)
        line.voice_characteristics = _sanitize_text(line.voice_characteristics)
    data.dialogue = [line for line in data.dialogue if line.line]
    for reveal in data.reveals:
        reveal.hidden_until = _sanitize_text(reveal.hidden_until)
        reveal.condition = _sanitize_text(reveal.condition)
    data.reveals = [reveal for reveal in data.reveals if reveal.subject]
    data.spatial = [_sanitize_text(item) for item in data.spatial if _sanitize_text(item)]
    data.continuity = [_sanitize_text(item) for item in data.continuity if _sanitize_text(item)]
    data.exclusions = [_sanitize_text(item) for item in data.exclusions if _sanitize_text(item)]
    if "none" in (data.subtitle_policy or "").lower():
        data.subtitle_policy = "none"
    elif not data.subtitle_policy:
        data.subtitle_policy = ""
    return data


def _dedupe_llm_beats(understanding: SceneUnderstanding) -> SceneUnderstanding:
    """The LLM occasionally stages the same event twice with only a leading
    discourse marker different ("Suddenly, a beam blasts…" + "A beam
    blasts…") — both survive coverage mapping and land in ACTION as a
    duplicate staging (live Scene 3 defect, peer round-7). Dedupe beats whose
    descriptions are identical after normalization; the FIRST occurrence wins
    to preserve intended beat order. LLM-path only: fallback beats map 1:1 to
    source sentences, and _coverage_backfill repetition beats are anchored to
    distinct source events — neither may be merged here."""
    seen: set[str] = set()
    unique: list[UnderstandingBeat] = []
    for beat in understanding.beats:
        key = _LEADING_ADVERB_RE.sub("", beat.description.strip().lower())
        key = re.sub(r"\s+", " ", key).strip(" .")
        if key and key in seen:
            continue
        seen.add(key)
        unique.append(beat)
    understanding.beats = unique
    return understanding


def _understanding_via_llm(message: str, llm_fn: LlmFn) -> SceneUnderstanding:
    raw = llm_fn(_SYSTEM_PROMPT, message)
    data = _extract_json_object(raw)
    if data is None:
        raise ValueError("LLM scene understanding returned no JSON object.")
    understanding = SceneUnderstanding.model_validate(data)
    understanding = _dedupe_llm_beats(_sanitize_understanding(understanding))
    # Dialogue-coverage backstop: "do not lose dialogue during prompt
    # synthesis" applies to the LLM path too. Any quoted line the LLM dropped
    # from its dialogue array is restored by the deterministic extractor
    # (exact line, attributed speaker).
    have = {re.sub(r"\s+", " ", line.line.strip().lower()) for line in understanding.dialogue}
    for line in _dialogue_from_text(message):
        key = re.sub(r"\s+", " ", line.line.strip().lower())
        if key and key not in have:
            understanding.dialogue.append(line)
            have.add(key)
    return understanding


# ---------------------------------------------------------------------------
# Deterministic universal fallback
# ---------------------------------------------------------------------------

_CAMERA_MOVES = (
    ("locked-off", re.compile(r"\blocked[\s-]?off\b|\bstatic\b|\bfixed camera\b", re.I)),
    ("dolly", re.compile(r"\bdoll(?:y|ies|ied)\b", re.I)),
    ("push-in", re.compile(r"\bpush[\s-]?in\b|\bpushes in\b", re.I)),
    ("pull-back", re.compile(r"\bpull[\s-]?back\b|\bpulls back\b|\bdolly out\b", re.I)),
    ("orbit", re.compile(r"\borbit(?:s|ing)?\b", re.I)),
    ("pan", re.compile(r"\bpan(?:s|ning)?\b", re.I)),
    ("tilt", re.compile(r"\btilt(?:s|ing)?\b", re.I)),
    ("crane", re.compile(r"\bcrane(?:s|d|ing)?\b|\bjib\b", re.I)),
    ("tracking", re.compile(r"\btracking\b|\btracks\b|\bfollow(?:s|ing)?\b", re.I)),
    ("handheld", re.compile(r"\bhandheld\b|\bhand[\s-]?held\b", re.I)),
    ("rack focus", re.compile(r"\brack focus\b|\bfocus pull\b", re.I)),
    ("zoom", re.compile(r"\bzoom(?:s|ing)?\b", re.I)),
)
_CAMERA_SPEED_RE = re.compile(r"\b(slow|slowly|gradual|gradually|creeping|ominous|steady|rapid|fast)\b", re.I)
_CAMERA_DIRECTION_RE = re.compile(
    r"\b(forward|toward(?:s)?\s+[^.,;]+|closer|away|backward|up|down|across|through\s+[^.,;]+)", re.I
)
_SHOT_RES = (
    (re.compile(r"\bwide\s+establishing\b|\bestablishing\s+shot\b|\bestablishing\b", re.I), "wide establishing"),
    (re.compile(r"\bextreme\s+close[\s-]?up\b|\becu\b", re.I), "extreme close-up"),
    (re.compile(r"\bclose[\s-]?up\b", re.I), "close-up"),
    (re.compile(r"\bmedium\s+shot\b|\bmedium\b", re.I), "medium"),
    (re.compile(r"\bwide\s+shot\b|\bwide\b", re.I), "wide"),
    (re.compile(r"\bover[\s-]?the[\s-]?shoulder\b|\bots\b", re.I), "over-the-shoulder"),
    (re.compile(r"\baerial\b|\bbird'?s\s+eye\b|\btop[\s-]?down\b", re.I), "aerial"),
    (re.compile(r"\blow\s+angle\b", re.I), "low angle"),
    (re.compile(r"\bhigh\s+angle\b", re.I), "high angle"),
)

_DIALOGUE_NAME_RE = re.compile(
    r"(?P<speaker>[A-Z][A-Za-z'’]*(?:\s+[A-Z][A-Za-z'’]*){0,3})\s*:\s*[\"“](?P<line>[^\"”]+)[\"”]"
)
_SAYS_RE = re.compile(
    r"(?P<speaker>[A-Z][A-Za-z'’]*(?:\s+[A-Z][A-Za-z'’]*){0,3})"
    # Optional action lead-in between speaker and speech verb ("Iris stands
    # by a stall and says: …") — no capitals (a new name), quotes, or
    # sentence ends may intervene.
    r"(?:\s+[^.!?\"“”A-Z]{0,60}?)?\s+"
    r"(?P<verb>(?i:says|said|asks|asked|whispers|whispered|shouts|shouted|replies|replied|"
    r"answers|answered|mutters|muttered|growls|growled|murmurs|murmured|calls out|called out))\b"
    # Delivery may carry a colon/comma ("says: "…"", "says, softly, "…"") —
    # any non-quote span up to the opening quote.
    r"(?P<delivery>[^\"“]*?)[\"“](?P<line>[^\"”]+)[\"”]"
)
# Verb + opening quote of a says-style line — used to split the spoken line
# away from a fused action prefix ("Iris stands by a stall and says: "…"").
_SAYS_VERB_QUOTE_RE = re.compile(
    r"\b(?:says|said|asks|asked|whispers|whispered|shouts|shouted|replies|replied|"
    r"answers|answered|mutters|muttered|growls|growled|murmurs|murmured|calls?\s+out|called\s+out)"
    r"\b[^\"“]*?[\"“]",
    re.I,
)
_NAME_ONLY_RE = re.compile(r"^[A-Z][A-Za-z'’]*(?:\s+[A-Z][A-Za-z'’]*){0,3}\.?$")
_VOICE_RE = re.compile(
    r"\bin\s+(?:a|an)\s+([^.;]*?\bvoice)\b|\bvoice\s+(?:is|sounds?)\s+([^.,;]+)", re.I
)
_SECTION_RE = re.compile(
    r"^\s*(CAMERA|ACTION|MOOD|CONTINUITY|IMPORTANT CONTINUITY|NEGATIVE|EXCLUSIONS?|DIALOGUE|"
    r"ENVIRONMENT|SUBJECTS?|SPATIAL(?:\s+RELATIONSHIPS)?|MOTION|SHOT|VFX|STYLE)\s*:\s*(.*)$",
    re.I,
)
_CAMERA_ONLY_RE = re.compile(
    r"^\s*(?:CAMERA:\s*)?(?:keep|continue|begin|start|hold|maintain)\s+"
    r"(?:with\s+(?:a|an|the)\s+)?(?:the\s+)?"
    r"(?:camera|slow|steady|ominous|forward|dolly|pan|tilt|orbit|crane|tracking)\b",
    re.I,
)
_HOLD_RE = re.compile(
    r"\bhold(?:s|ing)?\s+(?:for\s+)?(\d+(?:\.\d+)?|one|two|three|four|five|a|an)\s*(?:second|sec)",
    re.I,
)
_HOLD_WORDS = {"one": 1.0, "a": 1.0, "an": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0}
_NOT_VISIBLE_RE = re.compile(
    r"(?P<subject>[A-Z][A-Za-z'’]*(?:\s+[A-Z][A-Za-z'’]*){0,3})\s+is\s+NOT\s+yet\s+visible", re.I
)
_DO_NOT_REVEAL_RE = re.compile(
    r"do\s+not\s+(?:reveal|show|introduce)\s+(?P<subject>[A-Z][A-Za-z'’]*(?:\s+[A-Za-z'’]+){0,3}?)\s+"
    r"(?:before|until)\s+(?P<until>[^.,;]+)",
    re.I,
)
_REMAINS_HIDDEN_RE = re.compile(
    r"(?P<subject>[A-Z][A-Za-z'’]*(?:\s+[A-Z][A-Za-z'’]*){0,3})\s+remain(?:s|ing)?\s+"
    r"(?P<state>hidden|offscreen|off[\s-]?screen|unseen|out of frame|obscured)\s+until\s+(?P<until>[^.,;]+)",
    re.I,
)
_VISIBLE_FIRST_RE = re.compile(r"(?P<part>[^.,;]+?)\s+(?:become|becomes|appears?|is seen)\s+(?:visible\s+)?first\b", re.I)
_GRADUAL_REVEAL_RE = re.compile(r"gradually\s+reveal(?:s|ing)?\s+(?P<part>[^.,;]+)", re.I)
_PAUSE_RE = re.compile(r"^(silence|a\s+beat|beat of silence|pause|quiet|stillness)\.?$", re.I)
_IMPACT_CUE_RE = re.compile(
    r"\b(buckl\w+|impact\w*|slam\w*|crash\w*|smash\w*|strike\w*|hit(?:s|ting)?|blast\w*|burst\w*|"
    r"explod\w+|erupt\w*|shatter\w*|rip\w*|tear(?:s|ing)?\s+through)\b",
    re.I,
)
_REVEAL_CUE_RE = re.compile(
    r"\b(reveal\w*|emerg\w*|appear\w*|become\w*\s+visible|steps?\s+through|comes?\s+into\s+view|"
    r"materializ\w+|unveil\w*)\b",
    re.I,
)
_APPROACH_CUE_RE = re.compile(r"\b(approach\w*|advanc\w*|walks?\s+toward|moves?\s+toward|heads?\s+toward|closes?\s+in)\b", re.I)
_EXIT_CUE_RE = re.compile(r"\b(exit\w*|leaves|depart\w*|walks?\s+away|fades?\s+out|disappear\w*)\b", re.I)
_ESCALATION_CUE_RE = re.compile(r"\b(suddenly|abruptly|violently|escalat\w+|intensif\w*|surge\w*)\b", re.I)
_VFX_CUE_RE = re.compile(
    r"\b(portal|smoke|steam|mist|fog|glow\w*|beam\w*|energy|lightning|fire|flames?|sparks?|"
    r"explosion|shockwave|hologram|shield\w*|laser\w*|plasma|ember\w*)\b",
    re.I,
)
_EXCLUSION_RE = re.compile(r"^(?:no|never|do\s+not|don'?t|without)\b[^.!?]*[.!?]?", re.I)
_MOOD_LABEL_RE = re.compile(r"^\s*MOOD\s*:\s*(?P<mood>.+)$", re.I | re.M)
_STYLE_MOOD_RE = re.compile(
    r"\b(menacing|ominous|tense|suspenseful|serene|calm|chaotic|melancholic|hopeful|eerie|"
    r"triumphant|somber|playful|dramatic|mysterious|peaceful|violent|gentle)\b",
    re.I,
)
_SUBTITLE_FORBID_RE = re.compile(r"\bno\s+(?:subtitles|on[\s-]?screen\s+text|captions|text\s+overlays?)\b", re.I)
_META_LINE_RE = re.compile(
    r"^\s*(?:for\s+scene\b|i\s+would\s+like|i'?d\s+like|here\s+is\s+the\s+prompt|"
    r"the\s+scene\s+will\s+be\b|using\s+minimax\b|build\s+(?:this|a|the)\s+scene\b|"
    r"we\s+(?:want|need|would\s+like)\b|the\s+scene\s+is\s+that\s*$)",
    re.I,
)
_WE_SEE_PREFIX_RE = re.compile(
    r"^\s*(?:the\s+scene\s+is\s+that\s+)?we\s+(?:will\s+|would\s+like\s+to\s+|want\s+to\s+)?"
    r"(?:see|have|show)\s+",
    re.I,
)
_MEASUREMENT_RE = re.compile(
    r"^\s*[A-Z][\w'’ .-]{1,60}?\s+(?:is|are|is\s+over|over)\s+(?:over\s+)?"
    r"(?:\d+(?:\.\d+)?|a|an|one)\s*(?:kilometers?|km|meters?|metres?|m|feet|ft)\b",
    re.I,
)
_REF_ONLY_RE = re.compile(
    r"^\s*(?:and\s+)?(?:also\s+)?(?:the\s+)?[\w'’ -]*"
    r"\b(?:prop|character|environment)\s+reference\s+sheet\b[.\s]*$",
    re.I,
)
_RUNTIME_LINE_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*-?\s*seconds?\b|\d{1,2}\s*:\s*\d{1,2}\b|megapixels?\b|\b\d+\s+batches?\b|"
    r"\bminimax\b|\bh3\b|\bltx\b|\bseedance\b|\bframe\s+ratio\b|\bsingle\s+batch\b)",
    re.I,
)


_INLINE_SECTION_SPLIT_RE = re.compile(
    r"(?:^|(?<=[.!?]))\s*"
    r"(CAMERA|ACTION|MOOD|CONTINUITY|IMPORTANT CONTINUITY|NEGATIVE|EXCLUSIONS?|DIALOGUE|"
    r"ENVIRONMENT|SUBJECTS?|SPATIAL(?:\s+RELATIONSHIPS)?|MOTION|SHOT|VFX|STYLE)\s*:\s*"
)


def _split_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    """Split a request into labeled sections. Handles 'LABEL:' headers on their
    own line, inline 'LABEL: content' headers, and UPPERCASE labels embedded
    mid-text after a sentence boundary (single-paragraph creator requests).
    Returns (sections, preamble)."""
    sections: dict[str, list[str]] = {}
    preamble: list[str] = []
    current = ""

    def _emit(line: str) -> None:
        nonlocal current
        line = line.strip()
        if not line:
            return
        marker = _SECTION_RE.match(line)
        if marker:
            current = marker.group(1).upper().replace("IMPORTANT CONTINUITY", "CONTINUITY")
            sections.setdefault(current, [])
            inline = (marker.group(2) or "").strip()
            if inline:
                sections[current].append(inline)
            return
        if current:
            sections.setdefault(current, []).append(line)
        else:
            preamble.append(line)

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Split mid-line UPPERCASE section labels into their own logical lines.
        pieces = _INLINE_SECTION_SPLIT_RE.split(line)
        if len(pieces) > 1:
            # split keeps captured labels: [pre, LABEL, rest, LABEL, rest, ...]
            first = pieces[0].strip()
            if first:
                _emit(first)
            idx = 1
            while idx < len(pieces):
                label = pieces[idx]
                rest = pieces[idx + 1] if idx + 1 < len(pieces) else ""
                _emit(f"{label}: {rest}".strip())
                idx += 2
        else:
            _emit(line)
    return sections, preamble


# A sentence ends at terminal punctuation INCLUDING when a closing quote
# follows it ('…go." She runs.') — otherwise a quoted line fuses with the
# next sentence: the fused sentence then either double-stages the dialogue
# (says-style stays in the event pool) or silently drops the trailing event
# (colon-style is excluded wholesale). Python `re` lookbehinds are
# fixed-width, so tokenize with findall instead of split.
_SENTENCE_RE = re.compile(
    r".+?(?:[.!?]+[\"'”’]+(?=\s|$)|[.!?]+(?=\s|$)|\s*$)", re.S
)


def _sentences(text: str) -> list[str]:
    blob = re.sub(r"\s+", " ", (text or "").strip())
    if not blob:
        return []
    parts = _SENTENCE_RE.findall(blob)
    return [part.strip() for part in parts if part and part.strip()]


def _is_meta_or_runtime(sentence: str) -> bool:
    if _META_LINE_RE.search(sentence):
        return True
    if _RUNTIME_LINE_RE.search(sentence) and not _IMPACT_CUE_RE.search(sentence):
        return True
    if _REF_ONLY_RE.match(sentence):
        return True
    if re.search(r"\b(?:reference\s+sheet|timeline\s+prompt|in\s+timeline\b)", sentence, re.I) and re.search(
        r"\b(?:use|using|create|build|prepare|make)\b", sentence, re.I
    ):
        return True
    return False


def _classify_beat(sentence: str, *, has_dialogue: bool) -> str:
    if _PAUSE_RE.match(sentence.strip()):
        return "pause"
    if has_dialogue:
        return "dialogue"
    if _IMPACT_CUE_RE.search(sentence):
        return "impact"
    if _REVEAL_CUE_RE.search(sentence):
        return "reveal"
    if _EXIT_CUE_RE.search(sentence):
        return "exit"
    if _APPROACH_CUE_RE.search(sentence):
        return "approach"
    if _ESCALATION_CUE_RE.search(sentence):
        return "escalation"
    return "action"


def _camera_from_text(text: str) -> UnderstandingCamera:
    camera = UnderstandingCamera()
    for regex, label in _SHOT_RES:
        if regex.search(text):
            camera.shot_type = label
            camera.framing = "wide" if "wide" in label or "establishing" in label or "aerial" in label else label
            break
    moves: list[str] = []
    for label, regex in _CAMERA_MOVES:
        if regex.search(text):
            moves.append(label)
    speed = _CAMERA_SPEED_RE.search(text)
    direction = _CAMERA_DIRECTION_RE.search(text)
    movement_bits: list[str] = []
    if speed:
        movement_bits.append(speed.group(1).lower())
    if moves:
        movement_bits.append("-".join(moves[:2]) if len(moves) > 1 else moves[0])
    if direction:
        movement_bits.append(direction.group(1).strip())
    camera.movement = " ".join(movement_bits).strip()
    target = re.search(r"\btoward\s+(?:a|an|the)?\s*([^.,;]+)", text, re.I)
    if target:
        camera.target = target.group(1).strip()
    centered = re.search(r"\bkeep\s+the\s+camera\s+centered\s+on\s+(?:a|an|the)?\s*([^.,;]+?)(?:\s+and\s+|\s*$)", text, re.I)
    if centered:
        camera.target = centered.group(1).strip()
    if re.search(r"\bcontinuously\s+move\s+closer\b|\bthroughout\s+the\s+sequence\b", text, re.I):
        camera.evolution = "camera continuously closes distance throughout the sequence"
    return camera


def _dialogue_from_text(text: str) -> list[UnderstandingDialogue]:
    lines: list[UnderstandingDialogue] = []
    seen_lines: set[str] = set()
    for match in _DIALOGUE_NAME_RE.finditer(text):
        speaker = match.group("speaker").strip()
        line = match.group("line").strip()
        key = re.sub(r"\s+", " ", line.lower())
        if not line or key in seen_lines:
            continue
        seen_lines.add(key)
        prefix = text[max(0, match.start() - 220) : match.start()]
        delivery = ""
        voice = _VOICE_RE.search(prefix)
        if voice:
            delivery = (voice.group(1) or voice.group(2) or "").strip()
        lines.append(
            UnderstandingDialogue(
                speaker=speaker,
                line=line,
                delivery=delivery,
                voice_characteristics=delivery,
            )
        )
    for match in _SAYS_RE.finditer(text):
        speaker = match.group("speaker").strip()
        line = match.group("line").strip()
        key = re.sub(r"\s+", " ", line.lower())
        if not line or key in seen_lines:
            continue
        seen_lines.add(key)
        delivery = re.sub(r"\s+", " ", (match.group("delivery") or "")).strip(" ,;:")
        lines.append(UnderstandingDialogue(speaker=speaker, line=line, delivery=delivery))
    return lines


def _reveals_from_text(text: str, dialogue_free: str) -> list[UnderstandingReveal]:
    reveals: list[UnderstandingReveal] = []
    subjects: set[str] = set()

    def _add(subject: str, until: str, condition: str) -> UnderstandingReveal:
        token = subject.strip()
        key = token.lower()
        existing = next((item for item in reveals if item.subject.lower() == key), None)
        if existing is None:
            existing = UnderstandingReveal(subject=token)
            reveals.append(existing)
            subjects.add(key)
        if until and not existing.hidden_until:
            existing.hidden_until = until.strip()
        if condition and not existing.condition:
            existing.condition = condition.strip()
        return existing

    for match in _NOT_VISIBLE_RE.finditer(text):
        _add(match.group("subject"), "", "not yet visible")
    for match in _DO_NOT_REVEAL_RE.finditer(text):
        _add(match.group("subject"), match.group("until"), match.group(0))
    for match in _REMAINS_HIDDEN_RE.finditer(text):
        _add(match.group("subject"), match.group("until"), match.group(0))
    for match in _VISIBLE_FIRST_RE.finditer(dialogue_free):
        part = match.group("part").strip()
        if len(part) < 3 or len(part) > 60:
            continue
        owner = ""
        possessor = re.search(r"([A-Z][A-Za-z'’]*)[’']s\b", part)
        if possessor:
            owner = possessor.group(1)
        target = owner or (reveals[-1].subject if reveals else "")
        if not target:
            continue
        reveal = _add(target, "", "staged reveal")
        cleaned = re.sub(r"^[A-Z][A-Za-z'’]*[’']s\s+", "", part).strip()
        if cleaned and cleaned.lower() not in [item.lower() for item in reveal.reveal_order]:
            reveal.reveal_order.append(cleaned)
    for match in _GRADUAL_REVEAL_RE.finditer(dialogue_free):
        part = match.group("part").strip()
        if not part or len(part) > 60:
            continue
        target = reveals[-1].subject if reveals else ""
        if not target:
            continue
        reveal = _add(target, "", "gradual reveal")
        if part.lower() not in [item.lower() for item in reveal.reveal_order]:
            reveal.reveal_order.append(part)
    return reveals


def _exclusions_from_text(text: str) -> list[str]:
    exclusions: list[str] = []
    for sentence in _sentences(text.replace("\n", ". ")):
        token = sentence.strip()
        if not token:
            continue
        if _EXCLUSION_RE.match(token) or re.match(r"(?i)^[A-Z][A-Za-z'’]*\s+remains?\s+fully\b", token):
            cleaned = token.rstrip(".")
            if cleaned and cleaned.lower() not in {item.lower() for item in exclusions}:
                exclusions.append(cleaned)
    return exclusions


def _continuity_from_text(text: str) -> list[str]:
    rules: list[str] = []
    for sentence in _sentences(text.replace("\n", ". ")):
        token = sentence.strip()
        if re.match(r"(?i)^(maintain|preserve|keep|the\s+first\b.*originate)", token):
            cleaned = token.rstrip(".")
            if cleaned and cleaned.lower() not in {item.lower() for item in rules}:
                rules.append(cleaned)
    return rules


def _salient_event_sentences(text: str) -> tuple[list[str], list[str]]:
    """Ordered on-screen event sentences from a creator request, plus camera
    notes. This is the shared salience filter used by the deterministic
    fallback AND the LLM beat-coverage backstop: meta/runtime, dialogue,
    reveal-gating, exclusion, and pure measurement sentences are not beats."""
    sections, preamble = _split_sections(text)
    action_lines = sections.get("ACTION", []) + sections.get("MOTION", [])
    # Narrative lines parked under CAMERA/SHOT headers still belong to the
    # beat pool; camera-only sentences are folded into the camera plan.
    for stray in sections.get("CAMERA", []) + sections.get("SHOT", []):
        if _CAMERA_ONLY_RE.match(stray) or _is_meta_or_runtime(stray):
            continue
        if _DO_NOT_REVEAL_RE.search(stray) or _EXCLUSION_RE.match(stray.strip()):
            continue
        action_lines.append(stray)
    action_blob = " ".join(action_lines).strip()
    if not action_blob:
        # Salvage story sentences from the preamble per-sentence: a single-line
        # chat message mixes request framing, story beats, and runtime tokens,
        # and one runtime sentence must not poison the whole line.
        body: list[str] = []
        for line in preamble:
            if _is_meta_or_runtime(line):
                body.extend(
                    sentence for sentence in _sentences(line) if not _is_meta_or_runtime(sentence)
                )
            else:
                body.append(line)
        action_blob = " ".join(body)
    events: list[str] = []
    camera_notes: list[str] = []
    for sentence in _sentences(action_blob):
        if _is_meta_or_runtime(sentence):
            continue
        if _DIALOGUE_NAME_RE.search(sentence):
            continue
        says = _SAYS_VERB_QUOTE_RE.search(sentence)
        if says:
            # Says-style dialogue is extracted into `dialogue`, not staged as
            # an on-screen event — otherwise the line is staged twice (beat +
            # dialogue sentence). A fused action prefix ("Iris stands by a
            # stall and says: "…"") survives as its own event; a bare speaker
            # name ("Mara says: "…"") does not.
            residue = sentence[: says.start()].strip()
            residue = re.sub(r"\b(?:and\s+then|and|then)\s*$", "", residue, flags=re.I).strip(" ,;.")
            if residue and not _NAME_ONLY_RE.match(residue):
                events.append(residue + ".")
            continue
        if _DO_NOT_REVEAL_RE.search(sentence) or _EXCLUSION_RE.match(sentence.strip()):
            # Reveal gates / exclusions are captured in their own structures,
            # not staged as on-screen beats.
            continue
        if _NOT_VISIBLE_RE.search(sentence) or _REMAINS_HIDDEN_RE.search(sentence):
            # Visibility gates ("Cade is NOT yet visible", "X remains hidden
            # until Y") live in reveals — never beats, never coverage anchors.
            continue
        if _MEASUREMENT_RE.match(sentence):
            # Pure scale/measurement statements live in SPATIAL RELATIONSHIPS
            # via scale extraction, not in ACTION prose.
            continue
        if _CAMERA_ONLY_RE.match(sentence):
            note = _sanitize_text(sentence).rstrip(".")
            if note and note.lower() not in {item.lower() for item in camera_notes}:
                camera_notes.append(note)
            continue
        events.append(sentence)
    return events, camera_notes


_IMPERATIVE_START_RE = re.compile(
    r"^(hold|linger|stay|continue|keep|maintain|follow|track|pan|tilt|orbit|dolly|"
    r"push|pull|zoom|crane|move|begin|start|end|cut|reveal|show|introduce|unveil)\b",
    re.I,
)


def _third_person(verb: str) -> str:
    word = verb.lower()
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def _cinematicize_beat_sentence(sentence: str) -> str:
    """Deterministic Layer A → Layer B transform. Creator imperatives and
    instruction grammar become declarative on-screen staging statements with
    an explicit cinematic subject; already-declarative event prose is
    preserved. Meta/instruction copy is stripped before staging."""
    cleaned = _sanitize_text(sentence)
    # Normalize creator framing ("we will see X" / "the scene is that we
    # see X") into on-screen staging language ("X").
    cleaned = _WE_SEE_PREFIX_RE.sub("", cleaned).strip()
    if not cleaned:
        return ""
    match = _IMPERATIVE_START_RE.match(cleaned)
    if match:
        verb = match.group(1).lower()
        rest = cleaned[match.end() :].strip()
        if verb in {"hold", "linger", "stay", "reveal", "show", "introduce", "unveil"}:
            subject = "The shot"
        else:
            subject = "The camera"
        cleaned = f"{subject} {_third_person(verb)} {rest}".strip()
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


_HOLD_DURATION_WORDS = {
    1.0: "one", 2.0: "two", 3.0: "three", 4.0: "four", 5.0: "five",
    6.0: "six", 7.0: "seven", 8.0: "eight", 9.0: "nine", 10.0: "ten",
}


def _hold_duration_phrase(seconds: float) -> str:
    whole = float(seconds)
    word = _HOLD_DURATION_WORDS.get(whole)
    if word:
        return f"{word} {'second' if whole == 1.0 else 'seconds'}"
    return f"{whole:g} seconds"


def _verbalize_hold_duration(description: str, hold_seconds: float) -> str:
    """A beat that carries a timed hold must SAY the duration. The compiled
    prompt is the contract with the generator — "the scene holds on the door"
    silently loses the staged one-second beat the creator asked for."""
    phrase = _hold_duration_phrase(hold_seconds)
    match = re.search(r"\bhold(?:s|ing)?\b", description or "", re.I)
    if match:
        return (
            description[: match.end()] + f" for {phrase}" + description[match.end() :]
        ).strip()
    suffix = f"The shot holds for {phrase}."
    base = (description or "").strip()
    return f"{base} {suffix}".strip() if base else suffix


def _beat_from_sentence(sentence: str) -> UnderstandingBeat | None:
    description = _cinematicize_beat_sentence(sentence)
    if not description:
        return None
    has_dialogue_cue = bool(re.search(r"\b(?:says|said|asks|whispers)\b", sentence, re.I))
    kind = _classify_beat(sentence, has_dialogue=has_dialogue_cue)
    beat = UnderstandingBeat(kind=kind, description=description)
    hold = _HOLD_RE.search(sentence)
    if hold:
        token = hold.group(1).lower()
        beat.hold_seconds = _HOLD_WORDS.get(token) if not token[0].isdigit() else float(token)
        if kind == "action":
            beat.kind = "hold"
    vfx = _VFX_CUE_RE.search(sentence)
    if vfx:
        beat.vfx = vfx.group(1).lower()
    cam = _camera_from_text(sentence)
    if cam.movement:
        beat.camera = cam.movement
    return beat


_GENERIC_BEAT_WORDS = frozenset(
    {
        "scene", "shot", "camera", "slowly", "slow", "toward", "towards", "frame",
        "begins", "begin", "starts", "start", "continues", "continue", "then",
        "with", "from", "into", "through", "across", "this", "that", "there",
        "their", "they", "them", "his", "her", "its", "the", "and", "but",
        # Sequence/ordinal words describe ordering, not content — "a second
        # impact" must not count as covering "hold for one second".
        "first", "second", "third", "fourth", "fifth", "another", "again",
        "next", "final", "finally", "last",
    }
)


def _content_words(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z]+", (text or "").lower())
        if len(word) >= 4 and word not in _GENERIC_BEAT_WORDS
    ]


def _beat_coverage(sentence: str, beats: list[UnderstandingBeat]) -> tuple[int | None, float]:
    """Best-matching beat index + coverage score for a salient source sentence.

    Covered means: >= 50% of the sentence's content words appear in the beat,
    or >= 2 distinctive (len>=5, non-generic) shared words — paraphrase-
    tolerant so a genuinely rewritten LLM beat still counts as coverage.

    Class-aware: a timed hold ("Hold for one second") is only realized by a
    genuine hold beat (hold_seconds set or hold-duration language) — a beat
    that merely mentions "holding" the camera does not cover it.
    """
    words = _content_words(sentence)
    if not words:
        return (0, 1.0) if beats else (None, 0.0)
    hold_source = bool(_HOLD_RE.search(sentence))
    best_index: int | None = None
    best_score = 0.0
    best_distinctive = 0
    for index, beat in enumerate(beats):
        if hold_source and not (
            beat.hold_seconds or _HOLD_RE.search(beat.description or "")
        ):
            continue
        blob = (beat.description or "").lower()
        hits = sum(1 for word in words if word in blob)
        distinctive = sum(1 for word in words if len(word) >= 5 and word in blob)
        score = hits / len(words)
        if score > best_score:
            best_index, best_score, best_distinctive = index, score, distinctive
    if best_index is not None and (best_score >= 0.5 or best_distinctive >= 2):
        return best_index, best_score
    return None, best_score


_EVENT_CLASS_RES = (
    ("impact", _IMPACT_CUE_RE),
    ("hold", _HOLD_RE),
    ("pause", _PAUSE_RE),
    ("reveal", _REVEAL_CUE_RE),
    ("approach", _APPROACH_CUE_RE),
    ("exit", _EXIT_CUE_RE),
    ("escalation", _ESCALATION_CUE_RE),
)

# A single beat may realize several same-staging source events only when it
# explicitly stages the repetition ("two impacts", "twice", "both"). Bare
# ordinals ("second", "another", "again") mark WHICH event a beat stages —
# they do not signal merged coverage of the others. Multiplicity is
# count-aware: "buckles twice" stages exactly two stagings, so a third
# source impact must still be backfilled.
_MULTIPLICITY_COUNTS = {
    "two": 2,
    "twice": 2,
    "both": 2,
    "couple": 2,
    "three": 3,
    "thrice": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}
_MULTIPLICITY_FINITE_RE = re.compile(
    r"\b(" + "|".join(_MULTIPLICITY_COUNTS) + r")\b", re.I
)
# Unbounded repetition language ("repeatedly", "several") stages the event
# class as a whole — any number of source stagings may share the beat.
_MULTIPLICITY_UNBOUNDED_RE = re.compile(
    r"\b(?:multiple|several|repeated|repeatedly|each|every)\b|"
    r"\b(?:again and again|over and over)\b",
    re.I,
)


def _stem5(word: str) -> str:
    """Crude inflection stem: coverage matching is substring-based ("impact"
    matches "impacts"), so the repetition pass must compare the same way —
    exact-token matching lets a merged beat ("Two impacts buckle and
    shatter…") fail containment for every event it legitimately covers."""
    return word[:5] if len(word) >= 5 else word


def _stem_set(words) -> set[str]:
    return {_stem5(word) for word in words}


def _assign_multiplicity_capacities(blob: str, shared_list: list[set[str]]) -> list[int | None]:
    """Staging capacities a beat claims via multiplicity language, one per
    event cluster.

    Multiplicity is action-scoped: "the door buckles while Mara raises her
    hand twice" claims two RAISES, not two buckles. Each count/unbounded word
    is assigned to the cluster whose shared vocabulary sits NEAREST to it
    (ties assign to all tied clusters — "two impacts buckle and shatter…"
    legitimately claims both impact events). None = unbounded ("repeatedly");
    0 = no multiplicity claimed for that cluster; otherwise the finite count.
    """
    capacities: list[int | None] = [0] * len(shared_list)
    if not any(shared_list):
        return capacities
    tokens = re.findall(r"[a-z]+", blob)
    stems = [_stem5(token) for token in tokens]
    shared_stems = [_stem_set(shared) for shared in shared_list]
    for regex, unbounded in (
        (_MULTIPLICITY_UNBOUNDED_RE, True),
        (_MULTIPLICITY_FINITE_RE, False),
    ):
        for match in regex.finditer(blob):
            position = len(re.findall(r"[a-z]+", blob[: match.start()]))
            best_distance: int | None = None
            for index, stems_for_cluster in enumerate(shared_stems):
                distances = [
                    abs(token_index - position)
                    for token_index, stem in enumerate(stems)
                    if stem in stems_for_cluster
                ]
                if not distances:
                    continue
                nearest = min(distances)
                if best_distance is None or nearest < best_distance:
                    best_distance = nearest
            if best_distance is None:
                continue
            value = None if unbounded else _MULTIPLICITY_COUNTS[match.group(1).lower()]
            for index, stems_for_cluster in enumerate(shared_stems):
                distances = [
                    abs(token_index - position)
                    for token_index, stem in enumerate(stems)
                    if stem in stems_for_cluster
                ]
                if distances and min(distances) == best_distance:
                    capacities[index] = value
    return capacities


# An explicit source duration ("hold for one second") is hard continuity.
_DURATION_SOURCE_RE = re.compile(
    r"\bfor\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"\d+(?:\.\d+)?)\s*(second|seconds|moment|moments|beat|beats)\b",
    re.I,
)
_COUNT_EQUIVALENTS = {
    "a": "1",
    "an": "1",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def _duration_realized(source_sentence: str, beat_text: str) -> bool:
    """True when the covering beat preserves the source event's explicit
    duration. A beat that keeps the event but weakens the duration to a vague
    "a brief hold" silently drops the staged timing (live Scene 3 defect:
    "hold for one second" lost). Accepts equivalent phrasings — "a second" ~
    "one second" ~ "1 second", hyphenated "one-second". "a"/"an" require a
    "for"/hyphen context so the ordinal "a second brutal impact" does not
    masquerade as a duration."""
    match = _DURATION_SOURCE_RE.search(source_sentence or "")
    if not match:
        return True
    count = _COUNT_EQUIVALENTS.get(match.group(1).lower(), match.group(1).lower())
    unit = match.group(2).lower().rstrip("s")
    beat = (beat_text or "").lower()
    equivalents = [word for word, digit in _COUNT_EQUIVALENTS.items() if digit == count]
    if count not in equivalents:
        equivalents.append(count)
    for word in equivalents:
        if word in ("a", "an"):
            pattern = (
                r"\bfor\s+" + word + r"\s+" + unit + r"s?\b|"
                r"\b" + word + r"\s*-\s*" + unit + r"s?\b"
            )
        else:
            pattern = r"\b" + re.escape(word) + r"\s*-?\s*" + unit + r"s?\b"
        if re.search(pattern, beat):
            return True
    return False

# Trailing participial consequence clauses (", sending a wave across the
# arcade") stage their own on-screen event. The gerund maps to the finite
# third-person form used when the clause is re-staged as its own beat.
_CONSEQUENCE_GERUNDS = {
    "sending": "sends",
    "causing": "causes",
    "creating": "creates",
    "leaving": "leaves",
    "triggering": "triggers",
    "sparking": "sparks",
    "igniting": "ignites",
    "knocking": "knocks",
    "blowing": "blows",
    "forcing": "forces",
    "hurling": "hurls",
    "throwing": "throws",
    "setting off": "sets off",
}
_CONSEQUENCE_RE = re.compile(
    r",\s*(?:and\s+)?(?:[a-z]+ly\s+)?("
    + "|".join(re.escape(g) for g in _CONSEQUENCE_GERUNDS)
    + r")\s+([^.;]+?)\s*\.?\s*$",
    re.I,
)


def _consequence_clauses(sentence: str) -> list[tuple[str, str]]:
    """Trailing consequence clauses of a salient event sentence."""
    match = _CONSEQUENCE_RE.search(sentence or "")
    if not match:
        return []
    return [(match.group(1).lower(), match.group(2).strip())]


# Near-synonym groups for the consequence realization check: an LLM beat
# that preserves the consequence under a paraphrase ("huge jagged opening"
# for "large jagged hole") realizes it; only genuinely dropped content
# re-stages. Groups are symmetric — matching works in both directions.
_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"large", "big", "huge", "massive", "enormous", "giant"}),
    frozenset({"small", "tiny", "little"}),
    frozenset({"hole", "opening", "breach", "gap"}),
    frozenset({"wave", "surge", "shockwave", "ripple"}),
    frozenset({"fire", "flames", "blaze"}),
    frozenset({"smoke", "haze", "mist", "fog"}),
    frozenset({"door", "hatch", "gate"}),
    frozenset({"light", "glow", "flare", "flash"}),
    frozenset({"water", "flood", "floodwater"}),
    frozenset({"debris", "fragments", "rubble", "wreckage"}),
    frozenset({"sparks", "embers"}),
)


# Antonym pairs: a beat that states the OPPOSITE of a clause word does not
# realize it, no matter how many other words match — "massive smooth breach"
# must not count as realizing "large jagged hole" (2/3 of the words match
# via synonyms, but "smooth" contradicts "jagged").
_ANTONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"jagged", "smooth"}),
    frozenset({"hot", "cold", "freezing"}),
    frozenset({"open", "opened", "closed", "shut"}),
    frozenset({"bright", "dim", "dark"}),
    frozenset({"fast", "slow", "slowly", "quickly"}),
    frozenset({"loud", "loudly", "quiet", "quietly", "silent"}),
    frozenset({"rising", "falling", "sinking"}),
    frozenset({"intact", "broken", "destroyed", "shattered"}),
    frozenset({"full", "empty"}),
    frozenset({"visible", "invisible", "hidden"}),
)


def _word_realized(word: str, blob_words: set[str]) -> bool:
    if word in blob_words:
        return True
    return any(word in group and bool(group & blob_words) for group in _SYNONYM_GROUPS)


def _word_contradicted(word: str, blob_words: set[str]) -> bool:
    """The beat states an antonym of the word without stating the word."""
    if word in blob_words:
        return False
    return any(
        word in group and bool((group - {word}) & blob_words) for group in _ANTONYM_GROUPS
    )


def _clause_realized(clause_words: set[str], description: str) -> bool:
    """A consequence clause is realized when its distinctive content — or a
    close paraphrase of it — appears in some beat's prose. A beat that
    contradicts an unrealized clause word (antonym present, word absent)
    never realizes the clause."""
    if not clause_words:
        return True
    blob_words = set(re.findall(r"[a-z]+", (description or "").lower()))
    if any(_word_contradicted(word, blob_words) for word in clause_words):
        return False
    hits = sum(1 for word in clause_words if _word_realized(word, blob_words))
    return hits == len(clause_words) or hits / len(clause_words) >= 2 / 3


_LEADING_ADVERB_RE = re.compile(
    r"^\s*(?:suddenly|slowly|then|next|finally|meanwhile|afterwards?|"
    r"gradually|abruptly|quietly|quickly|immediately|instantly)\s*,?\s*",
    re.I,
)

# Leading prepositional/subordinate openers ("Without warning, …", "As the
# alarm sounds, …") are not part of the main-clause subject.
_LEADING_PP_RE = re.compile(
    r"^\s*(?:without|with|after|before|during|at|in|on|from|as|once|when|"
    r"while|although|though|if|because|since|until|unless|despite)\s+[^,;]+,\s*",
    re.I,
)

# A comma segment starting like this marks an appositive / reduced relative /
# participle phrase ("The tower, standing 12 meters tall, …", "The door,
# which bursts open, …", "Mara, determined, …") — the subject precedes it.
_APPOSITIVE_START_RE = re.compile(r"^(?:which|who|whose|where)\b|\w+(?:ed|ing)\b", re.I)

# Bare-stem cinematic verbs. A following bare stem disambiguates a plural
# -s noun from a 3rd-person verb: in "The twin towers groan", "towers" only
# looks like a verb until "groan" appears.
_VERB_STEMS = frozenset(
    {
        "groan", "tip", "topple", "fall", "collapse", "buckle", "snap", "tear",
        "rip", "shatter", "explode", "erupt", "burst", "crash", "slam", "smash",
        "strike", "hit", "blast", "blow", "break", "open", "close", "run",
        "walk", "move", "turn", "stop", "go", "come", "stand", "rise", "shake",
        "tremble", "spin", "roll", "slide", "step", "cross", "enter", "exit",
        "leave", "reach", "grab", "hold", "push", "pull", "lift", "drop",
        "throw", "send", "surge", "swell", "fade", "glow", "flash", "spark",
        "burn", "flood", "fill", "drain", "hum", "roar", "scream", "whisper",
        "emerge", "appear", "vanish", "begin", "start", "remain", "stay",
        "look", "stare", "nod", "kneel", "crouch", "lean", "climb", "descend",
        "ascend", "approach", "advance", "retreat", "charge", "lunge", "sit",
    }
)

_FINITE_VERB_RE = re.compile(
    r"^(?:is|are|was|were|has|have|had|does|do|did|goes|went|came|comes|"
    r"takes?|took|makes?|made|gets?|got|seems?|seemed|becomes?|became|"
    r"remains?|remained|begins?|began|starts?|started|continues?|continued|"
    r"keeps?|kept|holds?|held|stands?|stood|falls?|fell|sits?|sat|runs?|ran)$",
    re.I,
)


# Tokens that may follow a finite verb. An -ed/-ing word followed by one of
# these (or by nothing) is verbal ("blasted through", "standing over"); one
# followed by another content word is a participial adjective inside the
# subject noun phrase ("a CONCENTRATED red beam", "the BATTERED door").
_VERB_FOLLOWERS = frozenset(
    {
        "through", "from", "into", "across", "toward", "towards", "over",
        "under", "behind", "before", "after", "with", "without", "around",
        "down", "up", "off", "on", "out", "back", "away", "aside", "in", "at",
        "to", "for", "against", "along", "past", "inside", "outside", "open",
        "forward", "forwards", "backwards", "sideways", "apart", "together",
        "slowly", "quickly", "suddenly", "again", "then", "now", "first",
        "next", "the", "a", "an", "his", "her", "its", "their", "this", "that",
        "shut", "closed",
    }
)


def _main_verb_index(words: list[str]) -> int | None:
    """Index of the main-clause finite verb among the leading tokens."""
    cleaned = [w.lower().strip(",;'’\"-") for w in words]
    for i, w in enumerate(cleaned):
        if not w or any(ch.isdigit() for ch in w):
            continue
        nxt = cleaned[i + 1] if i + 1 < len(cleaned) else ""
        if _FINITE_VERB_RE.match(w):
            return i
        if w in _VERB_STEMS:
            # A stem followed by "of" is a noun ("a flash of light").
            if nxt == "of":
                continue
            return i
        if (w.endswith("ed") or w.endswith("ing")) and (
            not nxt or nxt in _VERB_FOLLOWERS or nxt.endswith("ly")
        ):
            return i
        if (
            w.endswith("s")
            and not w.endswith(("ss", "us", "ous", "is"))
            and len(w) > 3
        ):
            # 3rd-person verb OR plural/mass noun: any later verbal token
            # (stem, finite, -ed, -ing) means this token is the subject
            # ("the twin towers groan", "the battered doors slammed shut").
            later = cleaned[i + 1 :]
            if not any(
                x in _VERB_STEMS
                or bool(_FINITE_VERB_RE.match(x))
                or x.endswith("ed")
                or x.endswith("ing")
                for x in later
            ):
                return i
    return None


def _main_subject(sentence: str) -> str:
    """Leading noun phrase of the main clause (for re-staging a dropped
    consequence with its actor: "The winch tower groans…, sending a wave…"
    -> "The winch tower sends a wave…")."""
    head = _CONSEQUENCE_RE.sub("", sentence or "").strip()
    head = _LEADING_ADVERB_RE.sub("", head)
    head = _LEADING_PP_RE.sub("", head)
    if "," in head:
        # Appositive / reduced relative / participle phrase ("The tower,
        # standing 12 meters tall, groans…", "The door, which bursts open,
        # …"): when the pre-comma segment is a verbless noun phrase and the
        # post-comma segment opens like a participle/relative, the subject
        # precedes the comma.
        before, after = head.split(",", 1)
        before_words = before.split()
        if (
            0 < len(before_words) <= 8
            and _main_verb_index(before_words) is None
            and _APPOSITIVE_START_RE.match(after.strip())
        ):
            return before.strip()
    words = head.split()
    index = _main_verb_index(words)
    if index is None and "," in head:
        # Fallback: the subject precedes the first comma.
        words = head.split(",", 1)[0].split()
        index = _main_verb_index(words)
        if index is None:
            index = len(words)
    if index is None:
        return ""
    subject = " ".join(words[:index]).strip(" ,")
    if not subject or len(subject.split()) > 8:
        return ""
    return subject


def _coverage_backfill(understanding: SceneUnderstanding, message: str) -> SceneUnderstanding:
    """Beat-coverage guarantee: no salient on-screen event may be silently
    dropped between Layer A and Layer B, whichever extraction path ran.

    Two checks:
    1. Coverage — every salient event sentence must be realized by some beat
       (paraphrase-tolerant match).
    2. Event-class cardinality — when the source stages N events of a class
       (two impacts, a hold, …), the beats must stage at least N. Token
       overlap alone cannot tell "the first impact" from "the second impact"
       because the sentences share vocabulary; cardinality can.
    Missing events are re-staged from the source sentence at their
    source-ordered position among the covered beats.
    """
    events, _notes = _salient_event_sentences(message)
    beats = list(understanding.beats)
    if not events:
        return understanding
    if not beats:
        # Total beat omission: the LLM returned scene metadata but no beats.
        # Stage every salient on-screen event from the source rather than
        # compiling an empty ACTION.
        staged = [
            beat
            for beat in (_beat_from_sentence(event) for event in events)
            if beat is not None
        ]
        if staged:
            understanding.beats = staged
            if not understanding.opening_state:
                understanding.opening_state = staged[0].description
            if not understanding.end_state:
                understanding.end_state = staged[-1].description
        return understanding

    coverage: list[int | None] = [None] * len(events)
    scores: list[float] = [0.0] * len(events)
    for index, sentence in enumerate(events):
        coverage[index], scores[index] = _beat_coverage(sentence, beats)

    for _name, regex in _EVENT_CLASS_RES:
        source_idx = [i for i, sentence in enumerate(events) if regex.search(sentence)]
        # Cardinality is measured in COVERED source events, not beats: one
        # merged beat can realize several source events of the same class.
        covered_count = sum(1 for i in source_idx if coverage[i] is not None)
        missing = len(source_idx) - covered_count
        if missing <= 0:
            continue
        # Uncover the least-covered source sentences of this class — the ones
        # most likely absorbed by a similar sibling event ("second impact"
        # covering "first impact").
        pool = sorted(source_idx, key=lambda i: scores[i])
        for i in pool[:missing]:
            coverage[i] = None

    # Repetition cardinality: near-duplicate events ("the door buckles" …
    # "the door buckles again") may not share ONE beat beyond the number of
    # stagings that beat actually describes — otherwise the extra stagings
    # are silently dropped. This applies to ANY repeated on-screen event,
    # not just the cinematic classes above. A beat's staging capacity is its
    # explicit multiplicity count ("two impacts", "twice") or, failing that,
    # the number of times the cluster's shared vocabulary is staged in its
    # prose ("buckles … then buckles …" stages two). Genuinely distinct
    # events with disjoint vocabularies (a beam blast + bursting fragments)
    # may legitimately share a merged beat.
    by_beat: dict[int, list[int]] = {}
    for i in range(len(events)):
        if coverage[i] is not None:
            by_beat.setdefault(coverage[i], []).append(i)
    for beat_index, group in by_beat.items():
        if len(group) <= 1:
            continue
        blob = (beats[beat_index].description or "").lower()
        blob_words = set(re.findall(r"[a-z]+", blob))
        distinctive = {
            i: {word for word in _content_words(events[i]) if len(word) >= 5}
            for i in group
        }
        # Event signature: distinctive vocabulary when present, else the full
        # content vocabulary (short-worded events like "She runs").
        signature = {i: (distinctive[i] or set(_content_words(events[i]))) for i in group}
        # Cluster mutually indistinguishable events (equal/subset signatures):
        # each cluster is ONE repeated staging. Disjoint signatures are
        # distinct events legitimately sharing the beat.
        ordered = sorted(group, key=lambda i: scores[i], reverse=True)
        clusters: list[list[int]] = []
        for i in ordered:
            for cluster in clusters:
                head = signature[cluster[0]]
                if (not signature[i] and not head) or (
                    signature[i] and head and (signature[i] <= head or head <= signature[i])
                ):
                    cluster.append(i)
                    break
            else:
                clusters.append([i])
        # Multiplicity capacities are assigned across ALL clusters of this
        # beat at once: each count word belongs to the cluster whose shared
        # vocabulary sits nearest to it (action-scoped).
        capacities = _assign_multiplicity_capacities(
            blob, [set.intersection(*(signature[i] for i in cluster)) for cluster in clusters]
        )
        blob_stems = _stem_set(blob_words)
        blob_token_stems = [_stem5(token) for token in re.findall(r"[a-z]+", blob)]
        for cluster, capacity in zip(clusters, capacities):
            if capacity is None:
                continue  # unbounded repetition scoped to this cluster
            # Flavor words ("harder") are not a third event when the beat
            # already claims the cluster via explicit multiplicity
            # ("buckles twice" covers "buckles" + "buckles again, harder").
            # Containment only runs when NO count is claimed — otherwise a
            # merged "twice" beat is split back into a duplicate staging.
            if capacity == 0:
                for i in cluster:
                    if distinctive[i] and not _stem_set(distinctive[i]) <= blob_stems:
                        coverage[i] = None
                cluster = [i for i in cluster if coverage[i] is not None]
            if len(cluster) <= 1:
                continue
            shared = set.intersection(*(signature[i] for i in cluster))
            if capacity == 0:
                # No claimed multiplicity: derive capacity from how often the
                # cluster's shared vocabulary is staged in the beat prose
                # ("buckles … then buckles …" stages two).
                cap = max(
                    (blob_token_stems.count(_stem5(word)) for word in shared),
                    default=0,
                )
                cap = max(cap, 1)
            else:
                cap = capacity
            if len(cluster) <= cap:
                continue
            # Over capacity: keep the best-realized stagings covered and
            # uncover the rest for backfill — preferring members whose
            # distinguishing detail is missing from the beat, then the
            # lowest-scored, then the LATER staging (the first staging of a
            # repetition stays canonical).
            def _drop_priority(i: int) -> tuple[int, float, int]:
                missing_detail = bool(distinctive[i]) and not _stem_set(distinctive[i]) <= blob_stems
                return (0 if missing_detail else 1, scores[i], -i)

            for i in sorted(cluster, key=_drop_priority)[: len(cluster) - cap]:
                coverage[i] = None

    # Explicit-duration preservation: a staged duration ("hold for one
    # second") is hard continuity. A covering beat that kept the event but
    # dropped/weakened the duration ("a brief hold") silently loses the
    # timing — uncover the event so the backfill re-stages it verbatim. A
    # covering beat that states a DIFFERENT duration ("for two seconds") is
    # aligned in place instead — re-staging alongside it would hand the
    # generator two contradictory timings.
    for i, sentence in enumerate(events):
        if coverage[i] is None:
            continue
        source_duration = _DURATION_SOURCE_RE.search(sentence)
        if not source_duration:
            continue
        beat = beats[coverage[i]]
        beat_text = beat.description or ""
        if _duration_realized(sentence, beat_text):
            continue
        if _DURATION_SOURCE_RE.search(beat_text):
            beat.description = _DURATION_SOURCE_RE.sub(
                source_duration.group(0), beat_text, count=1
            )
            staged = _beat_from_sentence(sentence)
            if staged is not None and staged.hold_seconds is not None:
                beat.hold_seconds = staged.hold_seconds
            continue
        coverage[i] = None

    # Consequence-clause coverage: a trailing participial result clause
    # (", sending a wave across the arcade") stages its own on-screen event.
    # If no beat realizes the clause's distinctive content, re-stage ONLY the
    # consequence with its actor, directly after the beat covering its parent
    # sentence — never the whole parent sentence, which would duplicate the
    # already-staged cause.
    consequence_inserts: dict[int, list[UnderstandingBeat]] = {}
    for i, sentence in enumerate(events):
        if coverage[i] is None:
            continue  # whole-sentence drop: the event backfill carries the clause
        for gerund, rest in _consequence_clauses(sentence):
            clause_words = set(_content_words(rest))
            if not clause_words:
                continue
            if any(_clause_realized(clause_words, beat.description or "") for beat in beats):
                continue
            subject = _main_subject(sentence) or _main_subject(
                beats[coverage[i]].description or ""
            )
            if not subject:
                continue  # no recoverable actor — do not fabricate one
            subject = subject[0].upper() + subject[1:]
            beat = _beat_from_sentence(f"{subject} {_CONSEQUENCE_GERUNDS[gerund]} {rest}")
            if beat is not None:
                consequence_inserts.setdefault(coverage[i] + 1, []).append(beat)

    missing_events = [i for i in range(len(events)) if coverage[i] is None]
    if not missing_events and not consequence_inserts:
        return understanding

    # Anchor each missing event among the covered beats by source order.
    inserts_before: dict[int, list[UnderstandingBeat]] = {}
    tail: list[UnderstandingBeat] = []
    for i in missing_events:
        beat = _beat_from_sentence(events[i])
        if beat is None:
            continue
        anchor: int | None = None
        for j in range(i + 1, len(events)):
            if coverage[j] is not None:
                anchor = coverage[j]
                break
        if anchor is None:
            for j in range(i - 1, -1, -1):
                if coverage[j] is not None:
                    anchor = coverage[j] + 1
                    break
        if anchor is None or anchor >= len(beats):
            tail.append(beat)
        else:
            inserts_before.setdefault(anchor, []).append(beat)
    for anchor, extra in consequence_inserts.items():
        inserts_before.setdefault(anchor, []).extend(extra)

    merged: list[UnderstandingBeat] = []
    for index, beat in enumerate(beats):
        merged.extend(inserts_before.get(index, []))
        merged.append(beat)
    # Consequences of the final beat anchor past the end of the beat list.
    merged.extend(inserts_before.get(len(beats), []))
    merged.extend(tail)
    understanding.beats = merged
    # Boundary summaries track the (possibly re-ordered) beats only when the
    # extraction path did not curate them itself.
    if not understanding.opening_state:
        understanding.opening_state = merged[0].description
    if not understanding.end_state:
        understanding.end_state = merged[-1].description
    return understanding


def _fallback_understanding(message: str) -> SceneUnderstanding:
    text = message or ""
    sections, preamble = _split_sections(text)
    understanding = SceneUnderstanding()

    camera_blob = " ".join(
        sections.get("CAMERA", [])
        + sections.get("SHOT", [])
        + sections.get("ACTION", [])
        + preamble
    )
    understanding.camera = _camera_from_text(camera_blob)

    mood_blob = " ".join(sections.get("MOOD", []))
    mood_match = _MOOD_LABEL_RE.search(text)
    if mood_match:
        mood_blob = f"{mood_blob} {mood_match.group('mood')}".strip()
    if mood_blob:
        # Keep the mood statement itself, not the follow-on sentence.
        mood_blob = re.split(r"(?<=[.!?])\s+", mood_blob, maxsplit=1)[0]
    if not mood_blob:
        mood_hits = {m.group(1).lower() for m in _STYLE_MOOD_RE.finditer(text)}
        mood_blob = ", ".join(sorted(mood_hits))
    understanding.mood = re.sub(r"\s+", " ", mood_blob).strip(" .")

    dialogue = _dialogue_from_text(text)
    understanding.dialogue = dialogue
    dialogue_free = _DIALOGUE_NAME_RE.sub(" ", text)
    dialogue_free = _SAYS_RE.sub(" ", dialogue_free)

    understanding.reveals = _reveals_from_text(text, dialogue_free)

    continuity_blob = " ".join(sections.get("CONTINUITY", []) + sections.get("NEGATIVE", []) + sections.get("EXCLUSIONS", []))
    understanding.exclusions = _exclusions_from_text(continuity_blob or text)
    understanding.continuity = _continuity_from_text(continuity_blob)
    if _SUBTITLE_FORBID_RE.search(text):
        understanding.subtitle_policy = "none"

    events, camera_notes = _salient_event_sentences(text)
    beats: list[UnderstandingBeat] = []
    for sentence in events:
        beat = _beat_from_sentence(sentence)
        if beat is not None:
            beats.append(beat)
    if camera_notes and not understanding.camera.evolution:
        understanding.camera.evolution = "; ".join(camera_notes[:3])
    understanding.beats = beats

    if beats:
        first = beats[0]
        if first.kind in {"action", "establish"}:
            first.kind = "establish" if not understanding.reveals and not any(b.kind == "impact" for b in beats) else first.kind
        understanding.opening_state = beats[0].description
        understanding.end_state = beats[-1].description

    if dialogue:
        understanding.scene_type = "dialogue"
    if understanding.reveals and any(b.vfx for b in beats):
        understanding.scene_type = "vfx_reveal"
    elif understanding.reveals:
        understanding.scene_type = "suspense_reveal"
    elif re.search(r"\bestablishing\s+(?:shot|scene)\b", text, re.I) and len(beats) <= 4:
        understanding.scene_type = "establishing"
    elif len(beats) >= 6:
        understanding.scene_type = "multi_beat_cinematic"
    elif not dialogue and beats and not understanding.scene_type:
        understanding.scene_type = "establishing" if len(beats) <= 2 else "action"
    if not understanding.scene_type:
        understanding.scene_type = "cinematic"
    return _sanitize_understanding(understanding)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def default_llm_fn(*, timeout_sec: float = 180.0) -> LlmFn:
    """Bridge to the project's active Co-Director provider from sync code."""

    def _call(system_prompt: str, user_prompt: str) -> str:
        import asyncio
        import concurrent.futures

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        async def _run() -> str:
            from .. import service as codirector_service
            from ..providers.base import ChatRequest

            provider = codirector_service.get_provider()
            result = await provider.generate(
                ChatRequest(
                    request_id="scene-understanding",
                    messages=messages,
                    model_id=None,
                    project_context="",
                    temperature=0.2,
                )
            )
            return result.reply

        def _thread() -> str:
            return asyncio.run(_run())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_thread).result(timeout=timeout_sec)

    return _call


def extract_scene_understanding(
    message: str,
    *,
    llm_fn: Optional[LlmFn] = None,
    allow_llm: bool = True,
) -> tuple[SceneUnderstanding, str, str]:
    """Extract Layer B understanding. Returns (understanding, source, fallback_reason)."""

    text = (message or "").strip()
    if not text:
        return SceneUnderstanding(), "empty", ""

    fn = llm_fn
    if fn is None and allow_llm:
        try:
            fn = default_llm_fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("scene understanding: no LLM provider bridge: %s", exc)
            fn = None
    if fn is not None:
        try:
            understanding = _understanding_via_llm(text, fn)
            if understanding.beats or understanding.dialogue or understanding.scene_type:
                # Beat-coverage guarantee: an LLM rewrite may silently drop a
                # staged event (e.g. the first of two impacts). Backfill any
                # salient source event the beats failed to realize.
                return _coverage_backfill(understanding, text), "llm", ""
            logger.warning("scene understanding: LLM returned an empty understanding; using fallback")
        except Exception as exc:  # noqa: BLE001
            logger.warning("scene understanding: LLM extraction failed (%s); using fallback", exc)
            return _fallback_understanding(text), "fallback", str(exc)[:200]
    return _fallback_understanding(text), "fallback", "" if fn is None else "llm_empty"
