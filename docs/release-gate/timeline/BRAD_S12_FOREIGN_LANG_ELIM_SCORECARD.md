# Brad §12 — Scene 4 Take A Foreign-Language Elimination

**VERDICT: SCENE 4 TAKE A RETAKE — NO-GO**

## Why NO-GO
API bounce mid-job wiped Scene 4 director master to a single Draft batch. W1/W2/stk structure was restored from p6_v3_master_terminal.json (fail-closed W2=NeedsDialogueRetake). Omni/VCM/stitch on the new W2 render were **not** completed. New raw asset exists but was not safely reattached.

## What DID pass (Gen mute / foreign-audio path)
| Gate | Result |
|------|--------|
| Preflight empty lines/speakers/langs + silence_lock | PASS |
| generate_audio=false / silence_locked authority | PASS |
| Comfy: no VAEDecodeAudio; CreateVideo has no audio | PASS |
| Raw render audio stream | **NONE** (video-only) |
| Same Take / W2 only / no BP MUTE escalation | PASS |
| No foreign lines in dialogueAuthority | PASS |

## Blocked
| Gate | Result |
|------|--------|
| Omni affirmative silence | NOT RUN (bounce) |
| CandidateReady | Not claimed |
| Stitch W1+W2 30s | NOT DONE |
| Bounce hygiene | **FAIL** — master wipe |

## IDs
- Take: stk_ae5b66e9d0a7 · W2: bb_b5794fa154fe · Job: e556e388-037b-42e0-9332-b100c29d8153
- Freeze: C:\Users\bradj\AppData\Local\Temp\wave6_live_cert\foreign_lang_elim_freeze\20260918_190653
- Raw: video-only under freeze 
aw_w2.mp4 / job output asset in params

## Follow-ups
1. P6 hygiene finalizer + bounce recovery (Gen) — P0 given this wipe
2. CD Omni silence affirmative when available — QC retry without regen
3. Re-CLEAR only after master stability + attach orphan asset or controlled W2 re-prove
