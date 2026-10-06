# Session Memory: 2026-09-13 — Timeline H3 R2V / Track Integrity / Correct Area / Re-Take Mission

## Branches
- Working branch at memory write: `feat/character-creator-final-closure` @ `99665cf7` (Avatar GO earlier same day — do not overwrite).
- H3 Quality baseline (separate cert pack): FM4 2026-09-10, graph SHA `33fa6665…`.

---

## 1. Timeline H3 Canonical
- Timeline MiniMax H3 = **Reference-to-Video only**.
- FM4/FM5 3-ref R2V Quality identity cert; queued API graph SHA256 `33fa666501efd787ec6970e596fae9019bfaaced2d1550582c9095c6b541203c`.
- Pack: `C:\Users\bradj\theme_walk\timeline_final_mile\fm4_baseline\`.
- Builder: `h3_ref2v_builder.py` → `MiniMaxH3ReferenceToVideo` + ref2va UNET.
- Adapter id `minimax-h3-t2v-local` is a **label debt** — product mode is R2V.

## 2. Timeline Track Integrity (in flight / ready)
| Item | Status |
|---|---|
| Same-track no-overlap REJECT (+ SNAP) | Ready (TS+Py twins) |
| Media labels | Ready |
| `shouldMutePreviewVideoSoundtrack` (intersecting lipsync only) | Ready (Vitest 8/8) |
| Batch 2 playback: visual before `lipsync_output_path` | Ready |
| Scene 10 A/V SPLIT (MiniMax mouths + Qwen wavs) | Confirmed |
| Brad dialogue-truth widget | **Pending** |

Law: `memory/files/TIMELINE_PLAYBACK_VOICE_AUTHORITY_LAW.md`.

## 3. Spatial Map Correct Area
- Engine unlock: Certified `zimage.inpaint` for **Correct Area only**.
- Atlas / ERS generation remains **GPT Image 2**.
- Same-footprint gate: output WxH must match source (~1440×810 Map|Inpaint).
- Mess Hall enqueue: worked. **Brad visual GO pending**.

## 4. NEW Mission — Timeline Re-Take → R2V
- Goal: Re-Take must not present/select as MiniMax H3 T2V (`supportsImageToVideo:false`, no start/end) in place of H3 R2V.
- **Audit only** (no implement): `C:\Users\bradj\theme_walk\timeline_retake_r2v\AUDIT.md`.
- Constraints: no Seedance I2V; no T2V fallback design; H3 Comfy templates read-only unless assigned.

## 5. Avatar (same calendar day — preserved)
See `memory/session-2026-09-13-avatar.md` — Character propagation + UI convergence **GO**. Do not regress.

## 6. H3 approved voice wire (same day, later)
- Wired `apply_approved_voices` on `submit_batch_generation` (generate + retake).
- DR visual cast unchanged; voices ? `ref_audios` only (timbre conditioning, not exact-script TTS).
- Evidence: `theme_walk/timeline_h3_language_integrity/VOICE_WIRE_FIX.md`
- Detail: `memory/session-2026-09-13-h3-voice-wire.md`
- No Quarters GO.
