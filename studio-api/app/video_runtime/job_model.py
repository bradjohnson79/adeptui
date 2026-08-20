"""Canonical video job contract shared by local Comfy and cloud providers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class ProviderKindVideo(str, Enum):
    LOCAL = "local"
    EXTERNAL_API = "external_api"


class ConcurrencyClass(str, Enum):
    HEAVY_LOCAL = "heavy_local"
    LIGHT_LOCAL = "light_local"
    CLOUD = "cloud"


class VramSafetyState(str, Enum):
    SAFE = "VRAM_SAFE"
    TIGHT = "VRAM_TIGHT"
    HIGH_RISK = "VRAM_HIGH_RISK"
    INSUFFICIENT = "VRAM_INSUFFICIENT"
    UNKNOWN = "VRAM_UNKNOWN"


class NormalizedStage(str, Enum):
    VALIDATING = "validating"
    QUEUED = "queued"
    LOADING_MODELS = "loading_models"
    ENCODING = "encoding"
    SAMPLING = "sampling"
    DECODING = "decoding"
    WRITING_OUTPUT = "writing_output"
    REGISTERING_ASSET = "registering_asset"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    CANCEL_FAILED_RUNTIME_ACTIVE = "cancel_failed_runtime_active"
    FAILED = "failed"
    OUTPUT_INVALID = "output_invalid"
    OUTPUT_MISSING = "output_missing"
    OUTPUT_UNPLAYABLE = "output_unplayable"
    REGISTRATION_FAILED = "registration_failed"


CANONICAL_STAGES: tuple[str, ...] = tuple(s.value for s in NormalizedStage)


class FailureClass(str, Enum):
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    WORKFLOW_INVALID = "workflow_invalid"
    NODE_MISSING = "node_missing"
    MODEL_MISSING = "model_missing"
    MODEL_PATH_INVALID = "model_path_invalid"
    INPUT_INVALID = "input_invalid"
    UNSUPPORTED_RESOLUTION = "unsupported_resolution"
    UNSUPPORTED_FRAME_COUNT = "unsupported_frame_count"
    VRAM_EXHAUSTED = "vram_exhausted"
    CUDA_FAILURE = "cuda_failure"
    PROCESS_TERMINATED = "process_terminated"
    PROVIDER_REJECTED = "provider_rejected"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_QUOTA = "provider_quota_exceeded"
    SAFETY_REJECTION = "safety_rejection"
    OUTPUT_MISSING = "output_missing"
    OUTPUT_CORRUPT = "output_corrupt"
    PLAYBACK_UNSUPPORTED = "browser_playback_unsupported"
    REGISTRATION_FAILURE = "registration_failure"
    USER_CANCELLATION = "user_cancellation"
    RUNTIME_CANCEL_FAILURE = "runtime_cancellation_failure"
    COMFY_CANCEL_NOT_CONFIRMED = "COMFY_CANCEL_NOT_CONFIRMED"
    WORKFLOW_GRAPH_DRIFT = "WORKFLOW_GRAPH_DRIFT"
    WORKFLOW_NOT_CERTIFIED = "workflow_not_certified"
    UNKNOWN = "unknown"


@dataclass
class VideoJobContract:
    mode: str
    workflow_key: str
    provider_kind: ProviderKindVideo
    engine: str = ""
    model_id: str = ""
    project_id: str = ""
    scene_id: str | None = None
    concurrency_class: ConcurrencyClass = ConcurrencyClass.HEAVY_LOCAL
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    fps: int | None = None
    seed: int | None = None
    batch: int = 1
    start_asset_id: str | None = None
    end_asset_id: str | None = None
    middle_asset_id: str | None = None
    audio_asset_id: str | None = None
    vram_estimate_gb: float | None = None
    vram_state: VramSafetyState = VramSafetyState.UNKNOWN
    stage: NormalizedStage = NormalizedStage.QUEUED
    failure_class: FailureClass | None = None
    retry_eligible: bool = True
    compute_consumed: bool = False
    partial_output_path: str | None = None
    comfy_prompt_id: str | None = None
    safe_config_applied: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provider_kind"] = self.provider_kind.value
        d["concurrency_class"] = self.concurrency_class.value
        d["vram_state"] = self.vram_state.value
        d["stage"] = self.stage.value
        d["failure_class"] = self.failure_class.value if self.failure_class else None
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VideoJobContract":
        def _enum(enum_cls: type[Enum], key: str, default: Enum) -> Enum:
            raw = data.get(key)
            if raw is None:
                return default
            try:
                return enum_cls(raw)
            except ValueError:
                return default

        return cls(
            mode=str(data.get("mode") or "unknown"),
            workflow_key=str(data.get("workflow_key") or ""),
            provider_kind=_enum(ProviderKindVideo, "provider_kind", ProviderKindVideo.LOCAL),  # type: ignore[arg-type]
            engine=str(data.get("engine") or ""),
            model_id=str(data.get("model_id") or ""),
            project_id=str(data.get("project_id") or ""),
            scene_id=data.get("scene_id"),
            concurrency_class=_enum(ConcurrencyClass, "concurrency_class", ConcurrencyClass.HEAVY_LOCAL),  # type: ignore[arg-type]
            width=data.get("width"),
            height=data.get("height"),
            frames=data.get("frames"),
            fps=data.get("fps"),
            seed=data.get("seed"),
            batch=int(data.get("batch") or 1),
            start_asset_id=data.get("start_asset_id"),
            end_asset_id=data.get("end_asset_id"),
            middle_asset_id=data.get("middle_asset_id"),
            audio_asset_id=data.get("audio_asset_id"),
            vram_estimate_gb=data.get("vram_estimate_gb"),
            vram_state=_enum(VramSafetyState, "vram_state", VramSafetyState.UNKNOWN),  # type: ignore[arg-type]
            stage=_enum(NormalizedStage, "stage", NormalizedStage.QUEUED),  # type: ignore[arg-type]
            failure_class=(
                FailureClass(data["failure_class"])
                if data.get("failure_class")
                else None
            ),
            retry_eligible=bool(data.get("retry_eligible", True)),
            compute_consumed=bool(data.get("compute_consumed", False)),
            partial_output_path=data.get("partial_output_path"),
            comfy_prompt_id=data.get("comfy_prompt_id"),
            safe_config_applied=list(data.get("safe_config_applied") or []),
            extra=dict(data.get("extra") or {}),
        )


def apply_contract_to_job_params(params: dict[str, Any] | None, contract: VideoJobContract) -> str:
    """Embed canonical contract under params.videoRuntime (JSON string for Job.params_json)."""
    base = dict(params or {})
    base["videoRuntime"] = contract.to_dict()
    return json.dumps(base)


def extract_contract_from_job(job: Any) -> Optional[VideoJobContract]:
    try:
        params = json.loads(getattr(job, "params_json", None) or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(params, dict):
        return None
    vr = params.get("videoRuntime")
    if not isinstance(vr, dict):
        return None
    return VideoJobContract.from_dict(vr)


def merge_video_runtime_history(history_json: str | None, patch: Mapping[str, Any]) -> str:
    try:
        history = json.loads(history_json or "{}")
        if not isinstance(history, dict):
            history = {}
    except json.JSONDecodeError:
        history = {}
    vr = history.get("videoRuntime")
    if not isinstance(vr, dict):
        vr = {}
    incoming = dict(patch)
    hops = incoming.get("queueHops")
    if isinstance(hops, dict):
        prev = vr.get("queueHops") if isinstance(vr.get("queueHops"), dict) else {}
        merged = dict(prev)
        merged.update(hops)
        incoming["queueHops"] = merged
    vr.update(incoming)
    history["videoRuntime"] = vr
    return json.dumps(history)


def concurrency_for_workflow(workflow_key: str, provider_kind: ProviderKindVideo) -> ConcurrencyClass:
    if provider_kind == ProviderKindVideo.EXTERNAL_API:
        return ConcurrencyClass.CLOUD
    if workflow_key.startswith("lipsync.") or workflow_key.startswith("image."):
        return ConcurrencyClass.LIGHT_LOCAL
    return ConcurrencyClass.HEAVY_LOCAL
