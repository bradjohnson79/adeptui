# P6 generate_audio=false — CODE READY (no prove yet)

**When:** 2026-09-18 18:42 PT  
**Status:** CODE_READY — await Systems :8758 bounce + Chief CLEAR for one W2 prove.  
**Rule:** No BatchPrompt MUTE wording escalation. Adapter/request mute only.

## What landed (live tree BRAD-5090)

| File | Change |
|------|--------|
| 
equest_builder.py | _batch_silence_locked; _resolve_audio_authority silence → generateAudio=false / 
ativeAudio=disabled; re-assert after Dialogue Manifest apply |
| h3_ref2v_builder.py | uild_h3_ref2v(..., generate_audio=True\|False); false omits VAEDecodeAudio + CreateVideo.audio; skip LoadAudio binds |
| queue_worker.py | Honor generate_audio / udio_generation / udioAuthority; pass into builder; assert expects audio names only when gen_audio; stamp history.r2v.generate_audio |

Backup: p6_audio_false_backup_20260918_184000/

## Unit prove (local import on BRAD — PASS)

- Syntax: all three files parse.
- generate_audio=True graph: decode + mux audio present.
- generate_audio=False graph: decode + mux audio absent; ssert_h3_ref2v_graph PASS.
- Authority NONE / empty manifest → generateAudio=false; SPEECH → 	rue.

## Chain (authority → Comfy)

1. Silence lock from Dialogue Authority (expectedSpeech=NONE / empty silence-locked / speechKind=none).
2. providerOptions.audioAuthority + generate_audio=false + udio_generation=false.
3. H3 R2V worker forces gen_audio=False from those fields.
4. Comfy graph = video-only mux (native speech stem off). Ambience also off (single AV stem — known).

## NOT done yet

- API not bounced — patches not live in running :8758.
- No prove W2 burn (Chief freeze until bounce + CLEAR).
- Live NR / Omni / CandidateReady evidence still pending prove.

## Prove ask (when CLEAR)

Same stk_ae5b66e9d0a7 / prior_frame / W2 only / BP1 v3 text OK (no new MUTE spam). Verify NR generate_audio=false, graph no audio mux, speech silent?, lighting, stitch.

See also: P6_GENERATE_AUDIO_FALSE_CHAIN.json, P6_STUCK_GENERATING_FINALIZER.md.
