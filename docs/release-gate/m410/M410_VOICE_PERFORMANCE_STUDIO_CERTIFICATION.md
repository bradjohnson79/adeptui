# M4.10 — Voice Performance Studio + IndexTTS2 Certification

## Identity

| Field | Value |
| --- | --- |
| Starting branch | `feature/m4-8-m4-9-cinematic-image-storyboard` |
| Starting SHA | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| Feature branch | `feature/m4-10-voice-performance-index-tts2` |
| Final SHA | *(set after `feat(m4.10)` commit)* |
| Commit strategy | M4.10-scoped only (see Shared-file notes) |
| Adept UI version | Beta local (`8760` / `8758`) |
| Voice Studio version | M4.10 Voice Performance Studio |
| Voice Identity schema | Character Identity `VoiceProfileRow` (Qwen Stage 1) |
| Voice Performance schema | `voice_performance_records` / `voice_performance_takes` (M4.10) |
| IndexTTS2 runtime version | `m4.10-index-tts2` |
| IndexTTS2 git revision (pinned) | `13495845e3028f0bb6ca1462ad22aa0e76349e40` |
| IndexTTS2 model | `IndexTeam/IndexTTS-2` (official HF) |
| Qwen Voice Identity | Qwen3-TTS Design/Clone (unchanged Stage 1) |
| GPU / VRAM | RTX 5090 · ~32 GB (from beta health) |

## Architecture

- **Qwen3-TTS** owns Voice Identity (design, clone, approval). IndexTTS2 never mutates identity.
- **IndexTTS2** (`index-tts2-local`) is the exclusive Voice Performance engine via isolated runtime under `data/runtimes/index-tts2/`.
- **Co-Director** proposes editable performance plans (`voice.*` tools + UI Co-Director Recommended).
- **Manual Direction** preserves separate plan state when switching modes.
- **Creator approval** is mandatory before Timeline / Lip Sync handoff.
- If IndexTTS2 is not installed/ready, APIs report honest `not_installed` / `requires_setup` — no silent Qwen performance fallback presented as IndexTTS2.

## Feature Matrix

| Feature | Status | Evidence |
| --- | --- | --- |
| Qwen Voice Identity preserved | PASS | Identity tab + `character_identity` unchanged |
| IndexTTS2 catalog + Source Manager | PASS | `setup/catalog.py` `index_tts2`; `source_manager/voice_models.py` |
| Runtime health (honest) | PASS | `/api/voice-performance/m410/runtime/status` → not_installed until install |
| Co-Director performance plan | PASS | `m410_service.build_codirector_performance_plan` + `voice.*` tools |
| Manual Direction | PASS | FE mode switch + `set_direction_mode` |
| Emotion presets | PASS | `emotion_presets.py` + FE presets |
| Emotion vectors (Advanced) | PASS | Advanced collapsed by default; supported vectors only |
| Emotional-reference audio | PASS (wired) | Record field + passed as `emotionAudioPath` into IndexTTS2 worker |
| Multiple takes | PASS (code) | `create_takes` independent jobs; live gen blocked until install |
| Take comparison | PASS | `compare_takes` API + FE compare |
| Approval | PASS | Exclusive primary approve; alternatives retained |
| Scene dialogue batch | PASS | `create_scene_batch` + progression plans |
| Scriptwriter linkage | PASS | `prepare_timeline` now includes `elementId` + context |
| Timeline handoff | PASS | prepare + place with replace confirm |
| Lip Sync handoff | PASS | `prepare_lipsync` binds scene lipsync/audio assets |
| Persistence | PASS | SQLAlchemy M410 tables + unit tests |
| Live IndexTTS2 generation | NOT RUN | Runtime not installed on this host |
| Manual UX human stamp | PENDING | `M410_MANUAL_UX_CHECKLIST.md` |

## Test Results

| Command | Outcome |
| --- | --- |
| `PYTHONPATH=studio-api python -m pytest studio-api/tests/test_m410_voice_performance.py -q` | **7 passed** |
| `PYTHONPATH=studio-api python -m pytest studio-api/tests/test_m42_w44_voice_performance.py -q` | **13 passed** (with M410 suite: 20 passed) |
| `studio-web` `npm run build` | **passed** (per UX subagent) |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 npx playwright test tests/e2e/m410/* --project=chromium` | **2 passed, 1 skipped** (live gen skipped: IndexTTS2 not ready) |

### Playwright detail

- API contract: PASS (provider `index-tts2-local`, accent experimental, mixed_language not_recommended)
- Studio IA / identity gate / viewports: PASS
- Live generate → approve → timeline → lipsync → reload: **SKIPPED** (IndexTTS2 not installed)

## Evidence paths

- Audit: `docs/release-gate/m410/M410_REPOSITORY_AND_RUNTIME_AUDIT.md`
- Persistence: `docs/release-gate/m410/M410_DATA_AND_PERSISTENCE.md`
- Runtime docs: `docs/voice-studio/m4-10-voice-performance/`
- FE: `studio-web/src/components/voiceStudio/VoicePerformanceStudio.tsx`
- Runtime: `studio-api/app/voice_performance/runtime/index_tts2.py`
- E2E: `tests/e2e/m410/`

## Shared-file notes (M4.10-scoped commit)

Intentionally **not** staged in the milestone commit because they contain large unrelated uncommitted integration deltas (M4.8/M4.9 image/storyboard and earlier):

| File | Reason left unstaged | Working-tree dependency |
| --- | --- | --- |
| `studio-web/src/api.ts` | +3k lines mixed clients | Contains `voicePerformanceM410` + `confirmDownloadModels` install client |
| `studio-web/src/styles.css` | Mixed chrome/CSS | Contains Voice Performance Studio styles |
| `studio-api/app/codirector/tools/definitions.py` | +3k lines mixed tools | Contains `voice.*` tool defs |
| `studio-api/app/codirector/tools/registry.py` | Mixed handlers | Registers `voice_m410` handlers |
| `studio-api/app/setup/diagnostics.py` / `orchestrator.py` | Mixed installers | IndexTTS2 verify/install hooks |
| `studio-api/app/scriptwriter/service.py` | Untracked package surface | `elementId` dialogue linkage |
| `studio-api/app/main.py` | Mixed routers | Mounts `voice_performance` router |

`studio-api/app/setup/catalog.py` was **partially staged** (IndexTTS2 component only).

Runtime install contract fix in this closure: `RuntimeInstallBody.confirm_download_models` + Source Manager/UI acknowledgement (never defaults to true).

## Known Limitations

1. IndexTTS2 not installed on this machine — install via Source Manager / `POST .../m410/runtime/install` with `confirm=true` and `confirm_download_models=true`.
2. Accent consistency: **experimental**; mixed-language: **not recommended** until certified.
3. Live IndexTTS2 generation not certified in this gate run.
4. Manual UX checklist pending human stamp.
5. Full HF model download (~15GB) not executed in CI/agent session.
6. Production Dock model inventory still does not mirror Source Manager voice entries (pre-existing split).

## Verdict

**CONDITIONAL GO**

Conditions to upgrade to **GO**:

1. Install + verify IndexTTS2 at pinned revision; complete one live multi-take generation on a character with approved Qwen Voice Identity.
2. Re-run Playwright live flow (currently skipped) to PASS.
3. Human stamps `M410_MANUAL_UX_CHECKLIST.md`.

Architecture separation, Co-Director/Manual direction, persistence, Timeline/Lip Sync prepare, honest capability metadata, and UI IA are implemented and unit/API/UI-certified without live synthesis.
