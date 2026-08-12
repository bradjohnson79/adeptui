"""Entity classification, preference filter, false-character rejection, alias helpers."""

from __future__ import annotations

import re
from typing import Any, Literal

from .contracts import FALSE_CHARACTER_TOKENS, PROFESSIONAL_TOC_ROOTS

_PREF_RE = re.compile(
    r"\b(agent gold|working preference|how i(?:'|’)d like us to work|collaboration preference|"
    r"call me |address me as|skip the setup|relationship mode)\b",
    re.I,
)

# --- Conversation turn classification (write-time honesty gate) ----------------
#
# classify_conversation_turn returns a deterministic turn-type label so the
# Wiki write path can decide whether a user message may contribute narrative
# canon. It is intentionally a fast regex+heuristic classifier — no LLM calls.
#
# Labels:
#   story_canon        — genuine in-world narrative description (characters,
#                        plot, scene events, world rules, themes stated as canon)
#   user_preference    — addressing/relationship/working-mode setup
#                        ("please call me friend", "use balanced mode")
#   production_request — imperative commands to produce/create assets
#                        ("create the storyboard", "generate the image")
#   meta_conversation  — acknowledgments, workflow talk, system-talk
#                        ("let's get started", "thanks", "ok do it")
#   question           — ends with "?" or asks for information
#   brainstorming      — speculative options ("what if she…", "maybe the scene…")
#   unknown            — does not match confidently
#
# CRITICAL: A production instruction that merely MENTIONS a character/scene/
# location/storyboard must NOT be promoted to story_canon. Only genuine
# narrative description of in-world events counts.

TurnType = Literal[
    "story_canon",
    "user_preference",
    "production_request",
    "meta_conversation",
    "question",
    "brainstorming",
    "unknown",
]

# Relationship / addressing / working-mode setup. Broadened beyond _PREF_RE so
# the write path can quarantine all preference-style turns, not just the small
# set used for entity classification.
_TURN_PREF_RE = re.compile(
    r"\b(?:please\s+call\s+me|call\s+me\s+\w+|address\s+me\s+as|"
    r"i(?:'|’)?ll\s+call\s+you|you(?:'|’)?re\s+my\s+co[-\s]?director|"
    r"be\s+my\s+co[-\s]?director|act\s+as\s+my\s+co[-\s]?director|"
    r"use\s+(?:balanced|concise|detailed|creative|formal|casual)\s+mode|"
    r"working\s+preference|collaboration\s+preference|relationship\s+mode|"
    r"how\s+i(?:'|’)?d\s+like\s+(?:us\s+to\s+work|to\s+work)|"
    r"skip\s+(?:the\s+)?setup|lets?\s+skip\s+onboarding|"
    r"tone\s+(?:of\s+our\s+)?conversations?|friendly\s+tone|"
    r"be\s+(?:more\s+)?(?:friendly|concise|verbose|formal|casual)\b)\b",
    re.I,
)

# Imperative production commands — the verb list is deliberately concrete so a
# sentence like "Barnes creates the dreamweaver" is NOT mis-flagged as a
# production request (it reads as in-world narrative). We require an imperative
# shape (sentence-initial verb, or "please <verb>", or "<verb> the <asset>").
_TURN_PRODUCTION_RE = re.compile(
    r"^(?:please\s+|kindly\s+|can\s+you\s+|could\s+you\s+|let'?s?\s+|i\s+want\s+(?:you\s+)?to\s+|"
    r"go\s+ahead\s+and\s+|now\s+|next\s+|then\s+)?"
    r"(?:create|generate|make|build|produce|render|animate|draw|paint|design|"
    r"storyboard|compose|record|film|shoot|edit|export|save|approve|reject|"
    r"delete|rename|update|set|open|navigate|show|start|run|"
    r"place\s+(?:this|that|the)\s+(?:into|in)\s+(?:the\s+)?(?:wiki|story|logline|short\s+summary|long\s+summary)|"
    r"put\s+(?:this|that|the)\s+(?:into|in)\s+(?:the\s+)?(?:wiki|story|logline|short\s+summary|long\s+summary)|"
    r"summarize\s+|write\s+(?:a\s+)?(?:logline|short\s+summary|long\s+summary|synopsis|treatment))\b",
    re.I,
)

# Production-asset nouns — used to confirm a production_request when the verb
# shape is ambiguous. Mentions alone are NOT enough to promote to production.
_PRODUCTION_ASSET_RE = re.compile(
    r"\b(storyboard|image|video|clip|render|character\s+sheet|visual\s+sheet|"
    r"voice\s+clip|voice\s+version|audio\s+bus|casting\s+image|hero\s+portrait|"
    r"timeline|animatic|draft|outline|beat\s+sheet|scene\s+card)\b",
    re.I,
)

# Meta-conversation: acknowledgments, workflow talk, system-talk.
_TURN_META_RE = re.compile(
    r"^(?:ok(?:ay)?|sure|yes|yeah|yep|no|nope|thanks|thank\s+you|got\s+it|"
    r"understood|will\s+do|sounds\s+good|great|awesome|perfect|cool|nice|"
    r"let'?s?\s+(?:get\s+started|start|begin|go|continue|move\s+on|do\s+it)|"
    r"lets?\s+go|please\s+do|go\s+for\s+it|keep\s+going|continue|"
    r"hi(?:\s+there)?|hello|hey|yo|good\s+morning|good\s+evening|"
    r"(?:i\s+)?agree|exactly|right|correct|true|indeed|makes\s+sense|"
    r"(?:that'?s\s+)?(?:a\s+)?good\s+(?:idea|point|question|thought)|"
    r"(?:i\s+)?(?:don'?t|do\s+not)\s+(?:know|think)|let\s+me\s+think|"
    r"what(?:'?s|s|\s+is)\s+next|what\s+now|how\s+(?:about|do\s+we)|"
    r"that'?s\s+(?:fine|okay|great|enough))\b\.?!?",
    re.I,
)

# Brainstorming: speculative / hypothetical / option-exploring phrasing.
_TURN_BRAINSTORM_RE = re.compile(
    r"\b(?:what\s+if\s+\w+|maybe\s+(?:she|he|they|it|the\s+\w+|we|i)|"
    r"perhaps\s+(?:she|he|they|it|the\s+\w+|we)|"
    r"could\s+(?:she|he|they|it|the\s+\w+|we)\s+(?:be|have|do|go)|"
    r"how\s+about\s+(?:she|he|they|the\s+\w+|we|i)|"
    r"alternative(?:ly)?[:\s]|option\s+\d|one\s+option\s+(?:is|could\s+be)|"
    r"(?:a|another)\s+possibility\s+(?:is|could\s+be)|"
    r"suppose\s+(?:she|he|they|the\s+\w+)|"
    r"imagine\s+(?:if|she|he|they)|"
    r"i\s+(?:wonder|imagine|am\s+thinking)|on\s+the\s+other\s+hand)\b",
    re.I,
)

# Narrative canon signals: real in-world description of events / characters /
# world rules / themes stated as canon. These are content patterns, not just
# keyword mentions — they require a verb that describes in-world action or
# definition so a production instruction that mentions a character cannot
# masquerade as canon.
_TURN_STORY_RE = re.compile(
    r"\b("
    # Character doing / being something in-world
    r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|she|he|they)"
    r"\s+(?:is|are|was|were|enters?|exits?|arrives?|leaves?|discovers?|"
    r"meets?|hears?|calls?|orders?|tastes?|reacts?|remembers?|"
    r"wears?|carries?|holds?|speaks?|tells?|asks|answers|"
    r"investigates?|interviews?|chases?|flees?|fights?|loves?|fears?|"
    r"lives?|works?|dreams?|wakes?|dies?|kills?|saves?|finds?|loses?|"
    r"builds?|destroys?|creates?|opens?|closes?|crosses?|watches?)\b"
    r"|"
    # Scene / setting description
    r"(?:the\s+)?(?:scene|story|episode|film|series|chapter)\s+"
    r"(?:opens|begins|starts|ends|follows|is\s+set|takes\s+place|"
    r"cuts\s+to|fades\s+to|jumps\s+to)"
    r"|"
    # Stated world rule / continuity
    r"(?:world\s+rule|continuity\s+rule|the\s+rule\s+is|rule:\s*|"
    r"(?:every|always|never|must)\s+\w+\s+(?:costs?|requires?|stays?|remains?|holds?))"
    r"|"
    # Theme stated as canon ("the theme is…", "themes are…")
    r"(?:the\s+)?theme(?:s)?\s+(?:is|are|:)\s+"
    r"|"
    # Logline / synopsis opening
    r"(?:logline|synopsis|premise|treatment):\s*"
    r"|"
    # "Set in <place/time>" / "follows <character>"
    r"(?:set\s+(?:in|across|during)|follows\s+(?:a|an|the)\s+)"
    r")",
    re.I,
)

# Short, low-information responses (≤3 words after stripping punctuation) are
# almost never story canon — they're meta or unknown.
_SHORT_TOKEN_THRESHOLD = 3


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def classify_conversation_turn(text: str) -> TurnType:
    """Deterministic conversation-turn classifier for the Wiki write path.

    Returns one of: story_canon, user_preference, production_request,
    meta_conversation, question, brainstorming, unknown.

    The classifier is purposefully conservative: when in doubt it returns
    `unknown` rather than `story_canon`, because the Wiki honesty rule is
    "leave blank when insufficient" — never "promote anything plausible".
    """
    raw = (text or "").strip()
    if not raw:
        return "unknown"

    # Question: ends with "?" or starts with a question word and is short-ish.
    if raw.endswith("?"):
        # A brainstorming what-if that ends with "?" should still be
        # brainstorming, not a question.
        if _TURN_BRAINSTORM_RE.search(raw):
            return "brainstorming"
        return "question"
    # Brainstorming check must run BEFORE the generic question-word check so
    # "what if she orders espresso instead" (no "?") is classified as
    # brainstorming, not question. A genuine question starting with a question
    # word that is NOT a brainstorm ("what is the story about") still returns
    # question because it doesn't match the brainstorm pattern.
    if _TURN_BRAINSTORM_RE.search(raw):
        return "brainstorming"
    if re.match(
        r"^(?:what|why|how|when|where|who|which|should|could|would|can|do|does|did|is|are)\b",
        raw,
        re.I,
    ) and _word_count(raw) <= 24:
        return "question"

    # User preference: addressing / relationship / working-mode setup.
    if _TURN_PREF_RE.search(raw):
        return "user_preference"

    # Production request: imperative verb shape OR verb + asset noun.
    if _TURN_PRODUCTION_RE.match(raw):
        return "production_request"
    # Some production requests are framed as "let's make X" / "I want X" with
    # the asset noun present; catch those without mis-flagging narrative.
    if _PRODUCTION_ASSET_RE.search(raw) and re.match(
        r"^(?:please\s+|kindly\s+|can\s+we\s+|could\s+we\s+|let'?s?\s+|"
        r"i\s+(?:want|need|would\s+like)\s+(?:you\s+to\s+|to\s+)?)"
        r"(?:create|generate|make|build|produce|render|design|"
        r"compose|record|film|shoot|edit|export|draw|paint|animate)\b",
        raw,
        re.I,
    ):
        return "production_request"

    # Meta-conversation: short acknowledgments / workflow talk.
    if _TURN_META_RE.match(raw) and _word_count(raw) <= 12:
        return "meta_conversation"

    # Story canon: genuine in-world narrative description. Require the
    # narrative-pattern match AND a minimum content length so a single
    # capitalized sentence-fragment doesn't promote. The 40-char floor
    # mirrors story_compiler's own `len(t) >= 40` narrative filter so the
    # classifier and the compiler agree on what counts as a narrative sentence.
    if _TURN_STORY_RE.search(raw) and len(raw) >= 40:
        return "story_canon"

    return "unknown"


# Turn-types that must NEVER populate Logline / Short Summary / Long Summary
# or contribute narrative canon to the Wiki.
_NON_CANON_TURN_TYPES: frozenset[TurnType] = frozenset(
    {
        "user_preference",
        "production_request",
        "meta_conversation",
        "question",
        "unknown",
    }
)


def is_canon_turn(text: str) -> bool:
    """True if the turn may contribute narrative canon to the Wiki.

    `story_canon` always qualifies. `brainstorming` qualifies only when an
    explicit refine/rebuild operation has opted into it — that decision is
    made by the caller, not by this predicate. `unknown` is treated as
    non-canon so the write path leaves fields blank rather than guessing.
    """
    return classify_conversation_turn(text) == "story_canon"


def is_non_canon_turn(text: str) -> bool:
    """True if the turn must NOT contribute to Logline/Short/Long summaries."""
    return classify_conversation_turn(text) in _NON_CANON_TURN_TYPES
_LOC_HINT = re.compile(
    r"\b(location|room|set|harbor|archive|city|building|station|facility|anteroom|office|studio)\b",
    re.I,
)
_ORG_HINT = re.compile(
    r"\b(guild|agency|institute|organization|organisation|corp|company|cooperative|faction|council)\b",
    re.I,
)
_WARDROBE_HINT = re.compile(
    r"\b(wears?|wearing|coat|suit|wardrobe|outfit|dress|costume|footwear|accessory)\b",
    re.I,
)
_PROP_HINT = re.compile(
    r"\b(prop|recorder|device|weapon|tool|carries?|carrying|holds?|holding)\b",
    re.I,
)
_TIMELINE_HINT = re.compile(
    r"\b((?:19|20|21)\d{2}|timeline|flashback|flash[- ]forward|chronolog|before|after)\b",
    re.I,
)
_WORLD_HINT = re.compile(
    r"\b(world rule|must never|always |forbidden|continuity|metaphysic|technology|power system)\b",
    re.I,
)
_AGE_RE = re.compile(r"\b(?:age\s+\d{1,3}|\d{1,3}\s+years?\s+old)\b", re.I)
_KNOWN_ORG_TOKENS = re.compile(
    r"\b(fbi|nsa|cia|dw6|darpa|nasa|nato|kgb|mi6|interpol|pentagon|cdc|who|un)\b",
    re.I,
)


def is_user_preference_not_canon(text: str) -> bool:
    """True when the text is a user-preference / addressing turn, not canon.

    Consults both the legacy `_PREF_RE` (used by entity classification to
    quarantine preference-shaped candidates) and the new write-time
    `classify_conversation_turn` so preference turns that phrased differently
    than `_PREF_RE` are still caught.
    """
    if _PREF_RE.search(text or ""):
        return True
    return classify_conversation_turn(text or "") == "user_preference"


def is_false_character_name(name: str) -> bool:
    cleaned = re.sub(r"[^a-zA-Z0-9\s'\-]", "", (name or "").strip()).strip().lower()
    if not cleaned or len(cleaned) < 2:
        return True
    if cleaned in FALSE_CHARACTER_TOKENS:
        return True
    if cleaned in {"series synopsis", "project overview", "known details"}:
        return True
    # Pronouns / single generic nouns
    if cleaned in {"she", "he", "they", "it", "we", "you"}:
        return True
    return False


def classify_entity_type(
    text: str,
    *,
    hinted_section: str | None = None,
    entity_type_overrides: dict[str, str] | None = None,
) -> str:
    """Return a professional entity type for routing — conversational context only.

    Phase CK — entity classification is for conversational understanding only.
    It does NOT create canonical project entities.

    `entity_type_overrides` maps normalized (lowercase) entity names to a
    creator-corrected entity type. These are consulted FIRST so a learned
    correction ("Gakona is a location") permanently reclassifies that entity.
    """
    raw = (text or "").strip()
    lower = raw.lower()
    title = raw.split(":", 1)[0].strip()

    # Creator-learned overrides take highest precedence (CREATOR_CORRECTION_PRIORITY).
    if entity_type_overrides:
        for name, etype in entity_type_overrides.items():
            if name and name in lower:
                return etype

    if is_user_preference_not_canon(raw):
        return "preference"

    # Age / attribute detection: "age N" / "N years old" is an ATTRIBUTE, never a character.
    if _AGE_RE.search(raw):
        return "attribute"

    # Known organization acronyms / agency tokens are ORGANIZATION, never a character.
    if _KNOWN_ORG_TOKENS.search(raw) or _KNOWN_ORG_TOKENS.search(title):
        return "organization"

    if hinted_section:
        hs = hinted_section.lower()
        if "character" in hs:
            # Still reject false names when text looks like a name-only entry
            if is_false_character_name(title) or _LOC_HINT.search(raw) or _ORG_HINT.search(raw):
                pass
            else:
                # Phase CK — conversational context only; does not auto-persist
                return "note"
        if "location" in hs or "world" in hs:
            return "location" if not _ORG_HINT.search(raw) else "organization"
    if _ORG_HINT.search(raw) or _ORG_HINT.search(title):
        return "organization"
    if _LOC_HINT.search(raw):
        return "location"
    if _WARDROBE_HINT.search(raw):
        return "wardrobe"
    if _PROP_HINT.search(raw):
        return "prop"
    if _TIMELINE_HINT.search(raw) and len(raw) < 280:
        return "timeline_event"
    if _WORLD_HINT.search(raw):
        return "world_rule"
    if re.search(r"\b(theme|premise|synopsis|logline|act structure|story beat)\b", lower):
        # Phase CK — conversational context only; does not auto-persist
        return "note"
    if re.search(r"\b(lighting|lens|camera|palette|visual|storyboard)\b", lower):
        return "visual"
    if re.search(r"\b(voice|accent|music|ambience|sound|score)\b", lower):
        return "audio"
    if re.search(r"\b(episode|scene|treatment|script|screenplay)\b", lower):
        return "episode_or_scene"
    # Name-like character candidate — Phase CK: conversational context only, does not auto-persist
    if re.match(r"^(?:Dr\.|Agent|Professor|Captain|Detective)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", raw):
        if not is_false_character_name(title):
            return "note"
    return "note"


def target_section_for_entity(entity_type: str) -> str:
    mapping = {
        "character": "characters",
        "location": "locationsAndSets",
        "organization": "worldAndLore",
        "wardrobe": "visualDevelopment",
        "prop": "visualDevelopment",
        "timeline_event": "timelineAndContinuity",
        "world_rule": "worldAndLore",
        "story": "story",
        "visual": "visualDevelopment",
        "audio": "audioAndPerformance",
        "episode_or_scene": "episodesAndScenes",
        "preference": "references",  # quarantined / not overview
        "note": "story",
    }
    section = mapping.get(entity_type, "story")
    return section if section in PROFESSIONAL_TOC_ROOTS else "story"


def normalize_alias_key(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"^(dr\.|agent|professor|captain|detective)\s+", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def names_are_aliases(a: str, b: str) -> bool:
    ka, kb = normalize_alias_key(a), normalize_alias_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if ka in kb or kb in ka:
        # Prefer longer containment only when token overlap is strong
        short, long = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
        return len(short) >= 4 and short in long
    return False


def extract_display_name(text: str) -> str:
    head = (text or "").split(":", 1)[0].strip()
    head = re.sub(r"^(character|person|location|organization|prop|wardrobe)\s*[–\-:]?\s*", "", head, flags=re.I)
    return head[:80].strip() or (text or "")[:80]


def detect_domains_from_entries(entries: list[dict[str, Any]]) -> list[str]:
    domains: set[str] = set()
    for e in entries:
        text = str(e.get("text") or "")
        et = classify_entity_type(text, hinted_section=str(e.get("section") or ""))
        if et == "character":
            domains.add("characters")
        elif et == "location":
            domains.add("locations")
        elif et == "organization" or et == "world_rule":
            domains.add("world")
        elif et == "timeline_event":
            domains.add("timeline")
        elif et == "wardrobe":
            domains.add("wardrobe")
        elif et == "prop":
            domains.add("props")
        elif et == "visual":
            domains.add("visual")
        elif et == "audio":
            domains.add("audio")
        elif et in {"story", "episode_or_scene"}:
            domains.add("story")
        elif et == "preference":
            domains.add("canon")
        else:
            domains.add("story")
    if not domains:
        domains.add("story")
    domains.add("canon")
    return sorted(domains)
