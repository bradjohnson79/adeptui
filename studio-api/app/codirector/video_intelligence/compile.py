"""Compile a TemporalContinuityPacket into adapter-honest continuation text."""

from __future__ import annotations

from typing import Any

from app.director_timeline_w46.generation.window_script import scrub_observation_line

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
            item_text = scrub_observation_line(str(item))
            if item_text:
                lines.append(f"- {label}: {item_text}")
    # Full-clip Continuity: surface early/mid events and exit state into N+1 prompt.
    for ev in list(packet.importantEvents or [])[:4]:
        phase = getattr(ev, "phase", "unknown")
        label = str(getattr(ev, "label", "") or "").strip()
        label = scrub_observation_line(label)
        if label:
            lines.append(f"- Event({phase}): {label}")
    assessment = getattr(packet, "assessment", None)
    observed = str(getattr(assessment, "observedState", "") or "").strip() if assessment else ""
    if observed and observed != "Visual review produced no description.":
        json_at = observed.rfind("{")
        prose = observed[:json_at].strip() if json_at > 0 else observed
        prose = " ".join(prose.split())
        if len(prose) > 700:
            prose = prose[:700].rsplit(" ", 1)[0].strip()
        if prose:
            prose = scrub_observation_line(prose)
        if prose:
            lines.append(f"- Watched: {prose}")
    if packet.exitState is not None:
        exit_state = packet.exitState
        exit_summary = scrub_observation_line(str(exit_state.summary or ""))
        if exit_summary:
            lines.append(f"- Exit: {exit_summary}")
        if str(getattr(exit_state, "cameraState", "") or "").strip():
            lines.append(f"- ExitCamera: {str(exit_state.cameraState).strip()}")
        if str(getattr(exit_state, "environmentState", "") or "").strip():
            lines.append(f"- ExitPlace: {str(exit_state.environmentState).strip()}")
        for state in list(getattr(exit_state, "characterStates", None) or [])[:4]:
            state_text = scrub_observation_line(str(state))
            if state_text:
                lines.append(f"- ExitPerson: {state_text}")
    if packet.rollingSceneDigest is not None:
        digest = packet.rollingSceneDigest
        for item in list(digest.preserve or [])[:2]:
            item_text = str(item).strip()
            if item_text and f"- Preserve: {item_text}" not in lines:
                lines.append(f"- ScenePreserve: {item_text}")
    window_kind = (packet.extras or {}).get("reviewWindowKind")
    if window_kind:
        lines.append(f"- ReviewWindow: {window_kind}")
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
        "reviewWindowKind": window_kind,
        "importantEventCount": len(packet.importantEvents or []),
    }
