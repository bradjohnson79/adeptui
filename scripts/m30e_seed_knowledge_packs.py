#!/usr/bin/env python3
"""Seed M3.0e knowledge packs under studio-api/app/codirector/model_intelligence/packs/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "studio-api" / "app" / "codirector" / "model_intelligence" / "packs"


def write(pack: str, name: str, content: str) -> None:
    d = PACKS / pack
    d.mkdir(parents=True, exist_ok=True)
    (d / "examples").mkdir(exist_ok=True)
    (d / name).write_text(content.strip() + "\n", encoding="utf-8")


def seed_common(
    model_id: str,
    *,
    provider_id: str,
    engine_id: str,
    display: str,
    version: str,
    status: str,
    runtime: str,
    media: list[str],
    modes: list[str],
    native_audio: bool,
    generate_audio_param: str | None,
    music_class: str,
    max_duration: float | None,
    capability_map: dict,
    overall_conf: float,
    limitations: list[str],
    positive_append: list[str] | None = None,
    negative_base: list[str] | None = None,
    example_line: str = "EXAMPLE ONLY: laboratory observation room with sample character",
) -> None:
    write(
        model_id,
        "manifest.yaml",
        f"""
schemaVersion: 1
modelId: {model_id}
providerId: {provider_id}
engineId: {engine_id}
displayName: "{display}"
modelVersion: "{version}"
knowledgePackVersion: "1.0.0"
status: {status}
runtimeStatus: {runtime}
media: {media!r}
modes: {modes!r}
documentation:
  officialSources: []
  releaseNotes: []
  retrievedAt: null
  reviewedAt: "2026-07-27"
confidence:
  overall: {overall_conf}
licensing:
  summary: null
  commercialUse: unknown
  redistribution: unknown
maintainers: ["adept-ui-m30e"]
""".replace("'", '"') if False else f"""
schemaVersion: 1
modelId: {model_id}
providerId: {provider_id}
engineId: {engine_id}
displayName: "{display}"
modelVersion: "{version}"
knowledgePackVersion: "1.0.0"
status: {status}
runtimeStatus: {runtime}
media:
{chr(10).join('  - ' + m for m in media)}
modes:
{chr(10).join('  - ' + m for m in modes)}
documentation:
  officialSources: []
  releaseNotes: []
  retrievedAt: null
  reviewedAt: "2026-07-27"
confidence:
  overall: {overall_conf}
licensing:
  summary: null
  commercialUse: unknown
  redistribution: unknown
maintainers:
  - adept-ui-m30e
""",
    )
    caps_yaml = "capabilities:\n" + "\n".join(f"  {k}: {v}" for k, v in capability_map.items())
    write(model_id, "capabilities.yaml", caps_yaml)
    write(
        model_id,
        "parameters.yaml",
        f"""
maxDurationSec: {max_duration if max_duration is not None else 'null'}
maxReferenceImages: 4
allowedOverrides:
  - seed
  - durationSec
  - aspectRatio
  - preserveExactWording
  - generate_audio
""",
    )
    write(
        model_id,
        "prompt_rules.yaml",
        f"""
positiveAppend:
{chr(10).join('  - "' + p + '"' for p in (positive_append or [])) or '  []'}
negativeBase:
{chr(10).join('  - "' + p + '"' for p in (negative_base or ['blurry', 'low quality', 'watermark']))}
fallbacks: []
""",
    )
    gap = generate_audio_param or "null"
    write(
        model_id,
        "audio_behavior.yaml",
        f"""
supportsNativeAudio: {str(native_audio).lower()}
generateAudioParam: {gap if gap != 'null' else 'null'}
generateAudioOfficial: {str(bool(generate_audio_param)).lower()}
musicSuppressionClassification: {music_class}
musicProhibitedNegative:
  - background music
  - musical score
  - soundtrack
  - theme song
musicProhibitedPositive: []
musicSuppressionDisclosure: >
  {limitations[0] if limitations else 'See limitations.'}
""",
    )
    write(
        model_id,
        "limitations.yaml",
        "items:\n" + "\n".join(f'  - "{x}"' for x in limitations),
    )
    write(
        model_id,
        "workarounds.yaml",
        """
items:
  - id: external_audio
    summary: Prefer imported dialogue/ambience/SFX on Director timeline
    when: music_or_dialogue_control_required
""",
    )
    write(
        model_id,
        "evaluation_rules.yaml",
        """
rules:
  - id: artifact_required
    description: Approve only when a real artifact file exists
  - id: music_probe
    description: When music prohibited, flag probable music if probe available
""",
    )
    write(
        model_id,
        "provenance.yaml",
        f"""
claims:
  - sourceType: VERIFIED_INTERNAL
    sourceReference: studio-api/knowledgebase/generation/video_models
    modelVersion: "{version}"
    knowledgePackVersion: "1.0.0"
    verifiedAt: "2026-07-27"
    confidence: {overall_conf}
    notes: Elevated from foundation KB + runtime catalog; not a substitute for official docs.
""",
    )
    write(model_id, "examples/do_not_use_in_production.md", example_line)


def main() -> None:
    PACKS.mkdir(parents=True, exist_ok=True)

    seed_common(
        "z_image",
        provider_id="comfy.local",
        engine_id="zimage",
        display="Z-Image Turbo",
        version="turbo",
        status="ACTIVE",
        runtime="production",
        media=["image"],
        modes=["text_to_image", "image_to_image", "reference_images"],
        native_audio=False,
        generate_audio_param=None,
        music_class="NOT_APPLICABLE",
        max_duration=None,
        capability_map={
            "text_to_image": "SUPPORTED",
            "image_to_image": "SUPPORTED",
            "reference_images": "SUPPORTED",
            "text_to_video": "UNSUPPORTED",
            "image_to_video": "UNSUPPORTED",
            "negative_prompt_support": "SUPPORTED",
            "seed_support": "SUPPORTED",
        },
        overall_conf=0.82,
        limitations=["Local ComfyUI + zimage_models component required"],
        positive_append=[],
        negative_base=["blurry", "low quality", "watermark", "deformed hands"],
    )

    seed_common(
        "ltx_2_3",
        provider_id="comfy.local",
        engine_id="ltx",
        display="LTX 2.3",
        version="2.3",
        status="ACTIVE",
        runtime="not_production_ready",
        media=["video"],
        modes=["text_to_video", "image_to_video"],
        native_audio=False,
        generate_audio_param=None,
        music_class="BEST_EFFORT_EXTERNAL_AUDIO",
        max_duration=10,
        capability_map={
            "text_to_video": "EXPERIMENTAL",
            "image_to_video": "EXPERIMENTAL",
            "reference_images": "PARTIAL",
            "camera_control": "PARTIAL",
            "motion_control": "PARTIAL",
            "embedded_audio": "UNSUPPORTED",
            "dialogue_generation": "UNSUPPORTED",
            "soundtrack_generation": "UNSUPPORTED",
            "negative_prompt_support": "SUPPORTED",
            "seed_support": "SUPPORTED",
        },
        overall_conf=0.7,
        limitations=[
            "LTX 2.3 does not generate a native soundtrack; music suppression is BEST_EFFORT_EXTERNAL_AUDIO — not a guaranteed soundtrack toggle.",
            "Runtime classified NOT_PRODUCTION_READY in M3.0d; fal remains production motion route.",
        ],
        positive_append=["natural motion", "consistent lighting"],
        negative_base=["blurry", "jitter", "warped faces", "background music", "musical score"],
    )

    seed_common(
        "wan_2_2",
        provider_id="comfy.local",
        engine_id="wan",
        display="WAN 2.2",
        version="2.2",
        status="ACTIVE",
        runtime="not_production_ready",
        media=["video"],
        modes=["image_to_video"],
        native_audio=False,
        generate_audio_param=None,
        music_class="BEST_EFFORT_EXTERNAL_AUDIO",
        max_duration=10,
        capability_map={
            "image_to_video": "EXPERIMENTAL",
            "text_to_video": "UNSUPPORTED",
            "embedded_audio": "UNSUPPORTED",
            "soundtrack_generation": "UNSUPPORTED",
            "negative_prompt_support": "SUPPORTED",
            "seed_support": "SUPPORTED",
        },
        overall_conf=0.55,
        limitations=["WAN local path NOT_PRODUCTION_READY; prefer fal for production motion"],
    )

    seed_common(
        "fal_seedance",
        provider_id="fal.api",
        engine_id="fal_seedance",
        display="Seedance 2.0 (fal.ai)",
        version="2.0",
        status="ACTIVE",
        runtime="production",
        media=["video"],
        modes=["image_to_video", "text_to_video"],
        native_audio=True,
        generate_audio_param="generate_audio",
        music_class="PARAM_GENERATE_AUDIO",
        max_duration=12,
        capability_map={
            "image_to_video": "SUPPORTED",
            "text_to_video": "SUPPORTED",
            "embedded_audio": "SUPPORTED",
            "soundtrack_generation": "PARTIAL",
            "dialogue_generation": "PARTIAL",
            "reference_images": "SUPPORTED",
            "negative_prompt_support": "PARTIAL",
            "seed_support": "SUPPORTED",
        },
        overall_conf=0.88,
        limitations=[
            "Native audio via generate_audio; set false when music/dialogue must not be synthesized.",
            "Paid provider — preflight and single-submit guards required.",
        ],
    )

    for mid, eng, label, ver in (
        ("fal_kling", "fal_kling", "Kling 2.5 Turbo Pro (fal.ai)", "2.5"),
        ("fal_veo", "fal_veo", "Veo 3.1 (fal.ai)", "3.1"),
        ("fal_runway", "fal_runway", "Runway Gen-3 Turbo (fal.ai)", "gen3"),
    ):
        native = mid == "fal_veo"
        seed_common(
            mid,
            provider_id="fal.api",
            engine_id=eng,
            display=label,
            version=ver,
            status="VERIFIED",
            runtime="experimental",
            media=["video"],
            modes=["image_to_video"] + (["text_to_video"] if mid == "fal_veo" else []),
            native_audio=native,
            generate_audio_param="generate_audio" if native else None,
            music_class="PARAM_GENERATE_AUDIO" if native else "UNKNOWN",
            max_duration=10,
            capability_map={
                "image_to_video": "SUPPORTED",
                "embedded_audio": "PARTIAL" if native else "UNKNOWN",
                "negative_prompt_support": "PARTIAL",
                "seed_support": "SUPPORTED",
            },
            overall_conf=0.65,
            limitations=[f"{label} provisional pack from catalog metadata"],
        )

    for mid, display in (
        ("seedream", "Seedream (fal image)"),
        ("nano_banana_pro", "Nano Banana Pro (fal image)"),
        ("gpt_image_fal", "GPT Image via fal"),
    ):
        seed_common(
            mid,
            provider_id="fal.api",
            engine_id=mid,
            display=display,
            version="unregistered",
            status="QUARANTINED",
            runtime="product_approval_required",
            media=["image"],
            modes=["text_to_image"],
            native_audio=False,
            generate_audio_param=None,
            music_class="NOT_APPLICABLE",
            max_duration=None,
            capability_map={"text_to_image": "UNSUPPORTED"},
            overall_conf=0.0,
            limitations=["PRODUCT_APPROVAL_REQUIRED — not wired; FAL_IMAGE_MODELS empty; manifest locked"],
        )

    print(f"Seeded packs under {PACKS}")


if __name__ == "__main__":
    main()
