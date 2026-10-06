# Adept UI — Full Stack Convergence Journeys

**Governing document** for the loosened primary-loop journeys in this thread (Law 30).  
Does **not** supersede per-mission reports listed under [Authority](#authority). Those remain current for their own gates.

| Field | Value |
|---|---|
| Captured | 2026-09-01 |
| Thread | 2026-08-29 21:04 through 2026-09-01 (this conversation) |
| Mode | Tight missions (Aug 29–31 AM) → **Full Stack Convergence** loosened primary loop (Aug 31 18:05 onward) |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` (dirty worktree; **not committed**, **not pushed**) |
| Surface | Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/` |
| Named project (FSC onward) | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene 1 | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` |
| Characters | Korri `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed` · Anadriya `4c1c0bc8-a771-4998-b652-5d549b2a2b8d` |
| Comfy `:8188` | PID **77152** throughout the convergence loop · **COMFY RESTARTED?: NO** |
| MiniMax Route A `:8192` | Offline. Do not start without owner approval. |
| Retired | `:8760` is not product UI |

---

## Overall status

```text
NO-GO — ADEPT UI FULL STACK CONVERGENCE NOT COMPLETE
```

Several journeys **hold live** on Korri Anadriya. Timeline local generation is **Reference-to-Video only** (one canonical contract). MiniMax H3 runs on Adept Comfy `:8188` via `MiniMaxH3ReferenceToVideo` + ref2va — **not** Route A `:8192` and **not** first-frame I2V. Take N (Quality) holds Korri. **J14** added **Venture Corridor Dialogue** (2×8s). **J20** added a third 8s H3 R2V batch, proved bounded Re-Take on Batch 2, inset the Timeline workspace around the open Right Drawer, and compacted Inspector / Co-Director / Hot Keys. **J21** cleaned Scene 1 Timed Prompts: four intentional corridor clips, J19 bindings on each, coffee-shop / empty leftovers removed after snapshot proof. **J22** walked a 33-case Co-Director beta matrix on this project (clear / ambiguous / contradictory / missing refs / wrong generator / memory / recovery / misdirection / compile / false-success). First loss on T01 was silent Flux image-edit for a 5-second MiniMax H3 shot; that route is repaired. LTX 2.5 remains honest one-cond. **J29** rebuilt Audio Studio into a wired Music / SFX / Ambience / Project Audio surface. Home **J11** (400/502 honesty) remains open after a measured soak. Worktree is dirty; nothing in this thread was committed.

A stranger can open Timeline on Korri Anadriya, pick MiniMax H3 or LTX 2.5, and generate without a silent T2V / ordinary I2V fallback. A stranger can play the **24s** Venture Corridor Dialogue stitch across two 8s cuts, with Batch 3 looking toward each other and Batch 2 carrying a mid-shot hair-color Re-Take. Timed Prompt clips no longer paint under the open Inspector. Scene 1’s Timed Prompt track is corridor-only with explicit `@Korri` / `@Anadriya` / `#VentureCorridorScene` bindings. **J19** name bindings still hold. Korri now has an owner-approved clone voice (`283e8cf8` / Sample 3 asset `33a80b24`) that `voice_bind.resolve_approved_voice_audio` returns for MiniMax H3 `<Audio j>`, and **J26** keeps that same speaker through Voice Performance / Environment / Takes on the shared warm Qwen worker. **J27** adds Co-Director **Voice Creator** (Voice Identity Express) between Character Creator and Prop Creator so that same VoiceProfile is the default across Adept without later Voice Studio stages. A stranger **cannot** yet treat LTX 2.5 as multi-tensor identity, hear Anadriya on H3 (she still has no approved voice), or open Home with proven-clean request traffic.

---

## Authority

| Document | Role |
|---|---|
| This file | Journey record + current FSC truth |
| [`../platform-integrity-closure/ADEPT_UI_PLATFORM_INTEGRITY_CLOSURE_UNIFIED_REPORT.md`](../platform-integrity-closure/ADEPT_UI_PLATFORM_INTEGRITY_CLOSURE_UNIFIED_REPORT.md) | Platform Integrity Closure (Aug 29–30) |
| [`../timeline-ui-regression/ADEPT_UI_TIMELINE_VIDEO_GENERATOR_LIBRARY_ZOOM_REGRESSION_REPORT.md`](../timeline-ui-regression/ADEPT_UI_TIMELINE_VIDEO_GENERATOR_LIBRARY_ZOOM_REGRESSION_REPORT.md) | Timeline dock / Library / zoom remount |
| [`../video-generator-readiness/ADEPT_UI_VIDEO_GENERATOR_READINESS_AND_CANONICAL_ROUTING_REPORT.md`](../video-generator-readiness/ADEPT_UI_VIDEO_GENERATOR_READINESS_AND_CANONICAL_ROUTING_REPORT.md) | Generator readiness (still **NO-GO** on Seedance E2E) |
| [`../character-creator/CC_V3_LOCAL_SHEET_COMPOSE.md`](../character-creator/CC_V3_LOCAL_SHEET_COMPOSE.md) | V3 local sheet compose |
| [`../../architecture/codirector/CODIRECTOR_GENERATE_MEANS_EXECUTE_CERTIFICATION.md`](../../architecture/codirector/CODIRECTOR_GENERATE_MEANS_EXECUTE_CERTIFICATION.md) | Generate means execute |
| [`../../architecture/codirector/CODIRECTOR_CANONICAL_GENERATION_MEMORY_CERTIFICATION.md`](../../architecture/codirector/CODIRECTOR_CANONICAL_GENERATION_MEMORY_CERTIFICATION.md) | Canonical generation memory |
| [`../../architecture/codirector/CODIRECTOR_HOSTED_IMAGE_FALLBACK_ORCHESTRATION_CERTIFICATION.md`](../../architecture/codirector/CODIRECTOR_HOSTED_IMAGE_FALLBACK_ORCHESTRATION_CERTIFICATION.md) | Hosted fallback |
| [`../../architecture/codirector/CODIRECTOR_CHAT_VISION_ATTACHMENT_CERTIFICATION.md`](../../architecture/codirector/CODIRECTOR_CHAT_VISION_ATTACHMENT_CERTIFICATION.md) | Chat vision + attach |
| [`../../architecture/ADEPT_ALWAYS_ON_RUNTIME_SERVICE_CERTIFICATION.md`](../../architecture/ADEPT_ALWAYS_ON_RUNTIME_SERVICE_CERTIFICATION.md) | Dual-runtime (logon task still **NO-GO**) |

---

## How the loop works

Owner sends a short **journey** (or “keep going”). Primary walks the live chain, classifies **EXISTS / DISCONNECTED / MISSING**, reconnects before rebuild, and does not wait between a closed section and the next break.

Stop and ask only for: money spend, data destruction, Comfy/MiniMax lifecycle, or a genuine product-intent fork.

Fences that stayed in force:

- One project, one Library. No `POST /api/projects`.
- Comfy `:8188` leave-alone. No supervisor bounce.
- No mocks. No silent provider/model fallback.
- Subagents return `READY FOR PRIMARY REVIEW` only.

---

# Part I — Precursor missions (same thread, before FSC)

These were tight owner tickets. They built the stack the journeys later walked.

| # | When | Mission | Verdict | Notes |
|---|---|---|---|---|
| P1 | Aug 29 21:04 | Platform Integrity Closure | **GO** — owner-testing readiness | Scoped asset 403; one generator join; MiniMax honest 5/24 on experimental Route A; Comfy MCP stdio; live LTX 2.3 I2V. Project then: SenseNova / Schnick. |
| P2 | Aug 29 22:17 | Timeline Video Generator + Library + Zoom remount | **GO** | Restored canonical dock above Scenes. MiniMax duration **not** redefined here. |
| P3 | Aug 29 23:02 | Batch transport `\|<` `▶/⏸` `>\|` | **GO** (addendum on P2) | Centered on existing toolbar; uses batch boundaries, not a hardcoded 5s. |
| P4 | Aug 29 23:19 | Video Generator full readiness | **NO-GO** | Join/honesty repaired. Seedance Ready row not E2E-complete. WAN Testing. MiniMax Runtime Offline. |
| P5 | Aug 30 00:23 | Comfy/GPU guardrails | Standing law | Became `.cursor/rules/comfyui-gpu-runtime-guardrails.mdc`. |
| P6 | Aug 30 09:58 | HelpTip nested-button hydration | Closed as UI composition | Preflight `<button>` wrapping HelpTip. |
| P7 | Aug 30 10:01 | Left drawer vertical scroll | Closed | Layout/scroll container only. |
| P8 | Aug 30 11:34 | Drawer spacing + Turbo LoRA | Implemented in-scope | Turbo toggle under Video Generator. FastVideo/FastH3 judged too soon. |
| P9 | Aug 30 13:22 | Character Creator V3 cutover | Cutover authorized | Front → Qwen angles → sheet. Later blocked by readiness + save + vision. |
| P10 | Aug 30 13:47 | Spatial Map / Timeline / Scene Creator cutover | Planned + started | Owner reported old Spatial Map surface had returned. |
| P11 | Aug 30 14:39 | Qwen angle readiness | Surgical | Button disabled because UNET/runtime gate, not missing Front. |
| P12 | Aug 30 14:54 | Comfy down + Save Character | Runtime restore + save | `:8188` restored through supervisor; Anadriya not regenerated. |
| P13 | Aug 30 15:53 | Co-Director Front vision failure | Restored | Front pixels existed; vision path was not reading them. |
| P14 | Aug 30 16:20 | fal.ai vision + headless Comfy | Master closure | Vision provider is fal `chat_vision`, not Kie. |
| P15 | Aug 30 18:13 | V3 local sheet compose | **GO** | Compose is PIL stitch only. No fal/Kie/Qwen/Comfy on compose. |
| P16 | Aug 30 19:21 | Spatial Map Express GPT Image 2 routing | Surgical | Hosted Express route honesty. |
| P17 | Aug 30 19:37 | Always-on Adept Runtime Service | **NO-GO** on logon | Dual workers exist. `AdeptRuntimeService` task not registered (elevation). Old `AdeptBetaBackendManager` still present. |
| P18 | Aug 31 09:16 | Dual-runtime Background Services | Isolation proven | Manager `:8759` · API `:8758` · Comfy `:8188` independent recycle. |
| P19 | Aug 31 10:27 | Ownership cutover | **E2E BLOCKED** | Windows task registration needs elevation. Not faked. |
| P20 | Aug 30 22:42 | Generate means execute | **GO** | “Please create this image now” must enqueue, not draft a prompt. |
| P21 | Aug 30 23:09 | Default image generation contract | **GO** (policy) | AUTO = local-first, 16:9, 1920×1080 unless specified. |
| P22 | Aug 30 23:33 | Image generator authority | **GO** | Co-Director AUTO reads Production Control; no second catalog. |
| P23 | Aug 31 11:37 | Canonical generation memory | **GO** | Exact prior request wins over chat summary. Typed inherit/override. |
| P24 | Aug 31 13:57 | Hosted availability + fallback | **GO** | Try requested hosted → other configured API → AUTO local. No silent lock-break. |
| P25 | Aug 31 15:43 | Vision regression (attach) | **GO** | Attachment label was treated as pixels. Canonical fal vision restored. |

**Standing product law from P13–P25:** if the creator attaches an image Adept has ingested, Co-Director must see it or report the precise technical reason. Never pretend it is text-only.

---

# Part II — Full Stack Convergence journeys

Project from here: **Korri Anadriya** only.

## Journey index

| ID | When | Journey | Status |
|---|---|---|---|
| J1 | Aug 31 18:05 | Attach a look → Library still → refresh | **HOLDS** |
| J1b | same loop | PLACE still on Timeline + reload | **HOLDS** (two-click Library add) |
| J1c | same loop | CHARACTER on existing Korri sheet | **HOLDS** on `/cc-v2` + `/crs` |
| J2 | Aug 31 18:21 | Attachment chip contrast, then SHOT | **HOLDS** |
| J3 | Aug 31 18:30 | fal.ai GPT Image 2 still, or honest fail | **HOLDS** after route correction |
| J4 | Aug 31 18:43 | Extend LTX Scene 1 → Batch 2 + play + reload | **HOLDS** (see J5 for playback) |
| J5 | Aug 31 19:12 | 2-batch continuous Preview (then 3-batch / 15s) | **HOLDS** |
| J6 | Aug 31 20:57 | Creator Stitch beside Video Finishing | **IMPLEMENTED + LIVE** |
| J7 | Aug 31 21:12 | Named Korri + Anadriya in the generated shot | **PARTIAL** — identity bound; 2.5 two-still limit remains |
| J8 | primary loop | LTX 2.5 Fast / Quality reconnect | **HOLDS** on Fast 8 / Quality 40 |
| J9 | primary loop | Unified Video Finishing (range → mask → Z-Image) | **IMPLEMENTED** on Batch 1 Take E |
| J10 | primary loop | H3 + LTX 2.5 project-reference fidelity | **PARTIAL** — LTX 2.5 live; H3 **BLOCKED** `:8192` |
| J11 | Sep 1 ~03:09 | Home loads cleanly (no repeated 400/502) | **IN PROGRESS** — soak 40/40 **200**; list ~114 KB; `/api/runtime-manager/status` still ~10s |
| J12 | Sep 1 | Timeline Reference-to-Video only | **HOLDS** — H3 identity + extension live; LTX 2.5 one-cond disclosed |
| J13 | Sep 1 | H3 / LTX 2.5 acceleration | **HOLDS** — H3 EasyCache Fast; LTX Fast 8 / Quality 40; TeaCache **MISSING** |
| J14 | Sep 1 | MiniMax H3 R2V 16s corridor dialogue (2×8s) | **HOLDS** — identities + corridor + stitch 16.032s; prior-frame **role** was still place |
| J15 | Sep 1 | H3 prior-frame continuity + voice bind | **HOLDS** on prior-frame role + 16s rerun; voice **wired, unprovable** (no approved assets) |
| J16 | Sep 1 | Timeline R2V sheet tags + H3 CRS/ERS compile + PRS compose | **HOLDS** on Batch 2 sheets + 16s stitch; PRS compose exists, unused on this shot; leftover `#prop-tag` callers remain |
| J17 | Sep 1 | Per-generator R2V knowledge library + compile | **HOLDS** on compile proof (H3 / LTX 2.5 / WAN 2.2 / Seedance); every live PC video row has a researched `.md` |
| J18 | Sep 1 | Preview Monitor video action menu (Add Batch / Re-Take / eye) | **HOLDS** live on Scene 1 generated video |
| J25 | Sep 1 | Clone-from-Recording: hide Advanced, repair Select → Approve | **HOLDS** — Sample 3 approved onto Korri; Create New Voice controls retained |
| J26 | Sep 1 | Unify Voice Studio on Korri’s approved clone + shared warm Qwen worker | **HOLDS** — Performance/Environment/Takes stay on `283e8cf8`; warm takes ~5s vs IndexTTS2 ~61–86s |
| J27 | Sep 1 | Voice Creator Express + default VoiceProfile across Adept | **HOLDS** — Co-Director tab between Character Creator and Prop Creator; same `283e8cf8` / `33a80b24`; Anadriya honest empty |
| J28 | Sep 1 | Voice Studio Choose Another Character must stick | **HOLDS** — URL `characterId` is the only active-character authority; Anadriya no longer snaps back to Korri |
| J29 | Sep 1–2 | Rebuild Audio Studio (music / SFX / ambience / project audio) | **HOLDS** — ACE-Step + MMAudio generate → approve → Library → Timeline; Co-Director opens the surface |

---

## J1 — Attach look → Library → refresh

**Intent.** On Korri Anadriya, attach a look in Co-Director, get a still in this project’s Library, still see it after refresh.

**Classification.** Vision + generate + Library **EXISTS**. Not rebuilt.

**Live.** Library images present after refresh (Venture Corridor look + Co-Director stills). Same project. No new project.

**THEN.** PLACE and CHARACTER were closed in the same loop.

**PLACE.** Timeline Library tray looked empty despite 24 stills. That was staging copy, not a missing Library. Placed still `7a98347c-49d7-4397-8d62-dd253196d5cc` on Scene 1 Visual track. Survived reload as `@Image1` / `@codirector_image_generate_e2bf46ab`. Empty copy changed from “No assets yet.” to “Click Library to choose files from this project.”

**CHARACTER.** Korri SHEET_READY: Front / Side / 3/4 / Back + composed sheet `a97963c4` 2560×1080. Survives reload. **Advanced → Character Sheet** remains EXISTS + DISCONNECTED (`full_body_*` / empty `/visual-sheet`). Main Character Creator page is the working path.

**Change surface.** `AssetTray.tsx` + `en/timeline.json` only for PLACE honesty.

---

## J2 — Attachment chip + SHOT

**Intent.** Readable Co-Director attachment chip, then generate a shot on an actually-Ready engine.

**Chip.** White chip + light `--ink` was unreadable. Now `--ink` on `--panel-elevated`. Layout unchanged.

**SHOT.** Generate no longer treats every engine as unsupported. **LTX 2.3** I2V ran. Library video `cc4c6bb1-20c6-4be5-a138-2f6f817b6faa` (`scene_0_bec77617.mp4`). Provenance `ltx-local`. MiniMax stayed Offline (honest). First take was CandidateReady, later approved in J4/J5.

---

## J3 — GPT Image 2 on fal, or tell the truth

**Live break.** Request sat queued ~3 minutes, then “Live progress paused.”

**Root cause (not a timeout).**

1. A leftover local Qwen row stayed `running` after Comfy had finished, so the single worker never picked up the new still.
2. First honesty pass treated GPT Image 2 as Kie-only and refused fal — **wrong**. Owner updated the fal key; fal **does** host GPT Image 2.

**Repair.** Distinct rows: **GPT Image 2 (Kie)** vs **GPT Image 2 (fal.ai)** → `gpt-image-2-fal` → `openai/gpt-image-2`. Edit uses `openai/gpt-image-2/edit`. No silent Flux/Qwen/Kie swap.

**Live proof.**

| Item | Value |
|---|---|
| Job | `f071b368-cae0-45fe-8771-c2d1998ddc98` **done** |
| Pin | `hostedModelId=gpt-image-2-fal`, `falImageModelId=openai/gpt-image-2` |
| Size | 1920×1080 / 16:9 |
| Reference | Venture Corridor `b98585a0-8829-48cc-8c7b-63b9687955bb` |
| Library | `bb3c0246-e915-42d2-b0d2-9ab8806345c5` (`imagegen_fal_b7c156c4.png`) after reload |

Use the Co-Director **stream** path. A one-shot `/chat` reply can talk as if it generated without enqueueing.

---

## J4 / J5 — Multi-batch extension and continuous play

**Intent.** Extend the 5s LTX Scene 1 into Batch 2 as continuity, play Batch 1+2 as one scene, then 3-batch / 15s. Survive reload.

**Live break (J5).** Batches existed 0–5 and 5–10, but Preview stopped near 4s. Batch 2 looked like a still.

**Classification.**

| Layer | Finding |
|---|---|
| EXISTS | Batch assets, 10s scene clock, approved takes, last-frame bridge |
| DISCONNECTED | Empty `visualClips` ignored approved takes; monitor paused/scrubbed every frame; `<video key={src}>` remounted at 5s and lost play; native controls showed **clip** time |
| MISSING | Scene clock on the monitor; same video element across batch src changes; inclusive end resolve |

The needle at ~4s was clip-local time (~4.71s MP4), not a 4-second scene.

**Reconnect.** During Timeline Play, monitor plays and only drift-seeks if off by >0.25s. Same `<video>` across batches. Clock is `playhead / sceneEnd`. Empty `visualClips` still uses each batch’s approved take.

**3-batch live proof (after reload):** playhead 0→15, clock `0:15 / 0:15`.

| Batch | Window | Asset | Continuity |
|---|---|---|---|
| 1 | 0–5s | `cc4c6bb1-20c6-4be5-a138-2f6f817b6faa` | LTX 2.3 I2V |
| 2 | 5–10s | `81333962-7488-45ec-804f-0d2cae1d5717` | last-frame I2V |
| 3 | 10–15s | `e2bf245e-5cfe-4a91-bad7-11f3a0a29aeb` | last-frame I2V, same `ltx-local` |

**Honest generate note.** First Batch 3 completes (~1.6s) copied an older MP4 (same hash as `scene_0_b2c77db3.mp4`). Those takes were not used. A leftover-output gate and per-job Comfy filename stem were added.

---

## J6 — Stitch (additive, not destructive)

**Intent.** Stitch button beside Video Finishing. Confirm: “Stitch all completed batches together as one clip?” Co-Director concatenates completed/unstitched batches. Source batches, lanes, continuity, and extend remain. Stitch again after Batch 4 updates the sequence.

**Classification.** Concat capability **MISSING** as a creator control; media/Timeline pieces **EXISTS**.

**Reconnect.**

- API: `director_timeline_w46/scene_stitch.py` + `POST` stitch on the existing W46 router
- UI: Stitch beside Video Finishing in `TimelineEditorShell.tsx`
- Preview can play the stitched scene asset while batch structure remains

**Law.** Do not flatten or delete source batches.

---

## J7 — Named characters must be the project characters

**Live break.** Corridor generate produced a no-name man instead of Korri (and later needed Anadriya as well).

**Root cause (not a prompt-hack).**

- LTX 2.3 Ingredients IC-LoRA **EXISTS** on `:8188` (`ltx-2.3-22b-ic-lora-ingredients`).
- Resolver checked `wants_ingredients` **before** LTX 2.5. Combined with `ltx-2.5-distilled` aliasing to adapter `ltx-local`, a named-character **LTX 2.5** generate could **silently run LTX 2.3 Ingredients**.
- Extra character / environment / prop slots on LTX 2.5 are **MISSING** — one start image only. There is no 2.5 IC-LoRA on `:8188`. All IC-LoRA files are 2.3. Do not put 2.3 LoRA on a 2.5 UNET.

**Repair (keep; do not duplicate).**

| File | What |
|---|---|
| `workflow_resolver.py` | LTX 2.5 generator IDs win first. Ingredients never selected for 2.5. |
| `character_identity_bind.py` | `product_generator_id()` reads original/selected id. 2.5 → `ltx25_i2v_start`. H3 I2V → `h3_i2v_start`. 2.3 unchanged (`ingredients_ic_lora`). |
| `ltx_local.py` | Persist identity provenance when Ingredients is off. |
| `TimelineInspector.tsx` | Start Image tip: LTX uses it as first frame; empty = previous take. |

**Role rules.** Same-cast last-frame skip; joining new character uses place/environment, not last frame; creator start that is not a hero is kept as place; else first hero as I2V pixels.

**Tests.** `test_resolver_ltx_25_never_swaps_to_ingredients`; identity bind 2.5 / joining / H3; adapter provenance. 33 + 18 passed in-session.

---

## J8 — LTX 2.5 Fast / Quality

**Intent (primary-loop continuation).** LTX 2.5 must be a real Ready path, not a 2.3 alias.

**Holds.**

- `ltx_25_runtime_steps()` — Fast **8**, Quality **40**
- Fast keeps 1280×720
- `/free` before 2.5 (release models, **not** a restart)
- `ltx-2.5-distilled` Ready
- Live: Fast ~117s, Quality ~312s
- Comfy MCP validated live graphs (`LTXVImgToVideo`, distilled INT8 UNET)

---

## J9 — Unified Video Finishing

**Intent (primary-loop continuation).** Range → mask → Z-Image inpaint on an existing take. Stay Approved for Stitch.

**Holds on Batch 1 Take E** (`bb_2e4f42cb44fd`, Approved). Keyframe repair applied. **Do not regenerate Batch 1** — its last frame is an Ingredients sheet leak (`13943fd606754e048657a40dd165fe20`), which later poisoned last-frame I2V (Take H).

---

## J10 — H3 + LTX 2.5 reference fidelity

**Intent.** MiniMax H3 and LTX 2.5 must use project references with correct roles (character / environment / prior frame / props), not loose inspiration. LTX 2.3 is diagnostic only. Comfy MCP mandatory.

**Comfy MCP.** Cursor has no `comfy` namespace. Canonical: `data/venvs/mcp/Scripts/comfy-mcp.exe` via stdio against live `:8188` (Adept argv + extra_model_paths). 39 tools. Present: `LTXVImgToVideo`, `LTXVBaseSampler` `optional_cond_images`, 2.5 sampler/decode, IC-LoRA (2.3 files), `MiniMaxH3ImageToVideo`, `MiniMaxH3ReferenceToVideo`. Missing: invented `LTXV2*`, TeaCache, any 2.5 IC-LoRA.

**Live LTX 2.5 pixel proof** — Batch 2 `bb_581d6daed83e` CandidateReady. Do not regenerate Approved Batch 1.

| Take | Job | Start | Result | Library |
|---|---|---|---|---|
| H | `83f45387-…` | Last frame (Ingredients leak) | Frame 0 held a **sheet collage**; mid reset to photoreal stranger | `c399cccf-…` |
| I | `7b7892d3-…` | Korri Front, `ltx25_i2v_start` | Costume/tattoos/ears held; hair drifted; studio gray (no place) | `e62bdc4d-…` |
| J | `e6499d31-…` | Corridor place + both names | Place and walk held; **characters invented** (red scarves) | `e91e6035-…` |

Videos 1280×704, 5.04s, 24fps, Fast 8, distilled INT8. Library count 76 after reload. Audio VAE unused (known mux gap).

**H3 (superseded 2026-09-01 evening).** Route A `:8192` stays offline and is **not** the Timeline path. See **J12**.

**Generator limit (honest).** LTX 2.5 = one start tensor. Extra named characters stay in the prompt. Ingredients identity stays on LTX 2.3.

---

## J11 — Home load (current break, OPEN)

**Intent.** Opening Home shows the current project and system status without broken requests, stale project IDs, dead service calls, or misleading UI. If a service is unavailable, say so — do not hammer a broken endpoint.

**Live break.** Repeated **502** on runtime / capabilities / GPU-status style requests, plus **400** project requests. Do not swallow console errors.

**Walked 2026-09-01.** API `/api/healthz` 200 · Vite `/` 200 · Comfy PID 77152 200. Home rendered; status strip stayed on “Checking…” during first paint. Investigation started; **not finished**.

### Sequential probe (browser fetch via Vite origin, then PowerShell)

| Path | Class | Sequential status | Size / note |
|---|---|---|---|
| `/api/healthz` | EXISTS | 200 | 15 B |
| `/api/health` | EXISTS + contract split | 200 | `comfy_reachable:true` but `comfy.reachable:false` (“liveness only”) |
| `/api/gpu/stats` | EXISTS | 200 | RTX 5090 32 GB, ~21.4 / 32.6 GiB |
| `/api/capabilities` | EXISTS | 200 | ~122 KB; direct PowerShell 20s timeout once |
| `/api/runtime/beta` | EXISTS | 200 | Still advertises retired web port **8760** |
| `/api/runtime-manager/status` | EXISTS | 200 | Comfy owned/running |
| `/api/projects` | EXISTS + oversized | 200 | **~7.2 MB** full `ProjectOut` list |
| `/api/projects/beffd3d8-…` | EXISTS | 200 | ~481 KB |
| `/api/projects/beffd3d8-…/jobs` | EXISTS | 200 | ~897 KB |
| `/api/runtime/local-generation` | **MISSING** | 404 | Banner still names this path |

### Working hypotheses (not closed)

1. **502s under load, not missing routes.** Sequential 200s do not disprove Vite-proxy 502s when Home fans out health + GPU + capabilities + **7.2 MB project list** against a blocked API worker.
2. **400s may be stale project IDs.** `localStorage.adept_ui_recent_projects` still lists SenseNova `0ffe56e2-…`, Schnick `2347bf46-…`, Adept Stability Cert `2bc632b8-…` beside Korri. Home `SystemStatusStrip` is **not** given `projectId`.
3. Do **not** “fix” this by hiding console errors or disabling health checks.

**THEN (authorized).** J12/J13 closed in this session. A Vite oxc parse error in `draftCapabilities.ts` put a full-page overlay on Home/Timeline until repaired — that is a load-break, not a 502. Sequential Home now shows Studio API Online / ComfyUI Ready.

**J16 follow-through (this session).** Measured Home fan-out after the sheet-tag API recycle (new API PID **72496**, Comfy **77152** unchanged):

| Path | Status | Size | Note |
|---|---|---|---|
| `/api/projects` | 200 | 113,613 B | ~1.2–1.8 s; counts + cover, not full Library rows |
| `/api/runtime/local-generation` | 200 | 80 B | idle `{active:false}` |
| `/api/runtime-manager/status` | 200 | 1,562 B | **~10.3 s** — first-paint “Checking…” risk |
| Concurrent Home set ×4 | 40/40 **200** | — | **zero 400/502** |

Vite `/` with `Accept: application/json` returned 404 in the soak script; browser/HTML `GET /` is **200**. Stale `localStorage` recents and first-paint Checking vs a real outage are **not closed**.

**J15 follow-through (this session).** Two Home suspects were repaired, not hidden:

| Break | Class | Repair |
|---|---|---|
| `GET /api/runtime/local-generation` | **MISSING** route; client method also missing (`api.getLocalGeneration`) | Reconnected. Service `active_local_generation` already existed. Route on `/api/runtime/local-generation`. Client method added. Live Vite-origin **200**, idle `{active:false}`. |
| `GET /api/projects` **~7.2 MB** full `ProjectOut` (scenes + assets + spatial maps) | **DISCONNECTED** from the existing `scene_count` / `asset_count` / `cover_*` card fields | List now uses `_project_list_out` (empty `scenes`/`assets`, no spatial/learning blobs). Live **200 / 113,613 bytes**. `GET /api/projects/{id}` still returns the full project (Korri: 632 KB, 2 scenes, 89 assets). |

**Live Home after recycle.** Vite `/` shows Korri Anadriya as Active Project (2 scenes · 89 assets). Status strip settled to Studio API Online / ComfyUI Ready · Loading Nodes / Models Ready / Provider Offline / GPU Detected / Capabilities Ready. First-paint “Checking…” is the empty-health frame, not a stuck 502. 400/502 soak and stale `localStorage` recents are **not closed**.

```text
J11 IN PROGRESS — SOAK 40/40 200; RUNTIME-MANAGER/STATUS ~10s; STALE RECENTS OPEN
```

---

## J16 — Timeline R2V sheet tags (this session)

**Intent.** Reference-to-Video conditions on CRS / ERS / PRS, not I2V front stills. Prefix is the type: `@` CRS, `#` ERS, `%` PRS, `*` video. Co-Director loads per-generator `.md` knowledge. Prompt-clip typed tags + binding IDs are the authority.

**Live proving ground.** Venture Corridor Dialogue `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639`. No scene rebuild.

**Compile (source + live generate).** After attaching the three owner-placed bindings onto both Prompt clips:

| Picture | Role | Asset | Comfy name |
|---|---|---|---|
| 1 | character | Anadriya CRS `7e5a01f4-…` | `studio/character_sheet_4c1c0bc8_c1_2abb841a.png` |
| 2 | character | Korri CRS `a97963c4-…` | `studio/character_sheet_4a2e9cbe_c1_0ed74c11.png` |
| 3 | place | `#VentureCorridorScene` `b98585a0-…` | `studio/Venture-Corridor-scene.png` |
| 4 | prior_frame | last take `c7bed656-…` | `studio/cbr_0610f94d0f5a_last.png` |

No Korri Front / Anadriya Front in `ref_images`. No approved corridor ERS exists (`ersSheets: []`); the tagged corridor still is the honest place fallback. Knowledge file loaded: `knowledgebase/video-generators/minimax-h3.md`. Live token is `<Picture N>`.

**Generate.** Job `82ff5c35-be16-4207-a136-728afc154657` · Comfy prompt `01fd6c3f-bdff-446a-888e-d798eb9caf70` · Quality 8s · `CandidateReady` Take C `cand_6cc90d024226` / `cb473d14-7259-454f-8560-1b39fde7f0f9.mp4`. Mechanism `h3_ref2va`, EasyCache off.

**Pixels.** Batch 2 frames keep Anadriya’s silver Adept suit, Korri’s pigtails / pointed ears / tattoos, and the Venture corridor. 7.5s is the pointing beat (“Don't make me get the soap!”).

**Stitch / Library / reload.** Activate Take C → stitch `e1732ed6-ee3c-4551-a1a1-719a93630e5e` (`scene_stitch_ae8e5699_0dcaace1.mp4`, 16.032s). Library contains Batch 1, Batch 2, and the stitch. Master reload matches the same stitch id.

**Batch 1.** The approved first 8s (`5a2e74b3-…`) was **not** rerun. Its original identity slots were Front.png. Continuity last-frame is that take. Do not rebuild the scene.

**PRS.** Prop Creator compose exists (`prs_compose.py` after approve / Use This Prop). This corridor shot has no approved prop, so no `%` subject was invented.

---

## J12 — Timeline Reference-to-Video only (this session)

**Intent.** Timeline never generates a local shot as plain Text-to-Video or ordinary Image-to-Video. One canonical Adept R2V request; each generator maps to the mechanism it actually has. Do not fake R2V by stuffing one still into an I2V start slot.

**Classification**

| Path | Status |
|---|---|
| `generationMode: "reference"` on local Timeline | **EXISTS** — now emitted |
| Canonical R2V request `studio-api/app/director_timeline_w46/generation/r2v.py` | **EXISTS** |
| LTX 2.5 multi-character tensors | **MISSING** — one start image only; extras prompt + disclosure |
| LTX 2.3 Ingredients IC-LoRA | **EXISTS** (2.3 only) |
| H3 Route A I2V `first_frame` on `:8192` | **EXISTS** but **forbidden** as Timeline R2V; runtime offline |
| H3 `MiniMaxH3ReferenceToVideo` + ref2va on `:8188` | **EXISTS** and **wired** |

**Contract.** Local adapters set `supportsTextToVideo=False` / `supportsReferenceToVideo=True` and refuse `text_to_video` / `image_to_video`. WAN and Hunyuan use the same contract (single-cond + prompt extras). Hosted Seedance / Kling / Veo stay on existing T2V/I2V.

**Comfy MCP (live `:8188`).** `MiniMaxH3ReferenceToVideo` (`ref_images` autogrow, `<Picture n>` tags). `MiniMaxH3ImageToVideo` present — Timeline H3 must not submit it. UNETs include `minimax_h3_ref2va_pruned_int8_convrot.safetensors`. CLIP `qwen3vl_32b_minimax_h3_nvfp4_awq`. LTX: `LTXVImgToVideo` + `optional_cond_images` index 0. No 2.5 IC-LoRA.

**Live LTX 2.5 R2V** — Batch 2, job `80e68807-592e-45c7-a4ec-72d13d9b465a`, asset `84af38fa-6a36-4f12-b762-937c27f09e9d` (Take K). `generationMode=reference`, `mechanism=ltx25_single_cond`, mapped start = place (joining), not last-frame leak. Place holds. Characters invented (parkas). Honest one-cond limit.

**Live H3 Ref2V** — Adept Comfy `:8188`, Route A not started. Batches were patched to `minimax-h3` for generate, then restored (Batch 2 → `ltx-2.5-distilled`, Batch 3 → `ltx-local`). Adapter leaf id is still `minimax-h3-t2v-local` (naming debt; capabilities refuse T2V).

| Take | Job | Comfy prompt | Canvas | Tensors | Pixels | Asset |
|---|---|---|---|---|---|---|
| L | `2ee54497-f4b2-4ce7-aced-98a435f1db91` | `419da584-…` | 1280×704, 124f | 4 including **Ingredients leak** as Picture 4 | Place holds; two photoreal blondes — **not** Korri/Anadriya | `60071c80-…` |
| M | `107445ff-c7c4-4768-9eb3-c537d68b1b79` | `9e712121-…` | 768×448, 124f | 3 (Korri, Anadriya, place); leak prompt-only | Place holds; invented man + woman | `e06bb56a-…` |
| **N** Quality | `c142995f-08be-4d96-b0a6-839811bffc69` | `030be205-d6a1-4a5e-9004-018745c2cf61` | 768×448, 124f | 3 + appearance (first sentence) | **Korri holds** (pigtails, tattoos). Anadriya blonde; silver suit drifted to white tank. Place restyled anime | `6ffc37c9-…` `cand_a7c3a23305c4` |
| **G** ext Quality | `a248e341-75f4-4583-ba2a-3521ea09ed0d` | `72f83e27-ca21-4def-86e0-676a3fbf9812` | 768×448, 124f | 3 (Korri, Anadriya, Take N last as Picture 3 place) | **Korri holds**. **Anadriya silver Adept suit + gold gauntlets hold.** Corridor continues. Side swap vs Take N last | `c3cf3a67-9a6a-45af-aaf3-cd484264ae40` `cand_5349e480fbb8` |
| **O** Fast | `180c2a73-64ad-4238-8127-8896f97a7d4f` | `ef11a440-b9b8-49aa-9c34-85da639bee35` | 768×448, 124f | 3 + EasyCache | **Korri + Anadriya silver suit + corridor hold.** Same R2V roles as Take N | `d0ff5458-7640-4b51-9536-bd6c39a59e72` `cand_50ed890d1e5f` |

Submitted graphs: `MiniMaxH3ReferenceToVideo`, UNET `minimax_h3_ref2va_pruned_int8_convrot.safetensors`, LoadImage `Korri Front.png` / `Anadriya Front.png` / place or last-frame still. **No** `MiniMaxH3ImageToVideo`. **No** `first_frame`. Frames: `.runtime/_r2v_h3c/`, `_r2v_h3_ext/`, `_r2v_h3_fast/`.

Take N was **activated/approved** this session (`POST …/batches/bb_581d6daed83e/activate-take`). Outgoing bridge `cbr_6fd50c274d17` last frame `62a22c54045a43c09fca05dca572887d` is a clean Take N last, not the Batch 1 leak. Sequential chain did not auto-generate (`no_queued_batches`). Batch 3 extension used that last frame as Picture 3 place (`joining=False`, leak prompt-only).

**Joining rule.** When a new named character joins, the occupied / leaked previous take stays in the slot list but is **not** uploaded as an H3 picture (`pictureIndex=None`). Disclosure is explicit.

```text
HOLDS — TIMELINE R2V CONTRACT + H3 IDENTITY + EXTENSION
```

LTX 2.5 two-character tensors remain **MISSING**. Photoreal place lock while keeping illustrated identity is still imperfect (anime restyle on Take N). Side swap on extension is a continuity note, not an identity fail.

---

## J13 — H3 / LTX 2.5 acceleration (this session)

**Intent.** After clean R2V baselines, keep only acceleration that materially improves speed without breaking reference fidelity. Creator UI = Fast / Quality, not TeaCache.

**Comfy MCP (live `:8188`).** Evidence `.runtime/_r2v_accel_mcp.json`.

| Path | Status |
|---|---|
| Generic `TeaCache` / `MiniMaxH3TeaCache` | **MISSING** |
| `EasyCache` / `LazyCache` | **EXISTS** (MODEL wrappers) |
| `HyVideoTeaCache` / `WanVideoTeaCache*` | **EXISTS** — Hunyuan/WAN only. **Forbidden** on H3/LTX |
| `MiniMaxH3SigmaShift` | **EXISTS** — flow shift, **not** acceleration |
| `CompileModel` | **MISSING** (`TorchCompileLTXModel` exists; unused) |

Do **not** install TeaCache custom nodes (would risk a Comfy restart). Do **not** wrap H3 or LTX with Hunyuan/WAN TeaCache.

**H3 Fast = EasyCache** on the same 8-step Ref2V graph (`reuse_threshold=0.2`, `start_percent=0.15`, `end_percent=0.95`). Scheduler + guider read `["19",0]`. `assert_h3_ref2v_graph` refuses I2V and foreign TeaCache. Creator copy: “Fast finishes sooner. Quality takes longer and usually looks cleaner. Same picture size.”

| Job | Fast | Cache | Job wall (created→updated) | Identity |
|---|---|---|---|---|
| Take N `c142995f-…` | no | none | **40.2 s** | Korri holds; Anadriya suit drifted |
| Ext `a248e341-…` | no | none | **38.7 s** | Korri + silver suit + corridor |
| Take O `180c2a73-…` | yes | EasyCache | **37.2 s** | Korri + silver suit + corridor — **no R2V regression** |

History on Take O: `videoRuntime.r2v.mechanism=h3_ref2va`, `fast=true`, `cache=EasyCache`, 3 uploaded pictures. Wall win is **modest (~7–15%)** because every H3 job still `/free`s then reloads Qwen3-VL 32B + ref2va. Sampler-only EasyCache is real; end-to-end is dominated by reload. Live VRAM after these jobs: RTX 5090 **~31.4 / 32.6 GiB** used at idle — do **not** skip `/free` without a dedicated VRAM soak.

**Keep Fast.** Identity/place did not regress. Disclose the modest wall. Do not claim TeaCache.

**Creator UI.** Batch 2 inspector on Vite shows Fast checkbox, **Generate Fast**, **Generate Quality**, and the same-picture-size tip. Start Image tip names Reference-to-Video. Take N is active; Take O is listed. A `??` / `||` mix in `draftCapabilities.ts` crashed Vite oxc and put a full-page overlay on Home/Timeline — fixed with `usesFastQualityFlag()`. Test: H3 Fast/Quality copy from product id.

**LTX 2.5 Fast / Quality** already holds from **J8**: Fast **8** steps ~117 s vs Quality **40** ~312 s at 1280×720. Take K this session is Fast R2V (`draft=true`, `mechanism=ltx25_single_cond`, job wall **74.8 s**). No TeaCache on LTX 2.5.

```text
HOLDS — FAST/QUALITY WIRED; TEACACHE MISSING; H3 EASYCACHE NO R2V REGRESSION
```

---

## J14 — MiniMax H3 R2V 16s Venture corridor dialogue (this session)

**Intent.** After Timeline R2V was closed live, create a real 16-second MiniMax H3 Timeline scene as two continuous 8-second R2V batches. Korri and Anadriya walk the Venture corridor and speak the sibling exchange. Batch 2 extends Batch 1. Omni for camera/lighting if the live graph has it. Real audio. Prove playback across the 8s boundary and Library/reload.

**Project.** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` — one Library. Do **not** use Scene 1.

**Scene.** Venture Corridor Dialogue `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` · `minimax-h3` · `duration_sec=16` · `video_finishing`

| Batch | ID | Planned | Status | Asset |
|---|---|---|---|---|
| 1 | `bb_a062bbb7b274` | 8.0s | **Approved** | `5a2e74b3-8834-45b3-ba93-901af9120ef2` · `scene_1_cc5a0a7b.mp4` |
| 2 | `bb_78524a5ec75d` | 8.0s | **Approved** | `10a61e0f-8824-42ea-afa6-22aa0caec7d3` · `scene_1_3519e4ed.mp4` |

Stitch `b6d6a754-8285-4226-bf66-da981f80cb55` · `scene_stitch_ae8e5699_2f2a7568.mp4` · **16.032s** · h264 + aac · sources both approved batches.

**Comfy MCP (live `:8188`, not inferred).** Evidence `.runtime/_h3_scene_mcp.json`.

| Fact | Live |
|---|---|
| `MiniMaxH3ReferenceToVideo` | **EXISTS** — `ref_images` autogrow, `<Picture i>` / `<Video k>` / `<Audio j>` |
| `length` | min 5, max 3600, step 17. **192 frames = 8.000s at 24fps** |
| Audio | `audio_vae` required; `VAEDecodeAudio` + `CreateVideo`; optional `ref_audios` |
| UNET | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` |
| CLIP | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| MiniMax Omni node | **MISSING** — Gemini/Kling Omni API nodes only. Camera/lighting = prompt, no prescribed angles |
| Approved character voice refs | **None** — speech is prompt-driven native AV, not bound `<Audio j>` |

**R2V references actually received by H3**

| Picture | Role sent | File | Semantics |
|---|---|---|---|
| 1 | character | `Korri Front.png` | Korri identity |
| 2 | character | `Anadriya Front.png` | Anadriya identity (silver Adept suit in appearance) |
| 3 | place | `Venture-Corridor-scene.png` | corridor / place |
| 4 (Batch 2 only) | **place** labeled Scene | `cbr_0610f94d0f5a_last.png` | Batch 1 last frame at **7.95s** of 8.0s media |

Batch 2 `generationMode=reference`, `duration=8.0`, `lastFrameAssetId=c7bed656…`, `startImageAssetId` also the last frame (same-cast map). Ranking dedupes by `assetId` and keeps **place before prior_frame**, so the last frame was uploaded as Picture 4 place, not tagged `prior_frame`. Pixels of the previous take **were** sent. Prompt continue-clause for that picture is weaker than intended. Mechanism `h3_ref2va`, Quality (`fast=false`, cache `none`), length **192**. No I2V / T2V / EasyCache.

**Duration repair.** First H3 completion stamped `generatedDuration=5.0` because the H3 worker returned before `outputGate` and completion defaulted to 5.0. Fixed: H3 now writes `outputGate`; completion uses `plannedDuration` when measured duration is missing. Batch 1 restamped to 8.0 and re-placed. Detecting test: `test_missing_measured_duration_uses_planned_not_silent_five`. Batch 2 stamped **8.0** from the gate (`durationSec=8.0`, 192 frames).

**Batch 1 result.** Job `e8df5148-…` · Comfy `9b33d11c-…` · ~58s · 8.000s h264+aac. Pixels: Korri (pigtails, purple eyes, elf ears, tattoos, crop) left/right with Anadriya (blonde, metallic silver Adept suit) in the amber-panel corridor. Mouths open. Audio RMS **3280**, energy in every 0.5s window.

**Continuity handoff.** Bridge `cbr_0610f94d0f5a` Ready. Last frame extracted at 7.95s. Temporal packet `unavailable` (`INSUFFICIENT_VRAM` at extract time) — H3 R2V last-frame extend does not require that packet. Last-frame pixels show both identities + corridor, Anadriya left / Korri right.

**Batch 2 result.** Job `90b1ed9e-…` · Comfy `9f01a73b-…` · Quality · wall ~80s poll · 8.000s. Identities and corridor hold at 0/2/4/6/7.5s. Anadriya **points at Korri at ~7.5s** after a raise-hand gesture at ~7.0s. Audio RMS **2669**, not silence; one near-quiet window at 2.0s (RMS 49.5) then speech energy returns.

**Identity proof.** Generated pixels, not prompt names. Both identities survive the 8s boundary in the stitch (7.5 / 8.0 / 8.5). End frame 15.5s still Korri + Anadriya + corridor + point.

**Dialogue / audio proof.** Native H3 AV on both batches (aac). Energy throughout. **No local Whisper** — speaker-accurate transcript is **not independently ASR-verified**. No approved voice refs. Lips open on several frames; do not claim word-perfect sync.

**Omni camera / lighting.** No MiniMax Omni node on `:8188`. Camera stayed a cinematic mid-shot walking toward camera; amber corridor panels light Anadriya’s suit. Coherent, prompt-chosen, not an Omni graph.

**Library / reload.** Both batch videos and the stitch sit in the same project Library. Master reload keeps both Approved assets and 8.0s visible durations. Vite Timeline after reload still lists the scene; selecting it shows Batch 1 `0.00s–8.00s` Approved and Batch 2 `8.00s–16.00s` Approved Matched. Preview played the stitch (`b6d6a754-…`, duration 16.032) at ~0:06 with both identities; playhead later showed the stop-and-point.

**Playback across 8s.** Stitch probe 16.032s. Frames at 7.5 (Batch 1 walk/talk), 8.0 / 8.5 (Batch 2, same cast/place, modest wardrobe/camera micro-shift), 15.5 (Anadriya points). Not a new setup.

```text
HOLDS — 16S H3 R2V DIALOGUE LIVE; ASR / OMNI NODE / VOICE REFS / PRIOR_FRAME ROLE DISCLOSED
```

---

## J15 — H3 prior-frame continuity + character voice bind (this session)

**Intent.** When Batch 2 extends Batch 1, H3 must receive the previous take’s last frame as **continuity**, not as a place. Korri and Anadriya must use persistent project voice identities on the real H3 `ref_audios` / `<Audio j>` path. Reuse Venture Corridor Dialogue. Do not rebuild the scene.

**Classification**

| Path | Status |
|---|---|
| Canonical R2V `prior_frame` + `H3_ROLE_CLAUSE` | **EXISTS** |
| Ranking/dedup keeping last frame as place when `start == last` | **DISCONNECTED** — repaired |
| `merge_identity_slots` omitting last frame / adding it as Scene | **DISCONNECTED** — repaired |
| H3 identity mapping `startImageAssetId` onto last frame | **DISCONNECTED** — remaps to corridor |
| Live `MiniMaxH3ReferenceToVideo.ref_audios` + `LoadAudio.audio` | **EXISTS** (Comfy MCP) |
| `build_h3_ref2v` / worker `ref_audios` wiring | **EXISTS** after reconnect |
| H3 adapter `supportsAudioReferences` | **DISCONNECTED** — was false; now true, max 9 |
| Character `voice_profiles` API | **EXISTS** |
| Approved Korri / Anadriya voices on this project | **MISSING** — both `active_voice_profile_id` null; 0 profiles; 0 audio assets |
| Schnick “Cloned Korri-sample” | Other project — **not imported** |
| `speech_compile` Lip Sync / `@Name says` | **EXISTS**, still **DISCONNECTED** from H3 `ref_audios` |

**Repair (API recycle only).** `_ROLE_PRIORITY` puts `prior_frame` above `place`. Same `assetId` keeps continuity. `collect_slots_from_batch` / `merge_identity_slots` do not add start-as-place when start equals last; last is always `prior_frame`. H3 same-cast identity remaps start to the corridor. Voice bind reads **approved same-project** `VoiceProfileRow` only. H3 graph `LoadAudio` → `ref_audios.ref_audio_N`. Tests: `test_h3_same_cast_last_frame_stays_prior_not_place`, `test_h3_attach_maps_last_frame_to_prior_when_start_matches`, `test_apply_h3_same_cast_does_not_treat_last_frame_as_place`, `test_timeline_voice_bind.py` (4), H3 audio capability truth.

**Comfy MCP (live `:8188`).** `.runtime/_h3_continuity_mcp.json`. `MiniMaxH3ReferenceToVideo` inputs include `ref_images` and `ref_audios`. Description: `<Picture i> / <Video k> / <Audio j>`. `LoadAudio` required input **`audio`**. No MiniMax Omni node.

**Live Batch 2 Quality rerun.** Job `d1a9ba88-2e3d-4716-b095-50b809b24c58` · Comfy `3e9000f3-e59c-445b-b911-27397e1640c0` · Take B `cand_bde89c9b0616` · asset `3c1fcbf6-78ed-4965-9c41-4c670c7d7aea` · 8.000s h264+aac · `generationMode=reference` · `startImageAssetId` = corridor `2b1f1901-…` · `lastFrameAssetId` = `c7bed656…` · mechanism `h3_ref2va` · Quality (`fast=false`, cache `none`) · length **192**.

| Picture | Role sent | File |
|---|---|---|
| 1 | character | `Korri Front.png` |
| 2 | character | `Anadriya Front.png` |
| 3 | place | `Venture-Corridor-scene.png` |
| 4 | **prior_frame** | `cbr_0610f94d0f5a_last.png` |

Prompt includes `<Picture 4> Previous take (the previous take - continue motion only, do not invent new people)` and `continues the previous take`. Live Comfy graph: `MiniMaxH3ReferenceToVideo` only (no I2V), four `LoadImage`s in that order, **no** `LoadAudio` / `ref_audios` (honest — voices missing). `characterVoices.applied=false`, `missing=["Korri","Anadriya"]`.

**Pixels / audio.** Batch 2 frames 0/2/4/6/7.5s keep Anadriya (blonde, silver Adept suit) left and Korri (pigtails, purple eyes, elf ears, tattoos, crop) right in the amber corridor. 7.5s is the stop-and-point. Audio RMS **2180.6**, two brief quiet windows (2.0s / 5.0s), not silence. **No Whisper.**

**Stitch / Library / reload.** Activated Take B. Stitch `3f7e8a0f-84b4-4f43-a6d0-a0c77512ce19` · `scene_stitch_ae8e5699_661e7465.mp4` · **16.032s** · sources Batch 1 `5a2e74b3-…` + new Batch 2. Library holds both batches + stitch. Master reload keeps the same stitch id. Vite Timeline after reload: Batch 1 `0.00s–8.00s` Approved, Batch 2 `8.00s–16.00s` Approved Matched, clock `0:16 / 0:16`, end frame still both identities + corridor + point. Boundary frames 7.5 / 8.0 / 8.5 keep the same cast and place (modest wardrobe/camera micro-shift at the cut, disclosed).

```text
HOLDS — PRIOR_FRAME IS CONTINUITY ON LIVE H3; 16S RERUN PROVED; VOICE BIND READY, ASSETS MISSING
```

---

# Timeline batch state (do not clobber)

| Batch | ID | Status | Generator | Note |
|---|---|---|---|---|
| 1 | `bb_2e4f42cb44fd` | **Approved** | `ltx-local` | Take E keyframe repair. Last frame is Ingredients leak. **Do not regenerate.** |
| 2 | `bb_581d6daed83e` | CandidateReady | `ltx-2.5-distilled` | Approved take is **N** `cand_a7c3a23305c4`. Extra Fast take **O** `cand_50ed890d1e5f` unapproved. Generator restored to LTX 2.5. |
| 3 | `bb_9da7b6a7cd2c` | CandidateReady | `ltx-local` | Approved still `cand_660e6b1ae577`. New H3 ext take **G** `cand_5349e480fbb8` unapproved. Generator restored to LTX 2.3. |
| 4 | `bb_befb549d7d69` | Approved | `ltx-local` | Matched / stale vs new Batch 2 take |

Generate from the **browser on Vite origin**. Shell POST generate was auto-review blocked earlier.

### Scene 2 — Venture Corridor Dialogue (do not clobber)

| Batch | ID | Status | Generator | Note |
|---|---|---|---|---|
| 1 | `bb_a062bbb7b274` | **Approved** | `minimax-h3` | 8.000s Quality R2V. Take A. |
| 2 | `bb_78524a5ec75d` | **Approved** | `minimax-h3` | 8.000s Quality extend. **Take B** `cand_bde89c9b0616` (J15 prior-frame). Take A unapproved. |

---

# What a stranger can do now

**Can**

- Open Korri Anadriya on Vite `:5173` and Studio API `:8758`.
- Attach a look in Co-Director; fal vision runs; Library stills survive refresh.
- Ask for GPT Image 2 on fal at 16:9 and get a real hosted edit, or an honest refusal if that route cannot run.
- Place a Library still on Timeline and still see it after reload.
- Bind Timed Prompt names (`Korri` → `@Korri` CRS, `Anadriya` → `@Anadriya` CRS, `the corridor` → `#VentureCorridorScene` ERS) from the double-click modal **or** Inspect, then see the same rows on the other surface after reload.
- Open Korri’s Character Creator sheet (main page, not Advanced → Character Sheet).
- Generate LTX 2.3, LTX 2.5, and MiniMax H3 Reference-to-Video on `:8188` without restarting Comfy. H3 uses `MiniMaxH3ReferenceToVideo` + ref2va, not Route A.
- Use Fast / Quality on LTX 2.5 and MiniMax H3 (same picture size; H3 Fast is EasyCache, not TeaCache).
- Play Scene 1 across multiple batches with a scene clock; Stitch completed batches without deleting them.
- From the Preview Monitor overlay, Add a Batch or enter Re-Take on generated video; hide/restore the menu with the eye.
- Play **Venture Corridor Dialogue**: two Approved 8s MiniMax H3 batches as one 16s stitch, identities and corridor surviving the 8s cut.
- Repair a range on an approved take (Video Finishing).

**Cannot yet**

- Trust Home to stay quiet (J11 open).
- Hear approved Korri/Anadriya voices on H3 `<Audio j>` — bind path exists; **this project has no approved voice assets**. Independently ASR-verify the sibling lines.
- Expect a MiniMax Omni camera node (MISSING on `:8188`).
- Condition LTX 2.5 on two separate character stills plus a place (one start image only).
- Expect H3 Fast to be much faster than Quality until `/free` reload is reconsidered with VRAM evidence.
- Treat Batch 1 last-frame as a clean cinematic frame (Ingredients collage leak).
- Rely on Advanced → Character Sheet.
- Rely on Windows logon auto-start of Adept Background Services.

---

## J17 — Per-generator R2V knowledge library

**Intent.** One researched `.md` per video generator Adept actually exposes, so Co-Director translates `@` CRS / `#` ERS / `%` PRS / `*` motion into that generator’s real contract.

**Inventory (live `/api/director-timeline/generators`, 16 rows).**

| Product row | Class | Authority file | Source of truth |
|---|---|---|---|
| `minimax-h3`, `minimax-h3-i2v-local` | EXISTS → reconciled | `minimax-h3.md` | Live MCP/HTTP `MiniMaxH3ReferenceToVideo` (`<Picture i>` / `<Video k>` / `<Audio j>`); official HF Subject vs Picture/Video/Audio; Adept adapter wires images+audio only |
| `ltx-local` | DISCONNECTED stub → split | `ltx-2.3.md` | Live `LTXICLoRALoaderModelOnly` + `LTXAddVideoICLoRAGuide`; Ingredients, no `[R2V]` / Picture tokens |
| `ltx-2.5-full/distilled/comfy` | DISCONNECTED stub → split | `ltx-2.5.md` | Live `LTXVImgToVideo` one image; extras named; `optional_cond_images` exists but Adept 2.5 builder does not wire it |
| `wan-local` | DISCONNECTED stub → WAN 2.2 only | `wan-2.2.md` | Live `WanImageToVideo` / `WanFirstLastFrameToVideo`; **not** WAN 2.6/3.0 |
| `optional-wan` | MISSING → honest | `wan-optional.md` | Readiness: not a Timeline execution path |
| `hunyuan-video-1.5-local` | DISCONNECTED stub → split | `hunyuan-1.5.md` | Live `HyVideoI2VEncode` one image |
| `hunyuan-video-13b-local` | MISSING map → split | `hunyuan-13b.md` | Same HyVideo one-cond, engine `hunyuan13b` |
| `seedance-fal` / Timeline `seedance-api` | MISSING → created | `seedance-2.0.md` | Official fal `@ImageN`/`@VideoN`/`@AudioN` 9/3/3; Adept 4 images + 1 video, no audio; R2V only when video attached |
| `seedance-kie` | MISSING → honest | `seedance-kie.md` | No Timeline adapter; must not bind fal |
| `kling-fal`, `kling-kie` | MISSING → created | `kling.md` | Official fal I2V one `image_url`; adapter in-memory; no multi-ref tokens |
| `veo-kie` / Timeline `veo-api` | MISSING → created | `veo-3.1.md` | Official Veo 3.1 **3** images of **one** subject; Adept adapter **1**; no `referenceImages` POST |
| `veo-fal` | MISSING → honest | `veo-fal.md` | PC row, not a Timeline alias |

Old `ltx.md` / `wan.md` / `hunyuan.md` are pointers only and are **not loaded**.

**Compile chain now.** Creator bindings → canonical R2V slots → selected generator → that `.md` front-matter contract → `map_canonical_r2v` / `compile_for_generator` → adapter. Hosted generators also attach the canonical R2V payload.

**Same-intent proof** (Anadriya + Korri + Venture Corridor; Seedance also `*WalkCycle`):

| Generator | Loaded `.md` | Emitted prompt grammar |
|---|---|---|
| MiniMax H3 local | `minimax-h3.md` | `<Picture 1/2/3>` — no `@Image`, no `[R2V]` |
| LTX 2.5 distilled | `ltx-2.5.md` | `[R2V]` opening + named extras — no Picture |
| WAN 2.2 local | `wan-2.2.md` | `[R2V]` named — no `@Video1` / `@Image1` |
| Seedance fal + video | `seedance-2.0.md` | `@Image1–3` + `@Video1` — no `@Audio`, no Picture |

Artifact: `.runtime/_r2v_knowledge_audit.json`. Tests: `test_r2v_knowledge_compile.py` plus knowledge/Timeline compile regressions **71 passed**.

**Comfy MCP.** stdio `comfy-mcp` `ok: true` (39 tools). Live node description for `MiniMaxH3ReferenceToVideo`: `<Picture i> / <Video k> / <Audio j>`. HTTP `:8188/object_info` agreed. **COMFY RESTARTED?: NO.**

**Unresolved / honest gaps.**

- Official H3 six-section rewrite + `<Subject N>` is documented; Adept Timeline still emits live-node `<Picture N>` only.
- Adept H3 does not wire `ref_videos`; `*motion` must not emit `<Video N>`.
- Official Seedance `@Audio` / 3 videos / 9 images vs Adept 0 / 1 / 4.
- Official Veo 3-image R2V vs Adept 1 start image; Kling/Veo Timeline adapters are still in-memory ledgers.
- WAN 2.6 / 3.0 are **not** Adept product rows.
- `test_timeline_pane_refs.py` still fails on pre-existing `scene_prompt` kwargs (not this journey).

---

## J18 — Preview Monitor video action menu

**Intent.** When Timeline is showing generated video, a compact viewer overlay lets a stranger Add a Batch or enter Re-Take without leaving the Preview Monitor. Eye hides the menu to one restore control; hide must not change playback or scene state.

**Classification.**

| Class | What |
|---|---|
| **EXISTS** | Toolbar Add Batch → `addTimelineBatch` / `directorTimelineAddBatch`. Toolbar / hotkey Re-Take → `handleOpenRetake` (banner + range mark). |
| **DISCONNECTED** | Preview Monitor had no entrance (`inlineActions={false}`). |
| **MISSING** | Video-only mini-menu + independent hide/restore (not Guides `hideOverlay`). |

**Live (Scene 1, Korri Anadriya, Video Finishing, generated LTX clip).** Overlay appeared bottom-center: Add a Batch / Re-Take / eye. Eye collapsed to a crossed-eye restore above the `0:05 / 0:20` clock; playhead stayed **5.431s** paused; batches unchanged. Restore brought the full menu back. Overlay Add a Batch created **Batch 5 20.00s–25.00s** and the clock became `0:05 / 0:25`. Overlay Re-Take pressed both the viewer button and `timeline-open-retake`, and showed “Drag across the Timeline to mark the part to replace.” Cancel exited without mutating the take. Image Planning hid the overlay. Library `@Anadriya` still hid it even after returning to Video Finishing. Overlay returned after clearing the Library preview. Native browser fullscreen was not granted to the automation tab; overlay is `position: absolute` inside `.live-preview-stage` so it rides workspace fullscreen.

**Change surface.** Shared `addTimelineBatch` / `nextTimelineBatchPayload`; `shouldShowPreviewVideoMenu`; `PreviewVideoActionMenu`; pass-through from `TimelineEditorShell` → composer → `LivePreviewMonitor`. Library row click now toggles preview off (same asset) so the creator can return to generated video. Tests: 5/5.

**THEN.** Continue J11 Home. Scene 1 now has the verification Batch 5 (empty extension). Remove it from the existing Batch − control if the 20s four-batch board should be restored.

---

## J19 — Timed Prompt name bindings (modal + Inspect)

**Intent.** Creators write cinematic prose. Timeline binds those Prompt Names to Character / Prop / Environment references already on the scene References pane. Modal and Inspect edit the **same** clip fields. Co-Director compiles those bindings through the selected generator’s R2V `.md` — not by text-replacing `Korri` with `@Korri`.

**Classification.**

| Class | What |
|---|---|
| **EXISTS** | Timed Prompt clip + double-click modal (Prompt / Start / Length / Temperature). Inspect prompt fields. Scene References `@` / `#` / `%` / `*`. Canonical `apply_compiled_references` → `map_canonical_r2v` / `compile_for_generator`. |
| **DISCONNECTED** | Modal hydrated from DirectorTracks memory; Inspect wrote via shell `mutateTimeline`. Snapshot bridge existed but was unwired, so Inspect Prompt Name `the corridor` did not appear in the modal until the shared snapshot was bound. |
| **MISSING** | Shared `reference_name_bindings` contract, one `TimedPromptReferenceBindingsEditor` on both surfaces, scrollable modal body, compact Inspect rows, persist + compile of Prompt Name → binding ID → `@/#/%` role. |

**Frozen contract** (one clip, two surfaces):

```text
reference_name_bindings: [{ binding_id, prompt_name, type, tag }]
reference_binding_ids: string[]   // derived
```

Dropdowns list only this scene’s Character / Prop / Environment References. `*` video stays out. Duplicate Prompt Names and duplicate binding IDs on the same clip are rejected. A removed scene Reference stays missing/unavailable — never retargeted. Modal drafts until OK; Cancel keeps the last save. Inspect writes the same fields immediately.

**Live (Scene 1 clip `ps_79cf57adde16`).**

| Surface | Observed |
|---|---|
| Modal OK | Character `@Korri` / Korri · Character `@Anadriya` / Anadriya · Environment `#VentureCorridorScene` / Venture corridor → then Inspect-edited to **the corridor** |
| Prose | `Korri and Anadriya walk through the Venture corridor.` — no `@` / `#` tokens in the creator text |
| Inspect | Same three rows after select; Prompt Name edit to `the corridor` persisted to GET |
| Modal after Inspect | Same three rows including `the corridor` (after snapshot bridge) |
| Reload | GET still has the three bindings + prose. Inspect textarea value (CDP) matches GET. Modal Cancel left the save intact |

**Generator switch.** The dock Video Generator PUT rewrites **every** batch `generatorId` and can trim this 25s board. That was **not** done on the living scene. The same saved clip was compiled in-memory for `minimax-h3`, `ltx-local`, and `ltx-2.5-distilled`. Creator prose and bindings were unchanged.

| Generator | `.md` | Mechanism | What reached the compiler |
|---|---|---|---|
| MiniMax H3 | `minimax-h3.md` | `h3_ref2va` | `<Picture 1> Korri` · `<Picture 2> Anadriya` · `<Picture 3> the corridor` + authored prose. CRS `a97963c4-…` / `7e5a01f4-…`, ERS `b98585a0-…`. Identities Korri + Anadriya. No `@Korri` in the prefix. |
| LTX 2.3 | `ltx-2.3.md` | `ltx23_ingredients` | Authored prose unchanged. Bindings kept. `IMAGE_REFERENCE_UNSUPPORTED` disclosed (Ingredients, not H3 multi-ref). No Picture tokens. |
| LTX 2.5 distilled | `ltx-2.5.md` | `ltx25_single_cond` | `[R2V]` names the corridor as opening + Korri / Anadriya as extras. Honest one-cond disclosure. No Picture tokens. |

Artifact: `.runtime/_j19_timed_prompt_r2v_compile.json`. Tests: backend `test_timed_prompt_name_bindings.py` **4 passed**; frontend name-binding + snapshot bridge **8 passed** (then 4 overlay tests after the empty-text fix).

**PRS.** This project still has **no approved prop** on Scene 1 References. `%` row was not invented.

**Limitations.** LTX Inspect copy still says extras refuse generation until the creator switches models or removes them — that is capability honesty, not a silent drop. Scene 1 still has leftover overlapping Timed Prompts at 5 / 10 / 15s (including a coffee-shop mug line) with **no** name bindings.

**Journey.** **GO** — both surfaces hold, persist after reload, compile through real generator `.md` knowledge.

---

## J20 — Venture Corridor Batch 3 + Re-Take + Right Drawer

**Intent.** Keep the existing Venture Corridor Dialogue. Add a third MiniMax H3 R2V batch, prove bounded Re-Take on Batch 2 (hair swap only), stop Timed Prompt clips from painting under the open Right Drawer, and compact Inspector / Co-Director / Hot Keys.

**Classification.**

| Section | Class | What |
|---|---|---|
| Batch 3 extension | **MISSING** → now live | Third 8s H3 Quality R2V continuation |
| Batch 2 bounded Re-Take | **EXISTS** | `handleOpenRetake` → `resolveBoundedRetake` → `POST .../retake-range` → `apply_range_replacement_to_asset` |
| Timed Prompt / Right Drawer overlap | **DISCONNECTED** | Workspace used `padding-right`; `overflow:hidden` clips to the padding box, so clips still painted under the Inspector |
| Right Drawer button density | **EXISTS** (oversized) | Same three tabs; `primary`/`ghost` pills were too large |

**Scene (unchanged).** Venture Corridor Dialogue `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` · `minimax-h3` · Video Finishing · 24.0s.

**Batch 3** `bb_7384d4e6866a` · Timed Prompt `ps_j20_batch3` · 16.0s + 8.0s.

| Proof | Observed |
|---|---|
| Generator | `minimax-h3` / adapter leaf `minimax-h3-t2v-local` (naming debt) · `generationMode=reference` · 8.0s Quality |
| Slots | `<Picture 1>` Anadriya CRS `7e5a01f4-…` · `<Picture 2>` Korri CRS `a97963c4-…` · `<Picture 3>` `#VentureCorridorScene` ERS `b98585a0-…` · `<Picture 4>` prior_frame `6b95691dabff4701ac348b6c8468acf5` “Previous take” — continuity only |
| Comfy node | `GET :8188/object_info/MiniMaxH3ReferenceToVideo` — required clip/vae/audio_vae/prompt/width/height/length/ref_image_size; optional `ref_images` / `ref_videos` / `ref_audios` |
| Take | Candidate `cand_fd8c64b7420b` · asset `4252e9ff-…` · Approved |
| Pixels | `.runtime/_j20_b3_frames/b3_{1.0,3.5,6.5}s.png` — both people, corridor, they look toward each other. Silver Adept suit + blonde = Anadriya. Elf ears + tattoos + black pigtails = Korri. Canonical hair (correct for Batch 3) |
| Prompt line | Korri: “You won't take me alive if you try any soap sniping on me.” is on the clip. No approved voices; H3 AV is prompt-driven. Exact spoken words **not ASR-certified** |

**Re-Take Batch 2** — existing range API only. Batch-local **start 2.0 / length 5.0** (scene 10–15s). Leaves 0–2s and 7–8s of the original take so the B2→B3 last frame stays the original.

| Proof | Observed |
|---|---|
| Job | queue `a2df63af-473b-4b48-858f-9d9441a49e03` · mode `reference` · duration **5.0** · repair `rr_f1b935c0389d` |
| Slots | CRS Anadriya + CRS Korri + ERS place. **No** prior_frame (mid-shot; last_frame cleared). Not I2V |
| Compose | New Library video `retake_range_912140a5d3.mp4` · candidate `cand_8a958bc44b72` · asset `d5ccb19f-…` · Activated → Approved |
| 1.0s (unmarked) | Matches original — Anadriya blonde, Korri black pigtails |
| 4.5s (marked) | Anadriya **black hair**, silver suit/face/corridor held. Korri pigtails **blonde**, bangs/top still black (partial) |
| 7.6s (unmarked tail) | Original pointing beat, canonical hair — B3 prior_frame still matches |

**Layout.** First inset used padding; live measure showed Timed Prompt 8s `right=2346` crossing drawer `left=1941`. Switched to **margin** so the workspace border box shrinks. After the fix: scrollport right **1941** = drawer left **1941**, clipped intersection **no drawer hit**. Closed: `margin-right: 0`, workspace width 1169 → 1429. Horizontal scroll still works (`scrollWidth` 2310). Compact tabs: **22px** high, **10.88px** (0.68rem). Inspector / Co-Director / Hot Keys still switch. Screenshot: `.runtime/_j20_right_drawer_open.png`. Tests: `workspaceLayout.test.ts` **10 passed**.

**Stitch.** `POST .../stitch` → asset `ce5f4d3e-daf1-475a-be0e-8ea6189f246b` · `scene_stitch_ae8e5699_845f4bef.mp4` · **24.199s** · sources B1 `5a2e74b3-…` + retake B2 `d5ccb19f-…` + B3 `4252e9ff-…`. Play Timeline pressed live. Stitch frames at 12.5s show the hair-swap region; 20.0s shows Batch 3 look-toward.

**Reload.** After refresh, reselecting Venture Corridor Dialogue shows Batch 1/2/3 **Approved**, Timed Prompts 0 / 8 / 16, MiniMax H3, duration 24, same References. Batch 3 badge may say **Needs update** (fingerprint vs later-shot matching after the B2 activate) — still Approved and playable.

**Limitations.**
- CRS appearance text still says Anadriya blonde / Korri black on the Re-Take prompt prefix, so H3 only partly honored the hair swap (Korri bangs stayed dark).
- Batch 3 was generated from the **pre-Re-Take** B2 last frame. The marked mid-B2 region has swapped hair; the B2 tail and all of B3 stay canonical. That is intentional so the 16s cut still matches.
- No approved voices. Soap-sniping line is authored on the clip; spoken audio is not ASR-proven.
- Adapter id `minimax-h3-t2v-local` remains naming debt. Generation mode was `reference`.
- Scene picker has no URL param — reload lands on Scene 1 until the creator clicks Venture Corridor Dialogue.
- Comfy MCP namespace was not available; node proof used HTTP `object_info`.

**Journey.** **GO** — Batch 3, bounded Re-Take, drawer containment, compact tabs, 24s stitch, and reload all hold live.

---

## J21 — Scene 1 Timed Prompt cleanup

**Intent.** The Timed Prompt track on Scene 1 should contain only prompts that belong to this corridor scene. Classify first. Bind survivors through the existing J19 `reference_name_bindings` contract. Remove only after proving stale / wrong-scene **and** not referenced by a current approved generation. Do not invent a PRS for the mug.

**Walk (live).** Scene 1 `1f46b621-46f9-4b7e-8273-202a49e1ca7c` · `ltx-local` · Video Finishing · 25s / five batches. Director lane had **seven** clips (UI). W46 master had **eight** (IDs drifted; coffee/empty master rows used `legacyPromptSegmentId`). No `%` PRS on References.

**Classification (director lane = creator track).**

| ID | Time | Class | Why | Action |
|---|---|---|---|---|
| `ps_79cf57adde16` | 0–5s | **KEEP** | J19 proof. Approved `cand_cf8283bcbcad` / `snap_3976f97c32bd` used this id (older wording). Already bound. | Keep as-is |
| `ps_d6b2ad31598f` | 5–10s | **MISSING-BINDINGS** | Valid corridor continuation. Approved `cand_a7c3a23305c4` / `snap_bd80bfbf0873` compiled this exact text. | Bind J19 trio |
| `ps_034e5ed44fa8` | 10–15s | **MISSING-BINDINGS** | Valid corridor continuation. Approved `cand_660e6b1ae577` / `snap_d73732a71c30` used this id **without** the `LIVE-TP-B3-EDIT-0831` stamp. | Bind + strip test stamp |
| `ps_998fbe225b51` | 15–20s | **MISSING-BINDINGS** | Valid corridor continuation. Approved `cand_14729b0d794c` / `snap_d1a50ba53ee9` compiled this exact text. | Bind J19 trio |
| `ps_242e95264abc` (W46 `ps_21a0d94af93a`) | 5–10s | **WRONG-SCENE** | Coffee shop / glass mug / green liquid. **0/32** snapshots mention coffee/mug. No approved PRS. | Remove |
| `ps_737a11b559d5` (W46 `ps_0532e47517a3`) | 10–15s | **WRONG-SCENE** | Coffee service counter hold. Same snapshot proof. | Remove |
| `ps_a2a08dfd2401` (W46 `ps_22c1ddd1fc4e`) | 15–20s | **STALE** | Empty overlap on Approved Batch 4. Approved take used `ps_998fbe225b51`, not this empty row. | Remove |
| `ps_6626a88ed00d` | W46 Batch 5 20–25s | **KEEP** (draft placeholder) | Unmanaged empty stub for J18 Batch 5. Not on the 0–20s director track. No authored prompt — not invented. | Leave |

No **DUPLICATE** among survivors — 10s and 15s are sequential continuations, not copies.

**Edit path.** Existing `PUT /api/projects/{pid}/scenes/{sid}/director` only. Prompt Names copied from the J19 proof clip (`Korri` / `Anadriya` / `the corridor`). Reconcile deleted the W46 coffee/empty rows by `legacyPromptSegmentId`. Timing and corridor prose preserved. No generator PUT. No PRS invented. J20 prompt count stayed **3**.

**Compile (selected generator `ltx-local` / `ltx-2.3.md`).** All four survivors: mechanism `ltx23_ingredients`, authored prose unchanged, no `@Korri` text-replace, no `<Picture>` tokens, no `%` PRS. Bindings resolve to CRS `a97963c4-…` (Korri) / `7e5a01f4-…` (Anadriya) and ERS `b98585a0-…`. Disclosure: Ingredients IC-LoRA. Cross-check on `ps_d6b2ad31598f`: H3 `h3_ref2va` Picture tags from Prompt Names; LTX 2.5 `ltx25_single_cond` honest one-cond `[R2V]`. Artifact: `.runtime/_j21_compile.json`.

**Reload + surfaces.** After refresh, Scene 1 shows **four** Timed Prompts at 0 / 5 / 10 / 15 — no overlaps. Inspect on 5s: `@Korri` / Korri · `@Anadriya` / Anadriya · `#VentureCorridorScene` / the corridor · Start 5 · Length 5 · corridor prose. Modal (double-click) shows the same three rows, same prose, 5.00 + 5.00. Cancel left the save intact. LTX Inspect still discloses extras (capability honesty). Screenshots: `.runtime/_j21_scene1_before_overlap.png`, `.runtime/_j21_scene1_after_clean.png`.

**J20 hold (verify, no regenerate).** Venture Corridor Dialogue still 24s / three `minimax-h3` batches **Approved**, Timed Prompts 0 / 8 / 16, Batch 3 `Needs update` badge still Approved. Assets B1 `5a2e74b3-…` · retake B2 `d5ccb19f-…` · B3 `4252e9ff-…`. Inspector / Co-Director / Hot Keys still present. Artifact: `.runtime/_j21_verify_j20.json`.

**Limitations.**
- Scene 1 Inspector Duration spin still shows **20** while the board is **25s** (pre-existing director vs master drift). Not changed.
- Batch 5 empty unmanaged stub remains a Draft placeholder — no invented corridor line.
- LTX 2.3 cannot consume all stored image references as H3 multi-ref; bindings stay, generate extras stay disclosed.
- Binding a clip can badge CandidateReady batches **Needs update**. Approved takes were not regenerated.

**Journey.** **GO** — every remaining Scene 1 Timed Prompt is intentional, belongs to this scene, is bound where supported, has no coffee-shop/test residue, survives reload, and compiles honestly through `ltx-2.3.md`.

---

## J22 — Co-Director beta campaign

**Intent.** Treat Co-Director as a production assistant under beta load. Walk clear, ambiguous, contradictory, missing-ref, wrong-generator, memory, recovery, misdirection, compile, and false-success commands from the live chat stream (`POST /api/codirector/chat/stream`). Classify first loss. Repair source (routing / binding / runtime truth), not prompt wording. Do not approve generates. Do not start MiniMax `:8192`. Do not bounce Comfy.

**Walk.** 33 live cases on Korri Anadriya, Scene 1 unless noted. Ledger: `.runtime/_j22_codirector_beta_ledger_full.json` (first full sweep) and later retest rows. Family 9 compile (no generate): `.runtime/_j22_compile_matrix.json`.

**First full sweep.** 23 PASS / 10 FAIL (`T03 T08 T09 T10 T11 T14 T17 T21 T22 T27`). T01 empty-reply on the first runner was a broken SSE reader, not Co-Director — discarded. The real T01 defect was already live: job `517c2e4f-…` **imagegen / flux-fal** completed for “Create this now: a 5-second MiniMax H3 shot…”.

### Failures → first loss → repair → retest

| Case | Class | First loss | Repair | Retest |
|---|---|---|---|---|
| T01 H3 duration shot → Flux | **DISCONNECTED** | `is_executable_image_turn` + `create…corridor` collapsed video language to `image.generate` (DIRECT). `workspace_tab` dropped by API. Stream returned `execution_status` without `completed`. | Named-engine + duration-shot is video, not still. Timeline workspace / the word Timeline owns T2V/I2V as `timeline.generate_shot` handoff (no chat video job). Register `video.generate` (NEEDS_APPROVAL) and `timeline.generate_shot`. Wire `workspace_tab`. Close dispatch with spoken `assistant` + `completed`. | **PASS** — Timeline R2V handoff names MiniMax H3, Korri, Anadriya, the corridor. No new image job. |
| T08 H3 only + fallback | **DISCONNECTED** | LLM accepted both. | Deterministic contradiction gate before dispatch/LLM. | **PASS** |
| T09 identical + completely different | **DISCONNECTED** | LLM treated it as a look brief. | Same contradiction gate. | **PASS** |
| T10 no refs + exact characters | **DISCONNECTED** | LLM accepted both. | Same contradiction gate. | **PASS** |
| T11 `@SchnickWhoIsNotOnThisProject` | **MISSING** bind | Entity resolver existed; chat never consulted it. LLM wrote a shooting plan. | `unresolved_tagged_mentions` (`@` / `#` / `%`) before dispatch/LLM. | **PASS** — no invented CRS. |
| T13 `#MoonBaseHangar` | **MISSING** bind | Same — accepted a missing ERS (first-sweep scorer missed it). | Same tag gate. | **PASS** |
| T14 `%CoffeeMug` | **MISSING** bind | Claimed the PRS was now bound. | Same tag gate. Scorer no longer flags echoing `%CoffeeMug` in a “will not invent” refusal. | **PASS** |
| T17 Timeline T2V | **DISCONNECTED** | `_STANDALONE_T2V_RE` returned `video.generate` before Timeline ownership → “Shall I proceed?” | Timeline surface + T2V/I2V/video → `timeline.generate_shot` handoff. | **PASS** — R2V reframe, no proceed. |
| T21 scene/generator | **DISCONNECTED** | LLM said no scene. Then inspect used “do not use Scene 1” as the scene number and `Scene.engine` (stale) instead of Timeline master `generatorId`. | “What scene are we on” uses request `scene_id`. Numbered “scene N” ignores “do not use scene N”. Engine from W46 master batches. | **PASS** — Venture Corridor Dialogue · MiniMax H3. |
| T22 Schnick project | scorer false FAIL | Honest refuse still contained the word Schnick. | Bleed only if the name is claimed without a refuse. | **PASS** |
| T24 dead Library UUID | **DISCONNECTED** | Dispatch showed `Generate — 0/1 in progress` (first sweep scored PASS — false). | `missing_library_asset_ids` before dispatch. | **PASS** — not in this project, no generate. |
| T27 mind-change / Scene 1 engine | **DISCONNECTED** | `Scene.engine` said H3; live Timeline generator is `ltx-local`. | Master `generatorId`. | **PASS** — Scene 1 · LTX 2.3 local. |
| T34 confirm job id | **DISCONNECTED** | `MiniMax H3` + `shot` classified as execute. | Interrogatives / “you just generated” / “confirm job id” are not video production. | **PASS** — no handoff execute. |

**Family 9 compile (in-process, no generate).** Same walk prompt:

| Generator | Knowledge | Mechanism |
|---|---|---|
| `minimax-h3` | `minimax-h3.md` | `h3_ref2va` `<Picture n>` |
| `ltx-local` | `ltx-2.3.md` | `ltx23_ingredients` |
| `ltx-2.5-distilled` | `ltx-2.5.md` | `ltx25_single_cond` `[R2V]` |
| `seedance-api` | `seedance-2.0.md` | `seedance_r2v` |
| `seedance-kie` | `seedance-kie.md` | unmapped / not a Timeline path (not invented LTX `[R2V]`) |

Unknown `seedance-1.5-pro` was previously compiled as LTX-style `[R2V]`. Repair in `r2v.py`: unmapped dialect leaves authored prompt unchanged. Regression: `test_unknown_generator_does_not_invent_single_cond_r2v`, `test_seedance_kie_stays_unavailable_not_fal`.

**Regression tests added.** `test_minimax_h3_duration_shot_is_not_still_image`, `test_minimax_h3_duration_shot_on_timeline_is_handoff_not_t2v`, `test_use_minimax_h3_alone_is_not_video_execution`, `test_timeline_t2v_is_handoff_not_proceed`, `test_confirm_job_question_is_not_video_execution`, `test_contradictory_h3_only_and_fallback_is_disclosed`. Targeted suite: **52 passed** (`test_speech_act_imperative_and_pragmatic_request_execute` still fails on `Create Korri's CRS.` — pre-existing `classify_intent` without speech-act; not this campaign).

**Remaining weaknesses after the first campaign (closed in J22 closeout below).**
- T03 / T02 / T16 / T23 / T26 / T31 were open after the first 33-turn sweep.
- One Flux imagegen from the broken T01 (`517c2e4f-…`) remains in the Library. Not deleted (no destructive cleanup).

**Journey.** **GO** — the matrix was walked on the live creator stream; every reproducible routing/binding/runtime-truth defect found was repaired and retested, or listed with an exact leftover. Spoken reply, chosen capability, and runtime action agree on the repaired paths. No MiniMax job was approved. No Comfy bounce.

### J22 closeout (this session)

Did **not** rerun the original 33 from scratch. Closed the leftovers on the live stream, then ran 20 new adversarial commands that were not in that matrix. Ledger: `.runtime/_j22_leftover_adversarial_ledger.json`.

**Classify before repair.** Implied untagged refs **DISCONNECTED**. Generator action language **DISCONNECTED** (LLM paste homework). Cancel-without-job **DISCONNECTED**. Seedance named generate **DISCONNECTED** (handoff omitted Seedance). Chat-side R2V **MISSING** (compile only). `Create Korri's CRS.` **DISCONNECTED** (`classify_intent` without speech-act). Memory/error phrases **PARTIAL**.

**Repairs.** Deterministic situational gate in `service.py` (`implied_references.py`, `situational_replies.py`). CRS registered as `character.generate_visual_sheet` and speech-act COMMAND now executes that capability. Chat R2V answers load the same `video-generators/*.md` compile contracts as Timeline. No silent engine/CPU/hosted fallback. No generate approval.

**Leftover retests (live).** T02 T03 T16 T23 T26 T31 + CRS question **PASS**.

**Adversarial (new, live).** A01–A20 **20/20 PASS** after first-pass repairs (hallway/both girls, MiniMax explain, LTX switch, Seedance both+env, unbound prop, stop/never mind/try again/previous, same scene, previous generator, keep except environment, change only Korri, again with Anadriya, attached-none, Kori/Anadria misspell, 5s+8s conflict, LTX 2.5 three-cond refuse, Scene H3 same bindings, Seedance Kie unmapped).

**Full leftover+adversarial ledger.** **27/27 PASS**.

**Regression tests added.** `studio-api/tests/test_codirector_situational_beta.py` (implied bind, CRS execution, no-paste select, cancel-none, .md dialects, Seedance unready, LTX 2.5 one-cond). Targeted with generation-authority: **33 passed**.

**Exact remaining weaknesses.**
- Seedance fal is **Ready** on this machine (API key present). T23 now says that honestly instead of inventing “unready.” Seedance Kie remains **not a Timeline path**. Hosted Seedance E2E generate is still the older P4 NO-GO.
- “Use MaxiMin H3 for a 5 second and 8 second shot” asks the duration question first and does not also name MaxiMin as unknown.
- Misspell “Kori” asks about Korri; “Anadria” in the same turn is not also asked.
- `Create Korri's CRS.` now classifies as Character Creator execution. Live enqueue of a new Korri sheet was **not** run (Korri already has a CRS; no extra GPU sheet this session).
- Generator selection does not PUT the Timeline default (same J22 fence).
- Flux leftover `517c2e4f-…` still in Library.

**Journey closeout.** **GO** — leftover J22 weaknesses are closed or reduced to the exact blockers above. Co-Director names real bindings without `@/#`, speaks generator ownership without paste homework, cancels honestly, recites the same .md contracts as compile, and does not fabricate job/vision/reference success.

---

## J23 — Voice Studio images, method cards, four-sample preview

**Intent.** Keep Voice Studio’s locked steps. Restore Korri/Anadriya portraits. Modernize the four voice-method cards. Add near-realtime Voice Preview (four short candidates) on the existing Qwen3-TTS Voice Design path. Do not silently downgrade final generate. Do not bounce Comfy.

### Live classify (chooser + Voice Identity)

| Surface | Class | Evidence |
|---|---|---|
| Character images | **DISCONNECTED** presentation | Approved `hero_identity` assets **200**. Square `object-fit: cover` cropped the heads off. |
| Voice method cards | **DISCONNECTED** chrome | Four methods existed; icons were literal `\U+1F3A4` strings. Clone/upload/existing were not wired in source. |
| Script / prompt | **EXISTS** | Same fields; generate body ignored them (UI aliases vs `designBrief`/`testLine`). |
| Voice engine | **EXISTS** | `qwenVoiceDesign` + `qwenVoiceClone` + Kokoro **ready**. Worker reloads 1.7B per sample. Official `qwen_tts` has `generate_voice_design` only — **no PCM stream API**. |
| Preview latency | **MISSING** | Only batch GENERATE. No first-audio path. |
| Persistence | **DISCONNECTED** | Approve required `voiceId` the panel did not send. Approved-status was project-wide. Timeline `<Audio j>` bind **EXISTS** (`voice_bind.py`) once `active_voice_profile_id` is approved. |

### Repairs

- Portrait picker prefers canonical+approved hero; `object-position: 50% 12%`; `assetUrl(..., projectId)`.
- Compact SVG method cards. Clone / upload / existing keep their existing APIs.
- `Voice Preview` → `POST .../voice/design/preview-stream` (SSE). Warm Qwen serve worker. Four short variation instructs. Preview tagged `voice_preview`. Final GENERATE unchanged quality.
- Character-scoped approve + approved-status. Preview cannot approve onto another character.

### Engine report

| Item | Result |
|---|---|
| Current baseline | Qwen3-TTS Voice Design 1.7B, one-shot subprocess, sequential full WAVs |
| Streaming candidates | Official package: no `generate_*_streaming`. `non_streaming_mode=False` is simulated text input only. `faster-qwen3-tts` remains a candidate, not installed. |
| Time to first audio | **Not measured** — GPU preflight refused load |
| Four-sample completion | **Not measured** |
| Quality | Preview is disclosed short audition; final path unchanged |
| VRAM | RTX 5090: **359–514 MiB free** (Comfy holding ~31 GB). Preview requires ~4 GB free. Honest refuse. No CPU / hosted / Kokoro fallback. |
| Winning preview path | Warm Qwen Voice Design serve + progressive SSE + short `max_new_tokens`. PCM streaming deferred until official or faster-qwen3-tts can be benchmarked on free GPU. |

### Live verify

Chooser portraits now show Korri and Anadriya faces. Voice Identity shows Korri portrait, selected Create New Voice card, Voice Preview + four sample slots. Clicking Preview on Korri printed the GPU-memory refuse and did not start another engine.

**Blocker.** Live four-sample audio, distinct Korri/Anadriya approve/reload, and H3 `<Audio j>` proof need ~4 GB free GPU. Ask before Comfy `/free` (unload only — not restart).

**Journey.** **NO-GO** — UI + wiring hold; live audition audio is blocked by GPU residency. **Superseded for Preview UX by J24** (Preview path retired).

---

## J24 — Voice Studio clone/generate simplify, dark dropdowns, warm samples, real players

**Intent.** Make Voice Studio straightforward: recording/permission/transcript → spoken line → voice description → archetype/accent if useful → 1–4 samples → generate quickly on the local Qwen Voice Design path → audition each result with a real player → select/approve onto the correct character. Remove unused Preview. Fix unreadable native dropdown menus. Do not silently change engine, host, or CPU.

Project: **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` · Korri `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed` · Anadriya `4c1c0bc8-a771-4998-b652-5d549b2a2b8d`.

### Live classify (before)

| Surface | Class | Evidence |
|---|---|---|
| Clone controls | **EXISTS** | Recording upload, transcript, permission checkbox, script, prompt, advanced, sample count, Generate |
| Dead Preview path | **EXISTS** | Voice Preview button + SSE `preview-stream` + leftover GPU refuse + “Use Sample…” dropdown |
| Dropdown rendering | **DISCONNECTED** | Native `<select>` closed field looked dark; Windows/Chrome opened a white OS menu with nearly invisible text |
| Sample-generation latency | **DISCONNECTED** | Production generate cold-loaded 1.7B per sample; Preview warm serve capped tokens |
| Candidate-result UI | **DISCONNECTED** | Numbered cards / generic `<audio controls>` — not compact exclusive players |
| Approval persistence | **EXISTS** | Character-scoped approve + `voice_bind.py` once `active_voice_profile_id` is set |

### What was removed

- “Use Sample…” dropdown (`vs-sample-preset` / `SAMPLE_LINES`)
- Voice Preview button, `VoicePreviewRack`, `streamCharacterVoicePreview`
- `POST .../voice/design/preview-stream` and `stream_voice_previews`
- Preview-only token caps on the product generate path

Kept: permission checkbox, recording upload, transcript, Script / Sample Text, Voice Prompt Details, Advanced Voice Controls, 1–4 sample count, Generate Voice Samples, compile `/voice/design/preview` (prompt compile, not audio).

### Dropdown root cause / fix

Windows/Chrome does not honor CSS on the native opened `<option>` list. Restyling `.vip-select` cannot make that menu readable.

Replaced Archetype, Accent, Age, Character, and saved-voice fields with a custom Adept listbox (`VoiceStudioSelect`): dark navy panel `rgb(22, 36, 51)`, light text `rgb(232, 241, 248)`, teal hover/selected, keyboard Arrow/Home/End/typeahead/Escape, `max-height` 16.5rem with overflow scroll (Archetype 26 options, `scrollHeight` 1096 / `clientHeight` 262). Closed state shows the chosen label (Rebel proven).

### Generation bottleneck

1. **VRAM occupancy** — Comfy Desktop PID **77152** held ~31 GB. Existing `/free` (unload, not restart) freed the GPU. Same PID after. `COMFY RESTARTED?: NO`.
2. **CPU-only torch in the Voice Design venv** — `qwen-tts` pip-install pulled `torch 2.13.0+cpu`. Warm serve refused honestly: “needs a CUDA GPU. CPU was not used.” Repaired the venv to `torch 2.11.0+cu128` (`cuda True`, RTX 5090). Install script now force-reinstalls CUDA wheels after `qwen-tts`.
3. **Cold reload per sample** — production `run_voice_design` used one-shot `_try_m210b_generate`. Now every full-quality sample goes through the warm `--serve` worker, sequential, same engine, no token cap.

### 1 / 2 / 4 sample timings (local Qwen3-TTS Voice Design 1.7B, `cuda:0`, full quality)

| Request | Wall | Per-sample completeMs | Warm |
|---|---|---|---|
| 1 | **22.5 s** (includes serve start + model load) | 7599 | yes after load |
| 2 | **12.9 s** | 6876 + 5926 | yes |
| 4 | **23.9 s** | 6806 + 5847 + 5355 + 5828 | yes |

Stable production path: keep the Qwen Voice Design worker warm; generate samples sequentially on GPU.

### Audio-player proof

UI generate on Korri produced four compact players. Measured: play sample 1 (`paused:false`, 4.16s), pause, play 2 (1 paused), play 3, play 4 — only the intended sample playing. Seek sliders present. Sample 2 selected (`aria-pressed=true`).

### Approval / reload proof

- Approved selected Sample 2 → `voiceProfileId` `5c1f3ade-0b8d-4aae-bda1-4b9cb2fb8ab7`, asset `3a22e4c6-b945-4d43-9c71-e44c242570e7`
- Asset **200** `audio/wav` 172844 bytes
- After reload: Voice Performance unlocked with “Approved voice identity · Korri Voice Draft”; Voice Identity banner **Approved Voice — Korri Voice**, playable src on that asset
- Anadriya `hasApprovedVoice: false` — ownership stayed on Korri
- Timeline / MiniMax H3 `<Audio j>` bind path unchanged (`voice_bind.resolve_approved_voice_audio`)

### Limitations

- Clone still returns the existing clone API candidates (typically one), not a silent multi-clone
- A same-tick UI click of sample-count 2 + Generate can still send the previous count (4). A normal click-then-generate uses the chosen count
- Anadriya does not yet have an approved voice — H3 dual-character `<Audio j>` still needs her approval
- Voice Design venv CUDA torch is a runtime repair, not a committed wheel
- Official `qwen_tts` still has no PCM stream API

**Journey.** **GO** — clone/generate UX no longer contains Use Sample or Voice Preview; Archetype/Accent opened menus are readable; 1–4 local samples generate on the fastest proven warm GPU path; Korri candidates play, select, approve, and survive reload on Korri only.

---

## J25 — Clone-from-Recording: hide Advanced, repair Select → Approve

**Intent.** Clone from Recording should be Recording → permission → Script → sample count → Generate → audition → Select → Approve. Advanced Voice Controls / Archetype / Accent belong to Create New Voice only. A selected generated clone must make Approve Selected Voice active even when Korri already has an approved voice. Approving Sample 3 must attach that exact audio to Korri, survive reload, and resolve on the existing Timeline / MiniMax H3 voice-bind path. Do not touch Anadriya.

### Live classify (before)

| Stage | Class | Evidence |
|---|---|---|
| Sample generation | **EXISTS** | Four playable clone WAVs on the local Qwen clone worker |
| Candidate data (`id` + `assetId` + `audioUrl`) | **EXISTS** | Clone workspace meta UUIDs + Library assets |
| Select / visual Selected | **EXISTS** | Sample 3 showed `Selected` / `aria-pressed=true` |
| Canonical selected-candidate state | **EXISTS** | `selectedSampleId` matches the Selected row |
| Approve enable condition | **DISCONNECTED** | `approveDisabled={hasApprovedVoice}` kept Approve off because Korri already had **Korri Voice Draft** |
| Approve payload / VoiceProfile / asset / reload | **EXISTS** if Approve is allowed to run | `POST .../voice/approve` `{ voiceId, candidateId }` → `approve_voice_candidate` |

**First loss point.** Not a missing candidate ID. Not Preview-era state. Not a missing asset. The enable predicate treated “already has an approved voice” as “cannot approve a replacement.”

### Repair

- Hide Advanced Voice Controls, Character Archetype, and Accent unless Voice Method is Create New Voice. Clone payload still sends no `designBrief` / archetype / accent.
- Enable Approve only when the selected generated sample has audio and a just-generated `voiceId` (`canApproveSelectedVoice`). Existing approved Korri voice no longer disables the button; the UI discloses replacement.
- Approve sends the selected candidate ID, never `existingVoiceId` / Sample 1 by default.
- Restore only a newer unapproved clone than the current approved voice, so leftover proof benches do not become a stale approval target after reload.

### Live proof (Korri Anadriya)

| Item | Value |
|---|---|
| Selected candidate ID | `fce44d0a-cb9e-4a0a-b938-0285ac8400b9` (Sample 3) |
| Selected asset | `33a80b24-8b5a-4739-aca3-98c348febe4f` |
| Approved voice profile | `283e8cf8-3c59-4a9e-8ba9-2f7ba1535ad2` (CLONE, not the prior design draft) |
| Prior Korri Voice Draft | `5c1f3ade-0b8d-4aae-bda1-4b9cb2fb8ab7` still `approved` in history |
| Approved asset | **200** `audio/wav` 241964 bytes |
| Reload | Banner “Korri now owns this approved voice”; player src is Sample 3; no stale extra samples |
| Timeline bind | `resolve_approved_voice_audio` → Korri `283e8cf8` / `33a80b24`; Anadriya `None` |
| Select switch | Sample 3 → Sample 2 moved visual Selected + approval target; Sample 3 re-selected before Approve |
| Create New Voice | Still shows Voice Prompt Details, Advanced Voice Controls, Archetype, Accent |

Unit tests: `studio-web` `voiceIdentityBrief.test.ts` **9 passed**.

### Limitations

- Dual-character H3 `<Audio j>` still needs an owner-approved Anadriya voice. Do not invent one.
- Cursor browser cannot attach the file input (`DOM.setFileInputFiles` denied); this approve used the already-generated four-sample clone already on Korri’s workspace.
- Official `qwen_tts` still has no PCM stream API.

**Journey.** **GO** — Clone has no Advanced/Archetype/Accent; Sample 3 selected becomes Sample 3 approved; Korri keeps the new clone after reload; Timeline bind resolves that asset; Create New Voice design controls remain.

---

## J26 — One approved Korri voice, one warm local speech runtime

**Intent.** After J25, Korri’s approved Voice Identity is Qwen clone `283e8cf8` / Sample 3 `33a80b24`. Later Voice Studio stages must speak as that same Korri, and compatible speech generation must reuse the already-warm local Qwen worker instead of cold-loading IndexTTS2 (or another Qwen copy) on every take.

### Surface inventory

| Surface | Class | Engine / notes |
|---|---|---|
| Voice Identity generate (design/clone) | **EXISTS** | Warm Qwen `--serve` workers |
| Voice Identity → approved VoiceProfile | **EXISTS** | Active authority `283e8cf8` / preview `33a80b24` / reference `a61cd900` |
| Voice Performance Generate Takes | Was **DUPLICATE + DISCONNECTED** | Always IndexTTS2; new subprocess + cold model load per take |
| Scene Dialogue / Takes tabs | **EXISTS** (same studio) | Same `VoicePerformanceStudio` + same generate path |
| Voice Environment | **EXISTS** | DSP on the approved dry take — no new speaker |
| Lip Sync / Timeline send | **EXISTS** | Uses approved take file / Identity bind |
| Timeline H3 `<Audio j>` | **EXISTS** | `voice_bind.resolve_approved_voice_audio` → active profile + approved preview |
| `run_generate_dialogue` / W44 segments | Was **DISCONNECTED** | Cold m210b one-shot even for Qwen clone/design |
| Co-Director `voice.generate` | Was **DISCONNECTED** | Imported a nonexistent Kokoro `generate_voice` |
| IndexTTS2 | **Intentionally separate** | Emotion-vector / non-Qwen voices only |

### First loss points (measured, then repaired)

1. **Latency.** `create_takes` → `index_tts2.generate_take` → `subprocess.Popen(worker_infer.py)` loaded IndexTTS2 for every take. Live before (same Korri line family, record `4500bee1`): Take 1 created `02:40:48` → generated `02:42:14` (**~86s**); Take 2 `02:42:50` → `02:43:51` (**~61s**).
2. **Identity.** Those IndexTTS2 takes re-cloned Korri’s WAV through a second engine. Same VoiceProfile ID, new speaker approximation.
3. **Record binding.** `matching[0]` / newest-approved-by-date could attach a stale voice or another character’s record. Repair: prefer `active_voice_profile_id`, never fall back across voice IDs.

### Shared runtime chosen

`generate_approved_voice_speech` on the existing Voice Identity warm workers:

- Qwen **CLONE** → `generate_voice_clone_sample` (reference asset `a61cd900`, x-vector when no transcript)
- Qwen **DESIGN** → `generate_voice_design_sample` (+ optional performance instruct)
- Non-Qwen approved voices stay on IndexTTS2. No silent engine swap. No CPU. No hosted fallback.

Voice Performance `create_takes`, `run_generate_dialogue`, and Co-Director character `voice.generate` now call that function when `qwen_speech_compatible`.

### Before / after timings (same short line)

Line: `Light circuitry, not tattoos, doofus.`

| Surface | Cold / first | Warm subsequent | Notes |
|---|---|---|---|
| Voice Identity sample (prior J25 batch) | — | 10.3 / 13.2 / 12.4 / 13.0 s `completeMs` | Four clone samples, `cuda:0`, warm worker |
| Identity / dialogue after API recycle | **23.13s wall** (`completeMs` 6850) | — | Worker start after recycle + 6.85s infer |
| Voice Performance take 1 | — | **5.21s** | `providerId=qwen3-tts`, mock false |
| Voice Performance take 2 | — | **4.96s** | Same worker, no reload |
| Voice Performance takes 3+4 | — | **11.02s** (~5.5s each) | Sequential, same worker |
| Voice Environment render | — | **0.135s** | DSP only; dry take `e4de76bc` → processed `f83517d1` |
| IndexTTS2 (before, same character) | **~61–86s / take** | n/a | New subprocess + model load |

### VRAM

| When | Used / free MiB | GPU util |
|---|---|---|
| After API recycle, before speech | 1447 / 30741 | 1% |
| After identity dialogue | 6344 / 25844 | 19% |
| After take 1 | 6344 / 25844 | 19% |
| After four takes | 6344 / 25844 | 17% |
| End | 6344 / 25844 | 0% |

Worker stayed resident across Identity → Performance → Environment. No unload between takes. Comfy `:8188` left alone.

### Canonical Korri authority (reload + Timeline)

| Layer | ID |
|---|---|
| Character | Korri `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed` |
| Active VoiceProfile | `283e8cf8-3c59-4a9e-8ba9-2f7ba1535ad2` (CLONE, qwen3-tts, **Korri Clone**) |
| Approved preview | `33a80b24-8b5a-4739-aca3-98c348febe4f` (Sample 3, 200 `audio/wav` 241964 bytes) |
| Clone reference | `a61cd900-c066-4f0b-990f-5070db64bac5` (original recording; used to speak new lines) |
| Prior design draft | `5c1f3ade-0b8d-4aae-bda1-4b9cb2fb8ab7` still approved in history, **not** active |
| Performance record | `f2892a4f-9d42-470e-af74-93cb51ba6deb` `providerId=qwen3-tts` |
| Approved take | `9665f560-86ec-4c87-8d40-81e920edd278` asset `e4de76bc` 3120 ms, 200 `audio/wav` |
| Environment | profile `a1c7deb7` / render `953de5e7` approved; DSP on that dry take |
| Reload | `active_voice_profile_id` still `283e8cf8`; preview still `33a80b24` |
| Timeline bind | `resolve_approved_voice_audio` → Korri `283e8cf8` / `33a80b24` |
| Anadriya | `hasApprovedVoice: false` / bind `None` |

Browser (Vite): Voice Performance shows “Approved voice: Korri Clone. Takes use this same voice.” plus the warm-worker message. Four playable takes; Take 1 Approved; first `<audio>` played (`currentTime` 0.57s, `readyState` 4). After reload, Environment / Scene Dialogue / Takes unlock. Environment header: same Korri Clone + approved take `9665f560`, dry vs Small Room pass, no new speaker.

### Engines kept separate

- **IndexTTS2** remains for voices that were built on that engine and for IndexTTS2 emotion-vector direction. Qwen clone does not pretend to have those vectors.
- **Voice Environment** stays DSP. It must not synthesize a new identity.
- **Kokoro** is not a silent fallback for character speech.

### Limitations

- Generate Takes is still one synchronous API call; the UI now announces generation immediately, but takes appear together when the request finishes. Not claimed realtime.
- Qwen clone performance direction is seed + spoken text, not IndexTTS2 emotion vectors. Do not swap engines to “get emotion.”
- No in-repo speaker-embedding comparator. Consistency proof is IDs + same clone reference + playable audio, not a cosine score.
- Dual-character H3 `<Audio j>` still needs an owner-approved Anadriya voice. Do not invent one.
- Co-Director `voice.generate` now requires a character with an approved Qwen voice. Generic no-character narration is an honest error, not Kokoro.

**Journey.** **GO** — Korri’s approved clone stays the speaker through Performance, Environment, reload, and Timeline bind. Compatible speech uses the shared warm Qwen worker. Voice Performance is no longer the IndexTTS2 cold path for this voice.

---

## J27 — Voice Creator Express + one default VoiceProfile

**Intent.** An approved Voice Identity is the character’s default voice everywhere. Co-Director gets a compact Voice Creator (Voice Studio Express) between Character Creator and Prop Creator that reuses the same VoiceProfile authority. Timeline `@Korri` resolves that profile for new dialogue. No second voice tag, no second profile table, no requirement to finish Performance / Environment / Dialogue / Takes first.

### Classify (walked, then connected)

| Surface | Class | Notes |
|---|---|---|
| Voice Identity approval → `active_voice_profile_id` | **EXISTS** | Same contract as J25/J26 |
| Timeline `voice_bind` | **EXISTS** | Character binding → active approved VoiceProfile → asset |
| Co-Director Express nav | Was **MISSING** | `CONTENT_NAV` jumped Character Creator → Prop Creator |
| Voice Creator Express UI | Was **MISSING** | Needed a thin reuse of `VoiceIdentityPanel`, not a second system |
| `open_voice_creator` | Was **DISCONNECTED** | Navigated to Voice Studio (`workspaceUrl=voicestudio`) |
| Approval copy | Was **DISCONNECTED** | “owns this approved voice” / `{name} Voice` instead of default-voice language |
| No-approved-voice honesty | Was **MISSING** | Anadriya had no empty-state offer |
| Co-Director “give X a voice” | Was **DISCONNECTED** | `create … voice` mapped to `voice.generate` (segments) |
| Timed Prompt missing-voice offer | Was **MISSING** | Compile tracked `missing`; UI did not offer Voice Creator |

### What was reconnected (not rebuilt)

- `VoiceCreatorPanel` renders `VoiceIdentityPanel variant="express"`.
- Approval still calls `api.approveCharacterVoiceCandidate`.
- `open_voice_creator` stays in Co-Director (`contentTab=voice_creator`) and dispatches `adept:open-voice-creator`.
- `voice.creator` / `voice.inspect` capability patterns sit **before** `voice.generate`.
- Timed Prompt gap notice uses project `voice/approved-status` and opens Voice Creator.

### Live proving ground — Korri Anadriya

| Step | Result |
|---|---|
| Co-Director tabs | Character Creator → **Voice Creator** (selected) → Prop Creator |
| Select Korri | Banner **Approved Voice — Korri Clone** / Default voice across Adept UI |
| Play | `<audio>` `33a80b24` playing `currentTime=0.34s` / `duration=5.04s`; HTTP **200** `audio/wav` 241964 bytes |
| Leave without changing | `active_voice_profile_id` still `283e8cf8` / preview `33a80b24` |
| Use Existing surface | Inventory includes **Korri Clone (approved)**. Re-approve of the locked profile is **409** by design. |
| Anadriya | **No approved default voice** / `Anadriya doesn't have an approved default voice yet.` Not invented. |
| Timeline new line | `Korri says, "You won't take me alive if you try any soap sniping on me."` |
| H3 compile | Applied Korri `283e8cf8` / `33a80b24` as `<Audio 1>`; `missing: ["Anadriya"]` |
| Intents | Give/create/clone → `voice.creator`; “what voice does Korri have?” → `voice.inspect` |

Proof artifact: `.runtime/j27_voice_creator_proof.json`.

### Remaining generator-specific limits

| Generator | Voice compile |
|---|---|
| MiniMax H3 R2V | **Supported** — `ref_audios` / `<Audio j>` from the approved VoiceProfile |
| LTX 2.5 / WAN / Hunyuan / Seedance / Kling / Veo | **Honest no-audio-reference** — `generator_has_no_audio_reference`; do not invent TTS |

### Remaining consumers (audit)

Reconnects in this journey: Co-Director Express, Voice Identity approval copy, `open_voice_creator`, Timed Prompt gap notice, classify intents. Already on the same authority: Timeline `voice_bind`, Voice Performance / Environment (J26), Co-Director `voice.generate` (approved Qwen only), `speech_compile` via `active_voice_profile_id`.

Still later-stage / not default-identity:

- Voice Performance takes refine HOW, not WHO.
- Lip Sync still prefers an explicit clip when present.
- Kokoro remains a listed provider, never a silent substitute (`allow_kokoro_fallback=False` on character speech).
- A stale Co-Director Agent Work Surface (`JOB_NOT_FOUND` / Timeline generation Failed) can paint over Express panes. Voice Creator itself loaded and played underneath. Not claimed closed here.

**Journey.** **GO** — Voice Creator is Express reuse of Voice Identity. Approval is the character default. Korri’s clone is used for new Timeline dialogue. Anadriya stays honestly voiceless.

---

## J28 — Voice Studio character switch (Choose Another Character)

**Intent.** Choose Another Character → Anadriya must make Anadriya the canonical Voice Studio character. Korri’s approved VoiceProfile must not pull the workspace back to Korri. Anadriya stays honestly without a default voice.

### Root cause

Choose Another Character only cleared local `selectedCharacterId`. A hydrate effect then ran:

`preferred = URL characterId || sessionStorage adept_selected_character`  
`setSelectedCharacterId(current => current || preferred)`

Empty current therefore restored Korri. The one-frame Anadriya flicker was the chooser gallery, then Korri remounted. This was not a VoiceProfile fallback and was not a missing Anadriya GET.

### Authorities

| Before | Role |
|---|---|
| URL `characterId` | Won — still Korri after Choose Another |
| `sessionStorage adept_selected_character` | Won — still Korri; never cleared |
| Hydrate `current \|\| preferred` | Overwrote the picker |
| Local `selectedCharacterId` | Lost |
| VoiceIdentity in-panel Select Character | Second authority in Standard (hidden after this repair) |

**After.** URL `?workspace=voicestudio&characterId=` is the only active-character identity. Missing `characterId` is the chooser. Session is write-through after a real selection, and is cleared when the chooser opens. Unknown URL ids do not fall back to Korri.

### Repair

- `voiceStudioCharacter.ts` resolves the active id from the URL only.
- Choose Another Character deletes `characterId` and clears the remembered session key.
- Opening a character writes that id into the URL (`replace`) and session.
- `VoiceStudioWorkspace` is keyed by character id; in-flight GETs apply only when `requestedId === currentId`.
- Standard Voice Identity no longer has a competing character dropdown. Express Voice Creator still does, and lifts the change to `VoiceCreatorPanel`.
- Co-Director chips use the active character name. Korri’s sample dialogue is no longer the blank-state default for every character.

### Live proof — Korri Anadriya

| Step | Result |
|---|---|
| Start Korri | Header Korri · Approved voice: Korri Clone · profile `283e8cf8` |
| Choose Another → Anadriya | Sequence Korri → chooser → Anadriya. **snappedToKorri: false** |
| Anadriya Identity | **No approved default voice** / `Anadriya doesn't have an approved default voice yet.` |
| Async settle + 3s watch | Still Anadriya. URL `characterId=4c1c0bc8-…` |
| Reload Anadriya | Still Anadriya. Later stages locked (no identity). |
| Choose Another → Korri | Korri + Korri Clone banner. Empty-state gone after settle. |
| Reload Korri | Still Korri + approved clone. |
| Rapid Korri → Anadriya → Korri → Anadriya | Names `Anadriya, Korri, Anadriya`. No stale overwrite. |
| Direct nav each `characterId` | Each URL opens that character only. |
| VoiceProfile ownership | Korri still `283e8cf8` / Korri Clone. Anadriya `hasApproved=false`. |
| Co-Director chips on Anadriya | `Make Anadriya more sarcastic` — no Korri chip. |

Proof artifact: `.runtime/j28_voice_studio_character_switch_proof.json`.

**Journey.** **GO** — Choose Another Character changes the canonical Voice Studio character. Approved voice state belongs only to its owner. Async responses cannot snap the UI back to a previous character.

---

## J29 — Audio Studio production surface (this session)

**Intent.** Rebuild Audio Studio from the early-form four-tab layout into one compact production surface: Music, Sound Effects, Ambience, and Project Audio. A stranger should see kind → sound → length → source → Generate → Audition → Approve → Timeline/Library. One project, one Library. No fake audio. No silent engine or CPU fallback.

### Before-state classification

| Surface | Class | Notes |
|---|---|---|
| Tabs Music / SFX / Ambience / Project Audio | EXISTS | Early UX was **STALE**; rebuilt |
| Generate / poll / cancel / select / approve APIs | EXISTS | `/api/audio-studio/projects/{id}/…` |
| Workspace hydrate | EXISTS | `GET …/workspace` |
| Timeline place | EXISTS / was **DISCONNECTED** | `audioStudioPlace` + mix existed; product Timeline is director `audio_clips` / `sfx_clips`, not `putEditor` |
| Candidate Library fallback | **STALE** | Removed — leftover Library rows are not invented takes |
| Advanced / Prompt Intelligence on Music | **STALE** | Removed from default chrome |
| Co-Director phrase routing | was **DISCONNECTED** | Speech-act + unified intent now map music / SFX / ambience / open |
| Co-Director `audio.open_studio` → workspace | was **DISCONNECTED** | Tool succeeded; UI stayed on Timeline until `workspaceUrl` navigate |

### Preserved

Generate / poll / cancel / select / approve contracts. ACE-Step (music) and MMAudio (SFX + ambience). Workspace hydrate. Canonical Library keys `audio.music` / `audio.sfx` / `audio.ambience`. `audioStudioPlace` mix record. Co-Director tool ids `audio.open_studio` / generate / preview / select / approve / place.

### Rebuilt

`studio-web/src/components/audio-studio/*` — one workspace, four consistent panels, playable `AudioRow` (one-at-a-time), Select / Approve / Add to Timeline. Creator source chips: **Music Engine** / **Sound Engine**, kind-specific readiness. Generate disabled when the source is down or the brief is empty. Timeline handoff writes Scene 1 director clips (SFX → `sfx_clips`; music and ambience → `audio_clips`). Co-Director opens `?workspace=audiostudio&audioTab=`.

### Generator / provider inventory (live GPU)

| Kind | Engine | Creator name | Class | Ready | Notes |
|---|---|---|---|---|---|
| Music | ACE-Step | Music Engine | EXISTS | yes | CUDA RTX 5090, torch `2.11.0+cu128`, `data/m210b-ace-venv` |
| SFX | MMAudio | Sound Engine | EXISTS | yes | `data/m210b-sfx-venv` |
| Ambience | MMAudio | Sound Engine | EXISTS | yes | same runtime as SFX — honest, not forced onto ACE-Step |
| kie.ai | hosted | — | EXISTS / Uncertified | available | no silent switch |
| wavespeed.ai / fal.ai | hosted | — | Unavailable | no | shown honestly |
| CPU | — | — | blocked | — | `allowCpuFallback` default false |

Backend clamps: music/ambience 4–20s; SFX 1–12s. UI offers 1–3 takes (default 1).

### Live proof — Korri Anadriya

All three generations were real GPU jobs (`fixture: false`, `cpuFallbackUsed: false`).

| Path | Batch | Asset | Engine | Latency | Library | Audition | Approve |
|---|---|---|---|---|---|---|---|
| SFX | `21539af8` | `003efc2e` | MMAudio | ~45s (3s clip) | `audio.sfx` | play → pause | yes |
| Ambience | `2af5f795` | `26a2005b` | MMAudio | ~30s (8s clip, warm) | `audio.ambience` | play through | yes |
| Music | `0938d9fb` | `57a5bb2f` | ACE-Step | ~40s (8s clip) | `audio.music` | play ~8s | yes — persists after reload (`897aa5ff`) |

**Project Audio.** Canonical Library shelf (voice-heavy, not a second DB). Filters All / Music / SFX / Ambience / Voice. Search `sfx_gen` isolated the generated SFX; play worked.

**Timeline.** After replacing the legacy `putEditor` path: Scene 1 director has `audio_clips` music_gen + ambience_gen and `sfx_clips` sfx_gen. Timeline canvas showed `track-clip-audio-*` and `track-clip-sfx-*` after reload. Clip chrome labels are generic “Audio” / “SFX” (existing Timeline UI). Placement lengths were 5s because Library rows lacked `durationSec`; real files are 8 / 8 / 3. `addToTimeline` now probes file metadata.

**Co-Director.** Classify: orchestral cue → `audio.music`; metallic door slam → `audio.sfx`; spaceship corridor ambience → `audio.ambience`; approved corridor on Scene 2 → `audio.open`; visual corridor still stays `image.generate`. Live “Open Audio Studio” called `audio.open_studio` and, after the navigate repair, landed on `?workspace=audiostudio&audioTab=music`. Tabs then reached `audioTab=sfx` and `audioTab=library`. Generate phrases were not sent in chat (curated tools can start ACE-Step / MMAudio).

Proof artifact: `.runtime/j29_audio_studio_proof.json`. Frontend tests **14 passed**. Speech-act tests **7 passed**.

**Journey.** **GO** — Audio Studio is a wired production surface on this project. FSC overall remains **NO-GO**.

---

# Remaining (ordered)

1. **Finish J11 Home.** Soak is 40/40 **200**. Still need first-paint Checking vs a real outage, `/api/runtime-manager/status` ~10s, and stale `localStorage` recents. Do not swallow console errors.
2. Korri’s approved **clone** (`283e8cf8` / Sample 3) now holds through Voice Studio stages. **Anadriya still needs an owner-approved voice** before dual-character H3 `<Audio j>` can be live-proven. Do not invent or import Schnick audio.
3. H3 photoreal place lock while keeping illustrated identity is still imperfect (Take N restyled the corridor). Modest wardrobe/camera micro-shift at the 8s cut remains.
4. Continuity last-frame quality is polluted by Batch 1 Ingredients leak — do not regenerate Approved Batch 1.
5. Adapter leaf `minimax-h3-t2v-local` is naming debt, not silent T2V.
6. Video-generator readiness Seedance E2E (P4) remains an older **NO-GO**.
7. Dual-runtime logon task (P17–P19) remains **E2E BLOCKED** pending elevation / reboot proof.

---

# Runtime stamp

```text
CREATOR UI:  http://127.0.0.1:5173/
STUDIO API:  http://127.0.0.1:8758/   healthz 200  PID 57540
COMFY BEFORE: PID 77152 / health 200
COMFY AFTER:  PID 77152 / health 200
COMFY RESTARTED?: NO
WHY?: J29 UI + API-only recycle earlier; this closeout is frontend/HMR. Comfy leave-alone.
MINIMAX :8192: offline — not started
```

---

# Verdict

```text
NO-GO — ADEPT UI FULL STACK CONVERGENCE NOT COMPLETE
```

J1–J6, J8, J12, J13, J14, **J15**, **J16**, **J17**, **J18**, **J19**, **J20**, **J21**, **J22** (leftovers closed), **J24**, **J25**, **J26**, **J27**, **J28**, and **J29** hold in the running product. **J23 Preview UX is retired** by J24. J7/J10 hold with disclosed LTX 2.5 one-cond limits. J9 holds on the existing Approved take. **J20 Batch 3 + Re-Take + Right Drawer still hold**. Korri’s approved clone is the default voice through Voice Creator, Voice Studio Identity, and Timeline H3 `<Audio j>`; Anadriya still has none. Audio Studio now generates, auditions, approves, and places music / SFX / ambience on this project’s Library and Timeline. J11 Home soak is clean of 400/502 and is **not closed**. Continue — do not wait for a new prompt.
