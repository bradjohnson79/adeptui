"""WorkflowResolver — product intent → CanonicalWorkflowContract (M41 4.1B)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

from .certified_registry import CertifiedWorkflow, get_workflow
from .job_model import ConcurrencyClass, ProviderKindVideo


@dataclass
class CanonicalWorkflowContract:
    """Executable contract consumed by QueueWorker (execute-only)."""

    intent: str
    workflow_id: str
    workflow_key: str
    workflow_version: str
    leaf_workflow_key: str
    leaf_workflow_version: str
    provider_kind: ProviderKindVideo
    engine: str
    builder_path: str | None
    concurrency_class: ConcurrencyClass
    cancellation_support: bool
    orchestration: bool
    inputs: dict[str, Any] = field(default_factory=dict)
    disclosures: list[str] = field(default_factory=list)
    fingerprint_expected: dict[str, str | None] = field(default_factory=dict)
    status: str = "Blocked"
    capability_id: str = ""
    required_inputs: list[str] = field(default_factory=list)
    output_contract: dict[str, Any] = field(default_factory=dict)
    cancellation_policy: dict[str, Any] = field(default_factory=dict)

    @property
    def versioned_key(self) -> str:
        return f"{self.leaf_workflow_key}@{self.leaf_workflow_version}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provider_kind"] = self.provider_kind.value
        d["provider"] = self.provider_kind.value
        d["concurrency_class"] = self.concurrency_class.value
        d["versionedKey"] = self.versioned_key
        # Public Wave 6 consumer aliases (camelCase + snake_case)
        d["workflowId"] = self.workflow_id
        d["workflowKey"] = self.workflow_key
        d["workflowVersion"] = self.workflow_version
        d["leafWorkflowKey"] = self.leaf_workflow_key
        d["leafWorkflowVersion"] = self.leaf_workflow_version
        d["requiredInputs"] = list(self.required_inputs)
        d["outputContract"] = dict(self.output_contract)
        d["cancellationPolicy"] = dict(self.cancellation_policy)
        d["concurrencyClass"] = self.concurrency_class.value
        return d


def _concurrency(wf: CertifiedWorkflow) -> ConcurrencyClass:
    if wf.provider_kind == ProviderKindVideo.EXTERNAL_API:
        return ConcurrencyClass.CLOUD
    if wf.vram_profile.minimum_gb >= 16:
        return ConcurrencyClass.HEAVY_LOCAL
    return ConcurrencyClass.LIGHT_LOCAL


LTX_25_GENERATOR_IDS = frozenset({
    "ltx-2.5-full",
    "ltx-2.5-distilled",
    "ltx-2.5-comfy",
})


def is_ltx_25_generator(generator_id: str | None) -> bool:
    return (generator_id or "").strip().lower() in LTX_25_GENERATOR_IDS


def local_video_identity(
    *,
    requested_model: str | None,
    leaf_workflow_key: str,
    ltx_23_checkpoint: str,
    ltx_25_checkpoint: str,
) -> dict[str, str]:
    """Requested Timeline id vs the checkpoint that will actually load.

    Never copies scene.engine (which defaults to minimax-h3) onto LTX jobs.
    """
    requested = (requested_model or "").strip()
    leaf = (leaf_workflow_key or "").strip()
    if is_ltx_25_generator(requested) or leaf.startswith("ltx_25"):
        resolved = ltx_25_checkpoint
    elif requested.startswith("ltx") or leaf.startswith("ltx"):
        resolved = ltx_23_checkpoint
    else:
        resolved = requested
    return {
        "requestedModel": requested or resolved,
        "resolvedRuntimeModel": resolved,
        "videoModel": resolved,
        "workflowKey": leaf,
    }


def _require(key: str) -> CertifiedWorkflow:
    """Resolve Certified workflows; Hunyuan/LTX 2.5 Built leaves allowed until cert."""
    from .certified_registry import assert_executable

    allow = str(key).startswith("hunyuan") or str(key).startswith("ltx_25")
    return assert_executable(key, allow_non_certified=allow)


def _leaf_for_scene(
    *,
    engine: str,
    has_start: bool,
    has_middle: bool,
    has_end: bool,
    has_audio: bool,
    wants_ingredients: bool,
    paid_fal: bool,
    fal_engine: str | None,
    generator_id: str | None = None,
) -> tuple[str, list[str]]:
    disclosures: list[str] = []
    eng = (engine or "minimax-h3").lower().strip()
    gen = (generator_id or "").strip().lower()

    if eng.startswith("fal") or paid_fal:
        key = {
            "fal_seedance": "fal.seedance",
            "fal.seedance": "fal.seedance",
            "fal_kling": "fal.kling",
            "fal.kling": "fal.kling",
            "fal_veo": "fal.veo",
            "fal.veo": "fal.veo",
            "fal_runway": "fal.runway",
            "fal.runway": "fal.runway",
        }.get((fal_engine or eng).lower(), "fal.seedance")
        return key, disclosures

    if wants_ingredients and eng != "wan":
        return "ltx.ingredients_ic_lora", disclosures

    if eng == "wan":
        if has_middle and (has_start or has_end):
            return "wan.three_frame", disclosures
        if has_middle and not has_end:
            disclosures.append("WAN three-frame: middle present without end; using three_frame builder.")
            return "wan.three_frame", disclosures
        return "wan.first_last_frame", disclosures

    if eng in {"hunyuan15", "hunyuan13b"}:
        prefix = "hunyuan15" if eng == "hunyuan15" else "hunyuan13b"
        if has_start:
            return f"{prefix}.i2v", disclosures
        return f"{prefix}.t2v", disclosures

    # LTX 2.5 — Timeline ids must not silently resolve to the 2.3 leaf.
    if is_ltx_25_generator(gen) or eng in {"ltx-2.5", "ltx-2.5-distilled", "ltx-2.5-full", "ltx-2.5-comfy"}:
        if has_start:
            return "ltx_25.i2v", disclosures
        return "ltx_25.t2v", disclosures

    # LTX 2.3
    if has_start and not has_middle and not has_end and not has_audio:
        return "ltx.simple_i2v", disclosures
    return "ltx.scene", disclosures


def resolve_workflow(
    intent: str,
    *,
    engine: str = "ltx",
    present_inputs: Mapping[str, Any] | None = None,
    paid_fal_approved: bool = False,
    fal_engine: str | None = None,
    wants_ingredients: bool = False,
    force_workflow_key: str | None = None,
    generator_id: str | None = None,
) -> CanonicalWorkflowContract:
    """
    Resolve a product intent into a canonical execute contract.

    Intents: shot_render, scene_render, timeline_render, batch_timeline,
             extend, lipsync, txt2vid, txt2vid_cloud
    """
    present = dict(present_inputs or {})
    has_start = bool(
        present.get("start_frame")
        or present.get("start_asset_id")
        or present.get("start_image")
        or present.get("first_frame")
    )
    has_middle = bool(
        present.get("middle_frame")
        or present.get("middle_asset_id")
        or present.get("middle_image")
    )
    has_end = bool(
        present.get("end_frame")
        or present.get("end_asset_id")
        or present.get("end_image")
        or present.get("last_frame")
    )
    has_audio = bool(present.get("audio") or present.get("audio_asset_id") or present.get("audio_file"))

    intent_n = (intent or "").strip().lower()
    disclosures: list[str] = []

    if force_workflow_key:
        leaf_key = force_workflow_key
        orch_key = force_workflow_key
    elif intent_n == "lipsync":
        leaf_key = "lipsync.latentsync"
        orch_key = leaf_key
    elif intent_n == "extend":
        orch_key = "video.extend"
        # Leaf is local I2V — prefer LTX simple unless engine=wan or Timeline 2.5
        if engine == "wan":
            leaf_key = "wan.first_last_frame"
        elif is_ltx_25_generator(generator_id):
            leaf_key = "ltx_25.i2v"
        else:
            leaf_key = "ltx.simple_i2v"
        disclosures.append("video.extend: last-frame → certified local I2V")
    elif intent_n == "timeline_render":
        orch_key = "director.timeline_render"
        leaf_key = orch_key
    elif intent_n == "batch_timeline":
        orch_key = "director.batch_timeline"
        leaf_key = orch_key
    elif intent_n in {"shot_render", "scene_render", "txt2vid", "txt2vid_local", "txt2vid_cloud"}:
        orch_key = "director.shot_render" if intent_n == "shot_render" else "director.scene_render"
        if intent_n == "txt2vid_cloud" or (paid_fal_approved and not has_start and intent_n == "txt2vid"):
            leaf_key, more = _leaf_for_scene(
                engine=fal_engine or engine,
                has_start=has_start,
                has_middle=has_middle,
                has_end=has_end,
                has_audio=has_audio,
                wants_ingredients=False,
                paid_fal=True,
                fal_engine=fal_engine or engine,
                generator_id=generator_id,
            )
            disclosures.extend(more)
        elif intent_n in {"txt2vid", "txt2vid_local"} and not has_start and not paid_fal_approved:
            from .hunyuan_providers import allow_local_t2v

            if not allow_local_t2v(engine):
                raise RuntimeError(
                    "LOCAL_START_FRAME_REQUIRED: local video generation is I2V-only "
                    "(Hunyuan true local T2V requires per-provider certification)"
                )
            leaf_key, more = _leaf_for_scene(
                engine=engine,
                has_start=False,
                has_middle=has_middle,
                has_end=has_end,
                has_audio=has_audio,
                wants_ingredients=False,
                paid_fal=False,
                fal_engine=fal_engine,
                generator_id=generator_id,
            )
            disclosures.extend(more)
            disclosures.append(f"true_local_t2v:{engine}")
        else:
            leaf_key, more = _leaf_for_scene(
                engine=engine,
                has_start=has_start,
                has_middle=has_middle,
                has_end=has_end,
                has_audio=has_audio,
                wants_ingredients=wants_ingredients,
                paid_fal=paid_fal_approved and engine.startswith("fal"),
                fal_engine=fal_engine,
                generator_id=generator_id,
            )
            disclosures.extend(more)
    else:
        raise RuntimeError(f"Unknown workflow intent: {intent}")

    orch = _require(orch_key) if orch_key != leaf_key and get_workflow(orch_key) else None
    leaf = _require(leaf_key)
    primary = orch if orch and orch.orchestration else leaf
    cancel_policy = {
        "supported": bool(leaf.cancellation_support),
        "deepCancelRequired": bool(leaf.cancellation_support and leaf.provider_kind != ProviderKindVideo.EXTERNAL_API),
        "optimisticCancelForbidden": True,
    }
    output_contract = {
        "supportedOutputs": list(leaf.supported_outputs),
        "outputValidation": bool(leaf.output_validation),
        "playbackValidation": bool(leaf.playback_validation),
        "assetRegistrationRequired": True,
    }

    return CanonicalWorkflowContract(
        intent=intent_n,
        workflow_id=primary.workflow_id,
        workflow_key=primary.workflow_key,
        workflow_version=primary.workflow_version,
        leaf_workflow_key=leaf.workflow_key,
        leaf_workflow_version=leaf.workflow_version,
        provider_kind=leaf.provider_kind,
        engine=leaf.engine or engine,
        builder_path=leaf.builder_path,
        concurrency_class=_concurrency(leaf),
        cancellation_support=leaf.cancellation_support,
        orchestration=bool(primary.orchestration),
        inputs=dict(present),
        disclosures=disclosures,
        fingerprint_expected=leaf.fingerprints.to_dict(),
        status=leaf.status,
        capability_id=leaf.capability_id,
        required_inputs=list(leaf.supported_inputs),
        output_contract=output_contract,
        cancellation_policy=cancel_policy,
    )


def resolve_from_scene_params(
    *,
    engine: str,
    start_asset_id: Optional[str] = None,
    middle_asset_id: Optional[str] = None,
    end_asset_id: Optional[str] = None,
    audio_asset_id: Optional[str] = None,
    wants_ingredients: bool = False,
    paid_fal_approved: bool = False,
    intent: str = "scene_render",
    generator_id: Optional[str] = None,
) -> CanonicalWorkflowContract:
    return resolve_workflow(
        intent,
        engine=engine,
        present_inputs={
            "start_asset_id": start_asset_id,
            "middle_asset_id": middle_asset_id,
            "end_asset_id": end_asset_id,
            "audio_asset_id": audio_asset_id,
        },
        paid_fal_approved=paid_fal_approved,
        wants_ingredients=wants_ingredients,
        generator_id=generator_id,
    )
