# M3.0c — Sound Pipeline Certification

## Certified bounded path

The native sound path is **GREEN** for imported audio:

- **Import:** audio assets can be uploaded/imported through the M2.9 audio service.
- **Place:** cues can be promoted into the Director timeline with a scene and start
  position.
- **Gain:** cue gain/volume is persisted and represented in timeline/export data.
- **Normalize:** the audio processing path exposes normalization for imported material.

Evidence includes `studio-api/tests/test_m30_audio_timeline.py`, which exercises import,
cue promotion, and gain/timeline persistence. Existing tests are the source of truth for
what is proven; no new test count is asserted here.

## Generative audio boundary

Generative dialogue, SFX, and music are **UNAVAILABLE** for production certification.
The M2.10b adapters are sandbox/deferred candidates and must not be presented as
successful generation. The UI/API may expose a gated request, but that is not proof of a
generated artifact.

## Status

| Capability | Status |
|---|---|
| Imported audio reaches project library | **VERIFIED** by existing tests |
| Imported audio placed on timeline | **VERIFIED** by existing tests |
| Gain/volume persistence | **VERIFIED** by existing tests |
| Normalize imported audio | **VERIFIED** by existing implementation/test evidence |
| Generative dialogue | **BLOCKED / UNAVAILABLE** |
| Generative SFX | **BLOCKED / UNAVAILABLE** |
| Generative music | **BLOCKED / UNAVAILABLE** |

No generative audio endpoint or live audio artifact is claimed.
