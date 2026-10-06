# MiniMax H3 Reference Identity Contract — Completion Report

Governing: `docs/release-gate/minimax-h3-identity/GOVERNING.md`  
Transport remains: `docs/release-gate/direct-reference-route/GOVERNING.md`

**Scene 5 Korri/Addex verdict: NO-GO — MINIMAX H3 REFERENCE IDENTITY**

**Anadriya corridor identity (owner-accepted): PASS**

## Runtime

- Studio API: `http://127.0.0.1:8758/` (not recycled; no adapter change)
- Local creator UI: `http://127.0.0.1:5173/` (unchanged)
- **COMFY BEFORE:** PID 22044 / healthy
- **COMFY AFTER:** PID 22044 / healthy
- **COMFY RESTARTED?:** NO
- **WHY?:** Test B queue, then Test E validate + queue. After a cache-hit first queue, POST `/free` (`free_memory=true`, `unload_models=false`) cleared execution cache only. Same PID 22044. No process restart.

## Phase 0 — Baseline and node contracts

Test A reused the already-executed Scene 5 Timeline graph. It was not re-rendered.

- Baseline JSON: `docs/release-gate/minimax-h3-identity/Scene5_H3_Baseline_Current.json`
- Test A output: `data/projects/beffd3d8-791d-4adf-9c4d-681ec9d4efb0/renders/scene_4_40d9817c.mp4`
- Test A prompt: authored Timed Prompt + trailing `<Picture 1> <Picture 2>`
- Test A settings: `ref_image_size=match`, EasyCache node 90 present, seed `2248151181`

Live Comfy MCP `server_info`: `:8188` running, RTX 5090, ComfyUI 0.34.5.

Live `object_info` confirmed:

- `MiniMaxH3ReferenceToVideo.ref_image_size` enum = `match | max` (default `match`)
- `BasicScheduler.model` and `BasicGuider.model` accept raw UNET
- `EasyCache` exists and is optional
- `SamplerCustomAdvanced`, `VAEDecode`, `VAEDecodeAudio`, `CreateVideo`, `SaveVideo` match the baseline graph

## Phase 1 — Test B

No second compiler. `build_test_b.py` called existing `compile_h3_prompt()` / `render_h3` from Direct Reference payload order, then `build_h3_ref2v(..., ref_image_size="max", fast=False, seed=2248151181)`.

Preflight passed. Comfy MCP `validate_workflow`: valid (SaveVideo `format.codec=auto` added for the dynamic-combo validator). LoadImage 15/16 produced autogrow reachability warnings; live queue proof showed both images wired and executed.

During execution (`Scene5_H3_TestB_live_sockets.json`):

| Field | Required | Observed |
|---|---|---|
| Picture 1 / Subject 1 / `ref_image_0` | Addex original CRS | `studio/91b82df6-6c5a-410a-bdb8-6cd3f79753c7.jpeg` |
| Picture 2 / Subject 2 / `ref_image_1` | Korri original CRS | `studio/a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg` |
| `ref_image_size` | max | max |
| EasyCache | absent | absent |
| steps / sampler / scheduler | 20 / `res_multistep` / `simple` | match |
| seed / length / canvas | `2248151181` / 124 / 1280x704 | match |
| prompt | existing Subject↔Picture compiler | `<Subject 1>` `<Picture 1>` `<Subject 2>` `<Picture 2>` present |

Metrics:

- prompt_id: `cc9dd295-b8eb-4e5e-9e2a-59383d144803`
- elapsed: 80.2 s
- peak VRAM: 16.29 GB
- audio: AAC stereo present
- output: [http://127.0.0.1:8188/view?filename=h3_subject_binding_00001_.mp4&subfolder=identity_test&type=output](http://127.0.0.1:8188/view?filename=h3_subject_binding_00001_.mp4&subfolder=identity_test&type=output)

## Phase 2 — Visual acceptance

Pass rule: both people must be identifiable as the supplied CRS characters. “Closer” is not a pass.

| Score | Test A | Test B |
|---|---|---|
| Addex face | fail | fail |
| Addex hair | fail | fail |
| Addex wardrobe | fail | fail |
| Addex overall | fail | fail |
| Korri face | fail | fail |
| Korri hair | fail | fail |
| Korri ears | fail | fail |
| Korri wardrobe | fail | fail |
| Korri overall | fail | fail |
| Realistic Anime | fail (3D CGI uniforms) | closer, still not identity |
| Action | partial | closer (couch, sit, hold hands) |
| Dialogue/audio | present | present |

Test B still generated substitutes: a dark-haired man in a red/grey tactical jacket, and a brown-haired woman in a grey hoodie and jeans. Missing from Korri: sandy blonde hair, purple eyes, pointed ears, white crop, denim shorts, circuitry tattoo. Missing from Addex: black henley, khaki pants, the CRS face.

Primary hypothesis result: **the existing compiler output reached node 5 and did not restore identity.**

## Phase 3 — Isolation

Not run. The plan makes C/D mandatory only after a passing Test B. Test B failed identity.

`max` and EasyCache-off remain unisolated secondary variables. A failed Test B is not proof they are required or harmful.

## Phase 4 — Adapter integration

Not performed. The plan forbids Timeline / adapter changes after a failed direct-Comfy identity test.

`r2v.py` still has `if payload.promptPrefix and direct is None`. That bypass remains a real delivery defect for ordinary Timeline Generate, but installing it in production was not authorized after Test B failed to restore faces and wardrobe.

Direct Reference Route files were not modified.

## Phase 5 — Ordinary Timeline proof

Not performed. Blocked by Phase 2 / Phase 4.

## Verdicts

| Gate | Result |
|---|---|
| H3 SUBJECT ↔ PICTURE BINDING | FAIL — delivered to Comfy; identities not restored |
| REF_IMAGE_SIZE IDENTITY TEST | NOT ISOLATED — `max` used in Test B only |
| EASYCACHE IDENTITY IMPACT | NOT ISOLATED — bypassed in Test B only |
| DIRECT COMFY IDENTITY TEST | FAIL |
| TIMELINE ADAPTER INTEGRATION | NOT STARTED — blocked |
| LIVE TIMELINE CHARACTER FIDELITY | NOT STARTED — blocked |

**NO-GO — MINIMAX H3 REFERENCE IDENTITY**

Remaining Scene 5 issue is why `@Addex` + `@Korri40YearsOld` full CRS sheets do not lock, even after the official compiler text reaches the node.

That is not “H3 cannot preserve any identity.” Owner confirmed the Venture corridor Anadriya take: **that is Anadriya, and that test passed.**

| Test | Pair | Owner result |
|---|---|---|
| Venture corridor Anadriya | Anadriya (Adept-suit look) | **PASS** |
| Scene 5 Test B | `@Addex` + `@Korri40YearsOld` original CRS sheets | **FAIL** |
| Scene 5 Test E | same graph; FRONT stills only | **FAIL** |

## Test E — reference image form isolation (2026-09-08)

Bound: Test B graph and mp4 left untouched. Timeline / Direct Reference / `r2v.py` / production H3 builder defaults not edited. Prompt not rewritten. `h3_identity_still.py` not used.

Fixtures (PIL crop only):

- Addex FRONT `20,170,200,730` → `fixtures/addex_generation_ref_front.png` (180×560)
- Korri FRONT `15,155,150,655` → `fixtures/korri_generation_ref_front.png` (135×500)
- Staged as new Comfy names only: `studio/test_e_addex_front.png`, `studio/test_e_korri_front.png`

Graph: `Scene5_H3_TestE_SingleSubject.json` — only LoadImage 15/16 and save prefix changed. Preflight all match. Comfy MCP validate: valid (same LoadImage autogrow warnings as Test B).

First queue `1ca86f2c-…` was a cache hit (nodes 5/10 reused Test B). Discarded. `/free` cleared execution cache. Same PID 22044. Second queue `fde23980-4782-4df9-ab4b-ba8ee929fe01` ran uncached (`cached_nodes=[]`, 350.5 s).

Live sockets while running: Picture 1 / Subject 1 / `ref_image_0` = Addex FRONT; Picture 2 / Subject 2 / `ref_image_1` = Korri FRONT; prompt identical to Test B; seed `2248151181`; 1280×704; 124 frames; 20 steps; `res_multistep` / `simple`; `ref_image_size=max`; no EasyCache.

Output: [http://127.0.0.1:8188/view?filename=h3_single_subject_00002_.mp4&subfolder=identity_test&type=output](http://127.0.0.1:8188/view?filename=h3_single_subject_00002_.mp4&subfolder=identity_test&type=output)

| | Addex | Korri |
|---|---|---|
| face | fail | fail |
| hair | fail | fail |
| clothing | fail | fail |
| pointed ears | n/a | fail |
| overall identity | fail | fail |

Observed: same substitute pair as Test B (tactical red-piped jacket man; brown-haired woman in white shirt / jeans). CRS wardrobe did not survive.

**NO-GO — H3 IDENTITY FAILS WITH SINGLE-SUBJECT REFERENCES**

Stopped for owner. No more crops. No prompt work. No Generation Reference View architecture. Timeline `promptPrefix` defect remains recorded only.

Field-for-field vs known-good Anadriya corridor: `Scene5_H3_TestE_anadriya_compare.json`. Same H3 node and checkpoint. Anadriya PASS used named Front stills plus place (3–4 refs) at 768×448 Quality. Test E used two small FRONT crops only at 1280×704 / `ref_image_size=max`.
