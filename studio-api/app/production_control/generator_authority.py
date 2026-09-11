"""Single product-level generator authority.

Identity lives in Production Control. Live facts decide Ready.
Execution bindings live on Timeline adapters. This module is the join —
not a fourth catalog and not a label painter.
"""

from __future__ import annotations

from typing import Any

from ..hosted_providers import video_registry
from .video_readiness import (
    PRODUCT_ALIASES,
    adapter_for_product,
    canonical_product_id,
    collect_video_facts,
    derive_video_readiness,
)

# PRODUCT_ALIASES is re-exported from video_readiness (which derives it from
# the canonical video registry). Aliases never become products.

_MOCK_ID_MARKERS = ("mock-chat", ":mock-", "cert-stub")

# Products whose actual workflow can apply Turbo LoRA. File presence is a
# Preflight check, not a hide-toggle check. Distilled / INT8 LTX 2.5 stay off.
_TURBO_LORA_PRODUCTS = frozenset(
    {
        "ltx-2.5-full",
    }
)


def supports_turbo_lora(product_id: str | None) -> bool:
    """Canonical Turbo LoRA gate. UI and compilers must call this — not string matching."""
    token = str(product_id or "").strip()
    if not token:
        return False
    product = canonical_product_id(token) or token
    return product in _TURBO_LORA_PRODUCTS


# Adapter-only execution ids that must not appear as a second product row.
# Derived from the canonical video registry (exact historical set).
_ADAPTER_ONLY_IDS = frozenset(video_registry.adapter_only_ids())

# CREATE /api/engines tokens. Retired locals and generic Seedance are not defaults.
# Derived from the canonical video registry (exact historical rows + order).
CREATE_ENGINE_ROWS: tuple[tuple[str, str, str], ...] = tuple(video_registry.create_engine_rows())


def is_production_mock(model_id: str | None) -> bool:
    token = str(model_id or "").lower()
    return any(marker in token for marker in _MOCK_ID_MARKERS)


def _timeline_adapter_ids() -> set[str]:
    try:
        from ..director_timeline_w46.generation.registry import get_registry

        return {c.id for c in get_registry().list_capabilities()}
    except Exception:
        return set()


def timeline_adapter_for(model_id: str | None) -> str | None:
    """Return the execution adapter id, or None. Never collapses distinct products."""
    raw = str(model_id or "").strip()
    if not raw:
        return None
    product = canonical_product_id(raw)
    bound = adapter_for_product(product or raw)
    adapters = _timeline_adapter_ids()
    if bound and bound in adapters:
        return bound
    if product in adapters:
        return product
    if raw in adapters:
        return raw
    return None


def _non_video_readiness(
    *,
    executable: bool,
    capability: str,
    locality: str,
    model_id: str,
) -> tuple[str, str, bool]:
    if is_production_mock(model_id):
        return "Unsupported", "Test fixture — not a production model", False
    if capability in {"Requires Setup", "Unavailable", "Unsupported", "Error"}:
        return capability if capability != "Unavailable" else "Unsupported", capability, False
    if not executable:
        if locality == "hosted":
            return "Provider Not Configured", "Provider Not Configured", False
        if capability == "Testing":
            return "Testing", "Testing — not ready", False
        return "Requires Setup", "Requires Setup", False
    if capability == "Testing":
        return "Testing", "", False
    return "Ready", "", True


def apply_authority_to_model(model: dict[str, Any]) -> dict[str, Any] | None:
    """Annotate one inventory row. Returns None to drop mocks from production."""
    mid = str(model.get("id") or "")
    if is_production_mock(mid):
        return None
    modality = str(model.get("modality") or "")
    locality = str(model.get("locality") or "local")
    capability = str(model.get("capabilityLabel") or "Available")
    adapter_id = timeline_adapter_for(mid) if modality == "video" else None
    has_adapter = adapter_id is not None if modality == "video" else True

    if modality == "audio" and capability == "Certified" and not bool(model.get("executable")):
        capability = "Requires Setup"
    if modality == "llm" and capability == "Available" and not bool(model.get("executable")):
        capability = "Requires Setup"

    if modality == "video":
        facts = collect_video_facts(
            mid,
            locality=locality,
            estimated_vram_gb=model.get("estimatedVramGb"),
        )
        if adapter_id:
            facts.adapter_id = adapter_id
            facts.adapter_registered = True
        readiness, reason, executable = derive_video_readiness(facts)
        if readiness == "Provider Not Configured":
            readiness = "Requires Setup"
            reason = reason or "Provider API Key Missing"
        if facts.locality == "hosted" and readiness == "Requires Setup":
            capability = "Requires Setup"
        elif readiness == "Unsupported" and capability in {"Certified", "Available"}:
            capability = "Unsupported"
        elif readiness == "Testing" and capability in {"Certified", "Available"}:
            capability = "Testing"
        elif readiness == "Requires Setup" and capability in {"Certified", "Available"}:
            capability = "Requires Setup"
        elif (
            facts.locality == "hosted"
            and readiness == "Ready"
            and capability in {"Unavailable", "Requires Setup", "Error"}
        ):
            capability = "Available"
    else:
        executable = bool(model.get("executable"))
        readiness, reason, executable = _non_video_readiness(
            executable=executable,
            capability=capability,
            locality=locality,
            model_id=mid,
        )

    out = dict(model)
    out["id"] = mid
    out["canonicalId"] = canonical_product_id(mid) or mid
    out["capabilityLabel"] = capability
    out["executable"] = executable
    out["selectable"] = executable
    out["timelineAdapterId"] = adapter_id
    out["supportsTimelineGeneration"] = has_adapter if modality == "video" else bool(
        out.get("supportsTimelineGeneration", True)
    )
    out["readiness"] = readiness
    out["disabledReason"] = reason
    if modality == "video":
        out["workflowCapabilities"] = _workflow_capabilities(mid)
    return out


def _workflow_capabilities(product_id: str) -> dict[str, dict[str, Any]] | None:
    """Per-surface truth for CREATE pickers. Timeline flags never feed this.

    Registry authority: any product with surface workflow records in the
    canonical video registry — local OR hosted — emits the 4-surface record
    (hosted Kling/Veo/Runway included, so CREATE pickers render server truth;
    the frontend decideEngineOnSurface treats workflowCapability as authority
    when present). Hosted products without workflow records still return None
    so the UI falls back to the hosted capability path instead of being hidden
    by an all-unsupported record.
    """
    try:
        from ..video_runtime.workflow_capabilities import supports_any_local_surface, surface_workflow_status

        if not supports_any_local_surface(product_id):
            return None
        return {
            surface: surface_workflow_status(product_id, surface)
            for surface in ("t2v", "i2v", "multiFrame", "r2v")
        }
    except Exception:
        return None


def apply_authority_to_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in models:
        annotated = apply_authority_to_model(row)
        if annotated is not None:
            out.append(annotated)
    return out


def apply_authority_to_descriptors(models: list[Any]) -> list[Any]:
    """Same join for ModelDescriptor objects used by list_models()."""
    out: list[Any] = []
    for model in models:
        if is_production_mock(getattr(model, "id", "")):
            continue
        payload = apply_authority_to_model(model.model_dump())
        if payload is None:
            continue
        update = {
            "capabilityLabel": payload["capabilityLabel"],
            "executable": payload["executable"],
            "defaultEligible": bool(getattr(model, "defaultEligible", False))
            and bool(payload["executable"]),
            "selectable": payload["selectable"],
            "readiness": payload["readiness"],
            "disabledReason": payload["disabledReason"],
            "timelineAdapterId": payload.get("timelineAdapterId"),
            "supportsTimelineGeneration": bool(payload.get("supportsTimelineGeneration")),
            "workflowCapabilities": payload.get("workflowCapabilities"),
        }
        try:
            out.append(model.model_copy(update=update))
        except Exception:
            out.append(
                model.model_copy(
                    update={
                        "capabilityLabel": payload["capabilityLabel"],
                        "executable": payload["executable"],
                        "defaultEligible": bool(getattr(model, "defaultEligible", False))
                        and bool(payload["executable"]),
                    }
                )
            )
    return out


def _capability_from_row(row: dict[str, Any], adapter_caps: Any | None) -> Any:
    from ..director_timeline_w46.contracts import GeneratorCapability

    max_dur = None
    if adapter_caps is not None and getattr(adapter_caps, "maxDurationSec", None):
        try:
            max_dur = float(adapter_caps.maxDurationSec)
        except Exception:
            max_dur = None
    if max_dur is None and adapter_caps is not None and getattr(adapter_caps, "supportedDurations", None):
        try:
            max_dur = float(max(adapter_caps.supportedDurations))
        except Exception:
            max_dur = None
    if max_dur is None and str(row.get("id") or "").startswith("minimax-h3"):
        max_dur = 15.0
    notes = str(row.get("disabledReason") or "")
    if adapter_caps is not None and getattr(adapter_caps, "notes", ""):
        if notes:
            notes = f"{notes}. {adapter_caps.notes}"
        else:
            notes = str(adapter_caps.notes)
    locality = row.get("locality") or "local"
    if locality not in ("local", "hosted"):
        locality = "hosted" if locality == "hosted" else "local"
    return GeneratorCapability(
        id=str(row["id"]),
        label=str(row.get("label") or row["id"]),
        locality=locality,
        providerId=row.get("providerId"),
        capabilityLabel=row.get("capabilityLabel") or "Available",  # type: ignore[arg-type]
        maxDurationSec=max_dur,
        supportsStartEndFrame=bool(
            adapter_caps.supportsStartFrame if adapter_caps is not None else False
        ),
        supportsContinuation=bool(
            getattr(adapter_caps, "supportsPromptContinuation", False) if adapter_caps is not None else False
        ),
        inPaintStrategies=["complete_batch_retake"]
        + (
            ["range_replacement", "keyframe_repair"]
            if row.get("supportsTimelineGeneration") or row.get("timelineAdapterId")
            else []
        ),
        supportsAudio=bool(getattr(adapter_caps, "audio_generation", False) if adapter_caps else False),
        executable=bool(row.get("executable")),
        notes=notes,
        # list_models() stamps timelineAdapterId but drops this bool.
        # Adapter present = Timeline generation is wired (authority join).
        supportsTimelineGeneration=bool(
            row.get("supportsTimelineGeneration") or row.get("timelineAdapterId")
        ),
        supportsImageToVideo=bool(
            adapter_caps.supportsImageToVideo if adapter_caps is not None else True
        ),
        # Surface truth, not the Timeline adapter flag: a Timeline R2V adapter
        # declaring supportsTextToVideo=False must not hide a genuine T2V
        # workflow on the Text to Video surface.
        supportsTextToVideo=bool(
            (row.get("workflowCapabilities") or {}).get("t2v", {}).get("supported")
            or (adapter_caps.supportsTextToVideo if adapter_caps is not None else False)
        ),
        requiresLastFrame=bool(
            getattr(adapter_caps, "requiresLastFrame", False) if adapter_caps is not None else False
        ),
        supportsInterrupt=bool(
            getattr(adapter_caps, "supportsRunningCancel", False) if adapter_caps else False
        ),
        draftPathway=str(getattr(adapter_caps, "draftPathway", "none") if adapter_caps else "none"),
        supportsQueuedCancel=bool(
            getattr(adapter_caps, "supportsQueuedCancel", False) if adapter_caps else False
        ),
        supportsRunningCancel=bool(
            getattr(adapter_caps, "supportsRunningCancel", False) if adapter_caps else False
        ),
        supportsLivePreview=bool(
            getattr(adapter_caps, "supportsLivePreview", False) if adapter_caps else False
        ),
        supportsHonestProgress=bool(
            getattr(adapter_caps, "supportsHonestProgress", False) if adapter_caps else False
        ),
        supportsIntermediateFrames=bool(
            getattr(adapter_caps, "supportsIntermediateFrames", False) if adapter_caps else False
        ),
        supportsGenerationPreview=bool(
            getattr(adapter_caps, "supportsLivePreview", False)
            or getattr(adapter_caps, "draftPathway", "") == "local_live"
            if adapter_caps
            else False
        ),
        remoteCancelCostNote=(
            getattr(adapter_caps, "remoteCancelCostNote", None) if adapter_caps else None
        ),
        finalRequiresNewGeneration=bool(
            getattr(adapter_caps, "finalRequiresNewGeneration", True) if adapter_caps else True
        ),
        draftResolution=getattr(adapter_caps, "draftResolution", None) if adapter_caps else None,
        finalResolution=getattr(adapter_caps, "finalResolution", None) if adapter_caps else None,
        supportsVideoReferences=bool(
            getattr(adapter_caps, "supportsVideoReferences", False) if adapter_caps else False
        ),
        supportsImageAndVideoTogether=bool(
            getattr(adapter_caps, "supportsImageAndVideoTogether", False) if adapter_caps else False
        ),
        maximumReferenceVideos=int(
            getattr(adapter_caps, "maximumReferenceVideos", 0) if adapter_caps else 0
        ),
        supportedAspectRatios=list(
            getattr(adapter_caps, "supportedAspectRatios", []) if adapter_caps else []
        ),
        readiness=str(row.get("readiness") or ""),
        disabledReason=str(row.get("disabledReason") or ""),
        timelineAdapterId=row.get("timelineAdapterId") or (getattr(adapter_caps, "id", None) if adapter_caps else None),
        supportsTurboLora=supports_turbo_lora(str(row.get("id") or "")),
        usesFastQuality=str(row.get("id") or "").startswith(("ltx-2.5", "minimax-h3")),
        workflowCapabilities=row.get("workflowCapabilities") or None,
    )


def timeline_generator_snapshot() -> list[Any]:
    """Timeline `generators` view of the same join used by Production Control."""
    from ..director_timeline_w46.generation.adapters.stub_cert import stub_enabled
    from ..director_timeline_w46.generation.registry import get_registry
    from .model_registry import list_models

    registry = get_registry()
    adapter_caps = {c.id: c for c in registry.list_capabilities()}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for model in list_models("video"):
        payload = model.model_dump()
        # list_models already ran the join — do not re-probe live facts.
        annotated = payload if payload.get("readiness") else apply_authority_to_model(payload)
        if annotated is None:
            continue
        mid = str(annotated["id"])
        canon = str(annotated.get("canonicalId") or mid)
        if mid in seen or canon in seen or mid in _ADAPTER_ONLY_IDS or canon in _ADAPTER_ONLY_IDS:
            continue
        seen.add(mid)
        seen.add(canon)
        rows.append(annotated)

    try:
        from ..hosted_providers.discovery import dock_api_models

        for raw in dock_api_models("video").get("models") or []:
            mid = str(raw.get("id") or "")
            if not mid or mid in seen or mid in _ADAPTER_ONLY_IDS:
                continue
            if canonical_product_id(mid) in seen:
                continue
            annotated = apply_authority_to_model(
                {
                    "id": mid,
                    "modality": "video",
                    "label": raw.get("label") or raw.get("displayName") or mid,
                    "locality": "hosted",
                    "providerId": raw.get("providerId"),
                    "capabilityLabel": raw.get("capabilityLabel") or "Requires Setup",
                    "executable": bool(raw.get("executable")),
                    "selectable": bool(raw.get("selectable", True)),
                }
            )
            if annotated is None:
                continue
            seen.add(annotated["id"])
            rows.append(annotated)
    except Exception:
        pass

    for cap in adapter_caps.values():
        if cap.id in seen or canonical_product_id(cap.id) in seen:
            continue
        if cap.id in _ADAPTER_ONLY_IDS:
            continue
        if cap.id == "cert-stub-local" and not stub_enabled():
            continue
        annotated = apply_authority_to_model(
            {
                "id": cap.id,
                "modality": "video",
                "label": cap.label,
                "locality": "hosted" if cap.executionType == "api" else "local",
                "providerId": None,
                "capabilityLabel": "Testing" if cap.id.startswith("minimax-h3") else "Available",
                "executable": False,
            }
        )
        if annotated is None:
            continue
        seen.add(annotated["id"])
        rows.append(annotated)

    gens = []
    for row in rows:
        adapter_id = row.get("timelineAdapterId")
        gens.append(_capability_from_row(row, adapter_caps.get(adapter_id) if adapter_id else None))
    if stub_enabled() and "cert-stub-local" not in seen:
        from ..director_timeline_w46.contracts import GeneratorCapability

        gens.append(
            GeneratorCapability(
                id="cert-stub-local",
                label="Cert Stub (wiring certification only)",
                locality="local",
                providerId="cert-stub",
                capabilityLabel="Testing",
                maxDurationSec=10.0,
                supportsStartEndFrame=True,
                supportsContinuation=True,
                inPaintStrategies=["range_replacement", "keyframe_repair", "complete_batch_retake"],
                executable=False,
                supportsTimelineGeneration=True,
                notes="Certification stub — env-gated. Never executes GPU code.",
                readiness="Testing",
                disabledReason="Testing — certification stub",
            )
        )
    return gens


def list_create_engines() -> list[dict[str, str]]:
    """CREATE /api/engines view of the join — not fal_catalog.list_engines_for_ui."""
    by_canon: dict[str, Any] = {}
    try:
        for row in timeline_generator_snapshot():
            rid = str(getattr(row, "id", "") or "")
            canon = canonical_product_id(rid) or rid
            by_canon[canon] = row
            by_canon[rid] = row
    except Exception:
        by_canon = {}

    out: list[dict[str, str]] = []
    for engine_id, fallback_label, group in CREATE_ENGINE_ROWS:
        product = canonical_product_id(engine_id) or engine_id
        match = by_canon.get(product) or by_canon.get(engine_id)
        label = fallback_label
        if match is not None:
            live_label = str(getattr(match, "label", "") or "")
            if engine_id == "ltx-2.5":
                label = "LTX 2.5"
            elif engine_id == "minimax-h3":
                label = "MiniMax H3"
            elif engine_id.startswith("seedance-"):
                label = fallback_label
            elif live_label and group == "hosted" and engine_id.startswith("fal_"):
                label = live_label
        if engine_id in {"seedance-2.0", "seedance-2.5"} and "2." not in label:
            label = fallback_label
        out.append({"id": engine_id, "label": label, "group": group})
    return out
