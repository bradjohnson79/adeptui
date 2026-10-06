# ADEPT ZERO-BLOCKER RUNTIME + PROVIDER STATUS CONVERGENCE

Governing report for Setup Wizard / System Status / capability aggregation.
Supersedes screenshot-era contradiction between Status (blocked / Provider Offline)
and Setup (Ready to Generate). Historical AI-Guided Setup reports remain historical.

**Branch:** `feat/character-creator-final-closure`  
**Starting SHA:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Project walked:** Korri Anadriya (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`)  
**Local UI:** `http://127.0.0.1:5173/`  
**Studio API:** `http://127.0.0.1:8758/`  

---

## BEFORE

Ready: 37  
Not Installed: 5  
Needs Attention: 3  
Capability Blockers: 1  
Provider: Offline  
Overall (Setup): Ready to Generate  
Overall (Status): 1 Capability Blocker + Provider Offline  

That split was a false dual-aggregator, not two different machines.

### EXACT 5 NOT INSTALLED

1. **LTX 2.5 Spatial Upscaler** (`ltx_2_5_spatial_upscaler`) — optional LTX enhancement. Supported. ACTION: keep optional, exclude from required Not Installed.
2. **WaveSpeed.ai API key** (`wavespeed_key`) — optional hosted provider credential. Supported. ACTION: keep optional, never flip Providers Offline.
3. **InternVideo3 8B** (`internvideo3_8b`) — optional deep sequence reasoning. Supported advisory. ACTION: keep optional.
4. **Depth Anything V2 Small** (`depth_anything_v2_small`) — optional Co-Director near/far help. Supported. ACTION: keep optional.
5. **Wonder3D** (`wonder3d_multiview`) — obsolete AGPL leftover. Not used. Character Angles use Qwen Image Edit 2509. ACTION: remove from public Setup catalog.

### EXACT 3 NEEDS ATTENTION

1. **Ollama** — WHY: `apply_files_ready_gate` demanded a filesystem path for a live HTTP service. REQUIRED for Co-Director. ROOT CAUSE: local_service treated as folder install. ACTION: skip path gate for `local_service`. AFTER: Ready.
2. **Co-Director World Intelligence** (`vjepa2_world_intelligence`) — WHY: verifier `world_intelligence_files` fell through to `unsupported_verifier`. OPTIONAL. ROOT CAUSE: missing verifier. ACTION: implement file-presence verifier. AFTER: Ready (files present).
3. **Character Angles** (`character_multiview_engine`) — WHY: same filesystem-path gate on `detect_only` after the engine reported READY. OPTIONAL detect-only. ROOT CAUSE: path gate. ACTION: skip path gate for `detect_only`. AFTER: Ready.

### EXACT BLOCKER

- **name:** `references.ic_lora.ready` (Ingredients IC-LoRA readiness)
- **root cause:** Evaluator returned `NOT_CONFIGURED` (a blocking status) for a retired LTX 2.3 path. `v11_policy` already classified it OPTIONAL. `CapabilityStatusBadge` counted `snapshot.blockers` (all blocking statuses), while Setup used `requiredBlockers(REQUIRED_FOR_GENERATION)`.
- **feature:** leftover Visual References / LTX 2.3 Ingredients. Not MiniMax H3. Not LTX 2.5.
- **action:** evaluate as `deferred_version_1_2`; exclude OPTIONAL/advisory rows from the product blocker list; badge uses `productionBlockers`.

### PROVIDER OFFLINE

- **provider:** Co-Director local model provider (Ollama)
- **root cause:** `GET /api/health` is liveness-only. `operator.provider` was `{status: skipped, reachable: false}` so the UI mapped `Boolean(false)` → Provider Offline. Live `codirector.provider` was already `locally_verified` (`ollama` + `qwen3.6:35b-a3b`). Missing optional WaveSpeed/fal/kie keys were not the owner.
- **required/optional/obsolete:** Required Co-Director provider was healthy. Optional API keys must not own the strip.
- **action:** health now reports `not_probed` / `reachable: null`. Status strip resolves Providers Ready from `codirector.provider`.

---

## CLASSIFICATION (A–E)

| Item | Class | Action taken |
| --- | --- | --- |
| Studio API, ComfyUI, Python, FFmpeg, VideoChat3 | A REQUIRED — READY | None (already healthy) |
| MiniMax H3 / LTX 2.5 required video models, Z-Image, MAGI stack | A REQUIRED — READY | Proven on disk; aggregator already required-only |
| Co-Director provider (Ollama + qwen3.6:35b-a3b) | A REQUIRED — READY | Diagnostic + badge repaired |
| Co-Director Video Intelligence / Temporal Continuity | A REQUIRED — READY | CSS no longer paints ready as a blocker |
| LTX spatial upscaler, WaveSpeed key, InternVideo3, Depth Anything | C OPTIONAL — NOT INSTALLED | Labeled Optional — Not Installed |
| VJEPA2 World Intelligence, Character Angles | B OPTIONAL — AVAILABLE | False errors repaired |
| Unpublished photoreal/anime/cinematic packs | C OPTIONAL — source pending | Not counted as Not Installed |
| Wonder3D | D OBSOLETE — REMOVE | Removed from `public_components()` |
| Ingredients IC-LoRA | D OBSOLETE — REMOVE | Deferred; not a blocker |
| WAN / Hunyuan video / LTX 2.3 / Avatar / InfiniteTalk | D already filtered | Left out of public Setup |
| Deep sequence reasoning | Advisory | Non-blocking GPU recommendation |

No sixth category.

---

## REMOVED OBSOLETE MODULES

- `wonder3d_multiview` removed from live public Setup / status counts / install inventory. `get_component()` and license-blocked verifier remain so leftover callers still resolve honestly.
- `references.ic_lora.ready` removed from live blocker aggregation (`deferred_version_1_2`). Shared Comfy / references infrastructure kept.

WAN, Hunyuan **video**, LTX 2.3 Ingredients, InfiniteTalk, LongCat, MuseTalk, EchoMimic were already excluded from `public_components()`. No shared H3/LTX/MAGI/image runtime was deleted.

---

## REPAIRED REQUIRED MODULES

- Ollama Setup diagnostic (false `ready_requires_filesystem_path`)
- Provider strip (skipped health probe ≠ offline)
- Capability chrome (retired OPTIONAL IC-LoRA is not a production blocker)
- Video Intelligence ready styling

---

## OPTIONAL NON-BLOCKING

1. LTX 2.5 Spatial Upscaler — not installed  
2. WaveSpeed.ai API key — not configured  
3. InternVideo3 8B — not installed (deep sequence reasoning)  
4. Depth Anything V2 Small — not installed  
5. Essential Photoreal / Anime / Cinematic packs — source not published  

---

## CODIRECTOR / VIDEO INTELLIGENCE / GENERATORS

| Surface | After |
| --- | --- |
| CODIRECTOR | REQUIRED. `codirector.provider` = `locally_verified` — `ollama is reachable with model qwen3.6:35b-a3b.` Live `/co-director?projectId=…` opened Korri Anadriya Wiki (Korri, Anadriya, Story Complete). |
| VIDEO INTELLIGENCE | READY. `codirector.video_intelligence.ready` = `locally_verified`. VideoChat3 Temporal Continuity certified. InternVideo3 optional and not required. Setup card `data-state=ready` (no blocker chrome). |
| Deep sequence reasoning | Advisory: “Enhanced capability unavailable / additional GPU memory recommended.” Not a system blocker. |
| MINIMAX H3 | Timeline Scene 1: **MiniMax H3 — Local · Ready**. `models.video.ready` = `locally_verified`. |
| LTX 2.5 | Checkpoint / text encoder / video VAE / audio VAE ready on disk. Spatial upscaler optional missing. Timeline lists LTX 2.5 local engines. |
| IMAGE | `models.image.ready` = `locally_verified`. Z-Image, Qwen Image 2512, Illustrious paths resolve. Cinematic Image Generator loaded for Korri. |
| MAGI | `magi_gpu_upscale` (Real-ESRGAN), `ace_step_local`, `mmaudio_local` Ready. MAGI Editor opened with Library bins VIDEO / OBJECTS / AUDIO / MUSIC / SFX. Published-master assets remain in Korri Library. |
| AUDIO | ACE-Step + MMAudio + Qwen voice stacks Ready. |
| GPU | RTX 5090 detected (Status + Timeline GPU panel). |
| COMFY | Ready. Read-only during this mission. |

---

## AFTER

Required Ready: **4** (python, ffmpeg, comfyui, videochat3_4b)  
Optional Not Installed: **4** (labeled)  
Advisories: InternVideo3 / unpublished packs / deep sequence GPU note  
Needs Attention: **0**  
Capability Blockers: **0** (`productionBlockers=[]`, `blockers=[]`)  
Provider: **Providers Ready**  
Overall: **Ready to Generate**

Status dropdown (live Korri Home):

- Studio API Online  
- ComfyUI Ready  
- Models Ready  
- Providers Ready  
- GPU Detected  
- Capabilities Ready  
- 0 Jobs Queued  

Setup Wizard (live Korri Setup):

- 4 Required Ready  
- 4 Optional — Not Installed  
- 0 Needs Attention  
- Overall: Ready to Generate  
- Video Intelligence ready + advisory deep-sequence line  

One aggregator law:

- **READY TO GENERATE** only when every **required** Setup component and every **production** capability blocker list is empty.
- Optional unavailable = informational.
- Performance recommendation = amber advisory.
- Obsolete = absent from live status.

---

## COMFY

COMFY BEFORE: HTTP 200 `/system_stats`  
COMFY AFTER: HTTP 200 `/system_stats`  
COMFY RESTARTED?: **NO**  
WHY?: Status/diagnostic repair only. Studio API recycled via `scripts/restart_studio_api_only.py`. `comfyPid=34484 unchanged=True`.

---

## RESTART STABILITY

Studio API recycle (required by backend/config change):

- oldPid `18664` → newPid `27048`
- Comfy PID `34484` unchanged
- After recycle (no cache of the old process): Setup Ready to Generate, 0 required gaps, 0 production blockers, provider locally_verified

Not green-because-cached.

---

## OWNER LIVE WALK (Korri Anadriya)

| Surface | Result |
| --- | --- |
| Home | Korri Anadriya production command center (12/14 scenes) |
| Status | Providers Ready + Capabilities Ready (see AFTER) |
| Setup | Required Ready / Optional labeled / Ready to Generate |
| Timeline | MiniMax H3 Local Ready; LTX 2.5 present; Korri Scene 1 loaded |
| Image Generator | Cinematic Image Generator loaded (`workspace=imagegen`) |
| MAGI | MAGI Editor loaded; certified workspace; Library 559 |
| Co-Director | Full-screen Co-Director + Korri Wiki (Korri / Anadriya) |

No chargeable generations launched. Readiness contracts were proven from live health + capability + Setup + surface load.

---

## TESTS

- `studio-api` pytest: `test_readiness_contract.py`, `test_zero_blocker_status.py`, `test_setup_wonder3d_never_installs`, `test_reference_capabilities_are_project_scoped`, `test_v11_readiness_policy.py` — **18 passed**
- `studio-web` vitest `src/setup/helpers.test.ts` — passed
- `node --test src/status/status.test.ts` — **4 passed**

---

## FILES

- `studio-api/app/readiness/contract.py` — pathless ready kinds (local_service / detect_only / external_service)
- `studio-api/app/setup/catalog.py` — obsolete Wonder3D filter
- `studio-api/app/setup/status.py` — required vs optional counts
- `studio-api/app/setup/diagnostics.py` — VJEPA2 verifier; obsolete diagnose
- `studio-api/app/capabilities/service.py` — IC-LoRA deferred; product vs advisory blockers
- `studio-api/app/routers/api.py` — health provider `not_probed`
- `studio-web/src/status/mapHealth.ts` + `SystemStatusStrip.tsx` + `CapabilityPanel.tsx` + `SetupWizard.tsx` + `setup/helpers.ts`
- tests listed above

---

## LIMITATIONS

- Optional WaveSpeed key, InternVideo3, Depth Anything, and LTX spatial upscaler remain uninstalled. They are labeled optional and do not block Ready to Generate.
- Deep sequence reasoning stays an enhanced/GPU advisory until InternVideo3 is installed.
- `GET /api/health` still does not probe Ollama (timeout protection). Provider truth is `GET /api/capabilities` `codirector.provider`.
- Co-Director conversation history on Korri still contains pre-existing Retry rows; not in this status scope.
- Uncommitted on this branch until the owner asks for a commit.

---

## FINAL VERDICT

**GO — ADEPT ZERO-BLOCKER RUNTIME + PROVIDER STATUS CERTIFIED**
