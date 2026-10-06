# MiniMax H3 Comfy Template Parity — Completion Report

Governing: `docs/release-gate/minimax-h3-comfy-parity/GOVERNING.md`

**NO-GO — MINIMAX H3 COMFY PARITY**

Phase 4 direct Comfy did not preserve Addex and Korri. Timeline and `h3_ref2v_builder.py` were not replaced.

## Runtime

- Studio API: `http://127.0.0.1:8758/` (untouched)
- **COMFY BEFORE:** PID 22044 / healthy
- **COMFY AFTER:** PID 22044 / healthy
- **COMFY RESTARTED?:** NO
- **WHY?:** Validate + one parity queue. No lifecycle action.

## Phase 1 — Canonical API graph

Uploaded UI template copied to `46a303cbccf9_ui_template.json` and converted.

Flattened effective graph (Lightning LoRA off, no EasyCache): `Scene5_H3_Parity_DirectComfy.json`

Live Comfy MCP validate: valid. Same LoadImage autogrow warnings as prior H3 runs; sockets executed.

Full converted template API is invalid on this machine only because the unused Lightning LoRA file is not installed. That path stayed disabled.

## Phase 2 — Prompt

No `<Subject N>`. Creator text compiled to the template’s Picture-tag style:

`Use <Picture 1> as Addex and <Picture 2> as Korri` plus Scene 5 action and dialogue.

## Phase 3 — Field diff

See `FIELD_DIFF.json`. Live template widgets use scheduler **simple** (the note prefers beta/normal; we used the file). Material Adept deviations before any builder change: invented `<Subject N>` compiler, EasyCache on Fast, Timeline 1280×704 vs template 864×480.

## Phase 4 — Direct Comfy

Live sockets while running:

| Field | Required | Observed |
|---|---|---|
| Picture 1 / `ref_image_0` | Addex original CRS | `studio/91b82df6-….jpeg` |
| Picture 2 / `ref_image_1` | Korri original CRS | `studio/a42e77e0-….jpeg` |
| prompt | `<Picture N>` only | no `<Subject` |
| `ref_image_size` | match | match |
| scheduler / steps / sampler | simple / 20 / res_multistep | match |
| EasyCache / LoRA | absent / off | match |
| canvas / length | 864×480 / 124 | match |

prompt_id `9d24fab9-b03a-4c78-8cfd-898f5ccde165` · 71.7 s · H3 node + sampler + LoadImage executed · [h3_comfy_parity_00001_.mp4](http://127.0.0.1:8188/view?filename=h3_comfy_parity_00001_.mp4&subfolder=identity_test&type=output)

| | Addex | Korri |
|---|---|---|
| face | fail | fail |
| hair | fail | fail |
| clothing | fail | fail |
| pointed ears | n/a | fail |
| overall | fail | fail |

Observed: orange/black and teal/black sci-fi uniforms on a yellow couch. CRS wardrobe did not survive.

## Phase 5 / 6

Not started. Direct Comfy identity failed.

## Remaining difference

The Adept builder was not the thing under test in Phase 4. The proven template path ran and still recast both people.

The leftover gap is **reference media form**, not node architecture:

1. The template’s own example images are single-subject stills (rooftop boy, mech). Phase 4 swapped in the original multi-panel CRS JPEGs, as specified.
2. The owner-accepted Anadriya corridor PASS used named Front stills plus a place still at 768×448. This run used two CRS sheets, no place, 864×480, `ref_image_size=match`.

Direct Reference Route was not changed.
