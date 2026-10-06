"""Assistant text cannot manufacture a successful mutation."""

from __future__ import annotations

import json

from .models import ToolReceipt

_SUCCESS_MARKERS = (
    "placed on the timeline",
    "i've placed",
    "i have placed",
    "i've updated",
    "i have updated",
    "i've removed",
    "i have removed",
    "i've set",
    "i have set",
    "i've added",
    "i have added",
    "i set the",
    "i added the",
    "successfully",
    "it's on the timeline",
    "it is on the timeline",
    "saved to the project",
    "change is applied",
    "i applied",
    "voice has been assigned",
    "voice clip is ready",
    "ambience is ready",
    "sound is ready",
)


def project_creator_reply(reply: str) -> str:
    """Normal chat is a sentence. Receipts, ids, and JSON stay out of it."""

    text = (reply or "").strip()
    if not text:
        return text
    parsed = _json_object(text)
    if isinstance(parsed, dict):
        if str(parsed.get("mutation_status") or "") == "proposed":
            return "This is prepared and awaiting approval. Nothing has been placed or created yet."
        message = _creator_message(parsed)
        if message:
            return message
        from .bind import visible_character_matches

        matches = visible_character_matches(parsed)
        if len(matches) == 1:
            name = matches[0]["displayName"]
            return f"I found {name} and I'm using that saved character for the scene."
        if len(matches) > 1:
            name = matches[0]["displayName"]
            return f"I found more than one character named {name}. Which one would you like me to use?"
        if parsed.get("tool_id") or parsed.get("requested_action") or parsed.get("execution_status"):
            return "I looked that up. I'll keep going with what you asked."
        return "I'll keep going in plain language."
    failure = _studio_failure(text)
    if failure:
        return failure
    if _looks_internal(text):
        return "I'll keep going in plain language."
    return text


def _creator_message(value: dict) -> str:
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    evidence = value.get("evidence") if isinstance(value.get("evidence"), dict) else {}
    read = evidence.get("read") if isinstance(evidence.get("read"), dict) else {}
    result = read.get("result") if isinstance(read.get("result"), dict) else {}
    result_data = result.get("data") if isinstance(result.get("data"), dict) else {}
    read_data = read.get("data") if isinstance(read.get("data"), dict) else {}
    candidates = (
        value.get("message"),
        data.get("message"),
        read.get("message"),
        read_data.get("message"),
        result.get("message"),
        result_data.get("message"),
    )
    for item in candidates:
        message = str(item or "").strip()
        if message and not _looks_internal(message):
            return message[:500]
    return ""


def _studio_failure(text: str) -> str | None:
    folded = text.lower()
    if "voice_provider_error" in folded or "durationsec" in folded:
        if "durationsec" in folded:
            return "Audio Studio couldn't create that sound yet."
        return "Voice Studio couldn't start that voice generation."
    if any(marker in folded for marker in ("audio.generate_", "generate_ambience failed", "generate_sfx failed", "generate_music failed")):
        return "Audio Studio couldn't create that sound yet."
    return None


def _json_object(text: str) -> dict | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    if not raw.startswith("{"):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _looks_internal(text: str) -> bool:
    folded = text.lower()
    markers = (
        "requested_action",
        "execution_status",
        "toolreceipt",
        "verifiedmutationreceipt",
        "characterid",
        "projectid",
        "workflowid",
        "traceback (most recent call last)",
        "httstatus=",
        "httpstatus=",
    )
    return any(marker in folded for marker in markers) or "->" in text and "character.search" in folded


def scrub_unverified_success(reply: str, receipts: list[ToolReceipt]) -> str:
    verified = any(item.verification_status == "verified" and item.mutation_status == "written" for item in receipts)
    if verified:
        return reply
    folded = reply.lower()
    if not any(marker in folded for marker in _SUCCESS_MARKERS):
        return reply
    return (
        "I can't confirm that change in the project yet. "
        "Nothing was marked successful without a verified readback."
    )
