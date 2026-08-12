"""CanonicalImageWorkflowContract — image domain contract for unified resolver (M42 W2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .certified_registry import ImageWorkflow, get_workflow


@dataclass
class CanonicalImageWorkflowContract:
    intent: str
    workflow_id: str
    workflow_key: str
    workflow_version: str
    modality: str = "image"
    category: str = "Generation"
    provider: str = "local"
    engine: str = "zimage"
    model_family: str = "zimage"
    model_variant: str = ""
    operation: str = "image.generate"
    builder_path: str | None = None
    required_inputs: list[str] = field(default_factory=list)
    optional_inputs: list[str] = field(default_factory=list)
    required_models: list[str] = field(default_factory=list)
    required_nodes: list[str] = field(default_factory=list)
    runtime_requirements: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    asset_contract: dict[str, Any] = field(default_factory=dict)
    cancel_policy: dict[str, Any] = field(default_factory=dict)
    validation_policy: dict[str, Any] = field(default_factory=dict)
    provenance_policy: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    fingerprints: dict[str, Any] = field(default_factory=dict)
    certification_record_id: str | None = None
    status: str = "Draft"
    disclosures: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    # Phase C reference / LoRA inputs (Krea 2): role-grouped AssetRef dicts
    # ({assetId, role, image?, weight?, displayName?}) — see
    # image_runtime/asset_refs.py. Environment refs keep role="environment"
    # end-to-end (ERS Semantic Role Law).
    style_references: list[dict[str, Any]] = field(default_factory=list)
    character_references: list[dict[str, Any]] = field(default_factory=list)
    environment_references: list[dict[str, Any]] = field(default_factory=list)
    moodboard_references: list[dict[str, Any]] = field(default_factory=list)
    lora_id: str | None = None
    lora_strength: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["workflowId"] = self.workflow_id
        d["workflowKey"] = self.workflow_key
        d["workflowVersion"] = self.workflow_version
        d["modelFamily"] = self.model_family
        d["modelVariant"] = self.model_variant
        d["requiredInputs"] = list(self.required_inputs)
        d["optionalInputs"] = list(self.optional_inputs)
        d["requiredModels"] = list(self.required_models)
        d["requiredNodes"] = list(self.required_nodes)
        d["runtimeRequirements"] = dict(self.runtime_requirements)
        d["outputContract"] = dict(self.output_contract)
        d["assetContract"] = dict(self.asset_contract)
        d["cancelPolicy"] = dict(self.cancel_policy)
        d["validationPolicy"] = dict(self.validation_policy)
        d["provenancePolicy"] = dict(self.provenance_policy)
        d["builderPath"] = self.builder_path
        d["certificationRecordId"] = self.certification_record_id
        # Phase C reference / LoRA carriers (camelCase for API consumers)
        d["styleReferences"] = list(self.style_references)
        d["characterReferences"] = list(self.character_references)
        d["environmentReferences"] = list(self.environment_references)
        d["moodboardReferences"] = list(self.moodboard_references)
        d["loraId"] = self.lora_id
        d["loraStrength"] = self.lora_strength
        # Flatten capability booleans for consumers
        caps = dict(self.capabilities)
        for k in (
            "supportsReferences",
            "supportsEditing",
            "supportsControlNet",
            "supportsLoRA",
            "supportsInpaint",
            "supportsOutpaint",
            "supportsFill",
            "supportsIdentity",
            "supportsBatch",
        ):
            d[k] = bool(caps.get(k, False))
        return d

    def to_pinned_snapshot(self) -> dict[str, Any]:
        """Job-pinned contract — QueueWorker must not silently switch versions."""
        from datetime import datetime, timezone

        fps = dict(self.fingerprints or {})
        return {
            "workflowKey": self.workflow_key,
            "workflowVersion": self.workflow_version,
            "workflowId": self.workflow_id,
            "modelFamily": self.model_family,
            "modelVariant": self.model_variant,
            "certificationRecordId": self.certification_record_id,
            "fingerprint": fps.get("graphHash"),
            "fingerprints": fps,
            "provider": self.provider,
            "engine": self.engine,
            "status": self.status,
            "resolvedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def _default_capabilities(wf: ImageWorkflow) -> dict[str, Any]:
    caps = dict(wf.capabilities or {})
    defaults = {
        "supportsReferences": False,
        "supportsEditing": False,
        "supportsControlNet": False,
        "supportsLoRA": False,
        "supportsInpaint": False,
        "supportsOutpaint": False,
        "supportsFill": False,
        "supportsIdentity": False,
        "supportsBatch": True,
        # Phase C granular reference flags (Krea 2) — default False everywhere;
        # registry entries opt in per workflow.
        "supportsReferenceImages": False,
        "supportsStyleReferences": False,
        "supportsMoodboards": False,
        "supportsCharacterReference": False,
        "supportsImageEditing": False,
    }
    for k, v in defaults.items():
        caps.setdefault(k, v)
    return caps


def _from_workflow(wf: ImageWorkflow, *, intent: str, present: dict[str, Any]) -> CanonicalImageWorkflowContract:
    raw_strength = present.get("loraStrength")
    if raw_strength is None:
        raw_strength = present.get("lora_strength")
    return CanonicalImageWorkflowContract(
        intent=intent,
        workflow_id=wf.workflow_id,
        workflow_key=wf.workflow_key,
        workflow_version=wf.workflow_version,
        modality="image",
        category=wf.category,
        provider=wf.provider or wf.provider_kind,
        engine=wf.engine,
        model_family=wf.model_family,
        model_variant=wf.model_variant,
        operation=wf.operation,
        builder_path=wf.builder_path,
        required_inputs=list(wf.required_inputs),
        optional_inputs=list(wf.optional_inputs),
        required_models=list(wf.required_models),
        required_nodes=list(wf.required_nodes),
        runtime_requirements={
            "vramProfile": dict(wf.vram_profile),
            "engine": wf.engine,
            "requiredRuntime": wf.required_runtime,
            # Registry-declared runtime extras (e.g. Krea 2 "mu") — lets
            # image_product/compile pass them without hardcoding per-family keys.
            **dict(wf.runtime_params or {}),
        },
        output_contract={
            "supportedOutputs": list(wf.supported_outputs),
            "outputValidation": wf.output_validation,
            "assetRegistrationRequired": True,
        },
        asset_contract={"registerOnSuccess": True, "provenanceRequired": True},
        cancel_policy={
            "supported": wf.cancellation_support,
            "optimisticCancelForbidden": True,
        },
        validation_policy={
            "dimensions": True,
            "aspectRatio": True,
            "fileIntegrity": True,
            "metadata": True,
            "previewGeneration": True,
            "thumbnailGeneration": True,
            "checksum": True,
            "noOptimisticSuccess": True,
        },
        provenance_policy=dict(wf.provenance_policy)
        or {
            "schema": "ImageProvenance",
            "requiredFields": [
                "workflow",
                "workflowVersion",
                "provider",
                "prompt",
                "references",
                "parentImages",
            ],
        },
        capabilities=_default_capabilities(wf),
        fingerprints=dict(wf.fingerprints or {}),
        certification_record_id=wf.certification_record_id,
        status=wf.status,
        disclosures=list(wf.limitations),
        inputs=dict(present),
        style_references=list(present.get("styleReferences") or present.get("style_references") or []),
        character_references=list(
            present.get("characterReferences") or present.get("character_references") or []
        ),
        environment_references=list(
            present.get("environmentReferences") or present.get("environment_references") or []
        ),
        moodboard_references=list(
            present.get("moodboardReferences") or present.get("moodboard_references") or []
        ),
        lora_id=present.get("loraId") or present.get("lora_id"),
        lora_strength=float(raw_strength) if raw_strength is not None else 0.8,
    )


def _normalize_family(engine: str | None, model_family: str | None) -> str:
    fam = (model_family or engine or "zimage").strip().lower()
    if fam in {"z-image", "z_image", "zimg"}:
        return "zimage"
    if fam in {"qwen-image-2512", "qwen_image_2512", "qwen2512"}:
        return "qwen2512"
    if fam in {"krea-2", "krea_2", "krea 2", "krea2"}:
        return "krea2"
    if fam.startswith("flux"):
        return "flux"
    if fam.startswith("qwen"):
        return "qwen"
    if fam.startswith("imagen") or fam in {"google", "google_imagen"}:
        return "imagen"
    if fam in {"checkpoint", "sdxl", "sd3"}:
        return "checkpoint"
    return fam


def resolve_image_workflow(
    intent: str,
    *,
    engine: str = "zimage",
    model_family: str | None = None,
    present_inputs: dict[str, Any] | None = None,
    force_workflow_key: str | None = None,
    allow_draft: bool = True,
    provider_preference: str | None = None,
) -> CanonicalImageWorkflowContract:
    """
    Resolve image product intent → CanonicalImageWorkflowContract.

    Supports zimage.* | flux.* | qwen.* | qwen2512.* | krea2.* | imagen.* families.
    Production paths must use allow_draft=False.
    """
    present = dict(present_inputs or {})
    intent_n = (intent or "").strip().lower()
    family = _normalize_family(engine, model_family)

    if force_workflow_key:
        key = force_workflow_key
    elif intent_n in {"image.upscale", "upscale"}:
        key = "image.upscale"
    elif intent_n in {"image.chroma_key", "chroma_key"}:
        key = "image.chroma_key"
    elif intent_n in {"image.inpaint", "inpaint", "object_remove", "object_replace"}:
        if family == "flux":
            key = "flux.inpaint"
        elif family == "qwen":
            key = "qwen.edit"
        elif family == "imagen":
            key = "imagen.edit"
        elif family == "checkpoint":
            key = "checkpoint.img2img"
        else:
            key = "zimage.inpaint"
    elif intent_n in {"image.outpaint", "outpaint", "crop_extend"}:
        if family == "flux":
            key = "flux.outpaint"
        else:
            key = "zimage.outpaint"
    elif intent_n in {"image.background_remove", "background_remove"}:
        key = "image.background_remove"
    elif intent_n in {"image.transparent_extract", "transparent_extract"}:
        key = "image.transparent_extract"
    elif intent_n in {"image.restore", "restore"}:
        key = "image.restore"
    elif intent_n in {"image.face_restore", "face_restore"}:
        key = "image.face_restore"
    elif intent_n in {"image.composite", "composite"}:
        key = "image.composite"
    elif intent_n in {"image.reference_edit", "reference_guided", "image.reference", "img2img", "image.edit"}:
        if family == "flux":
            key = "flux.reference" if "reference" in intent_n else "flux.edit"
        elif family == "qwen":
            key = "qwen.reference" if "reference" in intent_n else "qwen.edit"
        elif family == "imagen":
            key = "imagen.reference" if "reference" in intent_n else "imagen.edit"
        elif family == "checkpoint":
            key = "checkpoint.img2img"
        else:
            key = "zimage.ref_edit"
    elif intent_n in {"txt2img", "image.generate", "image.storyboard_frame"}:
        if family == "flux":
            key = "flux.txt2img"
        elif family == "qwen2512":
            key = "qwen2512.txt2img"
        elif family == "qwen":
            key = "qwen.txt2img"
        elif family == "imagen":
            key = "imagen.txt2img"
        elif family == "checkpoint":
            key = "checkpoint.txt2img"
        elif family == "krea2":
            # Turbo is the inference target (LoRAs train on RAW, run on Turbo);
            # RAW is reachable via force_workflow_key="krea2.raw_txt2img".
            key = "krea2.turbo_txt2img"
        else:
            key = "zimage.txt2img"
    else:
        wf = get_workflow(intent)
        if wf:
            key = wf.workflow_key
        else:
            raise RuntimeError(f"Unknown image workflow intent: {intent}")

    # Cloud provider preference can force imagen family for generate/edit
    if provider_preference and provider_preference.lower() in {"google", "google_imagen", "imagen"}:
        if (
            key.startswith("zimage.")
            or key.startswith("flux.")
            or key.startswith("qwen.")
            or key.startswith("qwen2512.")
        ):
            if "edit" in key or "ref" in key:
                key = "imagen.edit"
            else:
                key = "imagen.txt2img"

    wf = get_workflow(key)
    if wf is None:
        raise RuntimeError(f"Unknown image workflow key: {key}")
    if wf.status in {"Blocked", "Retired", "Deferred"}:
        raise RuntimeError(f"Image workflow not executable: {key} status={wf.status}")
    if not allow_draft and wf.status != "Certified":
        raise RuntimeError(f"Image workflow not Certified: {key}")
    return _from_workflow(wf, intent=intent_n or key, present=present)
