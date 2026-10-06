"""Character Creator V2 generator inventory and per-view resolution.

Front without a reference uses that family's text-to-image path.
Front with a reference uses that family's reference-conditioned path.
Back / Close-up always bind approved Front pixels. Never remap T2I↔I2I.
"""

from __future__ import annotations

from typing import Any

from .crs_view_generation import (
    CRS_VIEW_FLUX_I2I,
    CRS_VIEW_FLUX_T2I,
    CRS_VIEW_ILLUSTRIOUS_T2I,
    CRS_VIEW_QWEN_T2I,
    flux_img2img_is_identity_conditioning,
    normalize_crs_view_family,
)

AUTO_ID = "auto"
AUTO_T2I_PRIORITY = ("flux", "qwen2512", "zimage", "illustrious", "gpt-image-2")
AUTO_I2I_PRIORITY = ("flux", "qwen2512", "zimage", "gpt-image-2")
AUTO_REF_PRIORITY = AUTO_I2I_PRIORITY

V2_QWEN_REF = "qwen2512.ref"
V2_FLUX_I2I = CRS_VIEW_FLUX_I2I
V2_FLUX_T2I = CRS_VIEW_FLUX_T2I
V2_QWEN_T2I = CRS_VIEW_QWEN_T2I
V2_ZIMAGE_REF = "zimage.ref_edit"
V2_ZIMAGE_T2I = "zimage.txt2img"
V2_ILLUSTRIOUS_T2I = CRS_VIEW_ILLUSTRIOUS_T2I

LOCAL_ADAPTERS: tuple[dict[str, Any], ...] = (
    {
        "id": "flux",
        "family": "flux",
        "label": "FLUX",
        "origin": "local",
        "provider": "comfyui",
        "t2iKey": V2_FLUX_T2I,
        "refKey": V2_FLUX_I2I,
        "identityRef": True,
    },
    {
        "id": "qwen2512",
        "family": "qwen2512",
        "label": "Qwen Image",
        "origin": "local",
        "provider": "comfyui",
        "t2iKey": V2_QWEN_T2I,
        "refKey": V2_QWEN_REF,
        "identityRef": True,
    },
    {
        "id": "illustrious",
        "family": "illustrious",
        "label": "Illustrious",
        "origin": "local",
        "provider": "comfyui",
        "t2iKey": V2_ILLUSTRIOUS_T2I,
        "refKey": None,
        "identityRef": False,
    },
    {
        "id": "zimage",
        "family": "zimage",
        "label": "Z-Image",
        "origin": "local",
        "provider": "comfyui",
        "t2iKey": V2_ZIMAGE_T2I,
        "refKey": V2_ZIMAGE_REF,
        "identityRef": True,
    },
)


class GeneratorUnavailable(ValueError):
    def __init__(self, message: str, *, code: str = "GENERATOR_UNAVAILABLE"):
        super().__init__(message)
        self.code = code


def is_txt2img_workflow_key(workflow_key: str | None) -> bool:
    key = str(workflow_key or "").strip().lower()
    return bool(key) and (key.endswith(".txt2img") or ".txt2img" in key)


def is_i2i_workflow_key(workflow_key: str | None) -> bool:
    key = str(workflow_key or "").strip().lower()
    if not key or is_txt2img_workflow_key(key):
        return False
    return key.endswith((".ref", ".img2img", ".ref_edit", ".edit")) or ".img2img" in key


def _certified_any(workflow_key: str | None) -> Any | None:
    if not workflow_key:
        return None
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(workflow_key)
    except Exception:
        return None
    if not wf or getattr(wf, "status", None) != "Certified":
        return None
    return wf


def _disk_ready(family: str) -> bool:
    try:
        from ..imagegen_workflows import _family_verified_on_disk

        return bool(_family_verified_on_disk(family))
    except Exception:
        return False


def _workflow_status(workflow_key: str | None) -> str:
    if not workflow_key:
        return ""
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(workflow_key)
    except Exception:
        return ""
    return str(getattr(wf, "status", "") or "") if wf else ""


def _t2i_workflow_ok(spec: dict[str, Any]) -> bool:
    key = spec.get("t2iKey")
    if not key or not is_txt2img_workflow_key(str(key)):
        return False
    return _certified_any(str(key)) is not None


def _ref_workflow_ok(spec: dict[str, Any]) -> bool:
    key = spec.get("refKey")
    if not key or is_txt2img_workflow_key(str(key)):
        return False
    wf = _certified_any(str(key))
    if wf is None:
        return False
    if spec["id"] == "flux":
        return flux_img2img_is_identity_conditioning(str(key))
    inputs = {str(x).strip().lower() for x in (getattr(wf, "required_inputs", ()) or ())}
    return bool(inputs & {"source_image", "reference_image"})


def _op(
    *,
    key: str | None,
    ok: bool,
    disk: bool,
    label: str,
    view: str,
    mode: str | None,
    missing: str,
    not_ok: str,
) -> dict[str, Any]:
    available = ok and disk and bool(key)
    reason = ""
    if key is None:
        reason = missing
    elif not ok:
        reason = not_ok
    elif not disk:
        reason = f"{label} needs setup before {view} can run."
    return {
        "available": available,
        "workflowKey": key if ok else None,
        "status": (
            "Available"
            if available
            else ("Requires Setup" if ok and not disk else "Unavailable")
        ),
        "reason": reason,
        "mode": mode if ok else None,
    }


def _local_entries(*, has_reference: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in LOCAL_ADAPTERS:
        disk = _disk_ready(spec["family"])
        t2i_ok = _t2i_workflow_ok(spec)
        ref_ok = _ref_workflow_ok(spec)
        from_desc = _op(
            key=spec.get("t2iKey"),
            ok=t2i_ok,
            disk=disk,
            label=spec["label"],
            view="front",
            mode="txt2img",
            missing=f"{spec['label']} has no text-to-image path for Character Creator.",
            not_ok=f"{spec['label']} text-to-image is not ready for Character Creator.",
        )
        from_ref = _op(
            key=spec.get("refKey"),
            ok=ref_ok,
            disk=disk,
            label=spec["label"],
            view="front",
            mode="ref" if str(spec.get("refKey") or "").endswith(".ref") else "img2img",
            missing=f"{spec['label']} is unavailable for Character Creator when a reference is attached — no reference generation.",
            not_ok=f"{spec['label']} cannot bind reference pixels for front.",
        )
        back = _op(
            key=spec.get("refKey"),
            ok=ref_ok,
            disk=disk,
            label=spec["label"],
            view="back",
            mode="ref" if str(spec.get("refKey") or "").endswith(".ref") else "img2img",
            missing=f"{spec['label']} cannot create Back from Front pixels.",
            not_ok=f"{spec['label']} cannot bind Front pixels for Back.",
        )
        closeup = _op(
            key=spec.get("refKey"),
            ok=ref_ok,
            disk=disk,
            label=spec["label"],
            view="closeup",
            mode="ref" if str(spec.get("refKey") or "").endswith(".ref") else "img2img",
            missing=f"{spec['label']} cannot create a Close-up from the Front picture.",
            not_ok=f"{spec['label']} cannot bind Front pixels for Close-up.",
        )
        front = from_ref if has_reference else from_desc
        if spec.get("refKey") is None and has_reference:
            hint = f"{spec['label']} · Unavailable with a reference"
        elif front["available"]:
            hint = f"{spec['label']} · Available"
        else:
            hint = f"{spec['label']} · {front['status']}"
        out.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "label": spec["label"],
                "display": f"{spec['label']} · Local",
                "origin": "local",
                "localOrApi": "local",
                "provider": spec["provider"],
                "providerKind": "local",
                "hostedModelId": None,
                "status": front["status"],
                "hint": hint,
                "selectable": front["available"] or back["available"],
                "operations": {
                    "front": front,
                    "frontFromDescription": from_desc,
                    "frontFromReference": from_ref,
                    "back": back,
                    "closeup": closeup,
                },
            }
        )
    return out


def _kie_configured() -> tuple[bool, str]:
    try:
        from ..secrets_store import secret_status

        status = secret_status("kie_api_key")
    except Exception:
        return False, "Requires Setup"
    if status.get("state") == "verified" or status.get("configured"):
        return True, "Available" if status.get("state") == "verified" else "Testing"
    return False, "Requires Setup"


def _api_entries(*, has_reference: bool) -> list[dict[str, Any]]:
    configured, api_status = _kie_configured()
    i2i = False
    try:
        from ..hosted_providers.adapters.kie_adapter import kie_image_supports_i2i

        i2i = bool(kie_image_supports_i2i("gpt-image-2-kie"))
    except Exception:
        i2i = False
    t2i_ok = configured
    i2i_ok = configured and i2i
    from_desc = {
        "available": t2i_ok,
        "workflowKey": None,
        "hostedModelId": "gpt-image-2-kie",
        "status": api_status if t2i_ok else "Requires Setup",
        "reason": "" if t2i_ok else "GPT Image needs an API key before Front can run.",
        "mode": "txt2img" if t2i_ok else None,
    }
    from_ref = {
        "available": i2i_ok,
        "workflowKey": None,
        "hostedModelId": "gpt-image-2-kie",
        "status": api_status if i2i_ok else ("Unavailable" if configured else "Requires Setup"),
        "reason": (
            ""
            if i2i_ok
            else (
                "GPT Image needs an API key before Front can run."
                if not configured
                else "GPT Image cannot use a reference picture for Character Creator."
            )
        ),
        "mode": "img2img" if i2i_ok else None,
    }
    back = dict(from_ref)
    if not i2i_ok and configured:
        back["reason"] = "GPT Image · Back unsupported"
    front = from_ref if has_reference else from_desc
    return [
        {
            "id": "gpt-image-2",
            "family": "gpt-image-2",
            "label": "GPT Image",
            "display": "GPT Image · API",
            "origin": "api",
            "localOrApi": "api",
            "provider": "kie",
            "providerKind": "api",
            "hostedModelId": "gpt-image-2-kie",
            "status": front["status"],
            "hint": "GPT Image · API" + ("" if front["available"] else " — not ready for this step"),
            "selectable": front["available"] or back["available"],
            "operations": {
                "front": front,
                "frontFromDescription": from_desc,
                "frontFromReference": from_ref,
                "back": back,
                "closeup": back,
            },
        }
    ]


def list_v2_generators(*, has_reference: bool = False) -> dict[str, Any]:
    local = _local_entries(has_reference=has_reference)
    api = _api_entries(has_reference=has_reference)
    front_order = AUTO_I2I_PRIORITY if has_reference else AUTO_T2I_PRIORITY
    auto_front = next(
        (
            g["id"]
            for fam in front_order
            for g in local + api
            if g["id"] == fam and (g["operations"]["front"].get("available"))
        ),
        None,
    )
    auto_back = next(
        (
            g["id"]
            for fam in AUTO_REF_PRIORITY
            for g in local + api
            if g["id"] == fam and (g["operations"]["back"].get("available"))
        ),
        None,
    )
    retired_back = {
        "available": False,
        "status": "retired",
        "reason": "Use Generate Character Angles for Side, 3/4, and Back.",
        "chooses": None,
    }
    generators = []
    for row in local + api:
        ops = dict(row.get("operations") or {})
        ops["back"] = {**retired_back}
        generators.append({**row, "operations": ops})
    return {
        "hasReference": bool(has_reference),
        "auto": {
            "id": AUTO_ID,
            "label": "Auto",
            "display": "Auto",
            "origin": "auto",
            "localOrApi": "auto",
            "status": "Available" if auto_front else "Unavailable",
            "operations": {
                "front": {"available": bool(auto_front), "chooses": auto_front},
                "back": retired_back,
                "closeup": {"available": bool(auto_back), "chooses": auto_back},
            },
        },
        "generators": generators,
    }


def resolve_v2_generation(
    *,
    view: str,
    generator_id: str | None,
    has_front_ref: bool = False,
) -> dict[str, Any]:
    """Resolve the adapter that will actually run. Never substitutes a different family."""
    wants_ref = bool(has_front_ref) or view in {"back", "closeup"}
    inventory = list_v2_generators(has_reference=wants_ref)
    by_id = {row["id"]: row for row in inventory["generators"]}
    requested = normalize_crs_view_family(generator_id)
    if str(generator_id or "").strip().lower() in {"", "auto"}:
        requested = ""

    if view in {"back", "closeup"}:
        order = AUTO_REF_PRIORITY
        op_name = view
    elif wants_ref:
        order = AUTO_I2I_PRIORITY
        op_name = "frontFromReference"
    else:
        order = AUTO_T2I_PRIORITY
        op_name = "frontFromDescription"

    if not requested:
        for fam in order:
            row = by_id.get(fam)
            op = (row.get("operations") or {}).get(op_name) if row else None
            if row and op and op.get("available"):
                return _route(row, view, selected_as=AUTO_ID, op_name=op_name, has_front_ref=wants_ref)
        raise GeneratorUnavailable(
            "No Character Creator generator is available for this view."
        )

    row = by_id.get(requested)
    if row is None:
        raise GeneratorUnavailable(f"Unknown Character Creator generator: {requested}")
    op = (row.get("operations") or {}).get(op_name) or {}
    if not op.get("available"):
        raise GeneratorUnavailable(
            str(op.get("reason") or f"{row.get('label') or requested} is unavailable for this view.")
        )
    return _route(row, view, selected_as=requested, op_name=op_name, has_front_ref=wants_ref)


def _route(
    row: dict[str, Any],
    view: str,
    *,
    selected_as: str,
    op_name: str,
    has_front_ref: bool,
) -> dict[str, Any]:
    op = (row.get("operations") or {}).get(op_name) or {}
    origin = str(row.get("origin") or "local")
    workflow_key = op.get("workflowKey")
    if view in {"back", "closeup"} and is_txt2img_workflow_key(workflow_key):
        raise GeneratorUnavailable(
            "Back and Close-up are created from the approved Front picture, not from text.",
            code="I2I_REQUIRED",
        )
    if view == "front" and has_front_ref and origin == "local" and is_txt2img_workflow_key(workflow_key):
        raise GeneratorUnavailable(
            "A reference picture is attached, so Character Creator must use reference generation.",
            code="I2I_REQUIRED",
        )
    if view == "front" and not has_front_ref and origin == "local" and is_i2i_workflow_key(workflow_key):
        raise GeneratorUnavailable(
            "No reference picture is attached, so Character Creator must use text-to-image.",
            code="T2I_REQUIRED",
        )
    mode = str(op.get("mode") or "")
    if not mode:
        if is_txt2img_workflow_key(workflow_key):
            mode = "txt2img"
        elif str(workflow_key or "").endswith(".ref"):
            mode = "ref"
        else:
            mode = "img2img" if origin == "local" else "txt2img"
    return {
        "id": row["id"],
        "family": row["family"],
        "label": row["label"],
        "display": row["display"],
        "origin": origin,
        "localOrApi": "api" if origin == "api" else "local",
        "provider": row.get("provider"),
        "providerKind": row.get("providerKind") or ("api" if origin == "api" else "local"),
        "hostedModelId": row.get("hostedModelId"),
        "workflowKey": workflow_key,
        "view": view,
        "selectedAs": selected_as,
        "mode": mode,
        "hasReference": bool(has_front_ref),
    }
