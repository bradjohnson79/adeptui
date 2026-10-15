"""Versioned registry boundary for existing, unmodified workflow builders."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ..providers import ProviderKind
from .image_tools import build_zimage_ref_workflow, build_zimage_txt2img_workflow
from .lipsync_builder import build_latentsync_workflow
from .ltx_builder import build_ltx_scene_workflow, build_ltx_simple_i2v
from .ltx_ingredients_compiler import compile_ingredients_workflow
from .wan_builder import build_wan_flf_workflow

WorkflowBuilder = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class WorkflowInput:
    name: str
    type_name: str = "any"
    description: str = ""


@dataclass(frozen=True)
class WorkflowCompatibility:
    engine: str
    required_node_types: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class WorkflowValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class WorkflowValidationResult:
    valid: bool
    issues: tuple[WorkflowValidationIssue, ...] = ()


class WorkflowValidator(Protocol):
    def validate(
        self, metadata: "WorkflowMetadata", inputs: Mapping[str, Any]
    ) -> WorkflowValidationResult: ...


class RequiredInputValidator:
    """Validate metadata requirements without invoking workflow builders."""

    def validate(
        self, metadata: "WorkflowMetadata", inputs: Mapping[str, Any]
    ) -> WorkflowValidationResult:
        issues = tuple(
            WorkflowValidationIssue(item.name, "Required input is missing")
            for item in metadata.required_inputs
            if item.name not in inputs
        )
        return WorkflowValidationResult(valid=not issues, issues=issues)


@dataclass(frozen=True)
class WorkflowMetadata:
    """Versioned compatibility and invocation metadata for one builder."""

    key: str
    family: str
    modality: str
    builder: WorkflowBuilder
    builder_path: str
    capabilities: tuple[str, ...]
    template_version: str
    supported_provider_kinds: tuple[ProviderKind, ...]
    required_inputs: tuple[WorkflowInput, ...]
    compatibility: WorkflowCompatibility
    validator: WorkflowValidator


class WorkflowRegistry(Protocol):
    """Lookup and metadata-only validation boundary."""

    def get(self, key: str) -> WorkflowMetadata: ...

    def list(self) -> tuple[WorkflowMetadata, ...]: ...

    def validate(
        self, key: str, inputs: Mapping[str, Any]
    ) -> WorkflowValidationResult: ...


class StaticWorkflowRegistry:
    """Immutable registry suitable for inventory and later composition."""

    def __init__(self, entries: Iterable[WorkflowMetadata]) -> None:
        registered = tuple(entries)
        by_key = {entry.key: entry for entry in registered}
        if len(by_key) != len(registered):
            raise ValueError("Workflow keys must be unique")
        self._entries = by_key

    def get(self, key: str) -> WorkflowMetadata:
        return self._entries[key]

    def list(self) -> tuple[WorkflowMetadata, ...]:
        return tuple(self._entries.values())

    def validate(
        self, key: str, inputs: Mapping[str, Any]
    ) -> WorkflowValidationResult:
        metadata = self.get(key)
        return metadata.validator.validate(metadata, inputs)


_VALIDATOR = RequiredInputValidator()


def _entry(
    *,
    key: str,
    family: str,
    modality: str,
    builder: WorkflowBuilder,
    builder_path: str,
    capabilities: tuple[str, ...],
    required_inputs: tuple[str, ...],
    required_node_types: tuple[str, ...],
) -> WorkflowMetadata:
    return WorkflowMetadata(
        key=key,
        family=family,
        modality=modality,
        builder=builder,
        builder_path=builder_path,
        capabilities=capabilities,
        template_version="1.0.0",
        supported_provider_kinds=(ProviderKind.LOCAL,),
        required_inputs=tuple(WorkflowInput(name) for name in required_inputs),
        compatibility=WorkflowCompatibility(
            engine="comfyui",
            required_node_types=required_node_types,
            notes="Inventory metadata only; runtime compatibility is not probed.",
        ),
        validator=_VALIDATOR,
    )


WORKFLOW_INVENTORY = (
    _entry(
        key="ltx.scene",
        family="ltx",
        modality="video",
        builder=build_ltx_scene_workflow,
        builder_path="app.workflows.ltx_builder:build_ltx_scene_workflow",
        capabilities=("text_to_video", "image_to_video", "audio_guidance", "keyframes"),
        required_inputs=(
            "checkpoint", "positive", "negative", "width", "height", "length", "fps", "seed"
        ),
        required_node_types=("LTXDirector", "LTXDirectorGuide", "SaveVideo"),
    ),
    _entry(
        key="ltx.simple_i2v",
        family="ltx",
        modality="video",
        builder=build_ltx_simple_i2v,
        builder_path="app.workflows.ltx_builder:build_ltx_simple_i2v",
        capabilities=("image_to_video",),
        required_inputs=(
            "checkpoint", "positive", "negative", "width", "height", "length", "fps", "seed",
            "start_image",
        ),
        required_node_types=("LTXVImgToVideo", "VHS_VideoCombine"),
    ),
    _entry(
        key="ltx.ingredients_ic_lora",
        family="ltx",
        modality="video",
        builder=compile_ingredients_workflow,
        builder_path="app.workflows.ltx_ingredients_compiler:compile_ingredients_workflow",
        capabilities=("text_to_video", "image_to_video", "ic_lora", "ingredients_reference"),
        required_inputs=(
            "object_info", "checkpoint", "positive", "negative", "width", "height", "length",
            "fps", "seed", "reference_image",
        ),
        required_node_types=(
            "LTXICLoRALoaderModelOnly", "LTXAddVideoICLoRAGuide", "EmptyLTXVLatentVideo", "SaveVideo",
        ),
    ),
    _entry(
        key="wan.first_last_frame",
        family="wan",
        modality="video",
        builder=build_wan_flf_workflow,
        builder_path="app.workflows.wan_builder:build_wan_flf_workflow",
        capabilities=("text_to_video", "image_to_video", "first_last_frame"),
        required_inputs=(
            "high_noise", "low_noise", "vae_name", "text_encoder", "positive", "negative",
            "width", "height", "length", "fps", "seed",
        ),
        required_node_types=("WanImageToVideo", "WanFirstLastFrameToVideo", "VHS_VideoCombine"),
    ),
    _entry(
        key="lipsync.latentsync",
        family="latentsync",
        modality="video",
        builder=build_latentsync_workflow,
        builder_path="app.workflows.lipsync_builder:build_latentsync_workflow",
        capabilities=("lipsync", "audio_conditioning"),
        required_inputs=("video_path", "audio_path"),
        required_node_types=("LatentSyncNode", "VHS_VideoCombine"),
    ),
    _entry(
        key="image.txt2img",
        family="zimage",
        modality="image",
        builder=build_zimage_txt2img_workflow,
        builder_path="app.workflows.image_tools:build_zimage_txt2img_workflow",
        capabilities=("text_to_image",),
        required_inputs=(
            "unet_name", "clip_name", "vae_name", "positive", "negative", "width", "height", "seed",
        ),
        required_node_types=(
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "ModelSamplingAuraFlow",
            "TextEncodeZImageOmni",
            "KSampler",
            "SaveImage",
        ),
    ),
    _entry(
        key="image.img2img_edit",
        family="zimage",
        modality="image",
        builder=build_zimage_ref_workflow,
        builder_path="app.workflows.image_tools:build_zimage_ref_workflow",
        capabilities=("image_to_image", "editing", "reference_image"),
        required_inputs=(
            "unet_name", "clip_name", "vae_name", "clip_vision_name", "reference_image", "prompt",
        ),
        required_node_types=("TextEncodeZImageOmni", "LoadImage", "KSampler", "SaveImage"),
    ),
    _entry(
        key="image.zimage_reference",
        family="zimage",
        modality="image",
        builder=build_zimage_ref_workflow,
        builder_path="app.workflows.image_tools:build_zimage_ref_workflow",
        capabilities=("text_to_image", "reference_image"),
        required_inputs=(
            "unet_name", "clip_name", "vae_name", "clip_vision_name", "reference_image",
            "prompt",
        ),
        required_node_types=("TextEncodeZImageOmni", "KSampler", "SaveImage"),
    ),
)

DEFAULT_WORKFLOW_REGISTRY: WorkflowRegistry = StaticWorkflowRegistry(WORKFLOW_INVENTORY)
