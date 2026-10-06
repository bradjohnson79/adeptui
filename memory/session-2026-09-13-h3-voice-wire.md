# Session Memory: 2026-09-13 - Timeline H3 approved voice wire

## Objective
Wire `apply_approved_voices` onto live Timeline H3 generate + retake (R2V only). From LANGUAGE_AUDIT: voices were approved `language=en` but unused; audio was generator_native improvisation.

## Done
- `voice_bind.py`: DR cast `identityId` → approved voice → DR `audio` / `ref_audio_N` + R2V audio slots. Honesty: `voice_timbre_ref_only`, not exact-script TTS.
- `orchestrator.submit_batch_generation`: calls `apply_approved_voices` after request build (covers generate + `retake_range`). Visual cast still DR — no `apply_character_identity`.
- `r2v.copy_r2v_into_job_params`: copies `characterVoices` into job params.
- Tests: `tests/test_timeline_voice_bind.py` (8) + related suites = 44 passed.

## Evidence
`C:\Users\bradj\theme_walk\timeline_h3_language_integrity\VOICE_WIRE_FIX.md`

## Explicit non-claims
- No Quarters GO / no live retake fired
- No prompt translation layer
- No exact-script dialogue control (H3 still native audio + voice refs only)
