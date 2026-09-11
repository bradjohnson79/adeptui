# Scene 10 — Dual Character Lip Sync Live E2E (Media Retake) — Unified Completion Report

**Date:** 2026-09-11
**Branch:** `feat/character-creator-final-closure` (starting HEAD `277f2424`)
**Mission:** Build a windowed media-retake executor (cut window segments → LatentSync per segment → splice → room-tone soundtrack rebuild → mux) and run the full live Scene 10 dual-character lip sync E2E against the user's 9 steps and 12 gates.
**Plan:** `scene_10_dual_lip_sync_retake_01e01c5a.plan.md` (executed as specified; deviations documented below)

---

## 1. Verdict

**GO — SCENE 10 DUAL CHARACTER LIP SYNC VERIFIED**

All 12 spec gates PASS with live measured evidence (§3); full-stack E2E trace PASS (§4); independent GLM 5.2 Max review verified all 8 claims and returned no blockers (§10); both reviewer repair items reconciled by the primary (§10).

## 2. Scope delivered

| Component | What shipped |
| --- | --- |
| `studio-api/app/media_retake/planner.py` | Pure window planner: clip-bounds validation, cross-track overlap rejection (`MediaRetakeOverlapError`), fit-or-fail (`FitError`, no silent atempo), donor-span selection (`DonorError`), per-window `roi` carry-through |
| `studio-api/app/media_retake/audio_rebuild.py` | Handle-aware ffmpeg filter-graph builder: old audio cut per window, new line at exact window start (`adelay={hl_ms}`), room-tone loop from Qwen donor span, RMS gain-match, 15 ms half-crossfade handles on shared boundaries (outside-window regions stay sample-aligned with the master) |
| `studio-api/app/media_retake/executor.py` | Job runner: cut segments (crf 16) → face-crop per window (`_face_crop_rect` from track ROI) → LatentSync on the **crop** → normalize → feathered-matte composite back onto the full-frame segment (`_build_composite_filter`) → single final splice encode → audio rebuild → mux AAC 32 kHz stereo → write `scene.lipsync_output_path` (master untouched) → Library asset + provenance → clips `status="synced"` |
| `studio-api/app/queue_worker.py` | New job kind `media_retake` dispatch (legacy `_dual_lipsync` untouched) |
| `studio-api/app/routers/api.py` | `POST …/lipsync-tracks/apply` gains `mode:"windowed"` (default `"legacy"` unchanged) + `roomToneStart/End`; **speaker-gate fix**: scene-column tracks merged via `attach_scene_lipsync` before `lipsync_speaker_errors` (previously validated `director_json` only — gate passed vacuously) |
| `studio-api/app/codirector/capabilities/handlers/analyze_video.py` | Resolver fix: `_resolve_scene_output_asset_id` prefers the Asset whose path == `scene.output_path`, wired first (Qwen previously watched the wrong batch take) |
| `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx` | **Plan deviation — required fix.** New step 3.5 in `resolvePreviewComposition`: `scene.lipsync_output_path` → `final_output` retake src, after library/failure/active-generation (those still win), before stitch/timeline-frame. Previously the playhead clip **always** won, so the canonical Preview Monitor showed the stale batch take instead of the retake |

## 3. The 12 gates (verbatim from the mission spec)

| # | Gate (verbatim) | Result | Evidence |
| --- | --- | --- | --- |
| 1 | LATENTSYNC LIVE NODE | PASS | `LatentSyncNode`, `D_LatentSyncNode`, `SyncLipSyncNode` HTTP 200 on `:8188`; 1 s smoke run proved weights + decord end-to-end before any mutation (`.runtime/_mr_preflight_evidence.json`) |
| 2 | QWEN SCENE WATCH | PASS | Qwen2.5-Omni watched the correct mastered take via `analyze.video` (packet `mip_3732fd1f5eb2`, resolver fix proved master-not-batch-take) + custom-question packet B (`.runtime/_mr_watch_packet_b.json`): timecoded face windows, baked dialogue spans, ambience map |
| 3 | FACE-VISIBLE WINDOW SELECTION | PASS | W1 Anadriya 0.1–2.9 s, W2 Korri 2.9–5.1 s from Qwen timecodes (not guessed from the prompt); mouth ROIs verified visually against master frames (`.runtime/_mr_frame_boxes2.png`) — first live attempt proved an initial ROI wrong (face-detect failure), corrected before the certifying run |
| 4 | VOICE ASSET GENERATION | PASS | Voice Performance path (`plans → compile → generate`), `qwen3-tts` approved clones: Anadriya "That's it - corridor's ours." 2.720 s (asset `a37cb212`, plan `9360788f`, voice version `5c221441`); Korri "Told you we'd walk out." 1.520 s (asset `10d93fed`, plan `7e4f0cd0`, voice version `283e8cf8`); durations fit windows (`.runtime/_mr_voice_lines.json`) |
| 5 | SPEAKER BINDING | PASS | Track 1 = Anadriya, Track 2 = Korri (track- and clip-level `character_id`); **unbound probe rejected live**: `400 LIPSYNC_SPEAKER_REQUIRED` ("Assign a character to this Lip Sync clip.") before binding (`.runtime/_mr_bound_tracks.json`) |
| 6 | PROMPT DIALOGUE SUPPRESSION | PASS | `compile_speech_windows` dump: 0.1–2.9 `lipsync_audio` (Anadriya), 2.9–5.1 `lipsync_audio` (Korri), no `prompt_dialogue` underneath (`.runtime/_mr_speech_windows.json`). Scene 10 has no `@token` cues (documented honestly); suppression proven by synthetic-cue unit tests (`test_timeline_prompt_refs_speech.py`, 10 tests incl. `test_lipsync_audio_beats_prompt_dialogue`) |
| 7 | BAKED AUDIO REPLACEMENT | PASS | Sample-level proofs (`.runtime/_mr_audio_proofs.json`): W1 corr(old dialogue)=0.067 vs corr(new line)=**0.761**; W2 corr(old)=0.007 vs corr(new)=**0.744**; outside windows (5.1–10.016 s) corr vs master = **0.9998**; RMS 0.116 (no dead silence); boundary max sample deltas 0.049–0.079 (no clicks). Old speech fully removed in windows; ambience/SFX/music outside windows bit-preserved; room-tone bed from Qwen donor span 5.4–8.4 s |
| 8 | DUAL-PASS PRESERVATION | PASS | **Structural**: pass 2's LatentSync input was only Korri's 346×256 crop — it physically cannot contain Anadriya's pixels; final audio built by the mix stage, never by LatentSync ("not last-pass-wins" by construction). Empirical: `.runtime/_mr_dualpass_proof.json` (pass-2 input identity, comp mtimes, window fidelity mean-abs-diff 7.12/10.45 = re-encode level) |
| 9 | ANADRIYA LIP SYNC | PASS | Qwen post-review: "Anadriya speaks first, saying 'That's it - corridor's ours'"; new-line correlation 0.761 @ 5 ms; retake frame 1.5 s shows Anadriya mouth open / Korri closed (`.runtime/_mr_retake_1_5s.png`) |
| 10 | KORRI LIP SYNC | PASS | Qwen post-review: "followed by Korri saying 'Told you we'd walk out.'"; new-line correlation 0.744 @ 5 ms; retake frame 4.0 s shows Korri mouth open / Anadriya closed (`.runtime/_mr_retake_4s.png`) |
| 11 | POST-RETAKE QWEN REVIEW | PASS | `.runtime/_mr_watch_packet_post.json`: correct speakers, correct lines, speech confidence 1.0, **zero visual/audio defects**, no old-dialogue collision, ambience preserved, no second-pass damage flagged |
| 12 | TIMELINE PERSISTENCE | PASS | API: fresh GETs show tracks + ROIs + clips (`synced`), `lipsync_enabled=1`, `lipsync_output_path` set. Playwright (system Chrome, headless): **6/6 checks** — Lip Sync track row shows Anadriya + Korri, Preview Monitor serves `scene_8_retake_a83cc6.mp4` (readyState 4, 1152×640, 10.04 s), reload persists both; 0 console errors, 0 page errors, 0 bad responses (`.runtime/_mr_pw_report.json`, screenshots `_mr_pw_lipsync_panel.png` / `_reloaded.png`) |

**Spec NO-GO conditions — all avoided:** real LatentSync ran (not sticky-mouth-only — sticky bake was never used as completion); audio proven intact by sample-level correlation; second pass structurally and empirically preserved the first.

## 4. E2E TRACE (Full-Stack E2E Law)

| Stage | Result |
| --- | --- |
| User action | Creator binds two lip-sync tracks in the Timeline Generator and applies (windowed mode) — PASS |
| Frontend | Lip Sync track row shows both tracks; Preview Monitor serves the retake (composer step 3.5) — PASS |
| Request | `PUT /lipsync-tracks` (bind) → `POST …/lipsync-tracks/apply {mode:"windowed", roomToneStart:5.4, roomToneEnd:8.4}` — PASS |
| API | Speaker gate validated merged scene-column tracks; job enqueued — PASS |
| Backend | `media_retake` job `2a90e9f9-236d-4576-8bdc-3ca6216c63fa` ran 190 s — PASS |
| Persistence | `scene.lipsync_output_path`, `lipsync_enabled=1`, clips `synced`, Library asset `201a1a5b` with full provenance + `parent_asset_id` → master — PASS |
| Runtime/Provider | LatentSync on Comfy `:8188` (cuda:0, RTX 5090) per window crop; qwen3-tts voice lines; Qwen2.5-Omni watch/post-review — PASS |
| Result | `scene_8_retake_a83cc6.mp4` — both new lines on the existing video, surrounding media intact — PASS |
| Reload | Playwright reload: tracks + retake preview persist — PASS |
| Downstream | Master `scene_8_65e7cdb1.mp4` SHA256 `289e2b91…` unchanged; retake registered as child asset — PASS |

## 5. Bugs found by live E2E and fixed (root cause → repair → regression)

1. **`_probe_video` stream selector** — requested `stream=r_frame_rate,width,height` without `codec_type`, so the `codec_type=="video"` filter never matched ("No video stream found"). Unit mocks never caught it. Fixed (`stream=codec_type,r_frame_rate,width,height`) + real-file regression test.
2. **`acrossfade` timeline desync** — 30 ms full crossfades overlapped inputs, shifting everything after each boundary ~30 ms early (outside-region correlation vs master ≈ 0 exposed it). Fixed with 15 ms half-crossfade handles; outside spans stay sample-aligned. Tests updated to handle-aware expectations.
3. **Initial mouth ROIs too high** — first live attempt: crop contained hair/shoulder → LatentSync face-detect exit 1. ROIs corrected from master-frame inspection (drawbox-verified) before the certifying run.
4. **analyze.video resolver watched the wrong take** — returned first batch take instead of the mastered output. Fixed (`_resolve_scene_output_asset_id` prefers the asset whose path == `scene.output_path`) + 2 regression tests.
5. **Canonical preview bypassed the retake** — `TimelinePreviewComposer` step 5 (playhead clip) always beat `lipsync_output_path`; the Preview Monitor showed the stale batch take. Fixed (step 3.5) + 3 regression tests. **This contradicts the plan's "no frontend changes needed" — the plan's research verified the preference existed in three files but missed the precedence bypass and the panel's reachability.**

## 6. Plan deviations (honest record)

- **Frontend change was required** (see §5.5). The legacy `LipSyncTracksPanel` is unreachable dead code in the current product (`showTracks=false`; `TimelineEditorShell` renders `DirectorTracks` with default `viewMode="tracks"`). The canonical creator surface is the Timeline Generator: Lip Sync track row + TimelineInspector + Preview Monitor. Playwright certifies that surface.
- **Known cosmetic issue (not fixed, out of scope):** the Co-Director pack wrapper marks an `analyze.video` execution pack FAILED under the zero-jobs law even though the analysis completes and persists (analyze.video returns `child_jobs: []` by design). Packet itself is intact.
- **Pre-existing failures excluded with proof:** backend `test_m42_w46_codirector_timeline.py` (2 failed — reproduced at a clean-HEAD worktree); frontend `TimelineToolbar.preflight.test.ts` (1 failed) and `generatorSupportsTemperature.test.ts` (no test suite) — both files byte-identical to HEAD, unrelated to this mission.
- **Vite served a stale `ProjectEditor.tsx`** transform for part of the session (missing `role="tab"` on the workspace tab strip — pre-existing HMR lag on this large repo; the watcher caught up between runs). Not a mission file; no action taken beyond verification that all retake-relevant served modules were current.

## 7. Test counts (exact, measured 2026-09-11)

- Backend mission suites: **49 passed** — `test_media_retake_planner` 10, `test_media_retake_audio` 15, `test_media_retake_executor` 7, `test_apply_windowed_gate` 5, `test_analyze_video_resolution` 2, `test_timeline_prompt_refs_speech` 10.
- Backend regression: **38 passed, 2 failed** — `test_m32f_lipsync_runtime` + `test_lipsync_character_identity` + `test_m42_w46_codirector_timeline` + `test_audio_studio_speech_act` (19 passed, 2 failed) + `test_director_timeline_audio_volume` + `test_editor_mix` (19 passed). The 2 failures (`test_guidance_priority_in_execution_snapshot`, `test_inpaint_mask_execute_approve_and_restore`) are pre-existing — reproduced at a clean-HEAD worktree.
- Frontend composer suite: **26 passed** (23 pre-existing + 3 new retake tests).
- Frontend timeline-master regression: **65 passed, 1 failed + 1 suite-less file** (`TimelineToolbar.preflight.test.ts`, `generatorSupportsTemperature.test.ts` — both pre-existing, byte-identical to HEAD).
- Playwright creator workflow: **6/6 checks passed**, 0 console errors, 0 page errors, 0 HTTP ≥ 400.

## 8. Runtime guardrails

- **COMFY BEFORE:** PID 45624, HTTP 200 (`/system_stats`, cuda:0 RTX 5090)
- **COMFY AFTER:** PID 45624, HTTP 200 — same process
- **COMFY RESTARTED?:** NO (ordinary build + live jobs only; API recycled once via `restart_studio_api_only.py` pattern after backend code shipped; Vite HMR covered the frontend change)
- **GPU provenance:** RTX 5090 `cuda:0` (live `system_stats`); LatentSync executed inside Comfy on `cuda:0`; qwen3-tts and Qwen2.5-Omni workers spawned on the same GPU host. No CPU fallback occurred.

## 9. Provenance (retake asset `201a1a5b-1255-43cb-9dbb-172f4cd64edf`)

`prompt_meta_json`: `mediaRetake:true`, `sourceMaster:"scene_8_65e7cdb1.mp4"`, both windows (clip ids, slots, character ids/names, audio asset ids, ROIs), `donorSpan {5.4–8.4}`, `models {lipsync: D_LatentSyncNode (ComfyUI_LatentSync), voiceProvider: qwen3-tts}`, `jobId`. `parent_asset_id` = master asset `92ff7c93-7016-4615-9075-e80bebcf567a`. Labels: `media-retake`, `lipsync`, `scene-8`.

## 10. Independent review

**GLM 5.2 Max independent review: all 8 claims VERIFIED, no blockers.** Master SHA256 re-hash matched exactly; live proof JSONs cross-checked clean; backend suites pass in logic; frontend vitest 26/26; legacy `dual_lipsync` path confirmed byte-identical to original.

**Primary reconciliation of reviewer notes:**

1. **Swallowed `try/except Exception: pass` around provenance graph edges** (`executor.py`) — **REPAIRED**: now `logging.getLogger(__name__).exception(...)` with a comment stating the canonical provenance record is `asset.prompt_meta_json` (committed regardless). Core Asset + provenance safety unchanged; edge loss is now diagnosable. `py_compile` clean; `test_media_retake_executor` 7/7 re-passed after the edit.
2. **Test-count reconciliation** — §7's **49 passed** is exact and stands. The reviewer ran 4 of the 6 mission files (34 tests) and missed `test_apply_windowed_gate.py` (5) and `test_timeline_prompt_refs_speech.py` (10). Primary re-ran all 6 files individually on 2026-09-11: 10 + 15 + 7 + 5 + 2 + 10 = **49 passed**. Combined-run caveat (unchanged): `test_analyze_video_resolution.py` shows 2 SQLite DB-path isolation errors when run in the same pytest process as the media_retake files; both tests pass in isolation — a test-harness quirk, not a product defect.
3. **Disclosures accepted and recorded**: hardcoded node `"2"` (`D_LatentSyncNode`) audio-injection index in `executor.py` (fragile if the LatentSync workflow's node numbering changes — the workflow builder is the single authority that emits it); `analyze_video.py` is a NEW previously-untracked file (the resolver fix certified in §5.4 lives in it), included in the mission commit with disclosure (§11).

## 11. Limitations / notes

- Qwen's timecodes are ±0.5 s rough; sample-level correlation is authoritative for timing.
- During active timeline **Play** on scenes that have a stitched scene clip, the stitch still wins the monitor (unchanged); the parked preview — the review surface — serves the retake. Scene 10 has no stitch asset, so Play also serves the retake there.
- The legacy whole-video `_dual_lipsync` path is unchanged (default `mode:"legacy"`).
- "Media retake" terminology adopted in code (`media_retake` job kind) and this report; Co-Director contract doc note about media-retake vs scene-regeneration deferred (optional docs edit, not required by the gates).
- The repo carries ~2900 pre-existing dirty/untracked entries from other missions; this mission's commit is focused to mission files only (staged-tree verification pattern). Notably, `studio-api/app/codirector/capabilities/handlers/` contains many pre-existing untracked handler files from other missions (a clean-clone concern owned by those missions, disclosed here); this mission's commit includes `analyze_video.py` because the resolver fix certified above lives in it.

## 12. Final verdict

**GO — SCENE 10 DUAL CHARACTER LIP SYNC VERIFIED**

- 12/12 spec gates PASS with live measured evidence (no predicted values).
- Full-stack E2E trace PASS (user action → frontend → request → API → backend → persistence → runtime → result → reload → downstream).
- Independent review (GLM 5.2 Max): all claims verified, no blockers; both repair items reconciled by the primary (§10).
- Master video integrity proven (SHA256 unchanged); retake persisted with full provenance; reload persistence proven by Playwright.
- COMFY RESTARTED?: NO (PID 45624 before and after).
