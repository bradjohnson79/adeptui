# Session Memory: 2026-09-13 — Timeline Retake R2V gate repair

## Branches
- Working tree: `C:\AdeptFilmWorks\AIVideoStudio` on BRAD-5090
- Evidence: `C:\Users\bradj\theme_walk\timeline_retake_r2v\`

---

## 1. Objective

Repair Timeline Re-Take so MiniMax H3 stays **Reference-to-Video** (FM4/FM5 DR→`ref_image_N`), not false T2V from `supportsImageToVideo=false` gates / mislabel. No Seedance I2V default, no T2V fallback, do not flip `supportsImageToVideo=true`. No live Quarters GO.

## 2. Root cause

- Adapter id `minimax-h3-t2v-local` is misnamed R2V (`supportsReferenceToVideo=True`, I2V/T2V False).
- `retake_range` image-frame gate used only `supportsImageToVideo` → `IMAGE_FRAME_I2V_UNSUPPORTED` + “text-to-video only” copy.
- `request_builder` mode tree fell through toward `text_to_video` when I2V false (local blanket later forced `reference`, but gates/package lacked pro-R2V contract).
- Timeline `GeneratorCapability.supportsTextToVideo` ORd CREATE `workflowCapabilities.t2v.supported` — CREATE t2v leaked onto Timeline.

## 3. Repair

- Expose + wire `supportsReferenceToVideo` on Timeline `GeneratorCapability`.
- Stop CREATE t2v leak; CREATE keeps `workflowCapabilities`.
- Image-frame gate: allow I2V **or** R2V; fix message.
- First-class R2V → `generationMode=reference` before T2V fallthrough.
- Retake context package: pro-R2V HARD CONSTRAINTS + `r2vAttached` honesty.
- Frontend: thread R2V flag; retake error copy mentions I2V/R2V.
- Tests: `studio-api/tests/test_retake_r2v_gates.py` (6 passed).

## 4. Proof

- `pytest tests/test_retake_r2v_gates.py` → 6 passed
- Related retake/authority/imgclip → 22 passed
- H3 request + range subset → 9 passed
- **No live Quarters GO**

## 5. Backlog follow-ons

- Dedicated rename wave off `minimax-h3-t2v-local` adapter id (out of scope this pass)
- Live Comfy Retake / Quarters R2V cert after Primary review

## 6. Language follow-on (same day)
Primary wired `apply_approved_voices` on Timeline H3 generate/retake (voice refs / `ref_audios`). Quarters live Re-Take still HELD. See `session-2026-09-13-h3-voice-wire.md` + `VOICE_WIRE_FIX.md`.
