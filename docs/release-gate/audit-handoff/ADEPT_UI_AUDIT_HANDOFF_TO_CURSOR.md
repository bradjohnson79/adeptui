# ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR

**Kind:** governing Cursor repair plan (one document for this audit cell).  
**Date ingested:** 2026-09-02 PT  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**This file is not a substitute for the three full auditor reports.**

Grok audit cell declaration: Chief Code Bot, Voice / Audio Audit Bot, and Setup / Source Audit Bot made **no** production code changes, commits, model installs, or Task Scheduler writes during the audit cell.

Cursor has since closed a subset of P1 grounding items. Status below is current as of this ingest, not as of the Grok snapshot.

## Source reports (authoritative evidence)

| Cell | Report |
|---|---|
| Co-Director | Chief Code Bot chat report 2026-09-02 (AUDIT PARTIAL) |
| Voice + Audio | `C:\Users\bradj\theme_walk\voice_audio_audit\AUDIT_COMPLETE_VOICE_AUDIO.md` |
| Setup + Source | `C:\Users\bradj\theme_walk\setup_source_audit\AUDIT_REPORT.md` |

**Merge rule:** symptoms are not combined unless a common root cause was proven by evidence.

## Auditor live snapshot (Grok cell — do not treat as current PIDs)

| Surface | Grok 2026-09-02 |
|---|---|
| UI `:5173` | PID 56720 |
| Studio API `:8758` | PID 51004 |
| Comfy `:8188` | PID 77152 |

Later Cursor API recycle left Comfy PID `77152` unchanged. Re-observe PIDs at the start of every mission. Do not restart `:8188` for ordinary repairs.

## What must not be merged

- **Voice assignment is not broken.** Voice/Audio proved Korri / Anadriya clones match UI + API (`283e8cf8`, `5c221441`, both APPROVED qwen3-tts). Co-Director failing to name them was a context-injection defect (H-P1-01/02), not a Voice Studio rewrite.
- **Comfy process ownership is not the H3 filename P0.** `:8188` PID 77152 owned/listening. H-P0-01 is graph identity, not supervisor spawn.
- **MiniMax `:8192` Runtime Offline is honest** (Setup SW-12). Do not treat it as the same Ready-lie as WAN `path=null`.
- **Layout Focus modes are not routing.** Do not “fix routing” by restyling the split.

## Passed (do not regress)

- Co-Director: complete still prompt executes (0 questions); live Library attach vision; send does not restart API/Comfy.
- Voice: Qwen3 real speech; compiler event fidelity; MMAudio warm ~1.5s; two diverse takes; centered Audio Studio; voice IDs persist after gens.
- Setup: MiniMax `:8192` honestly offline; `:8188` owned pid matches runtime-manager; fal/kie keys present (secrets not printed).

## Cursor status since the audit cell

| ID | Auditor severity | Cursor status | Evidence |
|---|---|---|---|
| H-P1-01 | P1 | **CLOSED — GO** | `docs/release-gate/codirector-grounding/CODIRECTOR_PROJECT_GROUNDING_ENTITY_RESOLUTION_REPORT.md` |
| H-P1-02 | P1 | **CLOSED — GO** | Same report. Live stream named Anadriya + Korri and Korri Clone / Anadriya Clone (qwen3-tts). Did **not** rewrite Voice Studio assignments. |
| H-P1-03 | P1 | **CLOSED — GO** | Same report. `@Korri` + `@Anadriya` both resolve to CRS; `requestedModelId=""`. No paid job this repair. |
| H-P0-01 | P0 | **CLOSED — GO** | Live job `e4ffc62d` (2026-09-02 21:33:51, done) bound `studio/{assetId}.wav` for Korri `33a80b24` and Anadriya `e3a305b6`. Historical fail `d562d5e2` still shows the old label collision. Dry stage+graph on those same live assets reused UUID names. 44 unit tests including `test_h3_loadaudio_binds_staged_asset_id_not_label`. No new H3 GPU job. |
| H-P1-04 | P1 | **CLOSED — GO** | UNLOCKED + leftover `gptimage2` now `step=auto_local` `qwen-image-2512-local`. Explicit “use GPT Image 2” / “with fal.ai” stay `step=exact` hosted. Tests in `test_codirector_image_route_fallback.py`. Live inspect after API recycle PID 45224; Comfy 77152 unchanged. No paid job this repair. |
| H-P1-09 | P1 | **PARTIAL** | Ready gate refuses URL/null paths. Live: Comfy path is ComfyUI-Shared (not `:8188`); WAN path is the high-noise file. `character_multiview_engine` no longer Ready with `path=null`. Source Manager `sources=[]` vs Setup paths is still open. |
| H-P1-10 | P1 | **CLOSED — GO** | `/api/health` is liveness: `comfy_probed=false`, `comfy_reachable=false`, `comfy_status=not_probed`. `/api/comfy/health` is the Comfy function: reachable ready 0.32.0. UI hook merges `comfyHealth` for the badge. |
| H-P1-11 | P1 | **CLOSED — GO** | runtime-manager `gpu` now uses `nvidia-smi` (`detected=true`, RTX 5090, 32607 MiB). No longer hardcoded `detected=false`. |
| H-P1-12 | P1 | **CLOSED — GO** | `windowsStartupPresent=true`, `legacyOwners=['AdeptBetaBackendManager']`, canonical `AdeptRuntimeService` still `taskRegistered=false`. UI no longer says “unregistered” when the older task exists. |
| H-P1-13 | P1 | **PARTIAL** | HF CLI is Ready only when `online_verified=true` (live now true). `model_roots` labels portable vs machine-specific (live: 1 portable, 2 machine). D: / Comfy-Desktop paths are disclosed, not rewritten. |
| H-P1-05 | P1 | **CLOSED — GO** | Qwen clone has no instruct API. `generate-dialogue` with `emotional_direction=whisper` on Korri Clone `283e8cf8` now returns **400 STYLE_UNSUPPORTED** instead of identical WAV bytes. DESIGN still forwards style as `performance_instruct`. Tests in `test_voice_performance_qwen_bridge.py`. No clone GPU job. |
| H-P1-06 | P1 | **CLOSED — GO** | Approve of auditor take `32c9339f` / `84946a4a` now returns `ingested=true`, `approvedAssetInLibrary=true`, `approvalState=approved`, durable path `projects/…/assets/sfx_generate_86b9fa9265.wav` (not m210b-sandbox). Workspace `libraryCount=115` lists it; file GET 200 RIFF. Tests in `test_m42_w45_audio_studio.py`. |
| H-P1-07 | P1 | **CLOSED — GO** | Live ACE-Step `ready (CUDA: RTX 5090)` `mode=local`. Music badge is **Music Engine**, not unavailable. After prompt fill, **Generate 1 Track** is enabled. No music GPU job. Screenshot `artifacts/audit-handoff/mission4-hp107-music-ready.png`. |
| H-P1-08 … H-P3-05 remaining | as listed | **OPEN** | Next: Mission 5 handlers + P2 (H-P1-08, H-P2-01…04). |

## Recommended Cursor repair missions (order)

Do not collapse missions. Do not “optimize” Voice warmup times from this handoff.

### Mission 1 — Durable media identity — H-P0-01

H3 LoadAudio must key on durable `Asset.id`, not uploaded basename / colliding `studio/<label>.wav`. Bind miss → `H3_REF2V_VOICE_MISSING`.

Re-verify the Re-Take staging path on a real voice-bound H3 submit. If label collision is gone, certify and move on. If any remaining submit still uses display names, repair only that boundary.

Do not restart or re-own Comfy `:8188`.

### Mission 2 — Co-Director session grounding — H-P1-01, H-P1-02, then H-P1-03, then H-P1-04

| Step | ID | Status | Cursor mission |
|---|---|---|---|
| 2a | H-P1-01 | **DONE** | Bind `activeSceneId` + character/voice IDs into every project-bound turn. |
| 2b | H-P1-02 | **DONE** | Inject `character_profiles` + `voice_profiles`. Do not “fix” Voice Studio. |
| 2c | H-P1-03 | **DONE** | Resolve `@` tags to CRS IDs before image route. Never parse leftover tokens as model ids. |
| 2d | H-P1-04 | **DONE** | UNLOCKED AUTO = Production Control local-first. fal only on explicit preference. Auditor: `plan_image_route` `step=exact` selected `gpt-image-2-fal` while Comfy `:8188` listening and `/api/comfy/health` ready. Jobs `3d8deaa1`, `210935fa`. |

Mission 2a–2c unblocks Voice VA-P1-02 `timeline.add_audio`. Mission 2d is the next Co-Director execution-path repair.

### Mission 3 — One Ready contract + honesty — H-P1-09 … H-P1-13

| ID | Title | Boundary |
|---|---|---|
| H-P1-09 | Multiple Ready contracts | installed / files / running / owned / executable. Never Ready with null/URL path. SM vs Setup one assignment authority. |
| H-P1-10 | Comfy health split-brain | `/health` `comfy_reachable=true` vs nested `comfy.reachable=false`. `/api/comfy/health` ready. `status/latest` offline. Co-Director chip Checking→Blocked. One health function. |
| H-P1-11 | GPU/VRAM three answers | runtime-manager `gpu.detected=false`; hardware RTX 5090; Comfy `cuda:0`. One GPU snapshot owner. |
| H-P1-12 | Start with Windows vs AdeptBetaBackendManager | API `startWithWindows=false` `taskRegistered=false`; OS task exists State=Ready. |
| H-P1-13 | Brad-shaped paths | `D:\01_Models` + Comfy-Desktop roots. Discoverable portable roots. HF CLI not Ready when `online_verified=false`. |

### Mission 4 — Audio Studio production path — H-P1-05, H-P1-06, H-P1-07

| ID | Title | Boundary |
|---|---|---|
| H-P1-05 | Clone `emotional_direction` ignored | **DONE.** Clone + style → 400 `STYLE_UNSUPPORTED`. DESIGN still applies instruct. |
| H-P1-06 | Approve does not ingest Library | **DONE.** Approve stamps durable `Asset.id` + `production_approval=approved` into project Library. |
| H-P1-07 | Music UI unavailable vs ACE-Step ready | **DONE.** Music badge follows ACE-Step GPU ready. Generate enabled after prompt. No music job. |

### Mission 5 — Capability holes + dual memory + confirmation — H-P1-08, H-P2-01 … H-P2-04

| ID | Title |
|---|---|
| H-P1-08 | Registered capabilities with no handler modules (`image.edit`, `image.generate_batch`, `character.generate_candidates`) |
| H-P2-01 | Image auto-executes; video asks “Shall I proceed?” |
| H-P2-02 | “Last corridor prompt” → Audio Studio NAVIGATE |
| H-P2-03 | Canonical retry image-only on execution packs; chat inherit is second memory |
| H-P2-04 | Leftover image job poisons next Co-Director turn |

### Mission 6 — UX polish + leftover hygiene — P3s, VA-P2-01

Do not fold P2/P3 into P1 unless re-proven.

## Deduplicated findings (full register)

### P0

| ID | Title | Severity | Verified root-cause boundary | Auditor(s) | Cursor mission | Status |
|---|---|---|---|---|---|---|
| H-P0-01 | H3 LoadAudio keyed on `studio/<label>.wav` not `Asset.id` | P0 | Comfy submit uses uploaded basename / `Asset.comfy_name`; bind miss → `H3_REF2V_VOICE_MISSING` | Voice/Audio VA-P0-01 | Durable asset UUID through voice bind → graph. Do not reuse colliding labels. | **CLOSED — GO** |

### P1 — grounding / session (before Co-Director audio actions)

| ID | Title | Severity | Verified root-cause boundary | Auditor(s) | Cursor mission | Status |
|---|---|---|---|---|---|---|
| H-P1-01 | Co-Director stream has no selected scene / entity snapshot | P1 | Chat POST `sceneId` null, `workspace_tab=home`. GET session-context `no_project` / `activeSceneId` null while header is Korri Anadriya. | Co-Director ISSUES 2+15; Voice VA-P1-02 | Bind `activeSceneId` + character/voice IDs into every project-bound turn. | **CLOSED — GO** |
| H-P1-02 | Co-Director denies approved characters and voices | P1 | Voice Studio/API assignments are correct. Co-Director answered from notes/vision, not those APIs. | Co-Director ISSUE 2; Voice AUDIT 1 | Inject character + voice profiles. Do not fix Voice Studio. | **CLOSED — GO** |
| H-P1-03 | `@Korri`/`@Anadriya` smash to fake model + paid fal | P1 | Tags not fully resolved before `plan_image_route`; `korriandanadriya` treated as model lock. Job `3aa7dbbd` cancelled after capture. | Co-Director ISSUE 3 | Resolve `@` tags to CRS IDs before image route. | **CLOSED — GO** |
| H-P1-04 | UNLOCKED AUTO still → paid `gpt-image-2-fal` | P1 | `plan_image_route` `step=exact`; selected `gpt-image-2-fal`; lock=UNLOCKED while Comfy ready. Jobs `3d8deaa1`, `210935fa`. | Co-Director ISSUE 1 | UNLOCKED AUTO = Production Control local-first. | **CLOSED — GO** |
| H-P1-05 | Clone `emotional_direction` ignored (identical SHA256) | P1 | Schema accepts whisper/angry; clone worker gets text/reference/seed only. | Voice VA-P1-01 | Wire style into clone path or stop accepting the field. | **CLOSED — GO** |
| H-P1-06 | Audio Studio approve does not ingest Library | P1 | Approve 200, candidate approved, `libraryCount` 0→0, `sandboxOnly=true`. | Voice VA-P1-03 | Ingest approved take as durable `Asset.id`. | **CLOSED — GO** |
| H-P1-07 | Music UI unavailable vs ACE-Step ready | P1 | Music Generate disabled; SFX reports ACE-Step ready sandboxOnly. Live music gen not click-tested. | Voice VA-P1-04 | Align Music CTA with ACE-Step health or label sandbox-only. | **CLOSED — GO** |
| H-P1-08 | Registered capabilities with no handler modules | P1 | `image.edit`, `image.generate_batch`, `character.generate_candidates` in `CAPABILITY_HANDLER`; import-by-convention will fail. Source-only. | Co-Director ISSUE 5 | Add handlers or unregister. | OPEN |

### P1 — Ready / path / health honesty (Setup)

| ID | Title | Severity | Verified root-cause boundary | Auditor(s) | Cursor mission | Status |
|---|---|---|---|---|---|---|
| H-P1-09 | Multiple Ready contracts | P1 | `setup_state.comfyui` Ready with `installation_path=http://127.0.0.1:8188` (URL). `wan_models` Ready `path=null`. SM `sources=[]` while Setup Ready. | Setup SW-02, SW-03, SW-08, SW-14 | One Ready enum. Never Ready with null/URL path. | **PARTIAL** — path contract live; SM empty sources still open |
| H-P1-10 | Comfy health split-brain | P1 | `/health` vs nested comfy vs `/api/comfy/health` vs `status/latest` vs Co-Director chip. | Setup SW-01; Co-Director Dim 36 | One Comfy health function. | **CLOSED — GO** |
| H-P1-11 | GPU/VRAM three answers | P1 | runtime-manager `gpu.detected=false`; hardware RTX 5090; Comfy `cuda:0`. | Setup SW-04, SW-05 | One GPU snapshot owner. | **CLOSED — GO** |
| H-P1-12 | Start with Windows vs AdeptBetaBackendManager | P1 | API `startWithWindows=false` `taskRegistered=false`; OS task exists State=Ready. | Setup SW-06 | UI matches Task Scheduler or stop claiming unregistered. | **CLOSED — GO** |
| H-P1-13 | Brad-shaped paths (D: + Comfy-Desktop) | P1 | Setup `model_locations` + MiniMax `modelRoot` on `D:\01_Models` and Comfy-Desktop. HF CLI in hermes-agent venv. | Setup SW-07, SW-10 | Discoverable portable roots. | **PARTIAL** — roots labeled; HF Ready only if online_verified |

### P2 (do not fold into P1 unless re-proven)

| ID | Title | Boundary | Auditor | Status |
|---|---|---|---|---|
| H-P2-01 | Image auto-executes; video asks “Shall I proceed?” | `should_act_image` privileged vs other caps confirmation | Co-Director | OPEN |
| H-P2-02 | “Last corridor prompt” → Audio Studio NAVIGATE | Referential resolver, not last image execution pack | Co-Director | OPEN |
| H-P2-03 | Canonical retry image-only; chat inherit is second memory | `generation_memory` `EXCLUDED_CAPABILITIES`; `used_chat_inherit` | Co-Director (source) | OPEN |
| H-P2-04 | Leftover image job poisons next Co-Director turn | Status leak (`67ef2ce9` queued on video turn) | Co-Director + Voice DIM16/VA-P1-02 | OPEN |
| H-P2-05 | Historical false capability denials in stored transcript | Aug 31–Sep 1 chat; live 2026-09-02 executed | Co-Director | OPEN |
| H-P2-06 | `/api/setup/status` timeout; Wizard UI not click-walked | Setup PARTIAL | Setup SW-09 | OPEN |
| H-P2-07 | Duplicate leftover Korri DESIGN v5 + extra clone rows | Hygiene; active v15 is correct | Voice VA-P2-01 | OPEN |
| H-P2-08 | Cancel marks completed warm SFX jobs cancelled | Race on ~1.5s gens | Voice VA-P2-02 | OPEN |
| H-P2-09 | Ambience is SFX/MMAudio + `audio_clips`, not a third lane | Architecture as found | Voice VA-P2-03 | OPEN |
| H-P2-10 | Hunyuan/LTX Ready = files-at-path, not Production Control executable | Do not merge with generator-matrix Ready≠known without PC snapshot | Setup SW-13, SW-15 | OPEN |
| H-P2-11 | Fixture Provider still listed in Source Manager | e2e leftover | Setup SW-11 | OPEN |

### P3

| ID | Title | Auditor | Status |
|---|---|---|---|
| H-P3-01 | Chat Focus / Balanced / Project Focus are layout-only | Co-Director | OPEN |
| H-P3-02 | no-project-banner flicker on bound project | Co-Director | OPEN |
| H-P3-03 | Anadriya Voice Studio tabs locked | Voice VA-P3-01 | OPEN |
| H-P3-04 | Wide Audio Studio unused gutters (centered 1120) | Voice VA-P3-02 | OPEN |
| H-P3-05 | Dialogue compile skips `approval_status` check | Voice VA-P3-03 | OPEN |

## Untestable / partial (do not certify from this handoff)

- Co-Director: Re-Take, STRICT fal-only, Flux Local exact, refresh+API-recycle retry, summarization overwrite, cross-project, MiniMax video.
- Voice: Music live generate, speaker listen, Add-to-Timeline click, API recycle durability.
- Setup: Wizard/SM first-run click-walk; `/api/setup/status` hang; Production Control vs Setup Ready snapshot; reboot logon (not rebooted).

Note: Timeline Re-Take later received a separate Cursor GO. That does **not** certify the Co-Director auditor’s untested Re-Take cell, and it does **not** close H-P0-01 without a fresh label-collision re-verify.

## Performance (Voice — context only, do not optimize in this plan)

| Job | Wall | Notes |
|---|---|---|
| First Korri TTS | 44.4s (`completeMs` 6.9s) | worker warmup |
| Later TTS | 3.1–4.3s | clone |
| First SFX POSTs | 16.7–37.3s | load / GPU queue |
| Warm SFX | ~1.5s wall, infer ~1.0–1.2s | not reload-every-request |

## Next executable mission

1. **Mission 5** — H-P1-08 handlers + H-P2-01…04 (confirmation, referential resolver, dual memory, leftover job poison).
2. Then leftover H-P1-09 SM `sources=[]` if still open, then Mission 6 P3 / VA-P2 hygiene.

Ordinary missions: `:8188` is read-only. Report `COMFY BEFORE` / `COMFY AFTER` / `COMFY RESTARTED?`.
