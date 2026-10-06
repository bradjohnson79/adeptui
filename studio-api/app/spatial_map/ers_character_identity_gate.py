"""Occupied ERS identity gate — compare generated still vs approved Character Creator reference."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FAIL_CHARACTER_IDENTITY = "FAIL_CHARACTER_IDENTITY"
PASS = "PASS"
NOT_VERIFIED = "NOT_VERIFIED"


def _asset_path(db: Any, asset_id: str) -> Path | None:
    from ..db import Asset

    row = db.get(Asset, str(asset_id or "").strip())
    if row is None:
        return None
    path = Path(str(getattr(row, "path", "") or ""))
    return path if path.is_file() else None


def parse_identity_verdict(text: str) -> dict[str, str]:
    raw = str(text or "")
    verdict = ""
    match = re.search(r"VERDICT:\s*([A-Z_]+)", raw, re.I)
    if match:
        verdict = match.group(1).upper()
    if verdict not in {PASS, FAIL_CHARACTER_IDENTITY, NOT_VERIFIED}:
        if "FAIL_CHARACTER_IDENTITY" in raw.upper() or "GENERIC" in raw.upper():
            verdict = FAIL_CHARACTER_IDENTITY
        elif re.search(r"\bPASS\b", raw.upper()):
            verdict = PASS
        else:
            verdict = NOT_VERIFIED
    reason_match = re.search(r"REASON:\s*(.+)", raw, re.I)
    reason = (reason_match.group(1).strip() if reason_match else raw.strip())[:400]
    return {"verdict": verdict, "reason": reason}


def expected_identity_failure(display_name: str) -> str:
    return f"Expected {display_name}, but the approved character identity was not verified."


def apply_occupied_identity_gate(
    db: Any,
    project_id: str,
    *,
    asset_id: str,
    packet: dict[str, Any],
    vision_output: str | None = None,
) -> dict[str, Any]:
    del project_id
    names = []
    ref_ids = []
    for item in packet.get("characters") or []:
        if item.get("visible") is False:
            continue
        name = str(item.get("displayName") or item.get("label") or "").strip()
        if name:
            names.append(name)
        ref = str(item.get("referenceAssetId") or "").strip()
        if ref:
            ref_ids.append(ref)
    display = ", ".join(names) or "the approved saved character"
    generated = _asset_path(db, asset_id)
    reference = _asset_path(db, ref_ids[0]) if ref_ids else None
    if generated is None or reference is None:
        return {
            "verdict": FAIL_CHARACTER_IDENTITY,
            "reason": expected_identity_failure(display),
            "characterNames": names,
        }
    if vision_output is not None:
        parsed = parse_identity_verdict(vision_output)
        parsed["characterNames"] = names
        if parsed["verdict"] == FAIL_CHARACTER_IDENTITY:
            parsed["reason"] = expected_identity_failure(display)
        return parsed
    try:
        from ..codirector.vision.vision_review import chat_vision, data_url_from_path

        ref_url = data_url_from_path(reference)
        gen_url = data_url_from_path(generated)
        if not ref_url or not gen_url:
            return {
                "verdict": FAIL_CHARACTER_IDENTITY,
                "reason": expected_identity_failure(display),
                "characterNames": names,
            }
        instructions = (
            "You compare a generated occupied-scale environment still against an approved "
            f"Character Creator reference for {display}.\n"
            "PASS only if the visible person is the same approved character "
            "(face, hair, skin, body, wardrobe). "
            "FAIL_CHARACTER_IDENTITY if the person is generic, anonymous, a different character, "
            "or missing when a named character is required.\n"
            "Respond with EXACTLY:\nVERDICT: <PASS|FAIL_CHARACTER_IDENTITY>\nREASON: <one sentence>"
        )
        parts = [
            {"type": "text", "text": "IMAGE 1 — approved Character Creator reference:"},
            {"type": "image_url", "image_url": {"url": ref_url}},
            {"type": "text", "text": "IMAGE 2 — generated occupied panel:"},
            {"type": "image_url", "image_url": {"url": gen_url}},
        ]

        async def _run() -> dict[str, Any]:
            return await chat_vision(instructions=instructions, parts=parts, temperature=0.0)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            response = asyncio.run(_run())
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(asyncio.run, _run()).result(timeout=120)
        if not response.get("ok"):
            return {
                "verdict": NOT_VERIFIED,
                "reason": str(response.get("error") or "Identity gate could not run."),
                "characterNames": names,
            }
        parsed = parse_identity_verdict(str(response.get("output") or ""))
        parsed["characterNames"] = names
        if parsed["verdict"] == FAIL_CHARACTER_IDENTITY:
            parsed["reason"] = expected_identity_failure(display)
        return parsed
    except Exception as exc:
        logger.warning("Occupied identity gate failed: %s", exc)
        return {
            "verdict": NOT_VERIFIED,
            "reason": str(exc)[:400],
            "characterNames": names,
        }
