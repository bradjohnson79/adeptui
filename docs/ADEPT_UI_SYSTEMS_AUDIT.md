# Adept UI Systems and Platforms Audit

> **UI Design Language (Phase 4.0):** See [`docs/design/ADEPT_UI_DESIGN_SYSTEM.md`](design/ADEPT_UI_DESIGN_SYSTEM.md) — authoritative Aurora Design System law for all UI work.

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Scope** | Read-only inventory of systems, platforms, models, providers, libraries, and services present in the repository and evidenced by configuration, code, and certification reports |
| **Method** | Repository inspection only — no installs, no code changes beyond this report |

Status labels used below: **Working**, **Partially Working**, **Installed but Not Tested**, **Available but Not Installed**, **Planned**, **Deferred**, **Unknown**.

Something is not marked Working merely because its name appears in code or a dropdown. Working requires certification or clear runtime evidence of real output.

---

## 1. Frontend and application runtime

| Piece | What is used | Evidence | Status |
|---|---|---|---|
| Frontend framework | React 19 + TypeScript + React Router 7 | `studio-web/package.json`, `src/main.tsx`, `src/App.tsx` | Working |
| Styling | Plain CSS / Aurora theme tokens (no Tailwind) | `studio-web/src/styles.css`, `theme/aurora-theme.css` | Working |
| Build system | Vite 8 (`tsc -b && vite build`) | `studio-web/package.json`, `vite.config.ts` | Working |
| Dev web server | Vite on `:5173` with `/api` `/media` proxy | `vite.config.ts`, root `package.json` `npm run dev` | Working (dev) |
| Local Beta web server | Starlette/uvicorn static SPA + proxy; serves `studio-web/dist`; **no Vite** | `scripts/beta_runtime/web_server.py`; port **8760** | Working — V1.1 Beta cert GO |
| API | FastAPI + uvicorn | `studio-api/requirements.txt`, `app/main.py` | Working |
| API ports | Dev default `:8742` (reload); Beta `:8758` (no reload; may adopt existing process) | `scripts/run-api.mjs`, `config/beta-local.env`, supervisor | Working |
| Queue / worker | In-process `JobQueue` + optional Production Executive worker (same API process) | `studio-api/app/queue_worker.py`, `main.py` lifespan | Working |
| Database | SQLite at `{STUDIO_DATA_DIR}/studio.db` (default `data/studio.db`) via SQLAlchemy | `studio-api/app/db.py`, `config.py` | Working |
| File storage | Project/media under `data/` (assets, exports, sandboxes, runtime) | `STUDIO_DATA_DIR`, `data/` layout | Working |
| Logging | Stdlib logging in API; Beta rotating logs under `data/runtime/logs/beta/` | `supervisor.py`, `Start-AdeptUI-Beta.ps1` | Working |
| Health checks | `GET /api/health`, `GET /__beta_web_health`, `GET /api/runtime/beta`, `AdeptUI-Beta-Health.ps1` | `routers/api.py`, `web_server.py`, `runtime_beta.py` | Working |
| Local runtime supervisor | `scripts/beta_runtime/supervisor.py` + Start/Stop/Restart/Health launchers | `config/beta-local.env`, Beta cert report | Working — GO |

Other frontend libraries present: `three` (360/environment viewport), `i18next`, `marked`, `dompurify`.

---

## 2. Co-Director

### What powers Co-Director

| Piece | Detail | Status |
|---|---|---|
| LLM runtime | **Ollama** local (`STUDIO_OLLAMA_URL`, default `http://127.0.0.1:11434`) | Working (reachable in Beta health) |
| Primary model | `gemma4:31b-it-qat` (fallback `gemma4:12b` in config) | Partially Working — smoke/benchmark docs; not a full production LLM cert |
| Cloud LLMs | Not registered (`PROVIDER_IDS = ["ollama", "mock"]`) | Not used |
| Tools | M2.2 tool registry + handlers (Bible, generation, character identity, Character Creator, timeline, etc.) | Partially Working — many tools registered; confirmations required for mutations |
| Memory / intelligence | Feature-flagged Co-Director intelligence (M2.4+), specialist runner, synthesis | Partially Working — many flags default off; Beta enables a subset |
| Production Bible | Domain schemas + approve/lock APIs + UI workspace | Working for core approve/reject; full provider matrix still open in older certs |
| Character Profile | REST under `/api/projects/{id}/characters` + Co-Director tools; flag `STUDIO_FEATURE_CHARACTER_IDENTITY_V1` | Partially Working — schemas/UI/tools GREEN; overall M3.3 NO-GO |
| Storyteller | Specialist prompt + M214 Storyteller surfaces | Partially Working — registered and wired; no dedicated GO stamp for full product |
| Character Creator | Specialist `character-creator` + structured tools writing into Character Profile | Partially Working — registered; tools GREEN; cert **NO-GO** pending imagegen + Playwright |
| Other specialists | ~31 specialists (director, cinematographer, casting-director, sound-designer, etc.) | Partially Working — inventory exists; not all auto-routed or product-certified |

### Clear statements

- **Fully working for local chat/tooling when Ollama + model are up:** Co-Director session against Ollama.
- **Partially wired:** Character Creator, Storyteller collaboration, Character Profile tools, intelligence v2 pipeline.
- **Planned / incomplete:** Full Character Creator GO; disposable M3.3 lipsync→Editor via Co-Director; some M214 exchanges.

Evidence: `studio-api/app/codirector/`, `docs/release-gate/m33/M33_CHARACTER_CREATOR_SUBAGENT_REPORT.md`, Beta health operator block.

---

## 3. Image generation

| System | Local/Cloud | Installed | Via ComfyUI | Used for | Real output |
|---|---|---|---|---|---|
| **ComfyUI** | Local (`:8188`) | Yes on cert machine (health shows ready) | N/A (runtime) | Node graph for image/video/lipsync | Yes |
| **Z-Image Turbo** (+ Qwen text encoder + AE VAE) | Local | Linked when `zimage_models` present | Yes | Stills, storyboards, ImageGen, reference-conditioned images | Yes — Hitchhiker / M32 stills |
| **FLUX / HiDream / SD3.5** checkpoint options | Local | Only if user installs weights | Yes (generic builder) | Alternate ImageGen | Unknown |
| **Essential asset packs** (photoreal/anime/cinematic) | Local | Optional Setup packs | Supports Comfy assets | Creative assets | Unknown (install-dependent) |
| **LTX 2.3 Ingredients IC-LoRA** | Local | Often missing / gated HF | Yes | Identity/reference-sheet conditioning | Unknown / often incomplete |
| **fal image models** | Cloud | N/A | No | — | Explicitly unwired (`FAL_IMAGE_MODELS` empty) |

Status summary: **Working** for local Z-Image/Comfy stills on certified projects. **Available but Not Installed** for optional checkpoints/packs until linked. **Not used** for fal stills.

---

## 4. Video generation

| System | Version / id | Local/Cloud | Installed | Purpose | State | Limitations |
|---|---|---|---|---|---|---|
| **LTX** | LTX 2.3 (`ltx_checkpoint`; distilled FP8 + Gemma text encoder) | Local Comfy | Yes on Hitchhiker cert machine | Primary local I2V / scene video | Working — M32F Hitchhiker Shot1 GO | Needs Comfy + weights; face-forward clips matter for lipsync |
| **WAN 2.2** | High/low noise FP8 + VAE + UMT5 | Local Comfy | Yes on Hitchhiker cert machine | Spatial / first-last-frame I2V | Working — M32G Test 2 GO | Large disk; optional in Setup catalog |
| **fal Seedance 2.0** | fal catalog | Cloud | Key optional | Cloud I2V | Partially Working — M30D queue proof when key present | Paid; not Hitchhiker primary |
| **fal Kling / Veo / Runway** | fal catalog | Cloud | Key optional | Cloud I2V options | Unknown — registered, not Hitchhiker-certified | Requires fal key |
| Other local video stacks | — | — | — | — | Unknown | — |

Native video production is gated by `STUDIO_FEATURE_VIDEO_PRODUCTION_V1` (enabled in Beta env).

---

## 5. Character creation and consistency

| Capability | What Adept UI uses | Status |
|---|---|---|
| Character Profiles | Canonical SoT in `character_identity` (versions, approve/lock) | Partially Working — product surface live under flag; M3.3 overall NO-GO |
| Character Creator | Co-Director specialist + tools (`create_from_brief`, plans, provenance) | Partially Working — scaffold + tools; cert NO-GO |
| Reference images | Role-tagged `CharacterReferenceAsset` (6 required views + optional) | Partially Working — schema/coverage; Korri imagegen pack incomplete |
| Turnarounds / pose / expression sheets | Roles + Character Creator plans; imagegen enqueue | Partially Working / Planned for full auto pack |
| Wardrobe | Versioned wardrobe profiles + library taxonomy | Partially Working |
| Hair / skin | Typed skin/hair profiles on CharacterVersion | Partially Working |
| Consistency / continuity | Continuity rules, coverage scoring, visual gates, provenance labels | Partially Working |
| Production Bible link | `characterProfileId` / `activeVoiceProfileId` on Bible character facade | Partially Working |

Korri sample cert: brief + voice **Working**; visual pack imagegen **Available but incomplete** (Comfy jobs timed out / not completed).

---

## 6. Dialogue, voice, and voice cloning

| System | Role | Present | Status |
|---|---|---|---|
| **Kokoro-82M** (`m2101-dialogue-001`) | Basic / preset dialogue TTS in M2.10b sandbox | Yes — sandbox ready | Working (sandbox; not silent Qwen identity fallback) |
| **Qwen3-TTS Voice Design 1.7B** | Character voice design from text direction | Yes — installed + real WAVs | Working for design previews (M3.3 product cert) |
| **Qwen3-TTS Voice Clone Base 1.7B** | Reference-conditioned clone + dialogue | Yes — installed + Korri clone WAVs | Working for clone/dialogue proofs |
| **Qwen CustomVoice / Chatterbox** | Alternate dialogue candidates | Authorized in locks; install failed/deferred | Available but Not Installed / Deferred |
| **ElevenLabs** | — | **Not in repository** | N/A |
| Emotional / performance tags | `emotional_direction`, `performance_instruction`, `pace` on dialogue request; VoiceProfile tone fields | Schema present | Partially Working — metadata fields; not a full SSML performance engine |
| Pauses | No dedicated pause/SSML system found | — | Planned / Unknown |
| Pronunciation | `pronunciation_notes` on VoiceProfile | Schema present | Partially Working |
| Voice consent | `VoiceConsentRecord` required for CLONE | Enforced in API/tests | Working |
| Voice approval | Approve VoiceProfile; immutable after approve/lock patterns | Product APIs | Working |
| Overall M3.3 voice→lipsync→Editor | — | — | Partially Working — voice GREEN; lipsync/Editor PENDING → overall **NO-GO** |

Sandbox audio is production-authorized **false** in M2.10b execution lock (sandbox isolation), even when real WAVs are produced.

---

## 7. Lip sync

| Piece | Detail | Status |
|---|---|---|
| Engine | **LatentSync** via ComfyUI (`lipsync.latentsync`; nodes `D_LatentSyncNode` / `LatentSyncNode`) | Working on certified Hitchhiker LTX/WAN paths (M32F/M32G GO) |
| Wiring | Queue worker + direct runner flags (`STUDIO_LIPSYNC_DIRECT`, feature `STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1`) | Working when Comfy + node pack present |
| M3.3 disposable chain | Parent MP4 prepared; job not completed in cert | Partially Working / Pending |
| Limitations | Needs suitable face-forward speaking plate; depends on Comfy custom node pack | Known from M30/M32 notes |

---

## 8. Music and sound effects

| System | Role | Installed | Status |
|---|---|---|---|
| **ACE-Step** (`m2101-music-045`) | Music generation (sandbox) | Venv/sandbox present; Hitchhiker music WAV in M32G artifacts | Working (sandbox) on Hitchhiker Test 2 |
| **MMAudio** (`m2101-sfx-031`) | SFX / ambience / foley (sandbox) | Venv/sandbox present; Hitchhiker SFX WAV in M32G | Working (sandbox) on Hitchhiker Test 2 |
| YuE / Riffusion | Alternate music | Authorized only | Available but Not Installed / Deferred |
| Stable Audio / Amphion | Alternate SFX | Authorized only | Available but Not Installed / Deferred |
| fal music | Cloud music | Attempted; failed policy/provider | Not a production path (NO-GO report) |
| Video-to-audio | MMAudio video-conditioned paths in sandbox adapters | Present in m210b | Partially Working / Installed but Not Tested outside Hitchhiker proofs |

---

## 9. Image editing, enhancement, and upscaling

From M32A generation-tools matrix and capability registry:

| Capability | Intended stack | Status |
|---|---|---|
| Inpainting / outpainting | Comfy / M29 image generate | Partially Working / backend_only — img2img path historically stubby |
| Cleanup / chroma key | OpenCV / FFmpeg | Partially Working — chroma key more complete than delighting |
| Background removal | BiRefNet (Comfy) | Partially Working — needs nodes/weights |
| Relighting / delighting | — | Missing / BLOCKED — no certified OSS stack |
| Restoration / face correction | CodeFormer / GFPGAN hints | Partially Working — acquisition-dependent |
| Image upscaling | RealESRGAN / SeedVR2 | Partially Working |
| Video upscaling | SeedVR2 temporal | Partially Working |
| Video extend | WAN / LTX I2V | Partially Working |

Honest gap: many enhance tools remain **PARTIAL** until Comfy nodes and weights are installed and re-certified.

---

## 10. Editing Suite

| Piece | What powers it | Status |
|---|---|---|
| Timeline (Director) | Scene `director_json`; DirectorTracks / timeline UI | Partially Working — propose/apply degraded/partial in capability matrix; M32G mix GO |
| Editor | `editor_sequences` / EditorWorkspace multi-track | Working on Hitchhiker Test 2 Editor mix cert |
| Video/audio handling | FFmpeg adapter + `media_ops` (concat, mux, re-encode) | Working |
| FFmpeg | Required Setup component; local executable | Working when installed |
| Subtitles | No SRT/VTT generation pipeline | Missing / Deferred architecture only |
| Transitions | Limited / Unknown as a dedicated system | Unknown |
| Titles | Editor titles track | Partially Working |
| Rendering / export | Job `export`; packs assets + provenance | Working (M30G/H, M32G export GREEN) |
| Project Library integration | Export + asset registration under taxonomy | Working |

---

## 11. Spatial, camera, lighting, and environments

| Capability | System | Status |
|---|---|---|
| Spatial Map (project / scene) | `spatial.py` + `spatial_scene.py`; SpatialMap / SpatialScene UI | Working in M32G spatial chain |
| 360 environments | Equirect / panoramas; Three.js EnvironmentViewport; library `scenes.panoramas_360` | Working as panoramic path (not native 3D) |
| Camera movement / specs | `CameraSpec` on spatial scene; camera-spin foundations gated | Partially Working — spatial blocking Working; advanced spin/virtual stage Deferred |
| Lighting controls | Light entities + lighting fields/presets; lighting-supervisor specialist | Partially Working |
| Scene references | Spatial entities + Project Library scene folders | Partially Working |
| Prompt construction | Spatial continuity standards + auto tags | Partially Working |
| Native 3D / Virtual Stage | Deferred to v1.2 | Deferred |

Supported v1.1 environment path: images → 360/equirect → Spatial Map → camera/lighting → WAN/LTX → lipsync → Editor.

---

## 12. Source Manager

Source Manager + Setup Wizard share the component catalog (`studio-api/app/setup/catalog.py`) and download/provider plumbing (`studio-api/app/source_manager/`).

### Catalog components

| Component | Typical state on cert machine |
|---|---|
| `python` | Installed |
| `ffmpeg` | Installed (required) |
| `comfyui` | Installed / reachable |
| `ltx_checkpoint` | Installed (linked) |
| `ollama` | Installed / reachable |
| `wan_models` | Installed (linked) on Hitchhiker cert host |
| `zimage_models` | Installed (linked) when stills certified |
| `fal_key` | Optional credentials — Unknown/conditional |
| Essential packs | Available but Not Installed unless user installed |
| `ltx23_ic_lora_ingredients` | Often unresolved / auth gated |
| `qwen_voice_design_17b` | Installed (M3.3i) |
| `qwen_voice_clone_17b` | Installed (M3.3i) |

### Buckets (evidence-based)

- **Installed:** Python, FFmpeg (when detected), ComfyUI (cert host), LTX, WAN (cert host), Ollama (cert host), Qwen Voice Design/Clone, Kokoro sandbox, ACE-Step/MMAudio sandboxes (Hitchhiker proofs).
- **Available but not installed:** Essential packs; alternate music/SFX candidates; fal key if absent.
- **Partially installed / unresolved:** IC-LoRA Ingredients (gated); enhance nodes (RealESRGAN etc.) until Comfy packs present.
- **Broken / deferred installs:** Qwen CustomVoice, Chatterbox (M2.10b qual failed/deferred).

Source Manager download queue: progress/cancel exist; Qwen voice HF snapshot executor wired; many packs still Setup Wizard–driven.

---

## 13. Project Library and Production Bible

### Storage / organization

| Kind | How stored |
|---|---|
| Projects | SQLite `projects` + filesystem under `data/` |
| Images / videos / audio | `Asset` rows + files under project asset paths; export packs under `data/exports/` |
| Character assets | Character Profile tables + library taxonomy `characters.*` |
| Scenes | Scene rows + outputs/lipsync paths; spatial docs |
| Scripts | Script/storyboard workspaces + library `scripts` |
| Production Bible | Versioned Bible domain entities (characters, locations, continuity, etc.) |
| Continuity / metadata | Bible continuity + Character continuity_json + job/export provenance |

Project Library taxonomy is mostly **virtual system folders** (`project_library/taxonomy.py`), lazy-created, including Production Bible and character subfolders. 3D folders labeled deferred to v1.2.

---

## 14. Cloud services and external APIs

| Service | Used for | Enabled | API key | Connection |
|---|---|---|---|---|
| **fal.ai** | Optional cloud video (Seedance, Kling, Veo, Runway) | Optional | Yes (`fal_api_key` encrypted store; env bridge) | Partially connected — Seedance proven; images unwired; music failed |
| **Hugging Face Hub** | Model/weight downloads (Qwen TTS, packs, LoRAs) | As needed for installs | Optional `HF_TOKEN` / related | Used for installs; not a runtime generation API |
| **GitHub** | Pack release downloads (CLI/API providers) | Optional | Optional pack token | Provider scaffolding + pack installs |
| **Ollama** | Local LLM (not cloud) | Local service | N/A | Working when running |
| OpenAI / Anthropic / AWS / Azure LLM | — | Not found as app providers | — | Not used |

No secret values are included in this report.

---

## 15. Version 1.2 or deferred systems

Intentionally deferred (V1.1 deferral GO — not treated as v1.1 failures):

- Native 3D modeling / scene assembly
- Mesh import
- Rigging
- Mocap
- Blender integration as product surface
- Unreal / game-engine integration
- Virtual Stage render / Environment Studio product nav (hidden; “Coming in Version 1.2”)
- Executable Co-Director `ve.*` / mesh / mocap tools

v1.1 substitute: panoramic 360 + Spatial Map + camera/lighting + WAN/LTX.

Evidence: `docs/release-gate/v11/V11_3D_SCOPE_DEFERRAL_REPORT.md`.

---

## Final summary table

| Adept UI area | Main system or provider | Current status | Notes |
|---|---|---|---|
| Co-Director | Ollama + Gemma 4 (local); tool registry; specialists | Partially Working | Chat Working when Ollama up; intelligence/Character Creator incomplete |
| Image Generation | ComfyUI + Z-Image Turbo | Working | Certified stills path; fal images unwired |
| Video Generation | LTX 2.3 + WAN 2.2 (Comfy); optional fal Seedance | Working | Hitchhiker M32F/M32G GO; fal optional |
| Character Creation | Character Profile + Character Creator specialist | Partially Working | Architecture/tools GREEN; Korri imagegen + full GO open |
| Dialogue TTS | Kokoro-82M (sandbox); Qwen for character dialogue | Working | Sandbox isolation; no silent Kokoro identity swap |
| Voice Design | Qwen3-TTS Voice Design 1.7B | Working | Real local design WAVs certified |
| Voice Cloning | Qwen3-TTS Base 1.7B | Working | Real clone + Korri sample proofs |
| Voice Performance Tags | Schema fields (emotion/pace/pronunciation notes) | Partially Working | Not a full pause/SSML engine |
| Lip Sync | LatentSync (Comfy) | Working | Hitchhiker GO; M3.3 disposable chain pending |
| Music | ACE-Step (M2.10b sandbox) | Working | Hitchhiker Test 2 music WAV |
| Sound Effects | MMAudio (M2.10b sandbox) | Working | Hitchhiker Test 2 SFX WAV |
| Upscaling | RealESRGAN / SeedVR2 (Comfy tools) | Partially Working | M32A PARTIAL until nodes/weights solid |
| Editing Suite | Editor sequences + FFmpeg export | Working | M32G Editor mix + export GREEN; subtitles absent |
| Spatial Map | Spatial scene engine + UI | Working | M32G spatial→WAN chain GO |
| 360 Environments | Equirect / Three.js viewport | Working | Panoramic path; not native 3D |
| Production Bible | Bible domain + workspace | Partially Working | Core approve/lock verified; deep matrix open |
| Project Library | Virtual taxonomy + assets | Working | Co-Director awareness reported |
| Source Manager | Setup catalog + download providers | Partially Working | Qwen voice install path added; packs/queue maturity mixed |
| Local Beta Runtime | Supervisor + static web `:8760` + API `:8758` | Working | V1.1 Beta cert GO |
| Native 3D | Deferred to Version 1.2 | Deferred | Clean deferral GO; not a v1.1 failure |

---

## Primary evidence roots

- Runtime: `config/beta-local.env`, `scripts/beta_runtime/`, `docs/release-gate/beta/V11_LOCAL_BETA_RUNTIME_REPORT.md`
- Setup / Source Manager: `studio-api/app/setup/catalog.py`, `studio-api/app/source_manager/`
- Co-Director: `studio-api/app/codirector/`
- Character / voice: `studio-api/app/character_identity/`, `docs/release-gate/m33/`
- Video / spatial / lipsync: `docs/release-gate/m32/M32F_*.md`, `M32G_*.md`
- Audio sandbox: `config/capabilities/adept-ui-v1.1-m2.10b-execution-lock.json`
- 3D deferral: `docs/release-gate/v11/V11_3D_SCOPE_DEFERRAL_REPORT.md`
- Capabilities: `studio-api/app/capabilities/registry.py`, `docs/audit/ADEPT_PRODUCTION_CAPABILITY_MATRIX.md`
