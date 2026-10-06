# Avatar Studio Correction Pass — Library Picker / Character Voice / Footer UX

**Date:** 2026-08-18  
**Branch:** `feat/movement-segments`  
**Starting SHA:** `06db6b08a017f298dc4340deea166814e57104bd`  
**Certification commit:** `c7280c54e0aacc5384178aa3cb05ee334acd8e28`  
**Project:** Schnick Coffee (`2347bf46-3762-4763-86c5-4a6032522278`) — never `POST /api/projects`  
**Session:** `avs-a10ef709c2` (Anadriya Presenter Session)  
**Law 27:** GPT 5.4 is not in the Task allowlist. Subagent C used **inherit**. C does not issue GO/NO-GO.  
**Law 30:** This is the **single governing report** for this correction pass. It does **not** overwrite `CODIRECTOR_AVATAR_STUDIO_ORCHESTRATION_CERTIFICATION.md` (that milestone remains historically NO-GO on live Co-Director chat).

Compact MAIN is unchanged: Source → Avatar Source Frame / Speaker / Dialogue / Voice / Generator / Aspect / Generate / Advanced. Source modes stay Character / Library Image / Still / Video. InfiniteTalk, LongCat, Movement, Timeline, Mini, and LoRA were frozen.

---

## Verdict

**GO — AVATAR LIBRARY PICKER / CHARACTER VOICE / FOOTER UX CERTIFIED**

---

## Principal live proof (Schnick)

```text
Source = Library Image
Avatar Frame = 8516a27b-4b5f-4a75-99b9-63ca33777aa6
Speaker = Korri (c49371ed-ba6b-4c16-ba98-a8b28b72118b)
Voice = Character
```

Observed on live GET `/api/projects/{SCHNICK}/avatar-sessions/avs-a10ef709c2` after Playwright Save Draft (updated_at `2026-08-19T02:34:00.693060Z`):

| Field | Value |
|---|---|
| `source_kind` | `library` |
| `source_still_asset_id` | `8516a27b-4b5f-4a75-99b9-63ca33777aa6` |
| `mode_kind` | `single` |
| `voice_mode` | `character` |
| Speaker A | Korri, `voice.mode=character`, no take ids |
| Preview | that Library still (not a character sheet) |
| Missing voice | creator copy + **Open Voice Studio**; footer chip **Character voice needed** |

Co-Director session-truth (not live chat): `POST /api/codirector/projects/{SCHNICK}/tools/read` `avatar.inspect` returned `sourceKind=library`, `sourceAssetId=8516a27b-…`, `voiceMode=character`. Evidence: `docs/release-gate/avatar/evidence/library-voice-inspect-preferred.json`.

---

## What shipped

### 1. Visual Library Image picker

Reuse `CharacterReferenceAssetPicker` (`variant="avatar-frame"`). Title **Choose Avatar Frame**. Confirm **OK**. Images only. Approved-first sort (`sortLibraryImagesForAvatarFrame`) without hiding unapproved stills. Thumbnail click is local until OK writes `source_still_asset_id` and keeps `source_kind` library/still. Compact label **Avatar Frame · {name}**. Still `<select data-testid="avatar-source-still">` is visually hidden. Stale non-image: “That Avatar Frame is not an image. Choose another frame.” Character Creator copy stays “Choose a Reference Image”.

Assigning Speaker=Korri no longer jumps to another Korri session (bind prefers the open session), so the Library frame is not replaced by a character sheet.

### 2. Voice = Character

Voice dropdown: None / **Character** / Approved / Audio file (conversation: Voice A / Voice B). Persist `voice_mode` and `speakers[].voice.mode`. Missing mode on old sessions infers approved/file/none — **never Character**. Resolve via M4.10 `approvedVoiceOptions` / `resolve_character_voice_take` for that speaker only. Missing take: `{Name} does not have a configured character voice.` + **Open Voice Studio**. No silent None, no copy of the other speaker’s take.

CD: `avatar.create_plan` / `avatar.create_job` accept `voiceMode` / `speakerAVoiceMode` / `speakerBVoiceMode`. Inspect reports `voiceMode`. Intent “character voice” / “avatar frame” / “library image” routes to `avatar.configure`.

### 3. Footer / review dark restyle

Scoped under `.avatar-studio` only: preview summary chips, `.avatar-review-card` / `.avatar-take-card`, selected tab `avatar-tab-selected`, Next Best Step buttons. Cream `#dce8e2` / `#d7e4de` no longer shows in Avatar footer. Character Creator, Spatial, Timeline, and Co-Director chrome were not restyled.

---

## Tests

| Layer | Result |
|---|---|
| Vitest `compact.test.ts` + `assetModel.test.ts` | **57 passed** |
| Vitest `types.test.ts` | **11 passed** |
| pytest `test_avatar_compact_speakers.py` + `test_codirector_avatar_orchestration.py` | **23 passed** |
| Playwright `tests/e2e/avatar/avatar-library-voice-footer.spec.ts` | **1 passed** (36.3s) on live Beta Schnick |

Playwright used `PLAYWRIGHT_BROWSERS_PATH=C:\Users\bradj\AppData\Local\ms-playwright`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`, `STUDIO_API_BASE=http://127.0.0.1:8758`. Spec forces single-speaker mode before `avatar-voice-mode` because the preferred session hydrates as conversation.

---

## Subagent C

[Subagent C](15d41e7e-7aa7-4095-970d-99b1bdca313e) — **inherit**. Verdict: **READY FOR PRIMARY REVIEW**. C does not issue GO/NO-GO.

| # | Line | C |
|---|---|---|
| 1 | Visual Library picker: 3-col, Choose Avatar Frame, OK/Cancel | PASS |
| 2 | OK writes `source_still_asset_id`; preview is that still | PASS |
| 3 | Images only; approved-first; unapproved visible; stale non-image CTA | PASS |
| 4 | Voice=Character persisted as mode; missing ≠ Character | PASS |
| 5 | Resolve / missing CTA / no silent None / no cross-speaker copy | PASS |
| 6 | Speaker change re-resolves; A/B isolation | PASS |
| 7 | PATCH/GET + `create_plan` `voiceMode`/`sourceAssetId` + job Library frame | PASS |
| 8 | Playwright Schnick + `avatar.inspect` session-truth | PASS |
| 9 | Footer/tabs dark restyle under `.avatar-studio` | PASS |

---

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Source=Library Image → Choose Image → 3-col picker → OK; Speaker=Korri; Voice=Character; Save Draft |
| Frontend | PASS | `avatar-frame-picker`, `avatar-preview-still` `data-asset-id`, `avatar-voice-mode=character` |
| API | PASS | PATCH session `source_still_asset_id` + `voice_mode=character`; GET after reload |
| Backend | PASS | `avatar_studio` persist + `_infer_voice_mode`; `apply_create_plan` voiceMode |
| Persistence | PASS | Reload keeps library + Character; GET `avs-a10ef709c2` |
| Runtime | N/A | Generate / InfiniteTalk frozen this pass |
| Result | PASS | Preview = Library still `8516a27b-…`; Voice=Character missing-take CTA (Korri has no M4.10 take) |
| Reload | PASS | Playwright reload asserts source/voice/preview id |
| Downstream | PASS | `avatar.inspect` packet matches session. Live Co-Director **chat** not used (prior Beta chat was Degraded; this pass’s session-truth is inspect / create_plan) |

Independent verifier (C): **READY FOR PRIMARY REVIEW**. Primary: **GO**.

---

## Beta (left running)

| Service | URL | Observed |
|---|---|---|
| Creator UI | http://127.0.0.1:8760/ | HTTP 200 |
| Web health | http://127.0.0.1:8760/__beta_web_health | HTTP 200 |
| Studio API | http://127.0.0.1:8758/api/health | HTTP 200, `apiRevision=06db6b0`, `apiStartedAt=2026-08-19T02:21:40Z` |

ComfyUI `:8188` was **not** recycled. Studio API-only recycle earlier this day used `Restart-AdeptBetaBackend.ps1 -Service studio_api -Force` (not `Stop-AdeptUI-Beta.ps1`).

---

## Manual review path

1. Open Schnick Coffee at http://127.0.0.1:8760/ → Avatar Studio → session **Anadriya Presenter Session** (`avs-a10ef709c2`).
2. Source = **Library Image** → **Choose Image** / **Change Image** → 3-column **Choose Avatar Frame** → pick a still → **OK**. Preview must be that still.
3. Force **single** speaker if Voice is hidden. Speaker = **Korri**. Voice = **Character**.
4. Expect Korri missing-voice copy + Open Voice Studio (Korri has no configured take). Footer Voice chip: **Character voice needed**.
5. Save Draft, refresh. Source, frame, and Voice=Character must survive.

---

## Limitations (honest)

- Live Co-Director **chat** was not recertified this pass (previously Degraded / “stopped before finishing”). Session-truth is `avatar.inspect` / `create_plan`. That does **not** clear the separate orchestration-chat NO-GO.
- Korri has no M4.10 approved take on Schnick; Character mode correctly shows the missing-voice CTA rather than a resolved audio asset.
- InfiniteTalk remains `repair_required`. This pass did not generate a talking-head movie.
- Cursor working copy may also contain unrelated Movement / Timeline / Mini / Scene Generation hunks. They were **not** staged. `definitions.py` commit is Avatar tools only (`open_studio`, compact plan/job params including `voiceMode`, `detect_speakers`).

---

## Files in this commit

- `studio-web/src/components/CoDirector/characters/CharacterReferenceAssetPicker.tsx`
- `studio-web/src/components/CoDirector/characters/characterCompact.css`
- `studio-web/src/components/CoDirector/library/assetModel.ts`
- `studio-web/src/components/CoDirector/library/assetModel.test.ts`
- `studio-web/src/components/AvatarStudioCreatePanel.tsx`
- `studio-web/src/components/AvatarStudioWorkspace.tsx`
- `studio-web/src/styles.css`
- `studio-web/src/avatar/compact.ts`
- `studio-web/src/avatar/compact.test.ts`
- `studio-web/src/avatar/types.ts`
- `studio-api/app/avatar_studio.py`
- `studio-api/app/codirector/tools/handlers/avatar_m412.py`
- `studio-api/app/codirector/tools/definitions.py` (Avatar tools only)
- `studio-api/app/codirector/routing/unified_intent.py`
- `studio-api/tests/test_avatar_compact_speakers.py`
- `studio-api/tests/test_codirector_avatar_orchestration.py`
- `tests/e2e/avatar/avatar-library-voice-footer.spec.ts`
- `docs/release-gate/avatar/AVATAR_LIBRARY_VOICE_FOOTER_CORRECTION.md`
- `docs/release-gate/avatar/evidence/library-voice-footer-tabs.png`
- `docs/release-gate/avatar/evidence/library-voice-footer-summary.png`
- `docs/release-gate/avatar/evidence/library-voice-inspect-preferred.json`
- `docs/release-gate/avatar/evidence/library-voice-latest-session.json`
