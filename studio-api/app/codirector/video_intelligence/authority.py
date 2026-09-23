"""Scene authority reconciliation for Qwen Omni temporal reviews.

Perception law: Qwen Omni observes; it never authors scene content. Raw
observations must be reconciled against the scene's authoritative entities and
dialogue BEFORE they enter continuity memory or the next batch's prompt.

- OBSERVED elements that match scene authority → continuity state.
- UNEXPECTED elements (figures/speech that violate scene authority) → isolated
  as artifacts in packet.extras["artifacts"]; never carried into continuation.
- UNCERTAIN → reported as uncertain; not woven into directives.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SPEECH_MARKERS = ("says", "says:", "says,", "says.", "speaks", "shouts", "whispers", "asks", "replies")


def authorized_character_labels(batch: Any) -> set[str]:
    """Authoritative character labels for a batch, from creator-bound references.

    Uses the batch's approved references (entity/character/characterIdentity
    kinds and identity refs) — NOT anything the review produced.
    """
    labels: set[str] = set()
    refs = list(getattr(batch, "references", None) or [])
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or ref.get("role") or "").lower()
        if kind in {"entity", "character", "characteridentity", "identity", "motion_subject"}:
            for key in ("label", "canonicalTag", "name"):
                val = str(ref.get(key) or "").strip().lstrip("@")
                if val:
                    labels.add(val.lower())
    return labels


def authorized_dialogue_lines(batch: Any) -> set[str]:
    """Authoritative spoken lines for a batch, from its dialogue manifest."""
    lines: set[str] = set()
    manifest = getattr(batch, "dialogueManifest", None)
    entries: list[Any] = []
    if isinstance(manifest, dict):
        entries = list(manifest.get("lines") or manifest.get("entries") or [])
    elif isinstance(manifest, list):
        entries = list(manifest)
    for e in entries:
        text = ""
        if isinstance(e, dict):
            text = str(e.get("text") or e.get("line") or e.get("dialogue") or "")
        else:
            text = str(e or "")
        text = text.strip().strip('"').strip()
        if text:
            lines.add(text.lower())
    return lines


def _mentions_new_person(sentence: str, authorized: set[str]) -> bool:
    """Heuristic: does this sentence introduce a person outside scene authority?

    Triggers on person-introducing nouns when no authorized label appears in
    the sentence and no possessive reference to an authorized character exists.
    """
    low = sentence.lower()
    if any(label in low for label in authorized):
        return False
    person_terms = (
        "woman", "man ", "man,", "man.", "girl", "boy", "person", "figure",
        "stranger", "officer", "guard", "soldier", "crew", "civilian", "child",
        "interviewer", "operator", "technician", "scientist", "people",
    )
    return any(term in low for term in person_terms)


def _looks_like_dialogue(sentence: str, authorized: set[str]) -> bool:
    low = sentence.lower()
    if any(marker in low for marker in _SPEECH_MARKERS):
        # Speech attribution — only a violation if the content is unauthorized.
        quoted = re.findall(r'"([^"]+)"', sentence)
        if quoted:
            return not any(q.strip().lower() in authorized for q in quoted)
        return False
    return False


def reconcile_packet_with_authority(
    packet: Any,
    batch: Any,
) -> Any:
    """Classify observed content vs scene authority; isolate artifacts.

    Continuity-driving fields (continuation, importantEvents, exitState,
    characters, nextBatchDirectives) keep only authority-compatible,
    confidently-observed state. Unexpected detections are preserved verbatim
    in packet.extras["artifacts"] for diagnostics — never deleted, never canon.
    """
    try:
        authorized_chars = authorized_character_labels(batch)
        authorized_lines = authorized_dialogue_lines(batch)

        artifacts: dict[str, list[str]] = {
            "unexpectedCharacters": [],
            "unexpectedDialogue": [],
            "uncertain": [],
        }

        # 1. Structured character observations vs authority.
        chars = list(getattr(packet, "characters", None) or [])
        kept_chars = []
        for ch in chars:
            label = str(getattr(ch, "label", "") or "").strip().lstrip("@").lower()
            if label and authorized_chars and label not in authorized_chars and not any(
                label in auth or auth in label for auth in authorized_chars
            ):
                artifacts["unexpectedCharacters"].append(label)
            else:
                kept_chars.append(ch)
        if len(kept_chars) != len(chars):
            packet.characters = kept_chars

        # 2. Prose-level reconciliation across continuity-driving text fields.
        def _clean_lines(lines: list[str]) -> list[str]:
            kept: list[str] = []
            for line in lines:
                text = str(line or "").strip()
                if not text:
                    continue
                if _mentions_new_person(text, authorized_chars):
                    artifacts["unexpectedCharacters"].append(text[:200])
                    continue
                if _looks_like_dialogue(text, authorized_lines):
                    artifacts["unexpectedDialogue"].append(text[:200])
                    continue
                kept.append(text)
            return kept

        cont = packet.continuation
        cont.continue_ = _clean_lines(list(cont.continue_ or [])) or [
            "Continue the same beat without resetting the shot."
        ]
        cont.nextBatchDirectives = _clean_lines(list(cont.nextBatchDirectives or []))
        packet.importantEvents = [
            ev
            for ev in (packet.importantEvents or [])
            if not _mentions_new_person(str(ev.label or ""), authorized_chars)
        ]
        exit_state = packet.exitState
        if exit_state is not None and _mentions_new_person(str(exit_state.summary or ""), authorized_chars):
            exit_state.summary = ""
            artifacts["uncertain"].append("exitState summary withheld: mentioned entities outside scene authority")

        if any(artifacts.values()):
            packet.extras = dict(packet.extras or {})
            packet.extras["artifacts"] = artifacts
            packet.extras["authorityReconciled"] = True
            logger.warning(
                "Qwen observation contained content outside scene authority: %s",
                {k: v for k, v in artifacts.items() if v},
            )
        else:
            packet.extras = dict(packet.extras or {})
            packet.extras["authorityReconciled"] = True
    except Exception as exc:  # noqa: BLE001 — reconciliation must never fail the review
        logger.debug("authority reconciliation skipped: %s", exc)
    return packet


def authority_question_suffix(batch: Any) -> str:
    """Perception-prompt grounding: tell the reviewer what scene authority allows.

    The reviewer must describe only what is actually visible/audible and must
    report unexpected detections as artifacts, never as scene content.
    """
    try:
        chars = sorted(authorized_character_labels(batch))
        lines = sorted(authorized_dialogue_lines(batch))
        parts: list[str] = [
            "SCENE AUTHORITY (grounding — perception only, no invention):",
            "- Describe ONLY what is actually visible and audible in this clip.",
            "- Do not name, add, or infer any character, prop, dialogue, or event you cannot see or hear.",
        ]
        if chars:
            parts.append(
                "- Authorized characters in this scene: "
                + ", ".join(chars)
                + ". If any other person appears, write exactly: UNEXPECTED VISUAL ARTIFACT: possible unidentified figure observed."
            )
        else:
            parts.append(
                "- No characters are authorized in this scene. If any person appears, write exactly: "
                "UNEXPECTED VISUAL ARTIFACT: possible unidentified figure observed."
            )
        if lines:
            parts.append(
                "- Authorized dialogue: " + " | ".join(f'"{l}"' for l in lines)
                + ". If any other speech is heard, write exactly: UNEXPECTED AUDIO ARTIFACT: possible additional speech detected."
            )
        parts.append(
            "- If something is unclear, say 'uncertain' or 'not observed' — never guess."
        )
        parts.append(
            "- Reply in English only. Do not answer in Chinese or any other language."
        )
        return "\n".join(parts)
    except Exception:
        return ""
