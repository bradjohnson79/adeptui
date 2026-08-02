# M4.10 — Voice Performance Studio + IndexTTS2 Certification

## Identity

| Field | Value |
| --- | --- |
| Starting branch | `feature/m4-8-m4-9-cinematic-image-storyboard` |
| Starting SHA | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| Feature branch | `feature/m4-10-voice-performance-index-tts2` |
| Implementation SHA | `91443db0e1b93aa3b260410b41db0b0419594c14` |
| Commit strategy | M4.10-scoped only (see Shared-file notes) |
| Adept UI version | Beta local (`8760` / `8758`) |
| Voice Studio version | M4.10 Voice Performance Studio |
| Voice Identity schema | Character Identity `VoiceProfileRow` (Qwen Stage 1) |
| Voice Performance schema | `voice_performance_records` / `voice_performance_takes` (M4.10) |
| IndexTTS2 runtime version | `m4.10-index-tts2` |
| IndexTTS2 git revision (pinned) | `13495845e3028f0bb6ca1462ad22aa0e76349e40` |
| IndexTTS2 model | `IndexTeam/IndexTTS-2` (official HF) |
| Install mode | `full` (`confirm=true`, `confirm_download_models=true`) |
| Torch / CUDA | `2.8.0+cu128` · `cuda:0` |
| GPU / VRAM | RTX 5090 · ~32 GB total (beta health) |
| Qwen Voice Identity under test | `f53ac2b6-aa00-4700-a7b3-a740d1b631d7` v1 · character `7337605b-8fb3-46ec-a66c-de5dec4f5360` · project `e32dae30-a014-4ea4-a2f2-69f4b7809bde` |

## Architecture

- **Qwen3-TTS** owns Voice Identity. IndexTTS2 never mutates identity (verified unchanged after live generation).
- **IndexTTS2** (`index-tts2-local`) is the exclusive Voice Performance engine under `data/runtimes/index-tts2/`.
- **Co-Director** proposes editable plans; **Manual Direction** preserves separate state.
- Creator approval is mandatory before Timeline / Lip Sync handoff.
- Product install now requires explicit `confirmDownloadModels` (never silently true).

## Feature Matrix

| Feature | Status | Evidence |
| --- | --- | --- |
| Qwen Voice Identity preserved | PASS | Before/after identity IDs match in `artifacts/m410/live-go-cert.json` |
| IndexTTS2 catalog + Source Manager | PASS | `confirmDownloadModels` UI + API; catalog IndexTTS2 entry |
| Runtime install + health | PASS | Manifest `status=ready`; torch CUDA probe OK |
| Co-Director performance plan | PASS | Live plan + Take 1 |
| Manual Direction | PASS | Take 3 |
| Emotion vectors (Advanced) | PASS | Take 2 advanced mix |
| Emotional-reference audio | PASS (wired) | Path wired; not separately exercised in this live run |
| Multiple takes | PASS | 3 completed WAV takes |
| Take comparison | PASS | `compare` payload in live cert |
| Approval | PASS | `75f80eef-7351-4a7c-894f-1ea7d9cef74a` primary-approved |
| Scene dialogue batch | PASS | 2 line plans; `autoApproved=false` |
| Scriptwriter linkage | PASS | `scriptElementId` on records |
| Timeline handoff | PASS | Clip `f26bdab6-df13-4a38-acf7-f7e1918f7ecd` |
| Lip Sync handoff | PASS | Prepare payload persisted |
| Persistence | PASS | Reload covered by Playwright live |
| Live IndexTTS2 generation | **PASS** | Live cert + Playwright live (no skip) |
| Manual UX human stamp | **PENDING** | `M410_MANUAL_UX_CHECKLIST.md` unsigned |

## Live evidence

| Item | ID / path |
| --- | --- |
| Performance record | `209df85f-1d8b-44fc-b2c9-0af65ac7d31a` |
| Take 1 (approved) | `75f80eef-…` · asset `981d86c3-…` · 1706 ms |
| Take 2 | `e01e652b-…` · asset `f1a91b02-…` · 1509 ms |
| Take 3 | `992354ce-…` · asset `2595c8a1-…` · 1114 ms |
| Timeline clip | `f26bdab6-df13-4a38-acf7-f7e1918f7ecd` |
| Runtime root | `data/runtimes/index-tts2/` |
| Manifest | `artifacts/m410/runtime-manifest.json` |
| Live cert JSON | `artifacts/m410/live-go-cert.json` |

## Test Results

| Command | Outcome |
| --- | --- |
| `pytest studio-api/tests/test_m410_voice_performance.py studio-api/tests/test_m42_w44_voice_performance.py -q` | **23 passed** |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 npx playwright test tests/e2e/m410 --project=chromium --retries=0` | **3 passed** (live generate included) |
| `python scripts/voice_studio/m410_live_go_cert.py` | **GO_CANDIDATE** · 3 completed takes |

## Shared-file notes (M4.10-scoped commit)

Intentionally **not** staged in `91443db` because they contain large unrelated uncommitted integration deltas:

| File | Note |
| --- | --- |
| `studio-web/src/api.ts` | Contains `voicePerformanceM410` + install client in working tree |
| `studio-web/src/styles.css` | Voice Performance styles in working tree |
| `studio-api/app/codirector/tools/definitions.py` / `registry.py` | `voice.*` registration in working tree |
| `studio-api/app/setup/diagnostics.py` / `orchestrator.py` | IndexTTS2 installer hooks in working tree |
| `studio-api/app/scriptwriter/service.py` | `elementId` dialogue linkage in working tree |
| `studio-api/app/main.py` | Router mount in working tree |

`studio-api/app/setup/catalog.py` was **partially staged** (IndexTTS2 component only).

## Known Limitations

1. Human UX checklist is still unsigned — blocks full **GO**.
2. Emotional-reference take was not separately live-exercised in the GO cert script (wiring exists).
3. HF Hub downloads were intermittently connection-reset; completed via resume after core weights landed.
4. Shared wiring files remain uncommitted outside the M4.10-scoped SHA (working tree still carries integration surface).

## Verdict

**CONDITIONAL GO**

### Remaining blocker for GO

1. Human must review and sign [`M410_MANUAL_UX_CHECKLIST.md`](M410_MANUAL_UX_CHECKLIST.md) at 1366×768 / 1440×900 / 1920×1080 / 2560×1440.

All other GO criteria from the closure prompt are met: pinned install verified ready, live multi-take synthesis succeeded, Voice Identity unchanged, approval/Timeline/Lip Sync handoffs succeeded, Playwright live passed without skipping synthesis.
