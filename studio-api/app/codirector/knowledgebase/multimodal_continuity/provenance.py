"""Stamp continuity packet provenance onto the image request creativeContext."""

from __future__ import annotations

from typing import Any

from .schema import InstructionPacket


def stamp_continuity_packet(body: dict[str, Any], packet: InstructionPacket) -> dict[str, Any]:
    ctx = body.get("creativeContext")
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    ctx["continuityPacket"] = {
        "compilerVersion": packet.compilerVersion,
        "fingerprint": packet.fingerprint,
        "panelTask": packet.panelTask,
        "provider": packet.provider,
        "sourceAssetId": (packet.referenceImage or {}).get("assetId") or "",
        "sourceType": (packet.referenceImage or {}).get("type") or "",
        "englishPrompt": packet.englishPrompt,
        "chinesePrompt": packet.chinesePrompt,
        "hardInvariants": list(packet.hardInvariants),
        "forbiddenChanges": list(packet.forbiddenChanges),
        "syncOk": packet.syncOk,
        "actors": [a.model_dump() for a in packet.continuityJson.actors],
        "props": [p.model_dump() for p in packet.continuityJson.props],
    }
    body["creativeContext"] = ctx
    return body
