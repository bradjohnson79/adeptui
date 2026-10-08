"""Local acknowledgement gate for third-party model licenses.

Adept UI does not grant the model license. The provider does.
This module stores a local acknowledgement and decides whether the existing
Setup installer may run. It does not download models or collect documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .state import load_state, update_state
from ..minimax_h3.capability import is_excluded_territory

MODEL_ID_H3 = "minimax-h3"
LICENSE_VERSION_H3 = "2026-08-02"
LICENSE_NAME_H3 = "MiniMax H3 Community License"
LICENSE_URL_H3 = "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE"
OFFICIAL_SOURCE_H3 = "https://huggingface.co/MiniMaxAI/MiniMax-H3"
AUTHORIZATION_URL_H3 = "https://platform.minimax.io/h3-license"

STATUS_NONE = "NO LICENSE REQUIRED"
STATUS_SETUP = "LICENSE SETUP REQUIRED"
STATUS_CONFIRMED = "LICENSE CONFIRMED"
STATUS_SEPARATE = "SEPARATE AUTHORIZATION REQUIRED"
STATUS_UNVERIFIED = "LICENSE SETUP REQUIRED"

ROUTE_STANDARD = "standard"
ROUTE_SEPARATE = "separate_authorization"

# Region list is user-selected. Eligibility uses the existing H3 excluded-territory
# check (EU, UK, Republic of Korea, United States). Empty or unknown codes stay locked.
_REGIONS: tuple[tuple[str, str], ...] = (
    ("AR", "Argentina"),
    ("AU", "Australia"),
    ("AT", "Austria"),
    ("BE", "Belgium"),
    ("BR", "Brazil"),
    ("BG", "Bulgaria"),
    ("CA", "Canada"),
    ("CL", "Chile"),
    ("CN", "China"),
    ("CO", "Colombia"),
    ("HR", "Croatia"),
    ("CY", "Cyprus"),
    ("CZ", "Czechia"),
    ("DK", "Denmark"),
    ("EG", "Egypt"),
    ("EE", "Estonia"),
    ("FI", "Finland"),
    ("FR", "France"),
    ("DE", "Germany"),
    ("GR", "Greece"),
    ("HK", "Hong Kong"),
    ("HU", "Hungary"),
    ("IS", "Iceland"),
    ("IN", "India"),
    ("ID", "Indonesia"),
    ("IE", "Ireland"),
    ("IL", "Israel"),
    ("IT", "Italy"),
    ("JP", "Japan"),
    ("KE", "Kenya"),
    ("LV", "Latvia"),
    ("LT", "Lithuania"),
    ("LU", "Luxembourg"),
    ("MY", "Malaysia"),
    ("MT", "Malta"),
    ("MX", "Mexico"),
    ("NL", "Netherlands"),
    ("NZ", "New Zealand"),
    ("NG", "Nigeria"),
    ("NO", "Norway"),
    ("PE", "Peru"),
    ("PH", "Philippines"),
    ("PL", "Poland"),
    ("PT", "Portugal"),
    ("RO", "Romania"),
    ("SA", "Saudi Arabia"),
    ("SG", "Singapore"),
    ("SK", "Slovakia"),
    ("SI", "Slovenia"),
    ("ZA", "South Africa"),
    ("KR", "South Korea"),
    ("ES", "Spain"),
    ("SE", "Sweden"),
    ("CH", "Switzerland"),
    ("TW", "Taiwan"),
    ("TH", "Thailand"),
    ("TR", "Turkey"),
    ("UA", "Ukraine"),
    ("AE", "United Arab Emirates"),
    ("GB", "United Kingdom"),
    ("US", "United States"),
    ("VN", "Vietnam"),
)


class ModelLicenseLocked(Exception):
    def __init__(self, view: dict[str, Any]):
        super().__init__(str(view.get("message") or "License setup required"))
        self.view = view


def _h3_definition() -> dict[str, Any]:
    return {
        "modelId": MODEL_ID_H3,
        "displayName": "MiniMax H3",
        "role": "Local AI Video Generation",
        "provider": "MiniMax",
        "licenseName": LICENSE_NAME_H3,
        "licenseVersion": LICENSE_VERSION_H3,
        "licenseUrl": LICENSE_URL_H3,
        "officialSource": OFFICIAL_SOURCE_H3,
        "authorizationUrl": AUTHORIZATION_URL_H3,
        "requiresAcknowledgement": True,
        "attributionRequired": True,
        "componentIds": ("minimax_h3_base_optimized",),
        "componentPrefix": "minimax_h3",
        "regions": [
            {"code": code, "name": name, "route": ROUTE_SEPARATE if is_excluded_territory(code) else ROUTE_STANDARD}
            for code, name in _REGIONS
        ],
    }


_DEFINITIONS: dict[str, dict[str, Any]] = {MODEL_ID_H3: _h3_definition()}


def definitions() -> dict[str, dict[str, Any]]:
    return _DEFINITIONS


def definition_for(model_id: str) -> dict[str, Any] | None:
    row = _DEFINITIONS.get(model_id)
    return dict(row) if row else None


def model_id_for_component(component_id: str) -> str | None:
    for model_id, row in _DEFINITIONS.items():
        if component_id in row.get("componentIds", ()):
            return model_id
        prefix = str(row.get("componentPrefix") or "")
        if prefix and component_id.startswith(prefix):
            return model_id
    return None


def verified(definition: dict[str, Any] | None) -> bool:
    if not definition:
        return False
    required = ("modelId", "licenseName", "licenseVersion", "licenseUrl", "officialSource", "provider")
    if any(not str(definition.get(key) or "").strip() for key in required):
        return False
    regions = definition.get("regions") or []
    return bool(regions) and all(item.get("code") and item.get("route") for item in regions)


def route_for_region(definition: dict[str, Any], region: str) -> str | None:
    code = region.strip().upper()
    for item in definition.get("regions") or []:
        if str(item.get("code") or "").upper() == code:
            route = str(item.get("route") or "")
            if route in {ROUTE_STANDARD, ROUTE_SEPARATE}:
                return route
    return None


def _records() -> dict[str, Any]:
    raw = load_state().get("model_license_acknowledgements")
    return dict(raw) if isinstance(raw, dict) else {}


def record_for(model_id: str) -> dict[str, Any] | None:
    raw = _records().get(model_id)
    return dict(raw) if isinstance(raw, dict) else None


def _status(definition: dict[str, Any] | None, record: dict[str, Any] | None) -> dict[str, Any]:
    if not verified(definition):
        return {
            "status": STATUS_UNVERIFIED,
            "installationUnlocked": False,
            "verified": False,
            "message": "MiniMax H3 licensing information could not be verified.",
            "route": "",
            "region": "",
        }
    assert definition is not None
    if not definition.get("requiresAcknowledgement"):
        return {
            "status": STATUS_NONE,
            "installationUnlocked": True,
            "verified": True,
            "message": "",
            "route": "",
            "region": "",
        }
    version = str(definition.get("licenseVersion") or "")
    stored_version = str((record or {}).get("license_version") or "")
    acknowledged = bool((record or {}).get("acknowledged")) and stored_version == version
    region = str((record or {}).get("region") or "")
    route = str((record or {}).get("route") or "")
    if acknowledged and route == ROUTE_SEPARATE:
        return {
            "status": STATUS_CONFIRMED,
            "installationUnlocked": True,
            "verified": True,
            "message": "You have confirmed the applicable MiniMax licensing requirements.",
            "route": route,
            "region": region,
        }
    if acknowledged and route == ROUTE_STANDARD:
        return {
            "status": STATUS_CONFIRMED,
            "installationUnlocked": True,
            "verified": True,
            "message": "You have confirmed the applicable MiniMax licensing requirements.",
            "route": route,
            "region": region,
        }
    if region and route == ROUTE_SEPARATE and not acknowledged:
        return {
            "status": STATUS_SEPARATE,
            "installationUnlocked": False,
            "verified": True,
            "message": "Separate MiniMax authorization is required for your region.",
            "route": route,
            "region": region,
        }
    return {
        "status": STATUS_SETUP,
        "installationUnlocked": False,
        "verified": True,
        "message": "License setup required",
        "route": "",
        "region": region,
    }


def public_view(model_id: str, *, definition: dict[str, Any] | None = None) -> dict[str, Any]:
    row = definition if definition is not None else definition_for(model_id)
    state = _status(row, record_for(model_id) if definition is None else None)
    base = row or {"modelId": model_id, "displayName": "MiniMax H3", "provider": "MiniMax", "officialSource": OFFICIAL_SOURCE_H3}
    return {
        "modelId": str(base.get("modelId") or model_id),
        "displayName": base.get("displayName") or "MiniMax H3",
        "role": base.get("role") or "",
        "provider": base.get("provider") or "",
        "licenseName": base.get("licenseName") or "",
        "licenseVersion": base.get("licenseVersion") or "",
        "licenseUrl": base.get("licenseUrl") or "",
        "officialSource": base.get("officialSource") or OFFICIAL_SOURCE_H3,
        "authorizationUrl": base.get("authorizationUrl") or "",
        "requiresAcknowledgement": bool(base.get("requiresAcknowledgement", True)),
        "attributionRequired": bool(base.get("attributionRequired")),
        "regions": list(base.get("regions") or []),
        **state,
    }


def license_summary_for_component(component_id: str) -> dict[str, Any] | None:
    model_id = model_id_for_component(component_id)
    if not model_id:
        return None
    view = public_view(model_id)
    view.pop("regions", None)
    return view


def assert_installation_allowed(component_id: str) -> None:
    summary = license_summary_for_component(component_id)
    if summary is None:
        return
    if not summary.get("installationUnlocked"):
        raise ModelLicenseLocked(summary)


def acknowledge(model_id: str, region: str, confirmed: bool) -> dict[str, Any]:
    definition = definition_for(model_id)
    if definition is None:
        raise ValueError("No license definition for this model.")
    if not verified(definition):
        raise ModelLicenseLocked(public_view(model_id, definition=definition))
    assert definition is not None
    if not confirmed:
        raise ValueError("Acknowledgement is required.")
    route = route_for_region(definition, region)
    if route is None:
        raise ValueError("Select a country or region from the list.")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    saved = {
        "model": model_id,
        "license": definition["licenseName"],
        "license_version": definition["licenseVersion"],
        "license_url": definition["licenseUrl"],
        "route": route,
        "region": region.strip().upper(),
        "acknowledged": True,
        "acknowledged_at": now,
    }

    def mutate(state: dict[str, Any]) -> None:
        bucket = state.setdefault("model_license_acknowledgements", {})
        if not isinstance(bucket, dict):
            bucket = {}
            state["model_license_acknowledgements"] = bucket
        bucket[model_id] = saved

    update_state(mutate)
    return public_view(model_id)


def simulate(case: str) -> dict[str, Any]:
    """Deterministic license-gate cases. Does not download a model or write state."""
    definition = definition_for(MODEL_ID_H3)
    assert definition is not None
    if case == "LICENSE METADATA FAILURE":
        broken = {**definition, "licenseUrl": "", "licenseVersion": "", "regions": []}
        view = public_view(MODEL_ID_H3, definition=broken)
        return {"case": case, "installationUnlocked": False, "status": view["status"], "verified": False}
    if case == "NO ACKNOWLEDGEMENT":
        view = _status(definition, None)
        return {"case": case, "installationUnlocked": False, "status": view["status"]}
    if case == "STANDARD LICENSE":
        view = _status(definition, None)
        route = route_for_region(definition, "CA")
        return {
            "case": case,
            "installationUnlocked": False,
            "status": view["status"],
            "route": route,
            "requiresAcknowledgement": True,
        }
    if case == "SEPARATE AUTHORIZATION":
        route = route_for_region(definition, "US")
        pending = _status(definition, {"region": "US", "route": route, "acknowledged": False, "license_version": ""})
        return {
            "case": case,
            "installationUnlocked": False,
            "status": pending["status"],
            "route": route,
            "authorizationUrl": definition["authorizationUrl"],
        }
    if case == "ACKNOWLEDGED":
        record = {
            "acknowledged": True,
            "license_version": definition["licenseVersion"],
            "route": ROUTE_STANDARD,
            "region": "CA",
        }
        view = _status(definition, record)
        return {"case": case, "installationUnlocked": True, "status": view["status"]}
    if case == "LICENSE VERSION CHANGED":
        record = {
            "acknowledged": True,
            "license_version": "1999-01-01",
            "route": ROUTE_STANDARD,
            "region": "CA",
        }
        view = _status(definition, record)
        return {"case": case, "installationUnlocked": False, "status": view["status"]}
    raise KeyError(case)
