# M5 Dock, Status, and Runtime Honesty Audit

## Run Context

- Audit timestamp: `2026-08-02T08:10:00Z`
- Branch: `feature/ai-guided-setup`
- Beta UI: `http://127.0.0.1:8760/`
- Beta API: `http://127.0.0.1:8758/`
- Scope owner: `M5.0 Subagent D — Dock, Status, Honest Status, Runtime Honesty`

## Fresh Live Evidence

### API probes executed

- `GET /api/production-control/gate`
- `GET /api/production-control/status`
- `GET /api/production-control/models?modality=video&action=generate`
- `GET /api/production-control/models?modality=image&action=generate`
- `GET /api/production-control/models?modality=audio&action=generate`
- `GET /api/production-control/models?modality=llm&action=chat`
- `GET /api/health`
- `GET /api/gpu/stats`
- `GET /api/setup/status`

### Key live facts

- Dock gate is live and passing: `/api/production-control/gate` returned `productionDockGo=true`, `verdict=GO`, `mock=false`.
- Setup status is live and currently reports `overall_status=ready`, counts `ready=35`, `not_installed=4`, `needs_attention=0`.
- The four live `not_installed` avatar motion runtimes are:
  - `longcat-video-avatar-1-5-local`
  - `infinitetalk-local`
  - `musetalk-1-5-local`
  - `echomimic-v2-local`
- Co-Director provider health is reachable in `/api/health`: provider `ollama`, `selectedModel=gemma4:31b-it-qat`, `reachable=true`.
- GPU probe is live in `/api/gpu/stats`: `NVIDIA GeForce RTX 5090`, CUDA visible, memory/utilization reported.
- Dock status is live in `/api/production-control/status`: hosted provider row is still `Requires Setup`, not silently upgraded.

## 1. Production Dock Gate And Setup Containment

| Surface | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `/api/production-control/gate` | PASS | `productionDockGo=true`, `verdict=GO`, `mock=false` | Dock shell is still gated by the production-control backend, not mocked. |
| Local model Install -> Setup containment | PASS | `studio-web/src/components/production-dock/ModelMenuDrawer.tsx` calls `openSetupWizard()` for `capabilityLabel === "Requires Setup"` | No competing installer action was found in the model row path. |
| Hosted API empty-state Setup containment | PASS | `ApiEmptyState` opens Setup via `openSetupWizard(projectId, "fal_key")` | Hosted-provider remediation stays inside Setup. |
| Competing installers in model menus | PASS | No live model-menu payload required a separate installer flow, and code paths route setup-needed entries into `buildAiGuidedSetupPath()` | This task found no competing installer button inside the dock model menus. |

### Containment conclusion

The dock gate is live and honest. Model-menu remediation stays routed into Setup rather than starting hidden installs. The current live payload did not surface any `Requires Setup` model rows to click through, so containment was verified through live API payloads plus the row action code path rather than a UI click recording.

## 2. Status Center Honesty Vs Setup Status

### Live status comparison

| Surface | Live value | Honest reading |
| --- | --- | --- |
| Setup overall | `ready` / `Ready to Generate` | Overall studio setup is considered sufficient for the current required baseline. |
| Setup counts | `35 ready / 4 not_installed / 0 needs_attention` | Optional runtimes still exist and must stay visibly not installed. |
| Avatar Motion components | all four motion runtimes are `not_installed` | Avatar motion must not be promoted to ready from the aggregate setup badge. |
| Production Dock hosted provider | `Requires Setup` in `/api/production-control/status` | Honest: hosted provider remains unconfigured. |

### Honesty bug fixed in this pass

The status strip was using probe-success wording that overstated what those probes actually prove:

- `Studio API Ready`
- `Provider Ready`
- `GPU Ready`

Those labels came from shallow availability/detection checks, not from end-to-end readiness or certification. This pass changed the strip to:

- `Studio API Online`
- `Provider Connected`
- `GPU Detected`

That keeps the visual affordance while removing false-ready language.

### Files changed

- `studio-web/src/components/dashboard/SystemStatusStrip.tsx`
- `studio-web/src/status/mapHealth.ts`
- `studio-web/src/status/status.test.ts`

## 3. Runtime Honesty Matrix

Unknown remains acceptable below when this pass did not freshly prove a dimension. No row is promoted to "ready" solely from presence.

| Runtime / provider | Installed | Running | Connected | GPU | Model | Provider | Version | Pinned | Certified | Last verified | Evidence / honesty note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Studio API | Yes | Yes | Yes | n/a | n/a | local API | Unknown | Unknown | Unknown | live `/api/health` probe | Honest label should be `Online`, not `Ready`. |
| ComfyUI | Yes | Yes | Yes | Unknown for generation jobs | multiple local stacks | local ComfyUI | `0.28.2` | Unknown | Unknown | `checkedAt` from `/api/health` | Reachable and enumerating devices/models, but this task did not certify a job run. |
| Co-Director / Ollama | Yes | Yes | Yes | Unknown | `gemma4:31b-it-qat` | `ollama` | Unknown | Unknown | No | live `/api/health`, `/api/setup/status` | Reachability is live; certification is still not implied. |
| IndexTTS2 | Yes | Unknown | Unknown | Unknown | `IndexTeam/IndexTTS-2` | local audio runtime | `13495845e3028f0bb6ca1462ad22aa0e76349e40` | Unknown | No | `2026-08-02T08:10:33.678083+00:00` | Setup component is ready, but this pass did not freshly execute audio generation. |
| Qwen3-TTS Voice Design 1.7B | Yes | Unknown | Unknown | Unknown | `qwen_voice_design_17b` | local voice sandbox | Unknown | Unknown | No | `2026-08-02T08:10:33.695592+00:00` | Setup says installed/ready; this pass did not re-prove the M410 runtime chain, so runtime fields remain unknown. |
| Qwen3-TTS Voice Clone 1.7B | Yes | Unknown | Unknown | Unknown | `qwen_voice_clone_17b` | local voice sandbox | Unknown | Unknown | No | `2026-08-02T08:10:33.708001+00:00` | Same honesty rule as Voice Design: do not invent runtime-ready from setup-only evidence. |
| Kie video providers | Yes | Yes | Yes | n/a | `seedance`, `kling` | `kie` | Unknown | Unknown | Yes in dock payload | live `/api/production-control/models?...video...` | Hosted rows are executable/selectable and marked `Certified` by the payload. |
| Hosted provider configuration | Unknown | Unknown | No | n/a | n/a | `automatic` preferred | Unknown | Unknown | No | live `/api/production-control/status` | Dock status still reports `Hosted Provider: Requires Setup`, which is honest. |
| LongCat Avatar 1.5 | No | No | No | Unknown | upstream runtime bundle | `longcat-video-avatar-1-5-local` | code rev `6b3f4b8582a8bc3f20f795735f5383716c4ba794` | Unknown | No | none (`last_verified_at=null`) | Live setup status is `not_installed`; must stay that way in UI. |
| InfiniteTalk | No | No | No | Unknown | upstream runtime bundle | `infinitetalk-local` | code rev `50aa0a94184315407a991ae804d9b58d6d311ba8` | Unknown | No | none (`last_verified_at=null`) | Live setup status is `not_installed`; must stay that way in UI. |
| MuseTalk 1.5 | No | No | No | Unknown | upstream runtime bundle | `musetalk-1-5-local` | code rev `0a89dec45a0192b824e3cf4daf96c239440c5ed8` | Unknown | No | none (`last_verified_at=null`) | Live setup status is `not_installed`; must stay that way in UI. |
| EchoMimicV2 | No | No | No | Unknown | upstream runtime bundle | `echomimic-v2-local` | code rev `38c86809efa041884c774ee31d984a9577c0e0aa` | Unknown | No | none (`last_verified_at=null`) | Live setup status is `not_installed`; must stay that way in UI. |

## 4. Avatar Motion Honesty Check

| Component | Live status | UI honesty requirement | Result |
| --- | --- | --- | --- |
| LongCat Avatar 1.5 | `not_installed` | Must not say ready | PASS |
| InfiniteTalk | `not_installed` | Must not say ready | PASS |
| MuseTalk 1.5 | `not_installed` | Must not say ready | PASS |
| EchoMimicV2 | `not_installed` | Must not say ready | PASS |

Additional code review result:

- `studio-web/src/components/AvatarStudioWorkspace.tsx` currently maps avatar runtime presentation to only three labels: `Experimental`, `Needs Repair`, or `Not Installed`.
- That means the Avatar Studio surface does not currently invent a creator-facing `Ready` label for motion runtimes.

## 5. Law 26 Note

Live GPU detection is not the same as GPU-certified workload execution.

This pass observed:

- `/api/gpu/stats` reports `NVIDIA GeForce RTX 5090`
- `/api/health` reports ComfyUI CUDA-visible devices
- `/api/production-control/status` reports local audio runtimes with CUDA metadata

But under Law 26, GPU-designated claims still require job-time proof:

- selected device
- CUDA/framework build
- model/tensor placement on GPU
- live VRAM/utilization during execution
- explicit fallback disclosure if CPU is ever used

Therefore this audit treats many GPU fields as `Unknown` unless the exact runtime chain was freshly executed in this pass.

## 6. Code Fixes And Verification

### Fix applied

- Status-strip wording now reflects probe scope instead of readiness claims.

### Tests

- `npm exec -- tsx --test src/status/status.test.ts` -> PASS (`4/4`)

### Build

- `npm run build` -> FAIL, unrelated pre-existing TypeScript error:
  - `src/setup/lifecycle/AiGuidedSetupPanel.tsx(57,3): error TS6133: 'projectId' is declared but its value is never read.`

This build failure was not introduced by the status honesty patch and was left untouched to avoid scope creep.

## Verdict For This Scope

- Dock gate honesty: PASS
- Model-menu Install -> Setup containment: PASS
- Status Center wording honesty: PASS after patch
- Avatar Motion `not_installed` honesty: PASS
- Runtime matrix honesty: PASS with explicit `Unknown` where fresh proof was not collected

`READY FOR PRIMARY REVIEW`
