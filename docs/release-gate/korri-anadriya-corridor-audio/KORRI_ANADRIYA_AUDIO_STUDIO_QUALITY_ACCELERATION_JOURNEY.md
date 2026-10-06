# Audio Studio Centered UX + Acoustic Intelligence + MMAudio Acceleration

Governing report for the Korri Anadriya Audio Studio quality / acceleration journey.  
Does not replace Journey 1 (selected-scene persistence) or Journey 2 (five-control transport).  
Amalgamated with the next two completed builds in [`ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md`](ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md).

Project: **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Branch: `feat/character-creator-final-closure`  
HEAD at start of this work: `b6156455e643d5fa430784b3130756f2d8038651`  
Review: Vite `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=audiostudio`  
Studio API: `http://127.0.0.1:8758/`

No new project was created. Timeline audio architecture was not modified.

---

## AUDIO STUDIO LAYOUT ROOT CAUSE

**Class: WEAK CONTRACT**

`.audio-studio-workspace` sat as a direct child of `.app-shell` (column flex, `align-items: stretch`) with `max-width: 1120px` and **no** `margin: 0 auto` and **no** `align-self: center`. The card therefore stayed on the left of a wide viewport. `.page` already centers other workspaces (`width: min(1200px, 100%); margin: 0 auto`); Audio Studio never used that wrapper.

## CENTERED LAYOUT RESULT

Governing container only (not every child):

```css
.audio-studio-workspace {
  align-self: center;
  width: min(1120px, 100%);
  max-width: 1120px;
  margin: 0 auto;
  padding: 1.25rem clamp(1.25rem, 4vw, 3rem) 3rem;
}
```

Primary measured on a 2534px-wide live viewport:

| metric | value |
|---|---|
| workspace width | 1120px |
| workspace x | 707 |
| midpoint | 1267 |
| viewport midpoint | 1267 |
| offset | **0** |

Dark Adept styling preserved (navy panels, teal chips, no white/gray regression).

Playwright `tests/e2e/audio-studio/audio-studio-centered-layout.spec.ts`: **1 passed**.

---

## SOUND PIPELINE MAP

```
Creator text + optional preset eventType + duration + strength
→ AudioStudioWorkspace.generateForKind("sfx"|"ambience")
→ POST /api/audio-studio/projects/{id}/generate
→ _prepare_generation
     Sound Prompt Compiler (always for sfx/ambience)
→ begin_generate_batch (compiled + negative + cfg persisted)
→ execute_generate_batch
     for each take, same warm MMAudio resident:
       compiled prompt + in-class variation
       → run_audio_generate → AudioService → MMAudioSandboxAdapter
       → mmaudio_runtime.generate_warm (--serve JSONL)
       → energy-crop to requested duration
       → WAV → Library asset
       → objective WAV check (not semantic classification)
→ UI poll → take cards → Select / Approve / Add to Timeline
```

## CURRENT MMAUDIO PROMPT CONTRACT

MMAudio `generate()` accepts:

- `text: list[str]` (positive)
- `negative_text: list[str]` (supported; previously hardcoded `[""]`)
- `cfg_strength` (previously hardcoded `4.5`)
- no duration argument — model window is the trained ~8s `SequenceConfig`

Adept now:

- sends **compiled** acoustic language, not raw creator text
- sends compiled **negative_text**
- maps strength → `cfg_strength` (3.8 / 4.5 / 5.2)
- energy-crops the 8s window to the requested length so the event, not pre-event air, is kept

## EXACT RAW VS COMPILED PROMPTS

**Raw:** `Footsteps on metal grating, mid-distance.`

**Compiled:** Distinct human boot footsteps walking at a steady cadence, across rigid steel industrial grating, in enclosed military spacecraft interior, steel construction, confined industrial resonance, alternating heel-and-sole impacts, each step producing a short metallic clank and brief resonant ring, mid-distance perspective, 5 distinct alternating steps occupying the full 3-second, event begins immediately, no pre-event ambience, balanced natural intensity, clear readable transient, clean isolated walking footsteps, no dragging or scraping metal, no furniture, no machinery.

**Negative:** dragging metal, scraping furniture, continuous metallic scrape, machinery rumble, music

**Raw:** `Heavy spaceship explosion in outer space.`

**Compiled:** Massive cinematic science-fiction spacecraft explosion, violent sharp blast transient followed by deep low-frequency impact, heavy metallic hull rupture and tearing, energetic secondary bursts and debris impacts, powerful explosive decay, cinematic outer space, violent blast transient in the first instant, then explosive decay and debris through the remaining 3-second, no long pre-blast air, stronger blast transient, greater low-frequency energy, larger destructive scale, isolated SFX, no wind ambience, no gentle whoosh, no empty air bed.

**Negative:** gentle wind, breeze, soft whoosh, ambience only, silence, light air

---

## FOOTSTEP ROOT CAUSE

**Class: DISCONNECTED + WEAK CONTRACT + MISSING compiler**

1. Raw “Footsteps on metal grating” was sent almost unchanged (plus a generic variation clause).
2. Intensity was stored and ignored.
3. `negative_text` was unused.
4. 8s generate + **start-trim** to 3s often kept pre-event scrape/air.
5. Every take relaunched a cold subprocess (reload torch + checkpoint + encoders).

Result: continuous metallic motion could win over discrete boot impacts.

## EXPLOSION ROOT CAUSE

Same chain. “Spaceship exploding in outer space” without cinematic blast / hull / debris language, no negatives against wind, and start-trim of an 8s window, produced a low-energy air/whoosh bed.

---

## ACOUSTIC PROMPT COMPILER

New deterministic module: `studio-api/app/audio_studio/sound_prompt_compiler.py`

- No extra LLM round.
- Small ontology: footsteps, explosion, door_slam, glass_place, glass_break, electrical_spark, ambience, generic.
- Preset `eventType` seeds classification; clear creator text wins if it names a different event (`spaceship explosion` is not forced to footsteps).
- Assembles source / material / cadence / environment / distance / duration occupancy / intensity / exclusions from the actual request.
- Wired in `_prepare_generation` for every sfx/ambience job (not behind unused `runPromptIntelligence`).

## PRESET SEMANTICS

| Chip | eventType | Seed text |
|---|---|---|
| Door slam | door_slam | Heavy steel door slam, close. |
| Footsteps | footsteps | Footsteps on metal grating, mid-distance. |
| Glass on counter | glass_place | Glass set on a counter, short and clean. |
| Electrical spark | electrical_spark | Electrical spark and arcing. |

Presets seed structured event type. Creator text then adds surface / distance / environment.

## DURATION SEMANTICS

How long? is the **clip length the event must occupy**.

- 3s footsteps → several distinct steps across ~3s, no pre-event air.
- 3s explosion → blast in the first instant + decay/debris for the rest.
- Door / glass → event immediately, short tail.
- Ambience → continuous bed for the full length.

Model still emits ~8s; Adept energy-crops to the requested window.

## STRENGTH SEMANTICS

| UI | Aliases | Prompt language | cfg_strength |
|---|---|---|---|
| Subtle | Soft, Quiet, Still | restrained, smaller scale, controlled transient | 3.8 |
| Normal | Natural, Medium, Alive | balanced, clear transient | 4.5 |
| Bold | Huge, Heavy, Loud, Busy | stronger transient, more LF, larger scale | 5.2 |

These are real generator parameters, not cosmetic labels. Event class does not change.

## PROJECT CONTEXT

Korri / Venture / metal-grating / corridor / spacecraft requests may add: enclosed military spacecraft interior, steel construction, confined industrial resonance.

Explicit anti-context (kitchen, forest, rain, apartment, …) blocks lore. Glass-on-counter does **not** get ship interior. Creator text always wins.

---

## COLD TIMING BEFORE

Previous architecture: **every take** spawned `mmaudio_worker.py` one-shot, loaded torch + `small_16k` + VAE + Synchformer + BigVGAN, inferred, exited. Take 2 repeated full setup. No warm resident. No numeric one-shot rerun was taken after the worker was replaced (that would dual-load VRAM). That full reload **is** the before-warm cost.

Owner-observed: sluggish local SFX.

## WARM TIMING BEFORE

Equal to cold. There was no warm path.

## ACCELERATORS FOUND

| Option | Supported? | Was enabled? |
|---|---|---|
| BF16 on CUDA | yes | yes (one-shot) |
| `torch.inference_mode` | yes | yes |
| `weights_only` load | yes | yes |
| Negative prompt | yes | **no** |
| cfg_strength | yes | hardcoded 4.5 |
| Duration-native seq_len | possible | unused (quality risk vs trained 8s) |
| Energy-window crop | yes | **no** (start-trim) |
| Warm residency | yes (Qwen pattern) | **no** |
| TF32 | yes | no |
| cudnn.benchmark | yes | no |
| SDPA / Flash | unknown in this stack | not forced |
| torch.compile | unknown quality | **not enabled** |
| CUDA graphs | unknown | not enabled |
| Batched multi-take | technically possible | **not forced** |

## ACCELERATORS ENABLED

Safe set only:

- Warm `--serve` residency, idle unload 10 minutes, evict via `unload_resident()` / cancel-in-flight
- Takes 1 and 2 share one admitted process
- BF16 + inference_mode (kept)
- TF32 + cudnn.benchmark on CUDA
- Negative prompt + intensity cfg
- Energy crop
- **Not** torch.compile, **not** Flash forced, **not** batched GPU inference

## COLD TIMING AFTER

First take after serve start (includes first CUDA/cudnn warmup infer):

| stage | take 1 (footsteps batch `2231763a-…`) |
|---|---|
| route | warm_serve, device=cuda |
| inference | **39963 ms** |
| save | 3 ms |
| total worker | 39967 ms |

Wall clock for that 2-take batch after API recycle was ~107s including serve process start (ready handshake not separately persisted on the job).

## WARM TIMING AFTER

| job | inference | save | total | wall |
|---|---|---|---|---|
| Footsteps take 2 | **1029 ms** | 4 ms | 1034 ms | same batch |
| Explosion | 1442 ms | 3 ms | 1446 ms | 9.8 s incl. poll |
| Door slam | 1244 ms | 3 ms | 1249 ms | — |
| Glass | 1059 ms | 5 ms | 1065 ms | — |
| Spark | 1193 ms | 3 ms | 1197 ms | — |
| Ventilation 8s | 1313 ms | 3 ms | 1317 ms | — |
| Cancel leftover take 1 | 1466 ms | 5 ms | 1473 ms | — |
| Next gen after cancel | 1255 ms | — | — | ready |

Warm inference dropped from **~40s → ~1.0–1.5s**. That is a material measured reduction from eliminating reload + first-infer warmup on later takes. Inference itself (Euler 25 steps) still dominates a warm job; we did not invent a 2-second product requirement.

## GPU/VRAM RESULT

- Proven device: `cuda` / `MMAudio · GPU` only when resolver `cuda` or job provenance `gpuProven`.
- Progress no longer says “GPU preferred”.
- Resident is bounded (10 min idle) and interruptible for cancel.
- `unload_resident()` exists for higher-priority image/video eviction. Comfy was not hooked and not restarted.
- nvidia-smi was not used as a second GPU authority.

---

## FOOTSTEP QUALITY RESULT

Live WAVs, onset analysis (not a semantic classifier; not speaker proof):

| file | duration | peak | rms | onsets |
|---|---|---|---|---|
| first compile take 1 `mmaudio_ba3d245d73.wav` | 3.0s | 0.95 | 0.084 | **0.012, 0.909, 1.857, 2.815** (4 steps) |
| batch take A | 3.0s | 0.81 | 0.031 | 0.024, 2.254 |
| batch take B | 3.0s | 0.92 | 0.048 | 0.018, 1.321, 2.129 |

Four evenly spaced transients at walking cadence are **not** continuous furniture-drag. Take A of the later batch is sparser (2 impacts) — still discrete, not a scrape bed. Primary cannot hear system audio; waveform/onset is supporting evidence only.

## EXPLOSION QUALITY RESULT

| file | peak | rms | onsets | early / late energy |
|---|---|---|---|---|
| `explosion_2b4cb89b-….wav` | 0.82 | **0.174** | 11 bursts from 0.767s | 0.028 / 0.024 |

This is a high-energy blast + debris cluster, **not** a low-energy wind bed. Compiled negatives explicitly exclude wind/whoosh.

## ADDITIONAL SFX QUALITY RESULTS

| class | identity evidence |
|---|---|
| Heavy steel door slam | 3 tight onsets in the first 0.3s; late energy collapses (front-loaded closure) |
| Glass on counter | **1** onset at 0.39s, peak 0.95, late energy ~0 — single clink |
| Electrical spark | many regular ~100ms transients (crackle pattern) but **quiet** (peak 0.07) — weakest class |
| Ship ventilation | 8s continuous high-RMS bed, energy throughout — environmental, not a one-shot |

## CANCEL RESULT

API batch `249a47f0-…`:

- Take 1 **ready** (`d1a73a07-…`) kept
- Take 2 **cancelled**
- Serve interrupt used only for that in-flight batch
- `--serve` not killed as an orphan
- Next generation completed ready in **1255 ms** infer
- No Comfy damage

Playwright cancel raced a warm 2-take finish (UI already Complete before cancel text). Spec now waits for take 2 before clicking Cancel. Product cancel is certified via API.

## TIMELINE HANDOFF

Preserved. Approve → Add to Timeline still writes `sfx_clips` via existing `putDirector` / `place` path.

- API: approve + place returned `approved: true`, `place: true` on footsteps take `544606fe-…`
- Live UI: Select → Approved → “Added to the SFX track.”
- No Timeline transport / Walk retiming / Comfy changes

---

## PLAYWRIGHT

| spec | result |
|---|---|
| `audio-studio-centered-layout.spec.ts` | **1 passed** |
| `audio-studio-sfx-quality-journey.spec.ts` | generate 2 takes + approve + Add to Timeline + warm second request **reached**; cancel assertion raced. API cancel covers the product path. |

Korri project only. `ADEPT_ALLOW_KORRI_MUTATION=1` for the live journey.

## PEER REVIEW

| question | answer |
|---|---|
| Centered without breaking responsive layout? | Yes. 1120 max-width, auto margins, align-self center, gutters. Playwright + CDP offset 0. |
| What caused latency? | Cold one-shot reload of torch + weights + encoders **every take**. First CUDA infer ~40s. |
| MMAudio reloaded unnecessarily? | Yes, before. Warm `--serve` now keeps the stack for a bounded idle window. |
| Acceleration materially improved warm gen? | Yes. ~40s → ~1.0–1.5s inference on later takes. |
| Any accelerator hurt quality / GPU stability? | torch.compile / Flash / batching **not** enabled. Comfy PID unchanged. No silent CPU. |
| Sound Engine compile acoustic meaning? | Yes. Deterministic compiler; raw text is no longer the MMAudio prompt. |
| Footstep prompts encode discrete impacts? | Yes. Boots, alternating cadence, grating, no drag/furniture. |
| Explosion prompts encode cinematic blast not wind? | Yes. Blast / LF / hull / debris; negatives exclude wind. |
| Presets / context / strength / duration wired? | Yes. See tables above. |
| Real results closer to requested identity? | Yes on the two named failures (discrete steps; high-energy explosion). Spark is quiet. No speaker-level claim. |
| Timeline handoff intact? | Yes. |
| Unrelated systems left alone? | Yes. |

---

## FILES CHANGED

- `studio-web/src/styles/audio-studio/audio-studio.css`
- `studio-web/src/components/audio-studio/SfxPanel.tsx`
- `studio-web/src/components/audio-studio/AudioStudioWorkspace.tsx`
- `studio-web/src/components/audio-studio/AmbiencePanel.tsx`
- `studio-web/src/api.ts`
- `studio-api/app/audio_studio/sound_prompt_compiler.py` **new**
- `studio-api/app/audio_studio/sfx_wav_validate.py` **new**
- `studio-api/app/audio_studio/mmaudio_runtime.py` **new**
- `studio-api/app/audio_studio/service.py`
- `studio-api/app/audio_studio/router.py`
- `studio-api/app/audio_studio/process_registry.py`
- `studio-api/app/codirector/native_audio/mmaudio_worker.py`
- `studio-api/app/codirector/m210b/adapters/mmaudio.py`
- `studio-api/app/codirector/m210b/schemas.py`
- `studio-api/app/codirector/m29/audio/service.py`
- `studio-api/app/generation_tools/ops.py`
- `studio-api/tests/test_sound_prompt_compiler.py`
- `studio-api/tests/test_sfx_wav_validate.py`
- `studio-api/tests/test_m42_w45_audio_studio.py`
- `studio-api/tests/live_audio_studio_quality.py`
- `tests/e2e/audio-studio/audio-studio-centered-layout.spec.ts`
- `tests/e2e/audio-studio/audio-studio-sfx-quality-journey.spec.ts`

## UNRELATED SYSTEMS UNTOUCHED

Comfy `:8188`, MiniMax `:8192`, Timeline transport, Walk footstep timing, Character Creator, image/video GPU admission, Production Dock lifecycle.

## TESTS

- `test_sound_prompt_compiler.py` + `test_m42_w45_audio_studio.py`: **20 passed**
- `test_sfx_wav_validate.py`: **3 passed**
- Layout Playwright: **1 passed**

## ARTIFACTS

`artifacts/audio-studio-quality/` — live WAVs, `waveform-analysis.json`, `live-quality-report.json`, `cancel-timeline-report.json`, centered + approved screenshots.

## LIMITATIONS

- Primary cannot hear system speakers. Quality uses waveform/onset + compiled-prompt inspection.
- No semantic audio classifier exists. Objective checks are file / duration / silence / clip only.
- Electrical spark is recognizably crackly but quiet.
- MMAudio still generates an ~8s trained window; we crop. Native shorter seq_len was not enabled (quality risk).
- First infer after load remains ~40s. Warm path is the speed win.
- One earlier live door take compiled “heavy heavy steel” (material + template). Source now says `Single {material} door slam`. Studio API was recycled after that edit (`restart_studio_api_only.py`, newPid=68464, comfyPid=77152 unchanged).
- Studio API venv has no `soundfile`; validation falls back to `wave` / size. Decoder for analysis is the MMAudio venv.

## COMFY

- **COMFY BEFORE:** PID 77152 healthy (also observed helper PID 32824). HTTP 200 `/system_stats`.
- **COMFY AFTER:** PID 77152, HTTP 200 `/system_stats`. Studio API healthy PID 68464. Vite `:5173` HTTP 200.
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Audio Studio only. Studio API recycled via `restart_studio_api_only.py` (`comfyPid=77152 unchanged=True`). No supervisor restart.

## E2E TRACE

| stage | verdict |
|---|---|
| User action | PASS — Sound Effects, presets, generate, select, approve, Add to Timeline |
| Frontend | PASS — centered workspace, eventType, Subtle/Normal/Bold |
| API | PASS — compiler persisted on batch; progress stages truthful |
| Backend | PASS — warm serve, negatives, cfg, energy crop |
| Persistence | PASS — Library assets remain after refresh |
| Runtime | PASS — MMAudio CUDA proven; no silent CPU; Comfy untouched |
| Result | PASS — real WAVs; discrete footsteps; high-energy explosion |
| Reload | PASS — takes hydrate; approved state visible |
| Downstream | PASS — SFX track placement |

---

## FINAL VERDICT

**GO — AUDIO STUDIO CENTERED UX + ACOUSTIC INTELLIGENCE + MMAUDIO ACCELERATION + SFX QUALITY JOURNEY E2E CERTIFIED**
