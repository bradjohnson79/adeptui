# M4.10 Wave 0 Repository and Runtime Audit

## Audit Gate

| Field | Value |
| --- | --- |
| Mission | M4.10 Voice Performance Studio + IndexTTS2 |
| Repository | `C:\AdeptFilmWorks\AIVideoStudio` |
| Starting branch | `feature/m4-10-voice-performance-index-tts2` |
| Starting SHA | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| Lineage | `feature/m4-8-m4-9-cinematic-image-storyboard` → M4.10 |
| Audit mode | Wave 0 repository/runtime audit only |
| Verdict | **AUDIT_COMPLETE — GO for Wave 1** |

---

## 1. Starting identity

- Branch: `feature/m4-10-voice-performance-index-tts2`
- HEAD: `f758744168ec93f559d7fa0d9098ce47c39fe3ff`
- Carries M4.8/M4.9 cinematic image + storyboard work forward.
- Prior family audit: `docs/release-gate/m48-m49/M48_M49_REPOSITORY_AUDIT.md`

---

## 2. Voice Studio FE surfaces and IA gaps

### Current surface

- [`studio-web/src/components/CharacterProfileWorkspace.tsx`](../../../studio-web/src/components/CharacterProfileWorkspace.tsx) — Voice Studio tab inside Character Creator; legacy `voice` / `voicePerformance` aliases map here.
- [`studio-web/src/components/VoiceStudioWorkspace.tsx`](../../../studio-web/src/components/VoiceStudioWorkspace.tsx) — unified create / select / performance / approve / timeline flow.
- [`VoiceCreatorWorkspace.tsx`](../../../studio-web/src/components/VoiceCreatorWorkspace.tsx) / [`VoicePerformanceWorkspace.tsx`](../../../studio-web/src/components/VoicePerformanceWorkspace.tsx) — thin wrappers.

### IA gaps

1. Voice is nested under Character Creator, not a top-level Production surface.
2. `Approve Performance` in FE is largely local UI state; assembly approve API is underused.
3. No director-facing Emotion / Intensity / Delivery / Pacing / Breath / Emphasis plan UI.
4. No take comparison studio, emotional-reference upload, or Advanced emotion-vector panel.
5. Several M42 Playwright testids are stale vs current M43 shell.

---

## 3. Voice Identity (Qwen) — keep as Stage 1

Persistence lives in `character_identity`, not `voice_performance`:

- Models: `VoiceProfileRow`, `VoiceConsentRecordRow`, `CharacterProfileRow.active_voice_profile_id` / `continuity_json.voiceStudioDraft`
- Runtime: [`character_identity/voice_runtime.py`](../../../studio-api/app/character_identity/voice_runtime.py)
- Creator: [`character_identity/voice_creator.py`](../../../studio-api/app/character_identity/voice_creator.py)
- API: [`character_identity/api.py`](../../../studio-api/app/character_identity/api.py)
- Providers readiness: kokoro, qwenVoiceDesign, qwenVoiceClone

**Rule for M4.10:** Qwen remains Voice Identity only. Do not move identity controls into IndexTTS2.

---

## 4. `voice_performance` package today

| File | Role |
| --- | --- |
| `models.py` | `voice_performance_plans`, `voice_performance_assemblies` |
| `service.py` | create/generate/retry/assemble/place-on-timeline |
| `providers/qwen.py`, `kokoro.py` | translation wrappers only |
| `router.py` | `/api/voice-performance/*` |

**Critical finding:** `generate_segments()` selects `qwen3-tts` or `kokoro` and calls `run_generate_dialogue()`. There is no IndexTTS2 path. Performance and identity share the same synthesis runtime.

---

## 5. ZERO IndexTTS footprint (pre-implementation)

Repository-wide search: no `IndexTTS`, `index-tts`, or `index_tts` matches in code, catalog, Source Manager, or tests.

Official sources (verified for Wave 1):

| Item | Value |
| --- | --- |
| Official repository | https://github.com/index-tts/index-tts |
| Pinned git revision | `13495845e3028f0bb6ca1462ad22aa0e76349e40` (main @ 2026-07-14) |
| Official model | https://huggingface.co/IndexTeam/IndexTTS-2 |
| Provider id | `index-tts-local` → product id `index-tts2-local` |

Note: GitHub tag `v1.5.0` is IndexTTS 1.5, not IndexTTS2. Pin main HEAD above for IndexTTS2.

---

## 6. Co-Director voice tools

Exist under `voice_performance.*` and `character_creator.*` (readiness, parse, generate, compare_takes, approve_take, assemble, place_on_timeline).

Missing vs M4.10:

- Scene-aware `voice.create_performance_plan` / `voice.create_scene_performance_plan`
- Emotion-reference / preset / advanced mix mapping
- Lip Sync prepare tool
- Honest IndexTTS2 health in tool status

---

## 7. Scriptwriter dialogue IDs

- Stable: `ScriptElement.id` in `scriptwriter/models.py`
- Gap: `prepare_timeline()` emits `{ speaker, text }` without `elementId`
- M4.10 must carry `scriptDocumentId`, `scriptElementId`, `sceneId`, parenthetical, prev/next into performance records

---

## 8. Timeline dialogueTracks

`place_on_timeline()` writes `project.settings_json.timeline.dialogueTracks`. No active FE timeline renderer consumes this key. Placement is backend-persisted state.

---

## 9. Lip Sync gap

Voice performance writes dialogueTracks. Lip sync reads `scene.lipsync_audio_asset_id` / `scene.audio_asset_id` / director lipsync tracks. **No bridge exists.**

---

## 10. Model manager / catalog

Present: `qwen_voice_design_17b`, `qwen_voice_clone_17b` in setup catalog + Source Manager.

Missing: IndexTTS2 component, install/verify/repair/remove, Production Dock inventory entry.

---

## 11. Tests

| Suite | Status |
| --- | --- |
| `test_m42_w44_voice_performance.py` | Still useful for plan/assembly/timeline persistence |
| `m43-voice-studio.spec.ts` | Best aligned to current FE |
| M42 W43/W44 FE specs | Partially stale testids |

---

## 12. Trace (current)

```text
CharacterProfileWorkspace
  → VoiceStudioWorkspace
  → character_identity voice APIs / VoiceProfileRow
  → voice_performance create_plan / generate_segments
  → run_generate_dialogue (qwen3-tts | kokoro)
  → assemble → place_on_timeline → dialogueTracks
  ✗ Lip Sync (no handoff)
```

---

## 13. Extend vs leave-alone

### Extend

- `VoiceStudioWorkspace.tsx`, `voiceStudio/*`, `api.ts`
- `voice_performance/*` (new runtime, records, IndexTTS2 provider, lipsync prep)
- `setup/catalog.py`, `source_manager/voice_models.py`
- `codirector/tools/definitions.py`, `handlers/voice_performance.py`
- `scriptwriter/service.py` (elementId propagation)
- New: `docs/voice-studio/m4-10-voice-performance/*`, `docs/release-gate/m410/*`, `tests/e2e/m410/*`

### Leave alone unless thin hook required

- Broad rewrites of `queue_worker.py`, `director_timeline.py`, Production Menu IA
- Qwen identity creation UX (Stage 1 stays)

---

## 14. Risks and gate

1. No IndexTTS foundation — must add isolated runtime honestly.
2. Script line identity lost before performance.
3. Timeline dialogueTracks not wired to Lip Sync.
4. FE overstates approval completion.
5. Split model inventory (Source Manager vs Dock).
6. Stale M42 FE tests.

**Gate recommendation:** AUDIT_COMPLETE. Broad implementation may begin (Wave 1 runtime + persistence).  
**NO-GO** for any claim that IndexTTS2 or Lip Sync handoff already works until Waves 1–5 land and Wave 7 certifies.
