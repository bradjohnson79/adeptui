"""Speech-act classifier for the current user turn.

Additive turn-control layer. Does not replace IntentType / UnifiedIntent.
Classifies from the current user text only.
"""

from __future__ import annotations

import re
from typing import Literal

SpeechAct = Literal[
    "COMMAND",
    "QUESTION",
    "CAPABILITY_QUESTION",
    "DISCUSSION",
    "CREATIVE_IDEATION",
]

_CAPABILITY_RE = re.compile(
    r"\b(?:"
    r"do you have vision|can you see|are you (?:able to )?see|can you look|"
    r"vision (?:enabled|active|on|working)|"
    r"what model|which model|what(?:'s| is) your model|"
    r"are (?:you )?(?:looking at|using) (?:the )?(?:image|reference|photo|picture)|"
    r"tools? available|what can you (?:do|see)"
    r")\b",
    re.I,
)

_IDEATION_RE = re.compile(
    r"\b(?:"
    r"give me (?:\d+|a few|some|three|four|five) ideas|"
    r"brainstorm|"
    r"alternate (?:costume |look |wardrobe )?ideas|"
    r"ideate|"
    r"throw (?:out |me )?(?:some )?ideas"
    r")\b",
    re.I,
)

_ADVICE_QUESTION_RE = re.compile(
    r"^\s*(?:"
    r"should we|should i|shall we|"
    r"do you think(?: we)?(?: should)?|"
    r"would creating|"
    r"would it help|"
    r"would you|"
    r"what if(?: we)?|"
    r"can we|could we|may we"
    r")\b",
    re.I,
)

_POLITE_QUESTION_RE = re.compile(
    r"^\s*(?:can you|could you)\b",
    re.I,
)

_CONFIRM_EXECUTE_RE = re.compile(
    r"^\s*(?:yes[,.]?\s+)?(?:please\s+)?(?:go ahead and\s+)?"
    r"(?:create|generate|do|run|execute)\s+(?:it|that|this)\b",
    re.I,
)

_IMPERATIVE_RE = re.compile(
    r"^\s*(?:yes[,.]?\s+)?(?:please\s+)?"
    r"(?:create|generate|build|run|execute|render|approve|regenerate|redo|"
    r"animate|use|assign|add|make|start|advance|change|update|remove|delete|put|set|"
    r"move|rename|replace|swap|drop|insert|split|merge|fix|adjust|time|sync|"
    r"enhance|improve|refine|edit|watch|review|extend|continue|lengthen|stitch)\b",
    re.I,
)

_PRODUCTION_OBJECT_RE = re.compile(
    r"\b(?:crs|character reference sheet|visual sheet|reference sheet|"
    r"scene|image|video|clip|shot|storyboard|atlas|ers|"
    r"character identity|identity|voice|voice creator|voice identity|"
    r"music|score|ambience|sound effect|audio studio|"
    r"footsteps?|footfalls?|sfx|foley)\b",
    re.I,
)

_VOICE_CREATOR_RE = re.compile(
    r"\b(?:"
    r"give\b.+\ba voice|"
    r"create a new voice|"
    r"clone (?:this |a |the )?(?:recording|voice)|"
    r"open (?:the )?voice creator"
    r")\b",
    re.I,
)

_VOICE_INSPECT_RE = re.compile(r"\bwhat voice does\b", re.I)

_AUDIO_MUSIC_RE = re.compile(
    r"\b(?:tense )?orchestral cue\b|\bscore for (?:this )?scene\b|\bgive me\b.+\b(?:music|cue|score)\b",
    re.I,
)
_AUDIO_SFX_RE = re.compile(
    r"\b(?:door slam|sound effect|foley|metallic door)\b"
    r"|\bmake a\b.+\b(?:slam|beep|hit|footsteps)\b"
    r"|\b(?:create|generate|make|add)\b.+\b(?:footsteps?|footfalls?|sfx|sound effects?)\b",
    re.I,
)
_AUDIO_AMBIENCE_RE = re.compile(
    r"\b(?:ambience|room tone|atmosphere|scene bed)\b|\bquiet spaceship corridor\b",
    re.I,
)
_AUDIO_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert|sync)\b.+\b(?:approved|existing)\b.+\b(?:footsteps?|footfalls?|sfx|sound effects?|foley|audio|music|ambience|score)\b"
    r"|"
    r"\b(?:add|place|put|insert)\b.+\b(?:footsteps?|footfalls?|sfx|sound effects?|foley|audio|music|ambience|score)\b.+\b(?:timeline|(?:this|the|current)\s+scene)\b"
    r"|"
    r"\b(?:footsteps?|footfalls?|sfx|audio|music|ambience|score)\b.+\b(?:on|to|onto)\s+(?:the\s+)?timeline\b"
    r"|"
    r"\btime (?:them|the (?:footsteps?|sfx|sound effects?))\b",
    re.I,
)
_MUSIC_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert)\b.+\b(?:music|score|cue|track|soundtrack)\b.+\b(?:timeline|(?:this|the|current)\s+scene)\b",
    re.I,
)
_AMBIENCE_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert)\b.+\b(?:ambience|room tone|atmosphere|scene bed)\b.+\b(?:timeline|(?:this|the|current)\s+scene)\b",
    re.I,
)
_WATCH_REVIEW_RE = re.compile(
    r"\b(?:watch|review|check|look at|see|analyze)\b.+\b(?:this|that|the|current|last|latest)\s+(?:scene|clip|shot|video)\b",
    re.I,
)
_STITCH_SCENE_RE = re.compile(
    r"\bstitch\b.+\b(?:clips?|scene|track|together)\b|\bstitch (?:these|this|the)\b",
    re.I,
)
_REORDER_SCENE_RE = re.compile(
    r"\bmove\b.+\bshot\s*\d+\b.+\b(?:before|after|earlier|later)\b"
    r"|\bput\b.+\b(?:imported|library)\b.+\b(?:after|before)\b.+\bshot\s*\d+\b",
    re.I,
)
_EXTEND_SCENE_RE = re.compile(
    r"\b(?:extend|continue|lengthen|make longer|advance)\b.+\b(?:this|the|current|scene|clip|video)\b",
    re.I,
)
_AUDIO_OPEN_RE = re.compile(
    r"\b(?:open|show|use)\b.+\baudio studio\b|"
    r"\bproject audio\b|"
    r"\buse the approved\b.+\b(?:ambience|music|sound|sfx)\b|"
    r"\bapproved (?:corridor )?ambience\b",
    re.I,
)

_MULTI_VIEW_IMAGE_RE = re.compile(
    r"\bmulti[-\s]?view\b.+\bimage\b|\bimage\b.+\bmulti[-\s]?view\b",
    re.I,
)

_CRS_ACTION_RE = re.compile(
    r"\b(?:create|generate|build|make|run)\b.+\b(?:character reference sheet|\bcrs\b|visual sheet)\b"
    r"|\b(?:character reference sheet|\bcrs\b|visual sheet)\b",
    re.I,
)

_REGENERATE_CRS_RE = re.compile(
    r"\b(?:regenerate|redo|advance)\b.+\b(?:character reference sheet|\bcrs\b|visual sheet)\b",
    re.I,
)

_APPROVE_CRS_RE = re.compile(
    r"\b(?:approve|accept)\b.+\b(?:character reference sheet|\bcrs\b|visual sheet|hero)\b",
    re.I,
)

_IDENTITY_RE = re.compile(
    r"\b(?:use|assign|set)\b.+\b(?:as\s+)?(?:character\s+)?identity\b",
    re.I,
)

CRS_CREATE_ALIAS = "create_character_reference_sheet"
CRS_CAPABILITY_ID = "character.generate_visual_sheet"
CRS_CREATE_TOOL = "character_creator.propose_visual_sheet"
CRS_ADVANCE_TOOL = "character_creator.advance_visual_sheet"


def classify_speech_act(user_message: str) -> SpeechAct:
    """Classify the current user text only. Interrogative advice is never COMMAND."""

    text = " ".join((user_message or "").split())
    if not text:
        return "DISCUSSION"

    if _CAPABILITY_RE.search(text):
        return "CAPABILITY_QUESTION"

    if _IDEATION_RE.search(text):
        return "CREATIVE_IDEATION"

    if _ADVICE_QUESTION_RE.search(text):
        return "QUESTION"

    # "Can you create the CRS?" is a pragmatic request. Capability questions
    # ("Can you see…") already returned above.
    if _POLITE_QUESTION_RE.search(text):
        # Capability-style: "Can you generate images?" stays QUESTION / TALK upstream.
        if re.search(
            r"^\s*(?:can|could)\s+you\s+(?:please\s+)?(?:generate|create|make)\s+images?\??\s*$",
            text,
            re.I,
        ):
            return "QUESTION"
        # Actionable: "Can you generate this for me?"
        if re.search(
            r"^\s*(?:can|could)\s+you\s+(?:please\s+)?(?:generate|create|make|enhance)\s+"
            r"(?:this|that|it)\b",
            text,
            re.I,
        ):
            return "COMMAND"
        if (
            _CRS_ACTION_RE.search(text)
            or _REGENERATE_CRS_RE.search(text)
            or _AUDIO_PLACE_RE.search(text)
            or (_IMPERATIVE_RE.search(text) and _PRODUCTION_OBJECT_RE.search(text))
            or (_PRODUCTION_OBJECT_RE.search(text) and re.search(r"\b(?:generate|create|make|enhance)\b", text, re.I))
        ):
            return "COMMAND"
        return "QUESTION"

    if text.rstrip().endswith("?") and not _IMPERATIVE_RE.search(text):
        # Short interrogatives only — long "Sound good?" listening turns stay DISCUSSION.
        if len(text) < 180 or _ADVICE_QUESTION_RE.search(text) or _POLITE_QUESTION_RE.search(text):
            return "QUESTION"

    if _CONFIRM_EXECUTE_RE.search(text):
        return "COMMAND"

    from ...routing.atlas_intent import is_atlas_assign_request, is_atlas_generate_request

    if is_atlas_generate_request(text) or is_atlas_assign_request(text):
        return "COMMAND"

    if _VOICE_CREATOR_RE.search(text):
        return "COMMAND"

    if _CRS_ACTION_RE.search(text) or _REGENERATE_CRS_RE.search(text) or _APPROVE_CRS_RE.search(text) or _IDENTITY_RE.search(text):
        return "COMMAND"

    if _IMPERATIVE_RE.search(text) and (
        _PRODUCTION_OBJECT_RE.search(text) or _CONFIRM_EXECUTE_RE.search(text)
    ):
        return "COMMAND"

    if _IMPERATIVE_RE.search(text) and re.search(
        r"\b(?:first frame|still|corridor|shot|clips?)\b", text, re.I
    ):
        return "COMMAND"

    if _STITCH_SCENE_RE.search(text) or _REORDER_SCENE_RE.search(text):
        return "COMMAND"

    return "DISCUSSION"


_DEPOSIT_VIDEO_RE = re.compile(
    r"\b(?:deposit|export|send)\b.+\b(?:completed|finished)?\s*(?:1\s*f(?:rame)?|3\s*f(?:rame)?|one[\s-]?frame|three[\s-]?frame|video|take)\b.+\b(?:timeline(?:\s+visual)?|visual)\b"
    r"|\bdeposit\b.+\b(?:completed\s+)?(?:video|take)\b.+\b(?:timeline|visual)\b",
    re.I,
)


def resolve_production_action(user_message: str) -> str:
    """Best-effort action id for the current command. Empty when none."""

    text = user_message or ""
    if _DEPOSIT_VIDEO_RE.search(text):
        return "timeline.deposit_video"
    if _STITCH_SCENE_RE.search(text):
        return "timeline.stitch"
    if _REORDER_SCENE_RE.search(text):
        return "timeline.reorder"
    if _WATCH_REVIEW_RE.search(text):
        return "analyze.video"
    if _EXTEND_SCENE_RE.search(text):
        return "timeline.extend"
    if _VOICE_CREATOR_RE.search(text):
        return "voice.creator"
    if _VOICE_INSPECT_RE.search(text):
        return "voice.inspect"
    if _MUSIC_PLACE_RE.search(text):
        return "timeline.add_audio"
    if _AMBIENCE_PLACE_RE.search(text):
        return "timeline.add_audio"
    if _AUDIO_PLACE_RE.search(text):
        return "timeline.add_audio"
    if _AUDIO_OPEN_RE.search(text):
        return "audio.open"
    if _AUDIO_MUSIC_RE.search(text):
        return "audio.music"
    if _AUDIO_SFX_RE.search(text):
        return "audio.sfx"
    if _AUDIO_AMBIENCE_RE.search(text):
        return "audio.ambience"
    if _IDENTITY_RE.search(text) or _APPROVE_CRS_RE.search(text):
        return "character.assign_reference"
    if _MULTI_VIEW_IMAGE_RE.search(text):
        return "image.generate"
    from .visual_generation import is_visual_image_request

    if is_visual_image_request(text):
        return "image.generate"
    if _REGENERATE_CRS_RE.search(text):
        return CRS_ADVANCE_TOOL
    if _CRS_ACTION_RE.search(text) and not _MULTI_VIEW_IMAGE_RE.search(text):
        return CRS_CREATE_ALIAS
    return ""


def is_crs_create_action(action: str) -> bool:
    return action in {
        CRS_CREATE_ALIAS,
        CRS_CAPABILITY_ID,
        CRS_CREATE_TOOL,
    }
