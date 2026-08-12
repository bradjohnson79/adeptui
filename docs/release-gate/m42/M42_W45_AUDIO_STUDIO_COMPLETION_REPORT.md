# M42 Phase 4.5 — Audio Studio Completion Report

**Milestone:** M42 W45 Audio Studio Completion (+ GPU wiring repair)  
**Branch:** `phase2/m42-audio-studio-completion`  
**Starting SHA:** `f758744` (tip of `phase2/m42-voice-performance-system` at branch create)  
**Final SHA:** working tree on `f758744` with W45 + GPU repair changes (uncommitted at report time)  
**Beta URL:** http://127.0.0.1:8760/  
**API health:** http://127.0.0.1:8758/api/health  
**Gate:** `GET /api/audio-studio/gate/w45` → `audioStudioGo` / binary **GO|NO-GO**  
**Primary authority:** sole integrator / certifier (subagents may only report `READY FOR PRIMARY REVIEW`)

---

## Objective

Promote Audio Studio from sandbox UI into a production Music / Sound Effects / Ambience / Project Audio subsystem with real generation, approval, library, Timeline placement, mixing (4.5A), Co-Director tools, cancel-to-source, and honest provider/GPU capability labels — ending only with binary certification and no mock completion.

---

## Scope completed

- Shared contracts frozen (mix + stems)
- Creator UX: Music / SFX / Ambience / Project Audio
- Real ACE-Step music + MMAudio SFX/ambience batches (async + progress %)
- Select ≠ Approve
- Project library roles + Timeline place + Audio Mixer persistence
- Co-Director `audio.*` tools (approval-gated)
- Certified cancel-to-source (process tree kill)
- CUDA/GPU repair for ACE-Step + MMAudio venvs
- Unit + Playwright + live certification artifacts

---

## Architecture / implementation summary

```text
UI (Audio Studio)
  → /api/audio-studio/projects/{id}/generate (asyncMode)
  → queued AudioCandidateBatch
  → background execute_generate_batch
  → run_audio_generate → AudioService → AceStepSandboxAdapter / MMAudio
  → tracked Popen worker (cancel-to-source registry)
  → ACE-Step / MMAudio on CUDA
  → WAV → asset register → library
  → select / approve / place → mix.json + editor tracks
```

Provider preference remains honest: local when ready; hosted Kie → WaveSpeed → fal declared; **no silent switch**.

---

## Failure Repaired

### Symptom

Audio Studio music generation stuck at **0%** for minutes with **no GPU activity** despite RTX 5090 present. Cancel worked, but generation never reached CUDA.

### Root cause

ACE-Step virtual environment contained **CPU-only PyTorch** (`2.13.0+cpu`), so `torch.cuda.is_available()` was `False` inside the running worker. The worker also defaulted to `cpu_offload=True`, keeping execution off the GPU even if CUDA had been present. MMAudio (`m210b-sfx-venv`) had the same CPU-only Torch package.

### Repair

1. Uninstalled CPU Torch from `data/m210b-ace-venv` and `data/m210b-sfx-venv`
2. Installed CUDA-enabled PyTorch **`2.11.0+cu128`** (+ matching `torchaudio` / `torchvision`)
3. Updated `ace_step_worker.py` to:
   - require/log `selected_device=cuda:0` when CUDA is available
   - set **`cpu_offload=False`** when CUDA is available
   - emit phase JSON: `device` → `load_model` → `model_device` → `generate` → final meta
4. Adapter passes `--cpu_offload 0`, `--device_id 0`, studio `infer_step=18`
5. Equivalent CUDA Torch install applied to MMAudio venv
6. Beta restarted; provider resolver now reports `cuda` / device name honestly

### Regression verification (runtime evidence)

Evidence pack: `artifacts/m42/w45/gpu-evidence/`  
Script: `scripts/m42_w45_gpu_evidence.py`

| Check | Result |
|---|---|
| `torch.cuda.is_available()` | **True** |
| `torch.cuda.device_count()` | **1** |
| `torch.cuda.get_device_name(0)` | **NVIDIA GeForce RTX 5090** |
| Worker `selected_device` | **`cuda:0`** |
| Worker `cpu_offload` | **`false`** |
| Worker `model_device` | **`cuda:0`** |
| Audio Studio API batch | **`complete`** |
| Candidate asset | `7d66002c-6985-4856-b8f2-9ad7e1fa78c2` |
| Approve | **True** |
| Timeline place + mix | **ok** |
| Direct worker WAV | **1,141,352 bytes** in ~18.7s |

**nvidia-smi during job** (`nvidia_smi_during_job.log`):

- GPU: NVIDIA GeForce RTX 5090
- CUDA compute processes: `python.exe` (PIDs observed e.g. 5744, 38312)
- VRAM climbed during generation (examples: ~2.5 GiB → ~9.3 GiB → ~14.2 GiB → ~18.3 GiB / 32607 MiB)
- GPU util samples up to ~15–16%; power samples up to ~71–73W on P1

**Pipeline timestamps captured:** UI/API submit → queue polls → worker phases → CUDA device/model → WAV output → select/approve/place (see `timeline.json`, `07_evidence_summary.json`).

**Evidence summary `ok`: true**

---

## Files created or changed (high level)

### Backend
- `studio-api/app/audio_studio/*` (contracts, store, service, router, production_gate, provider_resolver, process_registry)
- `studio-api/app/codirector/native_audio/ace_step_worker.py`
- `studio-api/app/codirector/m210b/adapters/ace_step.py`, `mmaudio.py`, `base.py`
- `studio-api/app/codirector/tools/handlers/audio_studio_tools.py` (+ registry/definitions/plans)
- `studio-api/app/project_library/taxonomy.py` (audio roles)
- `studio-api/app/generation_tools/ops.py` (role library keys)
- `studio-api/tests/test_m42_w45_audio_studio.py`

### Frontend
- `studio-web/src/components/audio-studio/**`
- `studio-web/src/styles/audio-studio/audio-studio.css`
- `studio-web/src/api.ts` (Audio Studio + mix + cancel APIs)
- `studio-web/src/components/EditorWorkspace.tsx` (mixer integration)

### Docs / artifacts / scripts
- `docs/release-gate/m42/M42_W45_*.md`
- `docs/ADEPT_UI_BUILD_MEMORY_LAYER.md`, `.cursor/rules/adept-ui-build-laws.mdc`, `AGENTS.md`
- `artifacts/m42/w45/**` including `gpu-evidence/**`
- `scripts/m42_w45_certify.py`, `scripts/m42_w45_gpu_evidence.py`
- `tests/e2e/m42/m42-w45-audio-studio.spec.ts`

### Database / schema
- No SQL migration; Audio Studio state is JSON under `data/audio_studio/{project_id}/` (batches, draft, mix)

---

## API and UI wiring

| Surface | Endpoint / control |
|---|---|
| Gate | `GET /api/audio-studio/gate/w45` |
| Generate (async) | `POST .../generate` `asyncMode=true` |
| Progress poll | `GET .../batches/{batchId}` |
| Cancel-to-source | `POST .../batches/{batchId}/cancel` |
| Project cancel | `POST .../cancel-generations` |
| Select / Approve | `POST .../candidates/{id}/select|approve` |
| Place + mix | `POST .../place`, `GET|PUT .../mix` |
| UI | Generate + % bar + **Cancel generation**; Preview ≠ Approve |

---

## Tests executed

| Suite | Result |
|---|---|
| `studio-api/tests/test_m42_w45_audio_studio.py` | **11 passed** (incl. cancel + progress) |
| Playwright `tests/e2e/m42/m42-w45-audio-studio.spec.ts` | **3/3 passed** (prior certification) |
| `scripts/m42_w45_certify.py` | Live music/SFX/ambience + mix persistence |
| `scripts/m42_w45_gpu_evidence.py` | **`ok: true`** CUDA + E2E persistence |

---

## Failures encountered and corrections

1. **CPU-only Torch in ACE/MMAudio venvs** → CUDA install + worker GPU path (documented above)  
2. **Beta build failed** on unused `slug` / bad `??` expression → TypeScript fixed; Beta restarted  
3. **Gate art_ok BOM** from PowerShell JSON → `utf-8-sig` reader  
4. **Background subagent store.py SQLite conflict** → kept JSON store (primary authority)  
5. **Cancel required** → process registry + `taskkill /T /F` cancel-to-source  

---

## Beta server verification

- Runtime restarted after GPU repair and worker updates  
- Provider probe: `ACE-Step` → `ready (CUDA: NVIDIA GeForce RTX 5090)`, `torchVersion=2.11.0+cu128`  
- Manual path: Production → Audio Studio → Music → Generate 3 Tracks (progress + Cancel)  
- Mixer: Editor when audio clips present; Project Audio → Open Audio Mixer  

---

## Screenshots and artifact locations

- `artifacts/m42/w45/` — certification stamps  
- `artifacts/m42/w45/gpu-evidence/` — CUDA repair evidence pack  
  - `01_worker_venv_cuda_probe.json`  
  - `02_batch_started.json` / `03_batch_final.json`  
  - `04_nvidia_smi_snapshot.txt`  
  - `nvidia_smi_during_job.log`  
  - `05_direct_worker_run.json`  
  - `07_evidence_summary.json` (`ok: true`)  
  - `timeline.json`  

---

## Co-Director operational wiring (Laws 1–26 audit repair)

Primary audit found the Audio Studio UI path certified, but Co-Director operational use had gaps. Repaired:

| Gap | Repair |
|-----|--------|
| `uiAction: open_audio_studio` ignored in UI | `CoDirectorSession` now calls `onGoTab("audiostudio")` |
| Sync `generate_batch` on approve (timeout risk) | Apply handlers start **async** batch + background thread; return `batchId` |
| No Co-Director cancel | `audio.cancel_batch` (`requires_approval=False` for GPU safety) |
| No batch poll tool alias | `audio.get_batch` + existing `audio.compare_candidates` |
| Silent CPU still “ready” | `resolve_execution` → `blocked_cpu` unless `allowCpuFallback=true` |
| Duration preview 45s vs clamp 20s | Defaults/contracts/UI/tools aligned to ≤20s music |
| Generation Tools / planner still on `propose_*` | Catalog + planner bridge map to `audio.generate_*` |
| Preview URL could bind candidate id | Asset-id-only audio URLs + distinct seeds/variations |

**Tests:** `tests/test_m42_w45_audio_studio.py` — **13 passed** (incl. CPU block, async Co-Director apply, unique seeds).  
**Live Beta:** ACE-Step `mode=local`, `cuda=True`, RTX 5090, torch `2.11.0+cu128`.  
**Beta URL:** http://127.0.0.1:8760/

### Law checklist (Co-Director ↔ Audio Studio)

```text
[x] Law 1 Beta reflects completed work
[x] Law 5 Full-stack E2E path (tools → service → worker → assets → UI)
[x] Law 7 No mock completion markers on audio tools
[x] Law 8 No silent provider/CPU switch
[x] Law 9 Controls/tools wired (open/generate/select/approve/place/cancel)
[x] Law 10 Persistence via audio_studio store + asset registry
[x] Law 11 Cancel/recovery via audio.cancel_batch + UI cancel
[x] Law 14 Project-scoped batch/asset checks
[x] Law 20 Honest capability labels (blocked_cpu / CUDA ready)
[x] Law 22 Manual review ready on Beta
[x] Law 23 Evidence: unit tests + live provider probe
[x] Law 26 GPU-first; CPU blocked without explicit approval
```

Remaining honest limitation: no dedicated Playwright Co-Director proposal→approve→async→cancel browser E2E yet (unit + live API/UI path covered).

---

## Known limitations

- Hosted Kie/WaveSpeed/fal audio remain **Available but Uncertified / Unsupported** as labeled — not silent-fallback  
- Stems: `stems_supported=false` until a certified provider returns real stem files (no fakes)  
- Audio Director (scene mix suggestions) out of scope for M42  
- Voice Studio M43 beginner manual UX remains PENDING (not fabricated)  
- Candidate batch duration capped (music ≤20s) for responsive first-pass; longer scores via refine later  
- Co-Director browser E2E for approve→async→cancel not yet added  

---

## Deferred items

- Hosted generative audio certification  
- Provider-returned music stems end-to-end when available  
- Audio Director automation (post Editing Suite)  
- Playwright Co-Director Audio Studio operational workflow  

---

## Final verdict

**GO** for M42 Phase 4.5 Audio Studio production path, including GPU-wired ACE-Step/MMAudio execution and Co-Director operational wiring (async generate, cancel-to-source, open-studio handoff, GPU-first block).

Binary gate outcome remains authoritative via `GET /api/audio-studio/gate/w45`. No Conditional GO.
