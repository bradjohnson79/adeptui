"""Honest generator capability registry for Timeline Master."""

from __future__ import annotations

from typing import Any

from .contracts import GeneratorCapability, InPaintStrategy


def list_generators() -> list[GeneratorCapability]:
    from ..video_runtime.hunyuan_providers import HUNYUAN_13B, HUNYUAN_15, describe_provider
    from .generation.adapters.stub_cert import stub_enabled

    hy15 = describe_provider(HUNYUAN_15)
    hy13 = describe_provider(HUNYUAN_13B)
    gens = [
        GeneratorCapability(
            id="minimax-h3-local",
            label="MiniMax H3 (Local)",
            locality="local",
            providerId="minimax-h3",
            capabilityLabel="Testing",
            maxDurationSec=5.0,
            supportsStartEndFrame=False,
            supportsContinuation=False,
            inPaintStrategies=["complete_batch_retake"],
            executable=True,
            supportsQueuedCancel=True,
            supportsRunningCancel=True,
            supportsInterrupt=True,
            draftPathway="none",
            notes=(
                "Experimental Private Profile — text-to-video with native audio. "
                "Routes through the shared Timeline generation adapter registry."
            ),
        ),
        GeneratorCapability(
            id="ltx-local",
            label="LTX 2.3/2.5 (Local)",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified",
            maxDurationSec=20.0,
            supportsStartEndFrame=True,
            supportsContinuation=True,
            supportsAudio=True,
            inPaintStrategies=["range_replacement", "complete_batch_retake", "keyframe_repair"],
            executable=True,
            supportsQueuedCancel=True,
            supportsRunningCancel=True,
            supportsInterrupt=True,
            draftPathway="local_live",
            draftResolution="768x432",
            finalResolution="1280x720",
            finalRequiresNewGeneration=True,
            notes="Default production engine. LTX 2.5 variants available via ltx-2.5-full, ltx-2.5-distilled, ltx-2.5-comfy.",
        ),
        GeneratorCapability(
            id="ltx-2.5-full",
            label="LTX 2.5 Full",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified",
            maxDurationSec=20.0,
            supportsStartEndFrame=True,
            supportsContinuation=True,
            supportsAudio=True,
            inPaintStrategies=["range_replacement", "complete_batch_retake", "keyframe_repair"],
            executable=True,
            supportsQueuedCancel=True,
            supportsRunningCancel=True,
            supportsInterrupt=True,
            draftPathway="local_live",
            notes="Full-precision LTX 2.5 with native audio. Recommended for high-quality production.",
        ),
        GeneratorCapability(
            id="ltx-2.5-distilled",
            label="LTX 2.5 Distilled",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified",
            maxDurationSec=20.0,
            supportsStartEndFrame=True,
            supportsContinuation=True,
            supportsAudio=True,
            inPaintStrategies=["range_replacement", "complete_batch_retake", "keyframe_repair"],
            executable=True,
            supportsQueuedCancel=True,
            supportsRunningCancel=True,
            supportsInterrupt=True,
            draftPathway="local_live",
            notes="Distilled BF16 LTX 2.5 with fast generation and native audio. Default for auto mode.",
        ),
        GeneratorCapability(
            id="ltx-2.5-comfy",
            label="LTX 2.5 Comfy INT8",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified",
            maxDurationSec=20.0,
            supportsStartEndFrame=True,
            supportsContinuation=True,
            supportsAudio=False,
            inPaintStrategies=["range_replacement", "complete_batch_retake", "keyframe_repair"],
            executable=True,
            supportsQueuedCancel=True,
            supportsRunningCancel=True,
            supportsInterrupt=True,
            draftPathway="local_live",
            notes="INT8 quantized LTX 2.5 for reduced VRAM. No native audio generation.",
        ),
        GeneratorCapability(
            id="wan-local",
            label="WAN 2.2 I2V (Local)",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified",
            maxDurationSec=8.0,
            supportsStartEndFrame=True,
            supportsContinuation=True,
            inPaintStrategies=["range_replacement", "complete_batch_retake"],
            executable=True,
            supportsTimelineGeneration=False,
            notes="No Timeline adapter registered; available for scene render only.",
        ),
        GeneratorCapability(
            id="hunyuan-video-1.5-local",
            label="HunyuanVideo 1.5 (Local)",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified" if hy15.executable else "Requires Setup",
            maxDurationSec=10.0,
            supportsStartEndFrame=False,
            supportsContinuation=False,
            inPaintStrategies=["range_replacement", "complete_batch_retake"],
            executable=hy15.executable,
            supportsTimelineGeneration=False,
            notes="; ".join(hy15.notes)
            or "Optional Hunyuan provider. True local T2V only after per-provider certification.",
        ),
        GeneratorCapability(
            id="hunyuan-video-13b-local",
            label="HunyuanVideo 13B (Local Advanced)",
            locality="local",
            providerId="comfy",
            capabilityLabel="Certified" if hy13.executable else "Requires Setup",
            maxDurationSec=10.0,
            supportsStartEndFrame=False,
            supportsContinuation=False,
            inPaintStrategies=["range_replacement", "complete_batch_retake"],
            executable=hy13.executable,
            supportsTimelineGeneration=False,
            notes="; ".join(hy13.notes)
            or "Advanced Hunyuan provider. Official FP8 profile when hardware recommends it.",
        ),
        GeneratorCapability(
            id="seedance-kie",
            label="Seedance 2.0 — Kie.ai",
            locality="hosted",
            providerId="kie",
            capabilityLabel="Testing",
            maxDurationSec=12.0,
            supportsStartEndFrame=True,
            inPaintStrategies=["complete_batch_retake"],
            executable=False,
            draftPathway="cheap_preview",
            supportsVideoReferences=True,
            supportsImageAndVideoTogether=True,
            maximumReferenceVideos=1,
            notes="Executable only when discovered API model is Ready.",
        ),
        GeneratorCapability(
            id="kling-fal",
            label="Kling 3.0 — fal.ai",
            locality="hosted",
            providerId="fal",
            capabilityLabel="Certified",
            maxDurationSec=10.0,
            supportsStartEndFrame=True,
            inPaintStrategies=["complete_batch_retake"],
            executable=False,
            draftPathway="none",
            supportsQueuedCancel=False,
            supportsRunningCancel=False,
            notes="Draft Mode is unavailable. Cancellation after submit is unavailable.",
        ),
        GeneratorCapability(
            id="comfy-workflow",
            label="ComfyUI Workflow",
            locality="local",
            providerId="comfy",
            capabilityLabel="Available",
            inPaintStrategies=["keyframe_repair", "complete_batch_retake"],
            executable=False,
            notes="Requires Setup for project-specific workflows.",
        ),
    ]
    # CERT_STUB_ENV_GATED: cert stub generator visible only in certification runs.
    if stub_enabled():
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
                inPaintStrategies=["range_replacement", "complete_batch_retake"],
                executable=True,
                supportsTimelineGeneration=True,
                notes=(
                    "Certification stub — replaces the provider execution boundary. "
                    "Records requests; never executes GPU code."
                ),
            )
        )
    return gens


def get_generator(generator_id: str | None) -> GeneratorCapability | None:
    if not generator_id:
        return None
    return next((g for g in list_generators() if g.id == generator_id), None)


def registry_snapshot() -> dict[str, Any]:
    gens = list_generators()
    return {
        "ok": True,
        "generators": [g.model_dump() for g in gens],
        "nativeVideoInPaintCertified": False,
        "defaultInPaintStrategy": "range_replacement",
        "mock": False,
    }


def validate_duration(generator_id: str | None, planned: float) -> dict[str, Any]:
    gen = get_generator(generator_id)
    if not gen or gen.maxDurationSec is None:
        return {"ok": True, "action": "keep", "plannedDuration": planned, "maxDurationSec": None}
    if planned <= gen.maxDurationSec + 1e-6:
        return {"ok": True, "action": "keep", "plannedDuration": planned, "maxDurationSec": gen.maxDurationSec}
    return {
        "ok": False,
        "action": "choose",
        "plannedDuration": planned,
        "maxDurationSec": gen.maxDurationSec,
        "options": ["split", "shorten", "keep", "cancel"],
        "message": f"Planned duration {planned}s exceeds {gen.label} max {gen.maxDurationSec}s — no silent truncate.",
    }


def disclose_inpaint_strategy(generator_id: str | None, requested: InPaintStrategy | None) -> dict[str, Any]:
    gen = get_generator(generator_id)
    requested = requested or "range_replacement"
    if requested == "native":
        # ok=False means nativeRequestSatisfied=False — not an overall Inpaint failure.
        return {
            "ok": False,
            "nativeRequestSatisfied": False,
            "fallbackAccepted": True,
            "executionReady": True,
            "strategy": "range_replacement",
            "requested": "native",
            "disclosed": True,
            "message": "Native video InPaint is not certified. Using range_replacement.",
            "mock": False,
        }
    supported = list(gen.inPaintStrategies) if gen else ["complete_batch_retake"]
    if requested not in supported:
        fallback = supported[0] if supported else "complete_batch_retake"
        return {
            "ok": True,
            "nativeRequestSatisfied": None,
            "fallbackAccepted": True,
            "executionReady": True,
            "strategy": fallback,
            "requested": requested,
            "disclosed": True,
            "message": f"{requested} unsupported for generator; using {fallback}.",
            "mock": False,
        }
    return {
        "ok": True,
        "nativeRequestSatisfied": None,
        "fallbackAccepted": False,
        "executionReady": True,
        "strategy": requested,
        "requested": requested,
        "disclosed": True,
        "mock": False,
    }
