"""ERS semantic gate — VLM verdict on generated sheet vs. source environment.

Master prompt §17: after each generation run, a semantic validation answers
"Does this ERS depict the same intended environment?" using the original
source image, the generated ERS, and the environment intent summary.

This gate is ADVISORY (human authority is absolute): the verdict is stamped
onto the sheet provenance and surfaced in the UI with Retry / Use Anyway.
It never blocks persistence, never auto-retries a chargeable generation, and
never fakes a pass — when no VLM is configured the verdict is NOT_VERIFIED.

Verdicts: PASS | ERS_LAYOUT_NONCOMPLIANT | ERS_CONTEXT_NONCOMPLIANT | NOT_VERIFIED
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ERS_GATE_PASS = "PASS"
ERS_GATE_LAYOUT = "ERS_LAYOUT_NONCOMPLIANT"
ERS_GATE_CONTEXT = "ERS_CONTEXT_NONCOMPLIANT"
ERS_GATE_NOT_VERIFIED = "NOT_VERIFIED"

ERS_GATE_VERDICTS = (
    ERS_GATE_PASS,
    ERS_GATE_LAYOUT,
    ERS_GATE_CONTEXT,
    ERS_GATE_NOT_VERIFIED,
)

_DEFAULT_VLM_MODEL = "gemini-3-pro"

_GATE_INSTRUCTIONS = """You are a strict production-design reviewer for an Environment Reference Sheet (ERS).

You are given:
1. The SOURCE environment image (the place the creator is actually building), when available.
2. The GENERATED Environment Reference Sheet image.
3. The environment intent summary (authoritative creator intent).

Answer exactly ONE question: does the generated sheet depict the SAME intended environment as the source / intent?

Verdict rules:
- PASS: the sheet depicts the intended environment (same kind of place, architecture, and mood). Layout may vary.
- ERS_CONTEXT_NONCOMPLIANT: the sheet depicts a DIFFERENT kind of place than the intent (e.g. a living room when the intent is a coffee shop, a spaceship corridor when the intent is a cafe). This is a semantic identity failure.
- ERS_LAYOUT_NONCOMPLIANT: the sheet depicts the right environment but is not a reference sheet (e.g. a single cinematic still, a character turnaround, or missing the required sections).

Respond with EXACTLY this format:
VERDICT: <PASS|ERS_CONTEXT_NONCOMPLIANT|ERS_LAYOUT_NONCOMPLIANT>
REASON: <one sentence, plain language, no jargon>"""


def _data_url(path: Path, *, max_bytes: int = 4_000_000) -> str:
    """Inline a local image as a data URL (bounded). Empty string when too big."""
    try:
        size = path.stat().st_size
        if size <= 0 or size > max_bytes:
            return ""
        raw = path.read_bytes()
    except OSError:
        return ""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def parse_ers_gate_verdict(text: str) -> dict[str, str]:
    """Parse the VLM response. Unknown / empty output degrades to NOT_VERIFIED."""
    raw = str(text or "")
    verdict = ERS_GATE_NOT_VERIFIED
    reason = ""
    match = re.search(
        r"VERDICT:\s*(PASS|ERS_CONTEXT_NONCOMPLIANT|ERS_LAYOUT_NONCOMPLIANT)",
        raw,
        flags=re.IGNORECASE,
    )
    if match:
        verdict = match.group(1).upper()
    reason_match = re.search(r"REASON:\s*(.+)", raw, flags=re.IGNORECASE | re.DOTALL)
    if reason_match:
        reason = reason_match.group(1).strip().splitlines()[0][:400]
    if verdict == ERS_GATE_NOT_VERIFIED and not reason:
        reason = "The reviewer did not return a recognizable verdict."
    return {"verdict": verdict, "summary": reason}


async def run_ers_semantic_gate(
    *,
    generated_image_path: str,
    intent_summary: str,
    sheet_name: str = "",
    source_image_url: str = "",
    model_id: str = _DEFAULT_VLM_MODEL,
) -> dict[str, Any]:
    """One Kie Gemini chat call: source image + generated ERS + intent -> verdict.

    Honest degrade: no VLM configured / no readable generated image /
    provider error all yield NOT_VERIFIED with the reason — never a fake pass.
    """
    from datetime import datetime, timezone

    from ...secrets_store import get_secret

    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _result(verdict: str, summary: str, **extra: Any) -> dict[str, Any]:
        return {
            "verdict": verdict,
            "summary": summary,
            "model": model_id,
            "checkedAt": checked_at,
            "advisory": True,
            **extra,
        }

    api_key = get_secret("kie_api_key")
    if not api_key:
        return _result(
            ERS_GATE_NOT_VERIFIED,
            "Semantic review was not run — no vision-capable provider is configured.",
            reason="no_vlm_configured",
        )

    generated_path = Path(str(generated_image_path or ""))
    if not generated_path.is_file():
        return _result(
            ERS_GATE_NOT_VERIFIED,
            "Semantic review was not run — the generated sheet file is missing.",
            reason="generated_missing",
        )

    generated_url = _data_url(generated_path)
    if not generated_url:
        return _result(
            ERS_GATE_NOT_VERIFIED,
            "Semantic review was not run — the generated sheet could not be read.",
            reason="generated_unreadable",
        )

    content: list[dict[str, Any]] = [{"type": "text", "text": _GATE_INSTRUCTIONS}]
    intent_text = (intent_summary or "").strip() or "(no environment intent was recorded)"
    header = f"Environment Reference Sheet: {sheet_name}\n\nENVIRONMENT INTENT SUMMARY:\n{intent_text}"
    if source_image_url:
        content.append({"type": "text", "text": header + "\n\nIMAGE 1 — SOURCE environment (authority):"})
        content.append({"type": "image_url", "image_url": {"url": source_image_url}})
        content.append({"type": "text", "text": "IMAGE 2 — GENERATED Environment Reference Sheet (under review):"})
    else:
        content.append({"type": "text", "text": header + "\n\nGENERATED Environment Reference Sheet (under review):"})
    content.append({"type": "image_url", "image_url": {"url": generated_url}})

    try:
        from ...hosted_providers.adapters.kie_adapter import chat_kie

        response = await chat_kie(
            api_key,
            model_id=model_id,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
            timeout_sec=90.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ERS semantic gate call failed: %s", exc)
        return _result(
            ERS_GATE_NOT_VERIFIED,
            "Semantic review could not reach the vision provider.",
            reason="vlm_error",
        )

    if not response.get("ok"):
        return _result(
            ERS_GATE_NOT_VERIFIED,
            "Semantic review was not completed by the vision provider.",
            reason=str(response.get("error") or "vlm_error"),
        )

    parsed = parse_ers_gate_verdict(str(response.get("output") or ""))
    return _result(parsed["verdict"], parsed["summary"])


def stamp_ers_gate_verdict(
    *,
    project_id: str,
    sheet_id: str,
    verdict: dict[str, Any],
) -> None:
    """Persist the advisory verdict onto the sheet provenance (frozen contract:
    rides ERSProvenanceRecord.details)."""
    from ...environment_reference_sheet.store import load_sheet, save_sheet

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        return
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    details["semanticGate"] = dict(verdict)
    provenance.details = details
    save_sheet(sheet)


def record_ers_gate_override(
    *,
    project_id: str,
    sheet_id: str,
    actor: str = "creator",
) -> dict[str, Any]:
    """Creator clicked 'Use Anyway' on a non-PASS verdict — explicit approval."""
    from datetime import datetime, timezone

    from ...environment_reference_sheet.store import load_sheet, save_sheet

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        return {"ok": False, "error": "SHEET_NOT_FOUND"}
    provenance = getattr(sheet, "provenance", None)
    details = dict(getattr(provenance, "details", None) or {}) if provenance is not None else {}
    gate = dict(details.get("semanticGate") or {})
    details["semanticGateOverride"] = {
        "decision": "use_anyway",
        "actor": actor,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gateVerdict": gate.get("verdict") or "",
        "note": "Creator explicitly approved this sheet despite the semantic gate verdict.",
    }
    if provenance is not None:
        provenance.details = details
    save_sheet(sheet)
    return {"ok": True, "sheetId": sheet_id, "override": details["semanticGateOverride"]}
