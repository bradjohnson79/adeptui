"""Server-authoritative Essential Components agreement.

Acceptance lives in setup_state.json. Browser storage is never enough.
Document-unavailable never auto-accepts. Material version change requires
a new agreement. VGGT gated access does not block MoGe-2 after agreement.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .essentials_pack import ESSENTIAL_IDS
from .license_metadata import essential_registry_rows, is_model_access_gated, license_row
from .state import load_state, update_state

CURRENT_VERSION = "2026.08.1"
EFFECTIVE_DATE = "2026-08-26"
DOCUMENT_RELATIVE_PATH = "docs/setup/ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md"
DOCUMENT_ID = "essential-components-license-and-terms"
ADEPT_APP_VERSION = "adept-ui-2026.08"

AGREEMENT_REQUIRED = "ESSENTIAL_AGREEMENT_REQUIRED"
UPDATED_TERMS = "UPDATED_TERMS_REQUIRE_AGREEMENT"
DOCUMENT_UNAVAILABLE = "ESSENTIAL_NOTICE_UNAVAILABLE"
DECLINED = "ESSENTIAL_AGREEMENT_DECLINED"

_REPO_ROOT = Path(__file__).resolve().parents[3]


class EssentialAgreementError(Exception):
    def __init__(self, payload: dict[str, Any], *, status_code: int = 409):
        super().__init__(str(payload.get("message") or payload.get("code") or "Essential agreement required"))
        self.payload = payload
        self.status_code = status_code


def _document_path() -> Path:
    override = (os.environ.get("ADEPT_ESSENTIAL_NOTICE_PATH") or "").strip()
    if override:
        return Path(override)
    return _REPO_ROOT / DOCUMENT_RELATIVE_PATH


def document_available() -> bool:
    path = _document_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def load_document() -> dict[str, Any]:
    path = _document_path()
    if not document_available():
        return {
            "available": False,
            "version": current_version(),
            "effectiveDate": EFFECTIVE_DATE,
            "documentId": DOCUMENT_ID,
            "documentPath": DOCUMENT_RELATIVE_PATH,
            "documentUrl": "/api/setup/essential-agreement/document",
            "body": "",
            "message": "document unavailable",
        }
    body = path.read_text(encoding="utf-8")
    return {
        "available": True,
        "version": current_version(),
        "effectiveDate": EFFECTIVE_DATE,
        "documentId": DOCUMENT_ID,
        "documentPath": DOCUMENT_RELATIVE_PATH,
        "documentUrl": "/api/setup/essential-agreement/document",
        "body": body,
        "message": "",
    }


def current_version() -> str:
    if os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE", "yes", "YES"}:
        override = str((load_state().get("essential_agreement") or {}).get("e2e_current_version") or "").strip()
        if override:
            return override
    return CURRENT_VERSION


def _empty_record() -> dict[str, Any]:
    return {
        "accepted_version": "",
        "document_path": DOCUMENT_RELATIVE_PATH,
        "document_url": "/api/setup/essential-agreement/document",
        "effective_date": EFFECTIVE_DATE,
        "accepted_at": "",
        "declined_at": "",
        "adept_app_version": "",
        "status": "pending",
    }


def agreement_record() -> dict[str, Any]:
    raw = load_state().get("essential_agreement")
    record = _empty_record()
    if isinstance(raw, dict):
        for key in record:
            if key in raw and raw[key] is not None:
                record[key] = raw[key]
        if raw.get("e2e_current_version"):
            record["e2e_current_version"] = raw.get("e2e_current_version")
    return record


def is_accepted() -> bool:
    if not document_available():
        return False
    record = agreement_record()
    accepted = str(record.get("accepted_version") or "").strip()
    return accepted == current_version() and str(record.get("status") or "") == "accepted"


def eligibility() -> dict[str, Any]:
    record = agreement_record()
    available = document_available()
    accepted = is_accepted()
    accepted_version = str(record.get("accepted_version") or "").strip()
    stale = bool(accepted_version) and accepted_version != current_version()
    declined = str(record.get("status") or "") == "declined"
    if not available:
        code = DOCUMENT_UNAVAILABLE
        message = "The Essential Components notice is unavailable. Retry. Adept will not treat this as accepted."
    elif accepted:
        code = ""
        message = "Essential Components agreement accepted."
    elif stale:
        code = UPDATED_TERMS
        message = "UPDATED TERMS REQUIRE AGREEMENT"
    elif declined:
        code = DECLINED
        message = "Essential Components remain ineligible until you agree."
    else:
        code = AGREEMENT_REQUIRED
        message = "Agree to the Essential Components notice before install or activation."
    return {
        "accepted": accepted,
        "eligible": accepted,
        "documentAvailable": available,
        "currentVersion": current_version(),
        "acceptedVersion": accepted_version or None,
        "effectiveDate": EFFECTIVE_DATE,
        "documentPath": DOCUMENT_RELATIVE_PATH,
        "documentUrl": "/api/setup/essential-agreement/document",
        "acceptedAt": record.get("accepted_at") or None,
        "declinedAt": record.get("declined_at") or None,
        "adeptAppVersion": record.get("adept_app_version") or None,
        "status": "accepted" if accepted else ("document_unavailable" if not available else str(record.get("status") or "pending")),
        "code": code,
        "message": message,
    }


def agreement_payload() -> dict[str, Any]:
    document = load_document()
    state = eligibility()
    return {
        **state,
        "documentId": DOCUMENT_ID,
        "title": "Essential Components license and terms",
        "body": document["body"] if document["available"] else "",
        "registry": essential_registry_rows(),
        "readinessFacts": [
            "Agreement Accepted",
            "Source Installed",
            "Runtime Ready",
            "Commercial Model Access",
            "Model Ready",
            "GPU Ready",
            "Production Certified",
        ],
        "actions": {
            "view": "/api/setup/essential-agreement",
            "openFull": "/api/setup/essential-agreement/document",
            "agree": "/api/setup/essential-agreement/accept",
            "decline": "/api/setup/essential-agreement/decline",
        },
        "notice": {
            "moge2": (
                "Adept permits MoGe-2 under owner policy. Weight terms are pending "
                "official clarification. This record will update if Microsoft or the "
                "MoGe publishers clarify the weights license."
            ),
            "vggt": (
                "VGGT-1B-Commercial is an Essential Spatial Intelligence component. "
                "Commercial model access is gated and independent. A git clone is not Ready. "
                "Gated VGGT access does not block MoGe-2 Express."
            ),
        },
    }


def accept_agreement(*, version: str, document_available_confirmed: bool) -> dict[str, Any]:
    if not document_available() or not document_available_confirmed:
        raise EssentialAgreementError(
            {
                "code": DOCUMENT_UNAVAILABLE,
                "message": "The Essential Components notice is unavailable. Retry. Adept will not treat this as accepted.",
                "eligible": False,
                "accepted": False,
                "currentVersion": current_version(),
            },
            status_code=409,
        )
    offered = str(version or "").strip()
    if offered != current_version():
        raise EssentialAgreementError(
            {
                "code": UPDATED_TERMS if offered else AGREEMENT_REQUIRED,
                "message": "UPDATED TERMS REQUIRE AGREEMENT" if offered else "Agree to the current Essential Components notice.",
                "eligible": False,
                "accepted": False,
                "currentVersion": current_version(),
                "offeredVersion": offered or None,
            },
            status_code=409,
        )
    now = datetime.now(timezone.utc).isoformat()

    def mutate(state: dict[str, Any]) -> None:
        existing = dict(state.get("essential_agreement") or {})
        existing.update(
            {
                "accepted_version": current_version(),
                "document_path": DOCUMENT_RELATIVE_PATH,
                "document_url": "/api/setup/essential-agreement/document",
                "effective_date": EFFECTIVE_DATE,
                "accepted_at": now,
                "declined_at": "",
                "adept_app_version": ADEPT_APP_VERSION,
                "status": "accepted",
            }
        )
        state["essential_agreement"] = existing

    update_state(mutate)
    return agreement_payload()


def decline_agreement() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    def mutate(state: dict[str, Any]) -> None:
        existing = dict(state.get("essential_agreement") or {})
        existing.update(
            {
                "accepted_version": "",
                "document_path": DOCUMENT_RELATIVE_PATH,
                "document_url": "/api/setup/essential-agreement/document",
                "effective_date": EFFECTIVE_DATE,
                "accepted_at": "",
                "declined_at": now,
                "adept_app_version": ADEPT_APP_VERSION,
                "status": "declined",
            }
        )
        state["essential_agreement"] = existing

    update_state(mutate)
    payload = agreement_payload()
    payload["eligible"] = False
    payload["accepted"] = False
    return payload


def reset_agreement_for_e2e(*, current_version_override: str | None = None) -> dict[str, Any]:
    def mutate(state: dict[str, Any]) -> None:
        record = _empty_record()
        if current_version_override:
            record["e2e_current_version"] = current_version_override
        state["essential_agreement"] = record

    update_state(mutate)
    return agreement_payload()


def set_e2e_current_version(version: str) -> dict[str, Any]:
    def mutate(state: dict[str, Any]) -> None:
        existing = dict(state.get("essential_agreement") or _empty_record())
        existing["e2e_current_version"] = str(version or "").strip()
        state["essential_agreement"] = existing

    update_state(mutate)
    return agreement_payload()


def is_essential_component(component_id: str) -> bool:
    return component_id in ESSENTIAL_IDS


def agreement_block(*, action: str, component_id: str | None = None) -> dict[str, Any]:
    state = eligibility()
    code = state["code"] or AGREEMENT_REQUIRED
    message = state["message"]
    if state.get("acceptedVersion") and state["acceptedVersion"] != state["currentVersion"]:
        code = UPDATED_TERMS
        message = "UPDATED TERMS REQUIRE AGREEMENT"
    return {
        "code": code,
        "message": message,
        "eligible": False,
        "accepted": False,
        "action": action,
        "componentId": component_id,
        "currentVersion": state["currentVersion"],
        "acceptedVersion": state["acceptedVersion"],
        "documentAvailable": state["documentAvailable"],
        "documentUrl": state["documentUrl"],
        "independence": {
            "vggtGatedDoesNotBlockMoge2": True,
            "componentReadinessIndependent": True,
        },
    }


def require_essential_agreement(component_id: str, *, action: str = "install") -> None:
    if not is_essential_component(component_id):
        return
    if is_accepted():
        return
    raise EssentialAgreementError(agreement_block(action=action, component_id=component_id), status_code=409)


def independence_gate(component_id: str) -> dict[str, Any]:
    """VGGT access-gated status never blocks unrelated Essential install after agreement."""
    require_essential_agreement(component_id, action="install")
    return {
        "ok": True,
        "componentId": component_id,
        "agreementAccepted": True,
        "modelAccessGated": is_model_access_gated(component_id),
        "blockedByVggt": False,
        "license": license_row(component_id),
    }


def component_readiness_badges(component_id: str, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or {}
    gated = is_model_access_gated(component_id)
    source_installed = bool(runtime.get("sourceInstalled"))
    runtime_ready = bool(runtime.get("runtimeReady"))
    commercial_access = bool(runtime.get("commercialModelAccess"))
    if gated:
        commercial_access = False
        if source_installed and not bool(runtime.get("modelReady")):
            runtime_ready = False
    model_ready = bool(runtime.get("modelReady"))
    gpu_ready = bool(runtime.get("gpuReady"))
    production_certified = bool(runtime.get("productionCertified"))
    return {
        "componentId": component_id,
        "agreementAccepted": is_accepted(),
        "sourceInstalled": source_installed,
        "runtimeReady": runtime_ready,
        "commercialModelAccess": commercial_access,
        "modelReady": model_ready,
        "gpuReady": gpu_ready,
        "productionCertified": production_certified,
        "ready": bool(
            is_accepted()
            and source_installed
            and runtime_ready
            and commercial_access
            and model_ready
            and gpu_ready
            and production_certified
        ),
        "license": license_row(component_id),
    }
