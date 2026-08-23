"""CRS_VIEW_GENERATION — one canonical character view, not a five-view pack.

Task type determines workflow.

AUTO / omitted: FLUX is primary (flux.txt2img, or flux.img2img only with a
real IDENTITY_REFERENCE crop that the graph uses as identity conditioning).
Qwen txt2img is fallback only when FLUX is unavailable. AUTO never selects
Krea.

Explicit family (qwen2512, flux, illustrious, gpt-image-2): that family's
isolated txt2img is used. Explicit krea2 is refused on this path.

Never ERS / scene / contact-sheet / collage / qwen2512.ref / extras.
"""

from __future__ import annotations

from typing import Any

CRS_VIEW_GENERATION_TASK = "CRS_VIEW_GENERATION"
CRS_VIEW_DEFAULT_VIEW = "front_full"
CRS_VIEW_ROLE = "hero_identity"

CRS_VIEW_FLUX_T2I = "flux.txt2img"
CRS_VIEW_FLUX_I2I = "flux.img2img"
CRS_VIEW_QWEN_T2I = "qwen2512.txt2img"
CRS_VIEW_QWEN_EDIT_2509 = "qwen_edit_2509.crs_single_view"
CRS_VIEW_ILLUSTRIOUS_T2I = "illustrious.txt2img"
CRS_VIEW_GPT_IMAGE_2_T2I = "gpt-image-2.txt2img"

CRS_VIEW_EXPLICIT_T2I = {
    "flux": CRS_VIEW_FLUX_T2I,
    "qwen2512": CRS_VIEW_QWEN_T2I,
    "qwen": CRS_VIEW_QWEN_T2I,
    "illustrious": CRS_VIEW_ILLUSTRIOUS_T2I,
    "gpt-image-2": CRS_VIEW_GPT_IMAGE_2_T2I,
    "gpt_image_2": CRS_VIEW_GPT_IMAGE_2_T2I,
    "gpt-image-2-kie": CRS_VIEW_GPT_IMAGE_2_T2I,
    "qwen_edit_2509": CRS_VIEW_QWEN_EDIT_2509,
    "qwen-edit-2509": CRS_VIEW_QWEN_EDIT_2509,
    "qwen-image-edit-2509": CRS_VIEW_QWEN_EDIT_2509,
}

_ALLOWED_FORCE_KEYS = frozenset(
    {
        CRS_VIEW_FLUX_T2I,
        CRS_VIEW_FLUX_I2I,
        CRS_VIEW_QWEN_T2I,
        CRS_VIEW_ILLUSTRIOUS_T2I,
        CRS_VIEW_GPT_IMAGE_2_T2I,
        CRS_VIEW_QWEN_EDIT_2509,
    }
)

CRS_VIEW_FORBIDDEN_KEYS = frozenset(
    {
        "qwen2512.ref",
        "qwen2512.ers",
        "flux.edit",
        "flux.kontext_edit",
        "flux.fill",
        "flux.inpaint",
        "flux.outpaint",
        "flux.reference",
    }
)
CRS_VIEW_FORBIDDEN_TOKENS = (
    "ers",
    "contact_sheet",
    "contact-sheet",
    "contactsheet",
    "collage",
    "scene",
    "qwen2512.ref",
    "edit_canvas",
    "edit-canvas",
    "four_view",
    "four-view",
    "turnaround",
)

_IDENTITY_CROP_ROLES = frozenset(
    {
        "full_body_front",
        "full_body_side_left",
        "full_body_side_right",
        "full_body_back",
        "full_body_three_quarter_front",
        "closeup_front",
        "identity_crop",
        "identity_reference",
        "reference_image",
    }
)
_SHEET_ROLES = frozenset(
    {
        "character_sheet",
        "hero_identity",
        "hero_portrait",
        "composed_sheet",
    }
)


def is_crs_view_generation_task(value: Any) -> bool:
    return str(value or "").strip().upper() == CRS_VIEW_GENERATION_TASK


def normalize_crs_view_family(value: Any) -> str:
    """Canonical family id, or empty for AUTO / omitted."""
    fam = str(value or "").strip().lower().replace("_", "-")
    if fam in {"", "auto"}:
        return ""
    if fam in {"qwen-edit-2509", "qwen-image-edit-2509", "qwenedit2509"}:
        return "qwen_edit_2509"
    if fam in {"qwen", "qwen2512", "qwen-2512"}:
        return "qwen2512"
    if fam in {"flux"}:
        return "flux"
    if fam in {"illustrious"}:
        return "illustrious"
    if "gpt-image-2" in fam or fam in {"gptimage2", "gpt-image2"}:
        return "gpt-image-2"
    if fam.startswith("krea"):
        return "krea2"
    return fam


def extract_crs_view_requested_family(
    generator_sources: dict[str, Any] | None = None,
    *,
    family: str | None = None,
    generator_family: str | None = None,
) -> str:
    """First explicit family from POST body / generatorSources. AUTO is empty."""
    candidates: list[Any] = [family, generator_family]
    if isinstance(generator_sources, dict):
        candidates.append(generator_sources.get("family"))
        candidates.append(generator_sources.get("generatorFamily"))
        candidates.append(generator_sources.get("generator_family"))
        local = generator_sources.get("local")
        if isinstance(local, dict):
            candidates.append(local.get("family"))
            candidates.append(local.get("selected"))
            candidates.append(local.get("model"))
        elif isinstance(local, list):
            for item in local:
                if not isinstance(item, dict):
                    continue
                enabled = item.get("enabled")
                if enabled is False:
                    continue
                raw = item.get("family") or item.get("selected") or item.get("model")
                norm = normalize_crs_view_family(raw)
                if norm:
                    return norm
    for raw in candidates:
        norm = normalize_crs_view_family(raw)
        if norm:
            return norm
    return ""


def normalize_crs_view_type(view_type: str | None) -> str:
    from .crs_law_view_gates import ROLE_TO_REQUESTED_VIEW, canonical_requested_view

    raw = str(view_type or CRS_VIEW_DEFAULT_VIEW).strip().lower() or CRS_VIEW_DEFAULT_VIEW
    if raw in ROLE_TO_REQUESTED_VIEW or raw == CRS_VIEW_DEFAULT_VIEW:
        # unknown-camera stays RECOMMEND at gate time; enqueue still maps known aliases.
        try:
            want = canonical_requested_view(raw)
        except ValueError:
            return raw
        if want == "front":
            return CRS_VIEW_DEFAULT_VIEW
        return raw
    try:
        want = canonical_requested_view(raw)
    except ValueError:
        return raw
    if want == "front":
        return CRS_VIEW_DEFAULT_VIEW
    return raw


def _workflow_blob(workflow_key: str, wf: Any | None = None) -> str:
    parts = [str(workflow_key or "")]
    if wf is not None:
        parts.extend(
            [
                str(getattr(wf, "workflow_key", "") or ""),
                str(getattr(wf, "operation", "") or ""),
                str(getattr(wf, "category", "") or ""),
                str(getattr(wf, "builder", "") or ""),
                " ".join(str(x) for x in (getattr(wf, "supported_operations", ()) or ())),
                " ".join(str(x) for x in (getattr(wf, "required_inputs", ()) or ())),
            ]
        )
        caps = getattr(wf, "capabilities", None)
        if isinstance(caps, dict):
            parts.append(" ".join(f"{k}={v}" for k, v in caps.items()))
    return " ".join(parts).lower()


def crs_view_graph_refusal(workflow_key: str, wf: Any | None = None) -> str:
    """Non-empty when the graph is ERS / scene / collage / edit-canvas / contact-sheet."""
    key = str(workflow_key or "").strip().lower()
    if not key:
        return "CRS_VIEW_GENERATION refuses empty workflow"
    if key in CRS_VIEW_FORBIDDEN_KEYS:
        return f"CRS_VIEW_GENERATION refuses graph {key}"
    blob = _workflow_blob(key, wf)
    for tok in CRS_VIEW_FORBIDDEN_TOKENS:
        if tok in blob:
            return f"CRS_VIEW_GENERATION refuses {tok} graph {key}"
    return ""


def _get_certified_workflow(workflow_key: str) -> Any | None:
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(workflow_key)
    except Exception:
        return None
    if not wf or getattr(wf, "status", None) != "Certified":
        return None
    return wf


def flux_img2img_is_identity_conditioning(workflow_key: str = CRS_VIEW_FLUX_I2I) -> bool:
    """True only when flux.img2img is Certified and consumes source_image as I2I.

    EDIT_CANVAS / kontext / panel / ERS graphs are refused even if named flux.
    """
    key = str(workflow_key or "").strip().lower()
    if key != CRS_VIEW_FLUX_I2I:
        return False
    wf = _get_certified_workflow(key)
    if wf is None:
        return False
    if crs_view_graph_refusal(key, wf):
        return False
    inputs = {str(x).strip().lower() for x in (getattr(wf, "required_inputs", ()) or ())}
    if "source_image" not in inputs:
        return False
    op = str(getattr(wf, "operation", "") or "").strip().lower()
    if op in {"image.inpaint", "image.outpaint", "image.fill", "image.scene"}:
        return False
    return True


def resolve_crs_view_generation_workflow(
    *,
    has_identity_crop: bool = False,
    force_workflow_key: str | None = None,
    requested_family: str | None = None,
) -> dict[str, Any]:
    """Pick one single-character T2I or identity I2I workflow. Advertised keys only.

    Explicit requested_family pins that family's isolated txt2img. AUTO / omitted
    still prefers FLUX then Qwen. AUTO never honors Krea.
    """
    forced = str(force_workflow_key or "").strip()
    if forced:
        wf = None
        try:
            from ..image_runtime.certified_registry import get_workflow

            wf = get_workflow(forced)
        except Exception:
            wf = None
        reason = crs_view_graph_refusal(forced, wf)
        if reason:
            raise ValueError(reason)
        if forced not in _ALLOWED_FORCE_KEYS:
            raise ValueError(f"CRS_VIEW_GENERATION refuses graph {forced}")

    explicit = normalize_crs_view_family(requested_family)
    if explicit == "krea2":
        raise ValueError("CRS_VIEW_GENERATION refuses graph krea2")
    if explicit == "qwen_edit_2509":
        key = CRS_VIEW_QWEN_EDIT_2509
        reason = crs_view_graph_refusal(key, None)
        if reason:
            raise ValueError(reason)
        return {
            "family": "qwen_edit_2509",
            "workflowKey": key,
            "mode": "i2i_edit",
            "fallback": False,
            "explicit": True,
            "identityRole": "IDENTITY_REFERENCE",
            "t2iOnly": False,
        }
    if explicit:
        key = CRS_VIEW_EXPLICIT_T2I.get(explicit) or CRS_VIEW_EXPLICIT_T2I.get(
            str(requested_family or "").strip().lower()
        )
        if not key:
            raise ValueError(f"CRS_VIEW_GENERATION refuses graph {explicit}")
        if key == CRS_VIEW_QWEN_EDIT_2509:
            return {
                "family": "qwen_edit_2509",
                "workflowKey": key,
                "mode": "i2i_edit",
                "fallback": False,
                "explicit": True,
                "identityRole": "IDENTITY_REFERENCE",
                "t2iOnly": False,
            }
        wf = _get_certified_workflow(key)
        reason = crs_view_graph_refusal(key, wf)
        if reason:
            raise ValueError(reason)
        if wf is None:
            raise ValueError(
                f"CRS_VIEW_GENERATION: no Certified isolated txt2img for {explicit}"
            )
        return {
            "family": explicit,
            "workflowKey": key,
            "mode": "txt2img",
            "fallback": False,
            "explicit": True,
        }

    if has_identity_crop and flux_img2img_is_identity_conditioning(CRS_VIEW_FLUX_I2I):
        return {
            "family": "flux",
            "workflowKey": CRS_VIEW_FLUX_I2I,
            "mode": "img2img",
            "fallback": False,
            "explicit": False,
        }

    t2i = _get_certified_workflow(CRS_VIEW_FLUX_T2I)
    if t2i is not None and not crs_view_graph_refusal(CRS_VIEW_FLUX_T2I, t2i):
        return {
            "family": "flux",
            "workflowKey": CRS_VIEW_FLUX_T2I,
            "mode": "txt2img",
            "fallback": False,
            "explicit": False,
        }

    qwen = _get_certified_workflow(CRS_VIEW_QWEN_T2I)
    if qwen is not None and not crs_view_graph_refusal(CRS_VIEW_QWEN_T2I, qwen):
        return {
            "family": "qwen2512",
            "workflowKey": CRS_VIEW_QWEN_T2I,
            "mode": "txt2img",
            "fallback": True,
            "explicit": False,
        }
    raise ValueError(
        "CRS_VIEW_GENERATION: no Certified single-character FLUX or Qwen workflow"
    )


def source_crop_is_proven_single_figure(
    path: str | None,
    *,
    detect_people: Any | None = None,
    detect_collage: Any | None = None,
) -> bool:
    """True only when the source pixels are a proven one-figure identity crop.

    Collage / sheet / multi-figure / unverified (no detector) fail-close.
    """
    if not path:
        return False
    from .crs_single_figure import validate_crs_single_figure

    kwargs: dict[str, Any] = {}
    if detect_people is not None:
        kwargs["detect_people"] = detect_people
    if detect_collage is not None:
        kwargs["detect_collage"] = detect_collage
    result = validate_crs_single_figure(path, **kwargs)
    return result.single_figure_pass is True


def valid_identity_reference_crop(
    references: list[dict[str, Any]] | None,
    *,
    readable: Any | None = None,
    image_path: Any | None = None,
    detect_people: Any | None = None,
    detect_collage: Any | None = None,
) -> str | None:
    """Return asset id of a proven single-character crop, else None.

    Fail-closed: composed sheets / hero_identity documents / unlabeled uploads
    are not identity crops. A labeled IDENTITY_REFERENCE or crs_derived_crop
    still fails unless the SOURCE pixels pass the one-figure gate. Unknown
    or unverified is not a pass. No pose CNN.
    """
    for item in references or []:
        if not isinstance(item, dict):
            continue
        aid = str(item.get("asset_id") or item.get("assetId") or "").strip()
        if not aid:
            continue
        role = str(item.get("reference_role") or item.get("referenceRole") or item.get("role") or "").strip().lower()
        source = str(item.get("source_type") or item.get("sourceType") or "").strip().lower()
        kind = str(item.get("referenceKind") or item.get("kind") or item.get("tag") or "").strip().upper()
        layout = str(item.get("layout") or "").strip().lower()
        if layout in {"law_views", "four_view", "character_sheet", "collage", "contact_sheet"}:
            continue
        if role in _SHEET_ROLES and source != "crs_derived_crop" and kind != "IDENTITY_REFERENCE":
            continue
        is_crop = (
            source == "crs_derived_crop"
            or role in _IDENTITY_CROP_ROLES
            or kind == "IDENTITY_REFERENCE"
        )
        if not is_crop:
            continue
        if callable(readable) and not readable(aid):
            continue
        path = None
        if callable(image_path):
            try:
                path = image_path(aid)
            except Exception:
                path = None
        elif isinstance(image_path, dict):
            path = image_path.get(aid)
        if not source_crop_is_proven_single_figure(
            str(path) if path else None,
            detect_people=detect_people,
            detect_collage=detect_collage,
        ):
            continue
        return aid
    return None
