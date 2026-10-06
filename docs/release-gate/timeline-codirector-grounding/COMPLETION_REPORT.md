# Timeline + Co-Director Live Grounding + Runtime Truth — Journey Closure

**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scenes:** Scene 1 · Venture Corridor Dialogue `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` · Venture Corridor Walk `b5282a4c-07eb-40db-9d5b-1512eac74dca`  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651`  
**Date:** 2026-09-03 / 2026-09-04  
**Peer review:** [Peer review closure](7daa8126-0615-4d4a-83a2-13074a312fb0)

## Verdict

**NO-GO — TIMELINE + CO-DIRECTOR CONVERGENCE INCOMPLETE**

The previous pass’s process blockers are closed. The repaired snapshot, Prompt Names, Lip Sync speaker, hosted-readiness join, and logical runtime IDs are live on the recycled Studio API worker and were walked in the creator UI. Production-critical residuals remain; they are a **narrow next boundary**, not a new investigation.

`COMFY BEFORE:` PID **74356** · healthy / `ready`  
`COMFY AFTER:` PID **74356** · healthy / `ready`  
`COMFY RESTARTED?:` **NO**  
`WHY?:` Ordinary API recycle through the Runtime Supervisor (`POST /restart-api`). Comfy was observed only.

## Before state (inherited NO-GO)

Studio API was running without reload. Background Services manager `:8759` was down. Vite had not consumed the repaired Generate / snapshot path. Playwright, live Co-Director HTTP, Runtime Supervisor recovery, Comfy MCP, and peer review were open.

Walk Prompt Names had been compiled in source but not proven in the Timed Prompt Inspector. ContinuityBridge and fal/Seedance dual labels were unrepaired.

## Repairs inherited from previous pass

1. ACTIVE TIMELINE SCENE SNAPSHOT (`active_timeline_scene_snapshot.py`).
2. Prompt Name compile (`prompt_token_bindings.py`) — Walk bound to Korri `16ce0150-…` / Anadriya `b034058d-…` / ERS `03d25ea2-…`.
3. Lip Sync accepts clip/track `character_id`; director load attaches `lipsync_tracks_json`.
4. Production snapshot no longer invents `scenes[0]`.
5. Header Generate disabled when executable is false (then tightened this pass).
6. Lineage *reads* `generationMode` / `adapterKind` when present (write path still incomplete — see residuals).

## Remaining repairs this closure

| Repair | Why |
|---|---|
| Logical IDs `runtime.comfy` + `runtime.video` on `logicalServices` | Freeze supervisor contract; SERVICE ≠ GPU residency |
| Startup gauge prefers those IDs | Creator Engine / Video Runtime no longer *only* port blobs |
| Hosted missing credentials → **Requires Setup** (not Provider Not Configured) | One hosted-provider authority; REQUIRES SETUP wins |
| Hosted join: Ready cannot keep `Unavailable` / `Requires Setup` | Closes Seedance dual-label |
| `_APPROVAL_Q` vs `_PRODUCTION_STATUS_Q` | Timeline batch approval ≠ scene lifecycle |
| Generate `executable === true` on header, toolbar, and Inspector | Missing option is not treated as ready |
| Playwright `korri-timeline-codirector-closure.spec.ts` | Live modal/Inspector IDs, snapshot Qs, Dialogue 3/0, reload |

## Runtime state (live)

| Service | Fact |
|---|---|
| Supervisor | PID **36572** owned · `:8759` |
| Studio API | **76148 → 62552** via `POST /restart-api` · `/api/healthz` 200 |
| Comfy `:8188` | PID **74356** owned · `runtime.comfy` **ONLINE** / **RESIDENT** |
| Route A `:8192` | Not running · `runtime.video` **ON_DEMAND** / **FREE** |
| Ollama | PID **28160** owned · `runtime.local_llm` running |
| Vite | `http://127.0.0.1:5173/` 200 |

Logical snapshot after API recycle:

```text
runtime.comfy   ONLINE / RESIDENT / pid 74356 / no port on the logical row
runtime.video   ON_DEMAND / FREE / not running / no port on the logical row
runtime.local_llm  running / pid 28160
```

**MiniMax architecture preserved:** Timeline H3 Reference-to-Video = canonical Comfy `:8188`. Isolated Route A = `:8192` on-demand + `/free` GPU handoff. Not collapsed.

**Recovery proof (CLOSURE 16):** Supervisor detected API recycle request → new healthy PID 62552 → generator Ready still truthful → Timeline usable. No PowerShell. No Comfy restart.

## Live creator evidence (primary walk at `:5173`)

Korri Anadriya → Production → Timeline → Walk `b5282a4c-…`.

**Timed Prompt Inspector (0.0s clip):**

| Prompt Name | Reference | Binding ID |
|---|---|---|
| Korri | `@Korri` | `16ce0150-ba8b-4b85-8bbd-0af56902b737` |
| Anadriya | `@Anadriya` | `b034058d-0014-4f1c-877d-5fa0c4458d9c` |
| Venture-Corridor-scene | `#VentureCorridorScene` | `03d25ea2-ae81-434b-8364-3913f1b52dec` |

Bindings survived Playwright reload. Not decorative. Not alias-only.

**Co-Director from Timeline** (`project_id` + `scene_id` + `workspace=timeline`; no `no_project`):

| Question | Authority | Live answer |
|---|---|---|
| What scene am I working on? | Active Timeline Scene Snapshot | We are working on **Venture Corridor Walk**. |
| Who is referenced in this shot? | Prompt Name IDs | **Korri and Anadriya** |
| What environment is assigned? | Prompt Name ERS | **Venture-Corridor-scene** |
| What generator is this scene using? | `sceneGeneratorId` | **minimax-h3** |
| How many Timeline batches are approved? (Walk) | `approvedClip` | **0 Approved / 1 Draft** |
| How many Timeline batches are approved? (Dialogue) | `approvedClip` | **3 Approved / 0 Draft** |
| What is the production status of this scene? | lifecycle slice | **not recorded** · project **BLOCKED** at **STORY** · *not* batch approval |

Unbound `GET /api/codirector/session-context` remains `no_project` (intentional). Bound GET with IDs is `bound`.

**Lip Sync:** Walk tracks have `character_id` for Korri and Anadriya. Live preflight `ok: true`, no `LIPSYNC_SPEAKER_REQUIRED`.

**Generator UI:** Dock **MiniMax H3 — Local · 8s · Ready**. Generate Draft visible. `runtime.comfy` ONLINE is the executable path (Comfy R2V), not Route A residency.

**ContinuityBridge (Dialogue batch 0 → 1):**

| Field | Live value |
|---|---|
| `lastFrameAssetId` | `c7bed656faf04cb08e99aac0029bc403` |
| tag | **`continuity_last_frame`** |
| file | `cbr_0610f94d0f5a_last.png` |
| source video | `5a2e74b3-8834-45b3-ba93-901af9120ef2` · tag `minimax-h3` · `scene_1_cc5a0a7b.mp4` |
| strategy | `prompt_context` |

That last frame is an extracted predecessor output, not a CRS. H3 R2V then slots it as `prior_frame` / “Previous take” while start image stays environment/identity. `none` = no strategy. `Superseded` = replaced after a retake. JEPA remains advisory.

## Playwright evidence

```text
npm run test:e2e:beta -- tests/e2e/timeline/korri-timeline-codirector-closure.spec.ts --project=chromium
ok 1 Walk bindings, snapshot questions, Dialogue approval, reload (18.4s)
1 passed
```

Against live `:5173` / `:8758`. Covers Dialogue/Walk load, scene switch, Co-Director context, Prompt Name Inspector IDs, modal/Inspector agreement, generator Ready vs Generate, Timeline approval, Lip Sync preflight, reload persistence, no `no_project` when bound.

## Comfy MCP evidence

`docs/release-gate/timeline-codirector-grounding/COMFY_MCP.json`  
Transport: stdio `comfy-mcp` → **`http://127.0.0.1:8188`**. Tools listed: 39. **Did not** call `launch/stop/restart_comfyui`.

Live nodes: `LoadImage`, `UNETLoader` (includes `minimax_h3_ref2va_pruned_int8_convrot.safetensors`), `CLIPLoader` (`minimax` type), `VAELoader` (`minimax_h3_video_vae_fp16.safetensors`), **`MiniMaxH3ReferenceToVideo`** (ref_images / Reference-to-Video conditioning). GPU: RTX 5090. Comfy argv uses Adept `extra_model_paths.yaml`.

## Unit / smoke

- **43 passed** — prior 20 + ollama fabric + generator authority + snapshot/approval + logical IDs.
- Vitest `startupSnapshot.test.ts` **8 passed**.
- `test_revision_d_smoke.py` **3 failed, 1 passed** — stale Revision D catalog flags (`select`, `vggt_1b_commercial`, `moge2_geometry`). **Not introduced by this closure.** Not used as this journey’s smoke.

Live smoke substitute: `:5173` 200, `:8758/api/healthz` 200, `:8188/system_stats` 200, supervisor status ready.

## Peer-review findings (resolved or blocked)

Independent review: [Peer review closure](7daa8126-0615-4d4a-83a2-13074a312fb0). Reviewers do not vote.

| Finding | Primary resolution |
|---|---|
| Inspector Generate ungated | **Repaired** — `executable === true` on Inspector + toolbar + header |
| Missing generator treated as executable | **Repaired** — `=== true` |
| Playwright generate testid / skipped preflight | **Repaired** — spec passed |
| Live worker / MCP unverified | **Closed this pass** — API recycled; MCP JSON captured |
| Approval vs lifecycle regex | **Closed** on deterministic path; live answers distinct |
| `:8188` vs `:8192` | **Keep separate** — RECLASSIFIED, not collapsed |
| Continuity last frame vs CRS | **Extract path closed**; strategy name `prompt_context` is H3 R2V, not CRS |
| Shot = all segments / playhead unused | **Open** — acceptable on current Walk/Dialogue (same refs); not closed for multi-shot |
| Lineage `adapterKind` never written | **Open** — previous claim overstated |
| Hosted Seedance Ready from credentials | **Partial** — dual Ready vs Requires Setup closed; certified-BLOCKED not added |
| Startup still has port fallbacks | **Partial** — logical IDs exist and are preferred; fallbacks remain |
| Co-Director Timeline mutation | **Open** — Q&A + read-back proven; no disposable mutation this pass |

## Grok closure matrix

| Issue | Original Finding | Root Cause | Repair | Live Evidence | Final State |
|---|---|---|---|---|---|
| TL-01 | MiniMax Ready vs Runtime Offline | Two MiniMax paths: `:8188` R2V vs `:8192` Route A | Logical IDs; gauge ON_DEMAND for video | `runtime.comfy` ONLINE; `runtime.video` ON_DEMAND | **RECLASSIFIED** then **CLOSED** as two products |
| TL-02 | Generate while Route A down | Header ignored `executable`; Timeline H3 does not need Route A | Generate gated on `executable === true` | H3 Ready + Generate Draft; Route A down | **CLOSED** |
| TL-04 | Who is referenced? | Cast, not Prompt Name IDs | Snapshot + compile | “Korri and Anadriya” | **CLOSED** |
| TL-05 | What environment? | Missing shot env | Snapshot environment | Venture-Corridor-scene | **CLOSED** |
| TL-06 | `no_project` | Unbound GET; UI already posts IDs | Proven live bind | Bound GET + Playwright `data-project-id` | **CLOSED** |
| TL-07 | Decorative `@`/`#` | Tokens ≠ IDs | Compiler + persist | Inspector IDs + reload | **CLOSED** |
| TL-08 | `minimax-h3-t2v-local` + start image | Historical adapter id; execution is R2V | Facts use `:8188` R2V; lineage write incomplete | MCP MiniMaxH3ReferenceToVideo; lineage fields still unread from H3 submit | **PARTIALLY CLOSED** |
| TL-09 | False `LIPSYNC_SPEAKER_REQUIRED` | Required `speaker_binding_id` | Accept `character_id` | Preflight ok, code absent | **CLOSED** |
| TL-10 | 3 Draft / 0 Approved | Scene lifecycle vs `approvedClip` | Two question classes | Dialogue 3/0; Walk 0/1; production BLOCKED/STORY | **RECLASSIFIED** then **CLOSED** on deterministic path |
| TL-11 | missing optional refs | Walk `missing_end_frame` + lipsync | Not a false speaker | Preflight ok; end-frame still Walk planning | **PARTIALLY CLOSED** |
| TL-12 | ContinuityBridge field exists | H3 last-frame → `prompt_context` + `prior_frame` | No extract-path repair needed | `continuity_last_frame` from approved H3 mp4 | **RECLASSIFIED** |
| TL-13 | MiniMax 8 seconds | Capability max 8s | None required | Dock 8s · Ready | **CLOSED** |
| TL-14 | Seedance Ready vs Requires Setup | Discovery vs readiness | One derive + join; REQUIRES SETUP wins | Unit: missing key → both Requires Setup | **PARTIALLY CLOSED** |
| TL-15 | Port-centric readiness | Feature pages probe ports | Logical IDs published; some fallbacks remain | `/api/runtime-manager/status` has three IDs | **PARTIALLY CLOSED** |

## Regressions

Not re-run this pass as a full pack: Creator UI, Text to Video, Scene Creator handoff, Library, Co-Director outside Timeline, startup modal cold-start, automatic supervisor boot.

Observed non-regression: Vite Timeline still loads; Comfy PID unchanged; Ollama still owned; Dialogue approved clips untouched.

**Visible leftover stale chrome (not repaired):** scene list still prints legacy `scene.engine` (`WAN · 24s`, `LTX · 8s`) while the Video Generator dock and master `sceneGeneratorId` are **minimax-h3**. That is a second authority on the same page.

## Unresolved / next closure boundary

Do **not** restart the investigation. Close only:

1. **Scene-list generator authority** — show Timeline `sceneGeneratorId` / readiness, not leftover `scene.engine`.
2. **Safe Co-Director Timeline mutation** on disposable Walk/Draft state (not approved Dialogue) — action routed, state read back, no false success.
3. **Lineage write** — H3 submit must persist `generationMode` / `adapterKind` if that claim stays in the product story.
4. **Optional:** playhead-scoped shot refs; drop remaining gauge port fallbacks once all consumers read `logicalServices`.

Route A remains supervisor-owned ON_DEMAND. Do not move it into `:8188`. Do not live-generate Route A merely to tidy the matrix.

## Primary double-check

| Question | Answer |
|---|---|
| Is the information correct? | Yes for Walk/Dialogue snapshot, Prompt Names, Lip Sync, Dialogue 3 Approved, Walk Draft, H3 Ready. Scene-list engine labels are **not** correct. |
| Is it coming from the correct authority? | Snapshot / master / Prompt Name IDs / `approvedClip` / `runtime.comfy`. Scene chips still use `scene.engine`. |
| Is the executable path real? | Yes — Adept Comfy `:8188` R2V (MCP + weights). Route A is a different ON_DEMAND service. |
| Does state survive reload? | Yes — Playwright + Inspector IDs after reload. |
| Can Co-Director understand and safely act? | **Understand: yes.** **Act (mutate Timeline): not proven.** |
| Free of feature-owned lifecycle? | Supervisor owns Comfy / API / Ollama / Route A start. Logical IDs exist. Some feature readiness still joins capability facts. |

## Test gate

| Gate | Result |
|---|---|
| Existing + new unit | **43 passed** |
| Startup snapshot unit | **8 passed** |
| Live smoke (health/UI/Comfy) | **PASS** |
| Revision D smoke file | **FAIL (pre-existing / stale)** |
| Playwright closure spec | **1 passed** |
| Live browser walk | **PASS** |
| Co-Director live request | **PASS** |
| Prompt Name persistence | **PASS** |
| Lip Sync | **PASS** |
| Runtime authority (IDs live) | **PASS** |
| Safe recovery (API recycle) | **PASS** |
| Comfy MCP | **PASS** |
| Peer review | **Returned findings; primary resolved or listed** |
| Double-check | **PASS with residuals** |
| Full regression pack | **NOT RUN** |
| Co-Director Timeline mutation | **NOT RUN** |

## URLs

- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/`
- Walk: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`
