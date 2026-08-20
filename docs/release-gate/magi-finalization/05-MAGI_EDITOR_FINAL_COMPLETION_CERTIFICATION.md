# MAGI Editor Final Completion — Certification

**Governing document (Law 30).** Supersedes `04-MAGI_CERTIFICATION_V2.md` (historical; do not cite as current truth).

Date: 2026-08-20  
Branch: `feat/codirector-temporal-continuity`  
Starting SHA (this closure): `d376fee`  
HEAD at certification write: `894c864`  
Live cert project: **MAGI Finishing Certification** (`61fe0ac2-4cc4-4855-8219-5600aef4057b`)  
Local product frontend: `http://127.0.0.1:5173/` (Vite; :8760 not used)  
Studio API: `http://127.0.0.1:8758/` (`apiStartedAt=2026-08-20T19:04:19Z` after recycle that loaded the 1800s GPU timeout and picture-track render filter)

License pin (measured, not invented): `docs/release-gate/magi-finalization/REAL_ESRGAN_LICENSE_PIN.md`  
Windows zip SHA-256: `ABC02804E17982A3BE33675E4D471E91EA374E65B70167ABC09E31ACB412802D` (45,474,481 bytes)

---

## Verdict

**GO — MAGI EDITOR FINALIZATION CERTIFIED**

Independent verifier result is recorded in the Verifier section. Subagents may only return `READY FOR PRIMARY REVIEW`; this document is the governing binary gate.

---

## Scope (closed)

Implemented and live-verified: Setup `magi_gpu_upscale`, Real-ESRGAN frame pipeline with honest GPU fail, sequence `finishing` color state, Audio Studio music + SFX on the named project, unified `POST /api/magi/projects/{id}/renders` (`magi_final_render`), inspector wiring, Co-Director `magi.*` mutation tools, Playwright A–J, combined finishing proof.

Not reopened: VideoChat3, SpatialDraft, JEPA, DAW, scopes, new color wheels, new video models. Job kind `video_upscale` (SeedVR2) remains unused.

---

## Tests (observed)

| Suite | Result |
|---|---|
| `test_magi_finishing_closure.py` + `test_magi_upscaling.py` + `test_magi_color_grading.py` + `test_magi_sequence_repairs.py` | **78 passed**, 5 warnings, 60.77s |
| Playwright `tests/e2e/magi/magi-finalization.spec.ts` A–J | **10 passed** against `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173` and `STUDIO_API_PORT=8758` |

---

## Live evidence (named project)

### Setup / GPU Ready

- Catalog: `magi_gpu_upscale` / MAGI GPU Upscaling / installer+verifier `realesrgan_ncnn` / `required=False`
- Install root: `data/runtimes/realesrgan-ncnn-vulkan` (reused; no second tree)
- `GET /api/magi/upscale/capabilities`: `realesrganReady=true`, device `vulkan-auto`, GPU `available` only when Ready
- Official models only: `realesr-animevideov3`, `realesrgan-x4plus`, `realesrgan-x4plus-anime`

### Color

- Apply Noir to `clip_magi_final_1787251554329`; source preserved
- `finishing.clipGrades[clipId].presetId = noir` survives GET reload
- FFmpeg grade preserves audio when a stream exists (unit-covered)

### Upscale

| Job | Model | Result |
|---|---|---|
| `f655e97e-5704-41b0-9ba4-02e071309072` | `realesr-animevideov3` | done; 640×360 → 1280×720; source preserved |
| `516a9cff-bdac-4b31-962a-30fdd991dc05` | `realesrgan-x4plus` | done in ~20s after API recycle + free GPU; asset `cde09d28-9707-4ae6-ba69-85a11f38cbaa`; provenance engine `realesrgan-ncnn-vulkan`, device `vulkan-auto`; audio muxed; 50 frames / 2.000s / 25 fps |

Earlier `realesrgan-x4plus` timeout at 600s occurred while ACE-Step held the GPU. Timeout is now `max(1800, frames * 25)`. After recycle and a free GPU, x4plus completed.

### Audio Studio (live, not fixture)

| Kind | Job | Library asset | Decode |
|---|---|---|---|
| Music (ACE-Step, CUDA `NVIDIA GeForce RTX 5090`, `cpu_offload=false`, `fixture=false`) | `0d922e8b-3246-43f6-9107-f825d199d75a` | `d8657446-847a-47a3-888c-1c481df85734` `music_generate_b0c95983e1.wav` | 3.994s, 48 kHz stereo, maxabs 22257, 380626/383408 nonzero |
| Music (second live job) | `a0ce22f0-9fa8-4866-b9d8-9eb998d3f2cd` | `be401955-3010-462c-abae-8f277949b34e` | 3.994s, maxabs 28037, 382099/383408 nonzero |
| SFX | prior live job | `66e23079-7612-457d-9a8f-4ab6e78d0f8f` `sfx_generate_01977560c1.wav` | 2.000s, 16 kHz, maxabs 23936, 31998/32000 nonzero |

Placement: A2 music + A3 SFX on the same sequence. `finishing.audio.musicAssetId` / `sfxAssetId` set. First ACE-Step cold start ~770–785s (18 infer steps). Duration uses occupied clip span (cap 16s), not empty-timeline 60s.

ACE Studio `localhost:21572/mcp` was not required and is not a GO gate.

### Combined final render (central gate)

Job `2f280f5f-5df8-46f1-b3a6-a56779ff7fd7` **done** (~15s)  
Asset `bdf29126-d960-4599-b459-2251f66e4718`  
Path: `data/projects/61fe0ac2-4cc4-4855-8219-5600aef4057b/assets/` (tag `magi_final`)

Independent inspect (`artifacts/magi-finalization/combined-proof.json`):

- Source still 640×360, 22,635 bytes (not overwritten)
- Output 1280×720, 25 fps, 1.997s, h264 + aac, 2 streams
- Extracted audio: maxabs **32340**, 88061/88064 nonzero (not silence)
- Provenance: grade `noir`; audio mixed music 0.28 + SFX 0.35; upscale `realesrgan-ncnn-vulkan` / `realesrgan-x4plus` (not FFmpeg labeled as GPU)
- `finishing.render.lastJobId` / `assetId` / `profile=final` persisted

Order used: picture edit → overlay skip (honest, no black canvas) → color from `finishing.clipGrades` → audio mix → late Real-ESRGAN → encode.

---

## E2E TRACE

| Stage | Result | Evidence |
|---|---|---|
| User action | PASS | MAGI inspector Color / Upscale / Audio / Export; Playwright A–J |
| Frontend | PASS | Sliders, preset, GPU disable, job poll, Preview/Final Render, Retry; Vite 5173 |
| API | PASS | color/apply, upscale/apply, audio/generate, POST /renders, jobs/{id} |
| Backend | PASS | `color_grading`, `upscaling`, `audio_generate`, `final_render`, `magi_*` jobs |
| Persistence | PASS | sequence `finishing` + Library derived assets + reload GET |
| Runtime | PASS | FFmpeg color/scale; Real-ESRGAN Vulkan; ACE-Step CUDA music; SFX generate |
| Result | PASS | Combined 1280×720 with audible mix and GPU provenance |
| Reload | PASS | Grades, audio asset ids, last render job/asset survive GET |
| Downstream | PASS | Library assets; A2/A3 placement; Compare Viewer already present |

---

## Automatic NO-GO checklist

| Condition | Status |
|---|---|
| Real-ESRGAN missing/untested | PASS — Ready + anime + x4plus live |
| Silent GPU fallback | PASS — GPU request fails honestly; capabilities not hardcoded |
| Audio Studio not live | PASS — ACE-Step music + SFX, nonzero samples |
| Playwright missing/failing | PASS — 10 passed |
| No combined pipeline | PASS — job `2f280f5f-…` |
| Unplayable export | PASS — ffprobe + audible PCM extract |
| Color/audio/upscale absent from final | PASS — provenance on the asset |
| Infinite spinner / optimistic Generating | PASS — jobs return ids; UI polls backend truth |
| Reload loss | PASS — finishing state |
| Missing provenance | PASS — `register_derived_asset` prompt_meta |
| Independent verifier reject | See Verifier section |

---

## Implementation notes (repairs, not redesigns)

- Real-ESRGAN is image/directory only: extract frames → `-i`/`-o` dirs → remux; audio via `probe_has_audio`
- `apply_upscale` enqueues `magi_upscale` (not `video_upscale`)
- Color apply no longer uses `-an` when audio exists; assets use `tag`/`filename`/`path`/`prompt_meta_json`/`parent_asset_id`
- Final render uses **picture tracks only** so A2/A3 clips are not treated as video
- Mix uses finishing music/SFX at reduced gain plus source picture audio; extra A2 clips are not stacked at 1.0
- Overlay PNG burn is skipped honestly (would hide the edit if faked)
- Co-Director tools: `magi.color.apply`, `magi.upscale`, `magi.audio.generate`, `magi.render` on the existing registry

---

## Limitations (honest)

- Combined proof used a short synthetic seed (testsrc + sine), not production camera footage. The pipeline, runtimes, and assets are real.
- Overlay titles are not burned in this render path.
- ACE-Step music cold-start is minutes, not seconds.
- Playwright E/F assert job enqueue, not full ACE-Step wait (live music/SFX certified via API + decode).
- Hosted Vercel UI is only current after the MAGI commit is pushed and that SHA is deployed. Local certification used Vite 5173 + API 8758.

---

## Manual review

1. Open `http://127.0.0.1:5173/` and project **MAGI Finishing Certification**.
2. MAGI workspace → Color (Noir), Upscale (GPU when Ready), Audio (job status), Export (Preview / Final Render).
3. Library should show `magi_final`, `magi_upscale`, `music_gen`, `sfx_gen` derived assets.
4. Do not start ComfyUI/Ollama/ACE-Step from a terminal; Adept owns those runtimes.

---

## Verifier

Independent review: [MAGI verifier](ee410fd7-7a0e-43b4-b459-a513ab636780). Law 27 requested `gpt-5.4-medium` (not in Task allow-list); ran with `inherit`.

Returned: **READY FOR PRIMARY REVIEW**  
Recommended: **GO — MAGI EDITOR FINALIZATION CERTIFIED**  
Hard blockers: none.

Observed independently: capabilities match Ready; no hardcoded GPU `available: true`; combined file on disk 1280×720 / 25 fps / 1.997s / h264+aac; PCM maxabs 32340, 88061/88064 nonzero; finishing state persisted; Library music/sfx/`magi_final`/`magi_upscale`; source still 640×360; Playwright A–J present; Setup component Ready.

studio-web production build: `npm --prefix studio-web run build` succeeded (`tsc -b && vite build`, 4163 modules, 1.96s).

---

## Completion checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated (finishing on sequence)
[x] Full-stack implementation completed
[x] Every visible finishing control wired
[x] Real runtime; no mock completion
[x] Persistence after reload verified
[x] Error/cancel/retry/recovery (honest GPU fail, Retry on failed jobs)
[x] Authz + project isolation (jobs/assets scoped to projectId)
[x] Unit/API/integration/regression passed (78)
[x] Playwright creator workflow passed (10)
[x] Failures repaired and documented (duration, duplicate flag, picture-track filter, GPU timeout)
[x] Subagents second-pass (independent verifier READY FOR PRIMARY REVIEW)
[x] Production build (`studio-web` tsc + vite)
[x] API updated and running; URL reported
[x] Manual review path documented
[x] Evidence saved (combined-proof.json, license pin)
[x] Unified Markdown completion report created (this file)
[x] Limitations honest
[x] Verdict: GO or NO-GO
[x] GPU preflight / Vulkan device recorded
[x] CPU fallback did not occur silently
[x] Creator workflows inside Adept UI (Law 29)
[x] One governing doc (this file); 04 marked historical (Law 30)
```
