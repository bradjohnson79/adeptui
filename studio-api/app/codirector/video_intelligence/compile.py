"""Compile a TemporalContinuityPacket into adapter-honest continuation text."""

from __future__ import annotations

from typing import Any

from .contracts import TemporalContinuityPacket


def compile_temporal_continuation(
    packet: TemporalContinuityPacket | None,
    *,
    supports_prompt_continuation: bool,
    creator_rejected: bool = False,
) -> dict[str, Any]:
    if packet is None:
        return {
            "applied": False,
            "reason": "NO_PACKET",
            "promptPrefix": "",
            "directives": [],
        }
    if packet.availability == "unavailable":
        return {
            "applied": False,
            "reason": packet.reason or "UNAVAILABLE",
            "promptPrefix": "",
            "directives": [],
            "packetId": packet.packetId,
            "availability": packet.availability,
        }
    if creator_rejected:
        return {
            "applied": False,
            "reason": "CREATOR_REJECTED",
            "promptPrefix": "",
            "directives": [],
            "packetId": packet.packetId,
            "availability": packet.availability,
        }
    if not supports_prompt_continuation:
        return {
            "applied": False,
            "reason": "GENERATOR_NO_PROMPT_CONTINUATION",
            "promptPrefix": "",
            "directives": [],
            "packetId": packet.packetId,
            "availability": packet.availability,
        }

    cont = packet.continuation
    lines = ["Co-Director visual continuity (do not restart the shot):"]
    for label, items in (
        ("Preserve", cont.preserve),
        ("Continue", cont.continue_),
        ("Avoid", cont.avoid),
        ("Next", cont.nextBatchDirectives),
    ):
        for item in items:
            text = str(item).strip()
            if text:
                lines.append(f"- {label}: {text}")
    prefix = "\n".join(lines).strip()
    return {
        "applied": True,
        "reason": None,
        "promptPrefix": prefix,
        "directives": list(cont.nextBatchDirectives),
        "packetId": packet.packetId,
        "availability": packet.availability,
        "decision": packet.decision,
        "supportsTemporalConditioning": False,
    }
