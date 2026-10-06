# Co-Director Character Reference + Style Generation Contract

Governing document for this audit. Historical prompt dumps and vision JSON in this folder are evidence, not competing authority.

**Date:** 2026-09-09  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455`  
**Project used:** Korri Anadriya (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`) — one project, one library. No disposable project.

## Verdict

**NO-GO — CO-DIRECTOR CHARACTER REFERENCE + STYLE GENERATION CONTRACT NOT LIVE-PROVEN**

Architecture and upstream contracts are implemented and unit-tested. Co-Director vision sees both sheet types. MiniMax received the correct Korri and Addex sheet pixels on the last live graph (hash-verified). The last live MiniMax prompt was still the **pre-repair** contract, and this mission did **not** complete a new-contract GPU generate whose output characters can be judged against the sheets.

Do not issue `GO — CO-DIRECTOR CHARACTER REFERENCE + STYLE GENERATION CONTRACT VERIFIED`.

## Separate required verdicts

| Gate | Verdict | Boundary |
| --- | --- | --- |
| CO-DIRECTOR CRS VISION | **PASS (understanding)** | fal `chat_vision` / Gemini 2.5 Flash Lite extracted identity from pixels only. Not used as video identity authority. |
| GPT IMAGE 2 SHEET INTERPRETATION | **PASS** | Type A Korri 40yo sheet: one identity, pointed ears, purple eyes, blonde hair, arm circuitry, wardrobe, multi-angle high. |
| QWEN/STITCHED SHEET INTERPRETATION | **PASS** | Type B unlabeled 4-panel sheet: one identity, pointed ears, purple eyes, black pigtails, tattoo, wardrobe. Layout class initially said `structured_labeled_sheet`; instruction now distinguishes unlabeled grids as `stitched_multiview`. |
| CHARACTER IDENTITY PROMPT CONTRACT | **IMPLEMENTED — NOT LIVE-GENERATED** | Layers + preserve clause + no appearance prose. Last GPU prompt was still “this person - keep the same face” + unlabeled third slot. |
| STYLE PROMPT CONTRACT | **IMPLEMENTED — NOT LIVE-GENERATED** | Style is a separate layer. Project settings have **no** `visual_style`; style is lifted from `Visual style: …` or the style registry. Last GPU job mixed style into the timed blob. |
| MINIMAX REFERENCE DELIVERY | **PASS (pixels) / RISK (extra slot)** | Picture 1 = Korri 40yo CRS. Picture 2 = Addex CRS. SHA-256 matched Library. Not WAV. Picture 3 = Anadriya Adept-suit CRS, empty label on the live job. |
| LTX REFERENCE DELIVERY | **FAIL (two-character tensors)** | Live `LTXVImgToVideo` has one `image` input. Extra CRS stay named in the prompt. A CRS collage must not be used as an I2V keyframe (`LTXVAddGuide` would show the sheet as a frame). |
| REALISTIC ANIME OUTPUT | **NOT VERIFIED** | No new-contract MiniMax/LTX clip was generated and judged for identity + style. |

## Where the creator-fidelity failure actually occurs

Do not collapse these.

### PROMPT FAILURE — proven on pre-repair live jobs

Job `499e4858` (2026-09-08 23:47) told MiniMax the scene should look like “a premium live-action cinematic production” and redescribed Korri in prose (`<subject 1> is @Korri40YearsOld` + blonde / purple eyes / clothing laundry list). That is archetype reconstruction. It can invent replacements.

Job `92678565` / Comfy `ccf2bba5-…` (2026-09-09 01:13) was cleaner Picture tags but still:

- old “keep the same face, body, and clothes” wrapper
- movement scaffolding (`UNCHANGED FACTS`, `PRIMARY Beat`, `PRIMARY Direction — Anadriya keeps walking`)
- timed prompt for **two** people (Korri + Addex greeting)
- **three** identity tensors

The dangerous live-action paragraph is **not** a hardcoded MiniMax yaml append in the current JSON resolver (`positiveAppend: []`). It was authored into the Timed / production prompt. The sanitizer now drops that class of language unless the style is photographic.

### STYLE FAILURE — proven in architecture (now repaired in source)

- `_style_prompt_phrase` imported `STYLE_PROFILES`, which does not exist, so claymation / watercolor never reached video. Now uses `STYLE_REGISTRY`.
- Style was prepended into the action blob (WHO mixed with HOW).
- Korri Anadriya `settings_json` has **no** project `visual_style`. Only `projectType.primary = animated_series`. Style on the last live shot came from the timed line `Visual style: Realistic Anime`.
- MiniMax `prompt.yaml` had a global photoreal-environment append; JSON already overrode it to empty. Both are empty now.

### IDENTITY REPRESENTATION FAILURE — partial

- Character Creator vision runs on individual FRONT/BACK/CLOSEUP photos, not on the composed CRS, unless the new sheet interpreter is called.
- Persisted CRS canon is mostly asset id + revision. Timeline generation does not re-run vision and must not dump vision facts into the video prompt.
- Korri profile JSON still describes 18yo dark pigtails while the **approved Timeline CRS** is the 40yo blonde sheet. If appearance prose is appended, text fights the sheet. Appearance is no longer compiled into the H3 prompt.
- Last live job bound a **third** identity (`4c1c0bc8` Anadriya) with an empty label (`this character`) and Anadriya’s voice on Audio 2 while Picture 2 was Addex. A two-person greeting plus a third unlabeled sheet is a recast invitation.

### VISION — not the failure

Both supplied sheet classes were understood as **one character, many views**, without filename or biography. Type A and Type B both recovered ears, eyes, hair, wardrobe, body, and tattoo/circuitry from pixels.

### REFERENCE BINDING — MiniMax pixels OK; extra identity RISK; LTX structural miss

Live MiniMax graph (Comfy MCP + queue inspect, not JSON-id-only):

| Slot | Comfy LoadImage | Library file | SHA-256 | Kind |
| --- | --- | --- | --- | --- |
| Picture 1 | `studio/a42e77e0-….jpeg` | Korri 40 years old.jpeg | match | jpeg image |
| Picture 2 | `studio/91b82df6-….jpeg` | Addex.jpeg | match | jpeg image |
| Picture 3 | `studio/7e5a01f4-….png` | Anadriya composed CRS | match | png image |
| Audio 1 | `studio/33a80b24-….wav` | Korri Clone sample | wav | audio |
| Audio 2 | `studio/e3a305b6-….wav` | Anadriya Clone sample | wav | audio |

No voice WAV in an image slot. No thumbnail substitution on the two intended sheets.

LTX 2.5: `LTXVImgToVideo.image` is a single start frame. Extra characters are named only. Wiring a multi-panel CRS into `LTXVAddGuideAdvanced` would treat the sheet as a video keyframe — wrong semantics. Two-character LTX identity is therefore **not** MiniMax-equivalent.

### WORKFLOW / MODEL LIMITATION — not certified

Upstream was not clean. Do not blame MiniMax or LTX until a new-contract shot with two intended sheets, no extra unlabeled identity, separate Realistic Anime layer, and a judged output exists.

## Journey results

### 1 — Vision sees the sheets

Script: `scripts/_crs_sheet_vision_audit.py`  
Evidence: `docs/release-gate/codirector-crs-vision/vision_results.json`

Fed each sheet through `interpret_reference_sheet` → existing `chat_vision` (fal). No filename, no stored biography.

### 2 — Sheet format comparison

| Field | GPT Image 2 (Type A, Korri 40yo) | Qwen/stitched (Type B) |
| --- | --- | --- |
| Face understood | oval, female, ~21 | oval, female, young adult |
| Hair understood | long wavy sandy blonde | black pigtails |
| Eyes understood | almond, purple | large, purple |
| Ears understood | pointed, elven | pointed, elven |
| Wardrobe understood | white ribbed crop, denim shorts, white runners | cropped tank, denim + fringe, strappy sandals |
| Body understood | petite slim athletic | slender athletic |
| Tattoo understood | circuitry-like arm tattoos | intricate arm tattoos |
| Multi-angle consistency | high | consistent across panels |
| One identity | **true** | **true** |

Addex structured sheet (second Timeline CRS): one identity, dark brown wavy hair, hazel eyes, black shirt, beige pants.

### 3 — What is stored about a CRS

Retained: image asset + textual profile/JSON + CRS revision/canon ids.  
Not retained for video: visual embedding.  
Sheet vision facts are for Co-Director understanding only (`used_for_video_prompt: false`).

### 4 — Exact pre-repair MiniMax prompt (live)

From Comfy queue job `ccf2bba5-fb0f-4a95-affc-6dae23a8cc6b` / Studio job `92678565` (DB later marked cancelled; graph was observed running):

```
<Picture 1> Korri-40-years-old (this person - keep the same face, body, and clothes)
<Picture 2> Addex (this person - keep the same face, body, and clothes)
<Picture 3> character (this person - keep the same face, body, and clothes)
…
TIMED PROMPT: @Korri40YearsOld and @Addex stand facing each other …
Visual style: Realistic Anime.
```

### 5–8 — Identity vs style; live-action bias; layered prompt; image over prose

Implemented in `semantic_contract.py` + `r2v.py` + `request_builder.py`.

Intended H3 contract (live compile against the real Korri + Addex asset ids, empty labels resolved from profiles):

```
CHARACTER IDENTITY
<Picture 1> Korri — Preserve the supplied visual identity. Do not invent a replacement person.
<Picture 2> Addex — Preserve the supplied visual identity. Do not invent a replacement person.
The people in this shot are <Picture 1> Korri and <Picture 2> Addex.
These are the characters. Preserve them. The reference pictures are identity authority.

VISUAL STYLE
Realistic Anime
Hybrid realistic-anime illustration …
A style change is a rendering treatment of the same referenced characters, not a recast.

ACTION
The two referenced characters stand facing each other and exchange a calm greeting.

CAMERA
Illustrative cinematic coverage … (composition, not “real actors”)
```

Appearance strings such as “dark pigtails” are not appended.

### 9 — Comfy MCP binding

- `server_info`: Comfy `:8188` up, ComfyUI 0.34.5, RTX 5090.
- `nodes get MiniMaxH3ReferenceToVideo`: `ref_images` autogrow IMAGE inputs; `ref_audios` separate. Prompt uses `<Picture i>` / `<Audio j>`.
- `nodes get LTXVImgToVideo`: single `image`.
- Live H3 graph decoded: LoadImage filenames hashed against Library files (above).

### 10 — Style matrix (compile only)

Same two character slots + same action, four style keys. Identity clause unchanged; style layer changes.

| Style key | Identity clause stable | Style layer present | Hair/eye redescribe |
| --- | --- | --- | --- |
| realistic_anime | yes | Realistic Anime | no |
| live_action | yes | Live Action | no |
| anime | yes | Anime | no |
| claymation | yes | Claymation | no |

Evidence: `docs/release-gate/codirector-crs-vision/binding_and_matrix.json`.  
GPU matrix not run.

### 11 — MiniMax vs LTX adapters

Shared `SemanticGenerationContract`. `render_h3` uses Picture/Audio tags. `render_ltx` uses the same layers plus a one-cond disclosure. Raw prose is not forced identical.

### 12 — Live output proof

**Not completed.** Queue was occupied by the pre-repair H3 job for most of this audit. After it drained, Studio API was recycled onto the new contract. A fresh Timeline generate through Co-Director (two approved CRS, Realistic Anime, no manual prompt surgery, judged output) is still required.

## Architectural law (this is the product change)

Co-Director may understand a reference sheet.

It must not redescribe the character into existence for the video model.

- **Identity authority:** the supplied CRS image(s).
- **Text:** behavior, environment, camera, dialogue.
- **Style authority:** project / scene style (Realistic Anime, live action, claymation, traditional anime, …). A style change is a rendering treatment of the **same** referenced people, not a recast.

This is not character-specific. Korri / Addex / Realistic Anime are test evidence, not implementation constants.

## Tests

`studio-api` pytest:

- `tests/test_semantic_generation_contract.py`
- `tests/test_timeline_r2v.py`
- `tests/test_timeline_knowledge_compile.py`
- `tests/test_reference_binding_contract.py`

**58 passed** on the combined contract + R2V + knowledge + binding set (26 on the last focused rerun after dedupe).

Independent review: [CRS prompt review](34845325-4a82-4761-85b5-ecc06b8e790d) — `READY FOR PRIMARY REVIEW`. Laws 1–7 PASS on the reviewed files; RISK noted that live-action bias regex is phrase-list based.

## Runtime

- Local creator UI: `http://127.0.0.1:5173/` (HTTP 200)
- Studio API: `http://127.0.0.1:8758/api/healthz` (`{"status":"ok"}`)
- Studio API recycled twice via `scripts/restart_studio_api_only.py` (new PIDs 40920 then 26088)
- **COMFY BEFORE:** `:8188` healthy, PID **21328**
- **COMFY AFTER:** `:8188` healthy, PID **21328**, ComfyUI 0.34.5
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Ordinary contract/API work. GPU runtime left owned and untouched.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | N/A for new-contract generate (not run) |
| Frontend | N/A for new-contract generate |
| API | PASS — request builder + semantic ledger on real asset ids |
| Backend | PASS — contract compile |
| Persistence | N/A — no new approved clip |
| Runtime | PASS observe MiniMax node + prior job images; FAIL new-contract job |
| Result | FAIL — no judged Realistic Anime output under new contract |
| Reload | N/A |
| Downstream | N/A |

## Scene 5 live evidence (creator Timed Prompt)

Scene `a16515ce-cde8-4786-99fa-091d8bede618`. Job `34b6a365` (2026-09-09 01:10). Creator attached **only** `@Korri40YearsOld` and `@Addex`. Output people were sci-fi extras in blue/red uniforms — not the CRS wardrobe or faces.

Effective MiniMax prompt (pre-repair) still contained:

- `<subject 1> is Korri (@Korri40YearsOld)` — MiniMax does **not** bind `<subject N>`. It binds `<Picture N>`.
- Duplicate timed action (followed — couch, hands, dialogue).
- Stale **Picture 3** = Anadriya Adept-suit CRS + Anadriya voice, leftover on the batch `characterIdentity` / `characterVoice` rows. The References section did not include her.

Sheets for Korri and Addex **did** reach `ref_images` (hash-verified on earlier jobs). Identity still failed because (1) subject-tag prose is not a Picture bind, (2) “sci-fi living quarters” restyled wardrobe, (3) a third sci-fi-suited identity tensor was in the graph.

Post-repair compile of that same Timed Prompt + same leftover batch refs:

- Picture 1 Korri CRS, Picture 2 Addex CRS only. Anadriya sheet and voice dropped.
- `<subject>` assignment lines removed. Action and dialogue kept.
- Identity clause forbids setting-driven costume recast.

## Remaining blockers for GO

1. Generate a **fresh Timeline scene** on Korri Anadriya with **only the two intended approved CRS**, Realistic Anime, no `<subject>` lines. Job `30e50370` already used a clean prompt and the two sheets — identity still failed because MiniMax received the **full labeled collages**. The next generate must upload `studio/{assetId}_h3id.png` stills cropped from those same sheets (front figure), not `studio/{assetId}.jpeg`.
2. Prove the ledger: `identityAuthority = reference_image`, `uploadedTensor = derived_identity_still`, only Korri + Addex pictures, output people match the sheets, look is Realistic Anime.
3. Close leftover `characterIdentity` / `characterVoice` rows on the batch so they cannot reattach a third identity if compile filtering regresses.
4. LTX two-character delivery remains structurally one-cond. Disclose; do not certify LTX as MiniMax-equivalent identity R2V.

## Files (this mission)

- `studio-api/app/director_timeline_w46/generation/semantic_contract.py`
- `studio-api/app/director_timeline_w46/generation/r2v.py`
- `studio-api/app/director_timeline_w46/generation/request_builder.py`
- `studio-api/app/character_identity/crs_sheet_vision.py`
- `studio-api/app/character_identity/h3_identity_still.py`
- `studio-api/app/video_runtime/comfy_asset_stage.py`
- `studio-api/app/character_identity/prompt_package.py`
- `studio-api/app/codirector/knowledgebase/video-generators/minimax-h3.md`
- `studio-api/tests/test_semantic_generation_contract.py`
- `studio-api/tests/test_timeline_r2v.py`
- `scripts/_crs_sheet_vision_audit.py`
- `scripts/_crs_binding_and_matrix_audit.py`
