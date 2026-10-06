"""Chat-side attachment intent for Timeline visual/background refs (Order 11A).

User intent overrides asset guessing. Ordinary café / location photos with
background/reference/Timeline-visual language map to timeline_*_ref — NOT
ERS/CRS/PRS sheet validation or ers.generate lectures.

Formal sheet validation only when the user explicitly asks to create/validate
a sheet. Timeline attach is proposed (approval-gated); never silently mutated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

AttachIntent = Literal[
    "timeline_background_ref",
    "timeline_visual_ref",
    "ers_sheet_validate",
    "crs_sheet_validate",
    "prs_sheet_validate",
    "screenplay",
    "reference_image",
    # Intelligence mission 2026-09-19 (RC8/Phase 8): an attached image with
    # discussion/opinion language is a visual conversation, not a Timeline
    # action. Attachment existence alone no longer decides the purpose.
    "visual_discussion",
    "unknown",
]

TIMELINE_REF_INTENTS = frozenset({"timeline_background_ref", "timeline_visual_ref"})
SHEET_VALIDATE_INTENTS = frozenset(
    {"ers_sheet_validate", "crs_sheet_validate", "prs_sheet_validate"}
)

# Explicit sheet create/validate — only then ERS/CRS/PRS formal path.
_ERS_SHEET_RE = re.compile(
    r"\b(?:(?:generate|create|make|build|assemble|validate|review|check)\b.{0,40}\b"
    r"(?:ers|environment\s+reference\s+(?:sheet|package|set))"
    r"|(?:ers|environment\s+reference\s+(?:sheet|package))\b.{0,40}\b"
    r"(?:generate|create|validate|review|check|layout))\b",
    re.I | re.S,
)
_CRS_SHEET_RE = re.compile(
    r"\b(?:(?:generate|create|make|build|validate|review|check)\b.{0,40}\b"
    r"(?:crs|character\s+reference\s+sheet)"
    r"|(?:crs|character\s+reference\s+sheet)\b.{0,40}\b"
    r"(?:generate|create|validate|review|check))\b",
    re.I | re.S,
)
_PRS_SHEET_RE = re.compile(
    r"\b(?:(?:generate|create|make|build|validate|review|check)\b.{0,40}\b"
    r"(?:prs|prop\s+reference\s+sheet)"
    r"|(?:prs|prop\s+reference\s+sheet)\b.{0,40}\b"
    r"(?:generate|create|validate|review|check))\b",
    re.I | re.S,
)

# User wants the image as Timeline set / background / look-of-place.
_BACKGROUND_RE = re.compile(
    r"\b(?:"
    r"background|"
    r"backdrop|"
    r"set\s+(?:dressing|piece|photo)|"
    r"look\s+of\s+(?:the\s+)?(?:place|café|cafe|location|shop|room)|"
    r"(?:café|cafe|location|shop)\s+photo\s+as\s+set|"
    r"as\s+(?:the\s+)?(?:background|backdrop|set)|"
    r"use\s+(?:it|this|the\s+(?:image|photo|picture))\s+as\s+(?:the\s+)?background|"
    r"timeline\s+background|"
    r"scene\s+background"
    r")\b",
    re.I,
)
_VISUAL_REF_RE = re.compile(
    r"\b(?:"
    r"timeline\s+visual|"
    r"visual\s+ref(?:erence)?|"
    r"(?:use|keep|treat)\s+(?:it|this|the\s+(?:image|photo|picture))\s+as\s+"
    r"(?:a\s+|the\s+)?(?:reference|visual)|"
    r"(?:as|for)\s+(?:a\s+|the\s+)?(?:visual\s+)?reference|"
    r"reference\s+(?:for|on)\s+(?:the\s+)?timeline|"
    r"on\s+(?:the\s+)?timeline\s+as\s+(?:a\s+)?(?:ref|reference|visual)|"
    r"look\s+reference|"
    r"location\s+reference|"
    r"set\s+reference"
    r")\b",
    re.I,
)
_SCREENPLAY_RE = re.compile(
    r"\b(?:INT\.|EXT\.|FADE IN|CUT TO:|V\.O\.|screenplay|script)\b",
    re.I,
)
# Long creative payload — do not collapse to attachment-only reply.
_LONG_CREATIVE_RE = re.compile(
    r"\b(?:screenplay|script|scene\s+\d+|beat(?:s)?|FADE IN|INT\.|EXT\.)\b",
    re.I,
)

# Preserve @Korri / @Cade (and common spellings) — never strip.
_TAG_RE = re.compile(r"@(?:Korri|Cade)\b", re.I)

# Intelligence mission RC8 / Phase 8: the creator is TALKING about the image
# (look, lighting, mood, staging) — visual discussion, not a Timeline action.
_VISUAL_DISCUSSION_RE = re.compile(
    r"\b(?:"
    r"what do you think|what do you see|how does (?:this|it|the)\s+(?:look|lighting|image|photo|shot)|"
    r"your take|thoughts on|opinion|feedback|do you like|does (?:this|it) work|"
    r"light(?:ing)?|mood|staging|composition|color grade|framing"
    r")\b",
    re.I,
)

_NEGATED_SHEET_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|never|no)\b.{0,24}\b(?:make|create|generate|build|validate|need)\b.{0,40}\b"
    r"(?:ers|crs|prs|environment\s+reference|character\s+reference|prop\s+reference)\b",
    re.I | re.S,
)


@dataclass
class AttachIntentResult:
    intent: AttachIntent
    role: str  # background | supporting
    confidence: float
    signals: list[str] = field(default_factory=list)
    suppress_ers_lecture: bool = False
    propose_timeline_attach: bool = False
    has_long_creative: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "role": self.role,
            "confidence": self.confidence,
            "signals": list(self.signals),
            "suppressErsLecture": self.suppress_ers_lecture,
            "proposeTimelineAttach": self.propose_timeline_attach,
            "hasLongCreative": self.has_long_creative,
        }


def extract_preserved_tags(text: str) -> list[str]:
    return list(dict.fromkeys(_TAG_RE.findall(text or "")))


def classify_attach_intent(
    user_text: str = "",
    *,
    mime_type: str = "",
    filename: str = "",
    has_image_attachment: bool | None = None,
) -> AttachIntentResult:
    """Classify chat attachment intent from user language (overrides guessing)."""
    text = user_text or ""
    signals: list[str] = []
    long_creative = bool(_LONG_CREATIVE_RE.search(text)) or len(text) >= 400
    if long_creative:
        signals.append("long_creative_payload")

    is_image = False
    if has_image_attachment is not None:
        is_image = bool(has_image_attachment)
    elif (mime_type or "").startswith("image/"):
        is_image = True
        signals.append("mime:image")
    elif re.search(r"\.(?:png|jpe?g|webp|gif|bmp)$", (filename or ""), re.I):
        is_image = True
        signals.append("filename:image")

    negated_sheet = bool(_NEGATED_SHEET_RE.search(text)) if text else False
    if negated_sheet:
        signals.append("negated_sheet_ask")

    # Background / Timeline visual intent overrides sheet guessing (Owner law).
    if _BACKGROUND_RE.search(text):
        signals.append("user:background")
        return AttachIntentResult(
            intent="timeline_background_ref",
            role="background",
            confidence=0.92,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=True,
            has_long_creative=long_creative,
        )
    if _VISUAL_REF_RE.search(text):
        signals.append("user:visual_ref")
        return AttachIntentResult(
            intent="timeline_visual_ref",
            role="supporting",
            confidence=0.88,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=True,
            has_long_creative=long_creative,
        )

    # Explicit sheet asks only when not negated — do not infer from café photo.
    if (not negated_sheet) and _ERS_SHEET_RE.search(text):
        signals.append("explicit_ers_sheet")
        return AttachIntentResult(
            intent="ers_sheet_validate",
            role="supporting",
            confidence=0.9,
            signals=signals,
            suppress_ers_lecture=False,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )
    if (not negated_sheet) and _CRS_SHEET_RE.search(text):
        signals.append("explicit_crs_sheet")
        return AttachIntentResult(
            intent="crs_sheet_validate",
            role="supporting",
            confidence=0.9,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )
    if (not negated_sheet) and _PRS_SHEET_RE.search(text):
        signals.append("explicit_prs_sheet")
        return AttachIntentResult(
            intent="prs_sheet_validate",
            role="supporting",
            confidence=0.9,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )

    if _BACKGROUND_RE.search(text):
        signals.append("user:background")
        return AttachIntentResult(
            intent="timeline_background_ref",
            role="background",
            confidence=0.92 if is_image else 0.75,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=True,
            has_long_creative=long_creative,
        )
    if _VISUAL_REF_RE.search(text):
        signals.append("user:visual_ref")
        return AttachIntentResult(
            intent="timeline_visual_ref",
            role="supporting",
            confidence=0.85 if is_image else 0.65,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=True,
            has_long_creative=long_creative,
        )
    if is_image and _VISUAL_DISCUSSION_RE.search(text):
        # Intelligence mission RC8 / Phase 8: the creator is TALKING about the
        # image (lighting, mood, staging) — visual discussion, not a Timeline
        # action. Explicit attach language above still wins.
        signals.append("visual_discussion_language")
        return AttachIntentResult(
            intent="visual_discussion",
            role="supporting",
            confidence=0.8,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )
    if is_image and re.search(
        r"\b(?:timeline|background|café|cafe|location|set)\b",
        text,
        re.I,
    ):
        signals.append("image+locationish_language")
        return AttachIntentResult(
            intent="timeline_visual_ref",
            role="supporting",
            confidence=0.85,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=True,
            has_long_creative=long_creative,
        )

    if _SCREENPLAY_RE.search(text) and not is_image:
        signals.append("screenplay_text")
        return AttachIntentResult(
            intent="screenplay",
            role="supporting",
            confidence=0.8,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )

    if is_image:
        # Intelligence mission RC8 / Phase 8: an attached image with NO stated
        # use is a referenced image. Attachment existence alone does not decide
        # a Timeline action — the model infers or asks the purpose from the
        # conversation. (Previously this defaulted to a Timeline attach
        # proposal.)
        signals.append("image_no_stated_use")
        return AttachIntentResult(
            intent="reference_image",
            role="supporting",
            confidence=0.4,
            signals=signals,
            suppress_ers_lecture=True,
            propose_timeline_attach=False,
            has_long_creative=long_creative,
        )

    return AttachIntentResult(
        intent="unknown",
        role="supporting",
        confidence=0.2,
        signals=signals or ["no_attach_signals"],
        suppress_ers_lecture=False,
        propose_timeline_attach=False,
        has_long_creative=long_creative,
    )


def should_suppress_ers_priority(
    intent: AttachIntentResult | AttachIntent | str,
    *,
    user_text: str | None = None,
) -> bool:
    """Suppress ERS lecture for Timeline visual/background / non-sheet turns.

    Timeline_*_ref always suppresses (Owner: user background intent wins).
    Sheet-validate intents never suppress.
    For ambiguous intents, Order 11B `is_explicit_sheet_knowledge_intent`
    decides whether formal sheet curriculum may load.
    """
    if isinstance(intent, AttachIntentResult):
        kind = intent.intent
        if kind in TIMELINE_REF_INTENTS:
            return True
        if kind in SHEET_VALIDATE_INTENTS:
            return False
        if bool(intent.suppress_ers_lecture):
            return True
    else:
        kind = str(intent)
        if kind in TIMELINE_REF_INTENTS:
            return True
        if kind in SHEET_VALIDATE_INTENTS:
            return False
        if kind in {"screenplay", "reference_image", "visual_discussion", "unknown"}:
            # fall through to 11B for ambiguous
            pass
        else:
            return False

    if user_text:
        try:
            from app.codirector.knowledgebase.sheet_intent_gate import (
                is_explicit_sheet_knowledge_intent,
            )
            if is_explicit_sheet_knowledge_intent(user_text):
                return False
        except Exception:
            pass
    return True
def build_timeline_attach_handoff(
    *,
    asset_ids: list[str],
    intent: AttachIntentResult,
    scene_id: str | None = None,
    batch_block_id: str | None = None,
) -> dict[str, Any]:
    """Approval-gated handoff payload (no silent Timeline mutation)."""
    ids = [str(a).strip() for a in asset_ids if str(a).strip()]
    primary = ids[0] if ids else None
    role = intent.role if intent.role in {"background", "supporting"} else "supporting"
    # Prefer timeline.attach_optional_reference when batch is known; otherwise
    # references.attach at scene scope (still proposal-gated).
    if primary and scene_id and batch_block_id:
        tool_id = "timeline.attach_optional_reference"
        arguments: dict[str, Any] = {
            "sceneId": scene_id,
            "batchBlockId": batch_block_id,
            "assetId": primary,
            "role": role,
            "label": "Chat attachment — Timeline visual/background ref",
        }
    elif primary and scene_id:
        tool_id = "references.attach"
        arguments = {
            "assetId": primary,
            "scopeType": "scene",
            "scopeId": scene_id,
            "referenceType": "environment" if role == "background" else "other",
            "usageModes": ["informational", "generation"],
            "referenceRoles": [role],
        }
    else:
        tool_id = "timeline.attach_optional_reference"
        arguments = {
            "assetId": primary,
            "role": role,
            "label": "Chat attachment — Timeline visual/background ref",
        }
    return {
        "kind": "timeline_attach_propose",
        "approvalRequired": True,
        "silentMutation": False,
        "toolId": tool_id,
        "arguments": arguments,
        "assetIds": ids,
        "intent": intent.intent,
        "role": role,
        "status": "proposed_handoff",
        "note": (
            "Propose attaching the chat image as a Timeline visual/background "
            "reference. Do not apply until the creator approves."
        ),
    }


def build_dual_layer_attach_reply(
    user_message: str,
    intent: AttachIntentResult,
    *,
    handoff: dict[str, Any] | None = None,
) -> str:
    """Creative companion reaction THEN production Timeline plan in one reply."""
    tags = extract_preserved_tags(user_message)
    tag_bit = (" " + " ".join(tags)) if tags else ""
    role = intent.role
    role_phrase = "background reference" if role == "background" else "Timeline visual reference"

    companion = (
        f"Love the energy in this — the place already feels like it has a pulse{tag_bit}. "
        "Comedy timing and character beats can ride on top of that look without fighting it."
    )
    if intent.has_long_creative:
        companion = (
            f"Got the screenplay energy and the photo together{tag_bit} — "
            "I'll keep the story beats and the location look in the same conversation, "
            "not collapse this into a sheet lecture."
        )

    production = (
        f"**Production plan (9:16)**\n"
        f"- Treat the attached image as a **{role_phrase}** on the Timeline "
        f"(role=`{role}`), not as an Environment Reference Sheet.\n"
        "- Beats: open on the location look → land character presence → punchline/"
        "turn → exit beat.\n"
        "- Cast / props: keep @Korri / @Cade grammar intact wherever you tagged them; "
        "props stay light unless you call them.\n"
        "- Aspect: vertical 9:16 Timeline plan first.\n"
    )
    if handoff:
        production += (
            f"- **Propose** `{handoff.get('toolId')}` with asset "
            f"`{(handoff.get('arguments') or {}).get('assetId') or 'attached'}` "
            f"— approval-gated; no silent Timeline mutation.\n"
        )
    else:
        production += (
            "- **Propose** Timeline attach for the attached asset as background/supporting "
            "— approval-gated; no silent Timeline mutation.\n"
        )
    production += (
        "- Skipping ERS/CRS/PRS how-to lecture unless you explicitly ask to "
        "create or validate a sheet."
    )
    return f"{companion}\n\n{production}"


def attachment_intent_context_lines(intent: AttachIntentResult) -> list[str]:
    """Extra honesty lines for attachment_context_block."""
    lines = [
        f"Attach intent (user-language override): {intent.intent} "
        f"(role={intent.role}, confidence={intent.confidence:.2f}).",
    ]
    if intent.intent == "visual_discussion":
        lines.append(
            "The creator is DISCUSSING the attached image (look, lighting, mood, "
            "staging). Respond conversationally. Do NOT propose Timeline actions "
            "or attach steps unless the creator asks."
        )
    if intent.intent == "reference_image":
        lines.append(
            "The attached image has no stated use yet. Do not propose Timeline "
            "actions from attachment existence alone — infer or ask the purpose "
            "from the conversation."
        )
    if intent.suppress_ers_lecture:
        lines.append(
            "Do NOT prioritize ers.generate or ERS_SPEC café lecture this turn. "
            "Formal ERS/CRS/PRS only if explicitly requested."
        )
    if intent.propose_timeline_attach:
        lines.append(
            "Propose timeline.attach_optional_reference (or references.attach) "
            "with the attached assetId and role background/supporting. "
            "Approval-gated. Do not silently mutate the Timeline."
        )
    if intent.has_long_creative:
        lines.append(
            "Long screenplay/creative payload present — respond with creative "
            "companion notes AND production Timeline plan together; do not "
            "short-circuit to attachment-only or ERS lecture."
        )
    lines.append(
        "Preserve @Korri / @Cade tag grammar exactly when present in the user message."
    )
    return lines
