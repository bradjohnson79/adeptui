"""M4.8 shared cinematic image contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

GenerationMode = Literal["best_match", "choose_model", "all_models"]
ShotIntent = Literal[
    "establishing",
    "medium",
    "close_up",
    "extreme_close_up",
    "over_shoulder",
    "pov",
    "insert",
    "wide",
    "two_shot",
    "custom",
]
ImageCategory = Literal[
    "storyboard",
    "concept",
    "keyframe",
    "character",
    "location",
    "prop",
    "mood",
    "general",
]
ResolutionLabel = Literal["1K", "2K", "4K", "8K"]
ResolutionOrigin = Literal["native", "upscaled", "requested"]
ProviderReadiness = Literal[
    "ready",
    "not_installed",
    "needs_auth",
    "unhealthy",
    "disabled",
    "incompatible",
    "draft",
]


class CinematicControls(BaseModel):
    """Artist-facing cinematic controls compiled into creativeContext (not sampler jargon)."""

    lens: Optional[str] = None
    lighting: Optional[str] = None
    colorTreatment: Optional[str] = None
    visualEra: Optional[str] = None
    productionStyle: Optional[str] = None
    aspectRatio: str = "16:9"
    shotIntent: ShotIntent = "medium"
    customShotIntent: Optional[str] = None
    category: ImageCategory = "storyboard"


class AdvancedDiffusionControls(BaseModel):
    """Collapsed Advanced drawer only — never required on primary surface."""

    steps: Optional[int] = None
    guidance: Optional[float] = None
    seed: Optional[int] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    denoise: Optional[float] = None
    referenceWeights: dict[str, float] = Field(default_factory=dict)


class ImageProviderDescriptor(BaseModel):
    """Unified local + dock API image provider row for Best Match / Choose / All Models."""

    id: str
    displayName: str
    family: str
    source: Literal["local", "hosted", "docker"] = "local"
    readiness: ProviderReadiness = "not_installed"
    imageCapable: bool = True
    licenseNote: Optional[str] = None
    costHint: Optional[str] = None
    requiresPaidConfirmation: bool = False
    nativeResolutions: list[ResolutionLabel] = Field(default_factory=list)
    upscaleSupported: bool = False
    providerPreference: Optional[str] = None
    modelId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolutionTruth(BaseModel):
    label: ResolutionLabel
    origin: ResolutionOrigin
    width: int
    height: int
    note: Optional[str] = None


class GenerationProvenance(BaseModel):
    jobId: str
    assetId: Optional[str] = None
    providerId: Optional[str] = None
    family: Optional[str] = None
    continuitySessionId: Optional[str] = None
    panelId: Optional[str] = None
    sceneId: Optional[str] = None
    creativeContextDigest: Optional[str] = None
    resolution: Optional[ResolutionTruth] = None
    recommendationMode: Optional[GenerationMode] = None


class CinematicGenerateRequest(BaseModel):
    """Creator request for Cinematic Image Studio → maps into image_product body."""

    prompt: str = ""
    negativePrompt: str = ""
    projectId: str
    mode: GenerationMode = "best_match"
    modelFamilyPreference: Optional[str] = None
    providerId: Optional[str] = None
    modelId: Optional[str] = None
    batchSize: int = Field(default=1, ge=1, le=4)
    resolution: ResolutionLabel = "1K"
    controls: CinematicControls = Field(default_factory=CinematicControls)
    advanced: Optional[AdvancedDiffusionControls] = None
    referenceAssetIds: list[str] = Field(default_factory=list)
    sceneId: Optional[str] = None
    continuitySessionId: Optional[str] = None
    inheritContinuityFromScene: bool = False
    panelId: Optional[str] = None
    purpose: str = "storyboard"
    runPromptIntelligence: bool = True
    creativeContext: dict[str, Any] = Field(default_factory=dict)
    spatialMapId: Optional[str] = None
    spatialMapVersion: Optional[str] = None
    spatialCameraId: Optional[str] = None


def cinematic_to_image_product_body(req: CinematicGenerateRequest) -> dict[str, Any]:
    """Map cinematic request into existing image_product generate payload."""
    ctrl = req.controls
    creative = dict(req.creativeContext or {})
    creative.setdefault("sceneId", req.sceneId)
    creative.setdefault(
        "cinematography",
        {
            "lens": ctrl.lens,
            "shotIntent": ctrl.shotIntent,
            "customShotIntent": ctrl.customShotIntent,
            "aspectRatio": ctrl.aspectRatio,
        },
    )
    creative.setdefault(
        "lighting",
        {"setup": ctrl.lighting} if ctrl.lighting else {},
    )
    creative.setdefault(
        "visualLanguage",
        {
            "colorTreatment": ctrl.colorTreatment,
            "visualEra": ctrl.visualEra,
            "productionStyle": ctrl.productionStyle,
        },
    )
    if req.continuitySessionId:
        creative["continuitySessionId"] = req.continuitySessionId

    body: dict[str, Any] = {
        "prompt": req.prompt,
        "negative": req.negativePrompt,
        "purpose": req.purpose or ctrl.category,
        "aspect": ctrl.aspectRatio,
        "resolution": _resolution_product_label(req.resolution),
        "batchSize": req.batchSize,
        "modelFamilyPreference": req.modelFamilyPreference,
        "providerId": req.providerId,
        "modelId": req.modelId,
        "sceneId": req.sceneId,
        "panelId": req.panelId,
        "continuitySessionId": req.continuitySessionId,
        "continuityId": req.continuitySessionId,
        "referenceAssetIds": list(req.referenceAssetIds),
        "runPromptIntelligence": req.runPromptIntelligence,
        "creativeContext": creative,
        "generationMode": req.mode,
        "spatialMapId": req.spatialMapId,
        "spatialMapVersion": req.spatialMapVersion,
        "spatialCameraId": req.spatialCameraId,
        "cinematic": {
            "lens": ctrl.lens,
            "lighting": ctrl.lighting,
            "colorTreatment": ctrl.colorTreatment,
            "shotIntent": ctrl.shotIntent,
            "customShotIntent": ctrl.customShotIntent,
            "category": ctrl.category,
            "visualEra": ctrl.visualEra,
            "productionStyle": ctrl.productionStyle,
        },
    }
    if req.advanced:
        adv = req.advanced
        if adv.steps is not None:
            body["steps"] = adv.steps
        if adv.guidance is not None:
            body["guidance"] = adv.guidance
        if adv.seed is not None:
            body["seed"] = adv.seed
        if adv.sampler:
            body["sampler"] = adv.sampler
        if adv.scheduler:
            body["scheduler"] = adv.scheduler
        if adv.denoise is not None:
            body["denoise"] = adv.denoise
        if adv.referenceWeights:
            body["referenceWeights"] = adv.referenceWeights
    return body


def _resolution_product_label(label: ResolutionLabel) -> str:
    return {"1K": "1080p", "2K": "2K", "4K": "4K", "8K": "4K"}.get(label, "1080p")
