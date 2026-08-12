# M3.2a — Generation Capability Matrix

Machine-readable source: [`artifacts/m32a/capability-matrix.json`](../../../artifacts/m32a/capability-matrix.json)

## Decision legend

| Decision | Meaning |
|---|---|
| **SHIP_M32A** | Approved for full wiring in this milestone |
| **ALREADY_PRESENT** | Existing Adept surface (may be PARTIAL) |
| **EXPLICITLY_DEFERRED** | Required for vision later; documented with OSS shortlist — not silently absent |

## Status legend

COMPLETE · PARTIAL · UI-ONLY · BACKEND-ONLY · PROVIDER-AVAILABLE-BUT-NOT-WIRED · MISSING · BLOCKED · NOT APPLICABLE

## Lifecycle summary

| Group | SHIP_M32A | ALREADY_PRESENT | EXPLICITLY_DEFERRED |
|---|---|---|---|
| Visual | image enhance ops | ImageGen, storyboards, keyframes, refs | matte painting, texture, vehicles/creatures dedicated |
| Video | upscale, extend | T2V, I2V, avatar, lipsync | performance transfer, RIFE interpolation |
| Audio | music, SFX | voice/dialogue, ambience, cleanup | voice conversion, emotion |
| Enhance | upscale, bg remove, chroma, skin, delight* | — | — |
| Production | scriptwriter, brand studio | Bible, Director, Library, continuity | — |
| 3D | — | validate import only | mesh/rig/mocap suite |
| Delivery | — | Editor, export | compositing, VFX, captions, localization, social |

\* De-lighting: COMPLETE only with production OSS; otherwise **BLOCKED** (never fake grade).

## Approved-10 certification columns (post-wiring)

| Tool | Completeness | E2E | Provider | Co-Director | Library | Tests |
|---|---|---|---|---|---|---|
| Video Upscaler | PARTIAL | queued + E2E lineage | SeedVR2 (when nodes/weights present) | propose_video_upscale | video.generated | GEN-TOOLS-01/04 |
| Image Upscaler | PARTIAL | queue specialized + E2E lineage | RealESRGAN/Comfy | propose_image_upscale | derived | GEN-TOOLS-03 |
| Background Remover | PARTIAL | queue specialized + E2E lineage | BiRefNet | propose_background_remove | derived | GEN-TOOLS-05 |
| Chroma key | COMPLETE (local) | yes | OpenCV/Pillow | propose_chroma_key | derived | GEN-TOOLS-06 |
| De-Lighting | **BLOCKED** | 503 | — | — | — | GEN-TOOLS-07 |
| Scriptwriter | PARTIAL→product | persist + Library | template/LLM | propose_script_document | scripts | GEN-TOOLS-08..10 |
| Music | PARTIAL | Audio Studio + Asset register | ACE-Step sandbox | propose_music_generate | audio.music | GEN-TOOLS-11 |
| SFX | PARTIAL | Audio Studio + Asset register | MMAudio sandbox | propose_sfx_generate | audio.sfx | GEN-TOOLS-12 |
| Video Extender | PARTIAL | generative_continuation job | WAN/LTX I2V | propose_video_extend | video.generated | GEN-TOOLS-13/14 |
| Portrait Skin | PARTIAL | specialized face_refine | CodeFormer path | propose_portrait_skin | derived | GEN-TOOLS-15 |
| Brand Studio | PARTIAL | locked metadata + workspace | ref-locked ImageGen | propose_brand_generate | props.generated | GEN-TOOLS-16 |

**Honesty:** COMPLETE only where real local ops are proven without fixture copies. Comfy-backed enhance/video tools remain PARTIAL until operator installs weights/nodes (see M32A_OSS_ACQUISITION.md). De-lighting stays BLOCKED — never color-correction.

Evidence: `artifacts/m32a/`, `tests/e2e/m32a/generation-tools.spec.ts`, `studio-api/tests/test_m32a_generation_tools.py`.
