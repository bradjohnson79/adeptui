# 03 — Timeline UX / Creator-Workflow Review

**Subagent C — Independent Timeline UX / Creator-Workflow Reviewer**
**Branch:** `feat/timeline-final-certification` @ HEAD `aa6b72b` — **Status:** AUDIT-ONLY (single deliverable file; no source modified)
**Method:** static code audit of the Timeline experience as a creator would drive it. Every claim cites file:line. Companion files: `01-ARCHITECTURE_AUDIT.md` (reserved), `02-TRACK_WIRING_MATRIX.md` (Subagent B).

---

## 1. Can a creator place real Library media on a track? Usable track types

Rendered in the v2 shell board (`DirectorTracks.tsx`, mounted by `TimelineEditorShell.tsx:985-995`):

| Track | Usable | How media is attached in shell mode | Evidence |
|---|---|---|---|
| BATCHES (generation lane) | ✅ interactive (select / generate / status) | batch blocks are buttons; per-batch config in Inspector | DirectorTracks.tsx:1627-1731 |
| VISUAL — image OR video (media_mode-switched, one at a time) | ✅ | drag-drop onto track (image lane only), AssetTray “Add to Timeline”, Inspector asset select (imageClip only) | DirectorTracks.tsx:1733-1897; EditorShell.tsx:664-698; Inspector.tsx:961-966 |
| TIMED PROMPT | ✅ interactive | + Prompt (track header / toolbar); drag/trim; tokens | DirectorTracks.tsx:1901-1957; Toolbar.tsx:178-194 |
| CAMERA | ✅ interactive | + Camera (track header); preset drag-drop | DirectorTracks.tsx:1959-2126 |
| AUDIO | ✅ (drop / tray add; no inline select in shell) | drag-drop audio asset | DirectorTracks.tsx:2128-2192 |
| SFX | ✅ (same as audio) | drag-drop | DirectorTracks.tsx:2194-2258 |
| LIP SYNC (dialogue) | ✅ | drop dialogue audio onto track; clip inspector | DirectorTracks.tsx:2260-2342; Inspector.tsx:1509-1620 |
| MASK · REPAIR | ⚠️ read-only display | repair ranges appear after add | DirectorTracks.tsx:2344-2367 |
| Image/Video REFERENCE lanes | ❌ **retired from board** | bindings live on Prompt clips; arrays still in data model + Inspector/delete/preview handle them | DirectorTracks.tsx:1899; spec asserts count 0 (timeline-timed-prompt-track.spec.ts:83-84,165-166) |
| Music | ❌ no dedicated track (an audio clip on AUDIO) | — | contracts.ts:191-194 (audioClips only) |

**Notable gaps:** (a) video clips have **no asset selector** in the shell — the Inspector videoClip section only edits start/length/trim (Inspector.tsx:971-978) and inline clip selects render only in legacy mode (DirectorTracks.tsx:1788-1808,1869-1891); (b) uploads are disabled in the Timeline tray (`allowUpload={false}`, EditorShell.tsx:1060; default true at AssetTray.tsx:24) — media must be imported on the project page first (ProjectEditor.tsx:366); (c) the VISUAL track’s media_mode can only be switched by adding the other kind (DirectorTracks.tsx:1733/1815) or via legacy buttons.

## 2. Clip placement & duration editing; ruler; drift risk

- **Add**: toolbar +/− groups for Batch/Image/Prompt/Audio/SFX/Lip Sync (Toolbar.tsx:437-495); drops on image/audio/sfx lanes (DirectorTracks.tsx:1736-1737,2130-2131,2196-2197).
- **Move/trim**: pointer-drag with move / trim-left / trim-right handles, snapping (default 1/fps), min 0.15s, overlap clamp against lane neighbors, commit-only-on-move (no passive selection loss) (TrackClipInteractive.tsx:16-100; DirectorTracks.tsx:734-852). Undo toast after remove (DirectorTracks.tsx:1530-1537).
- **Exact timing**: numeric Start/Length/Trim fields per clip in Inspector (Inspector.tsx:905-917,957-958,974-976,983-985,991-992,1512-1538); ruler shows per-second ticks, hover time, click/drag seek (DirectorTracks.tsx:1562-1611); playhead time readout (DirectorTracks.tsx:1523-1525).
- **Duration math drift**: **none found**. Board windowing (`batchWindows`, DirectorTracks.tsx:694-710: cumulative `Math.max(0.1, plannedDuration)`, sorted by order) is byte-for-byte the same formula as the preview resolver (resolveTimelineAtTime.ts:52-66), so lane geometry and playhead resolution cannot diverge. px mapping is linear (90px/s × zoom, DirectorTracks.tsx:720). Snap math is consistent between preview (TrackClipInteractive.tsx:16-19) and commit (DirectorTracks.tsx:779).
- **Minor**: playhead keyboard clamp uses scene.duration while scrub clamp uses boardDuration (EditorShell.tsx:628-631 vs DirectorTracks.tsx:1116) — different ranges when batches exceed scene duration; scene-duration edits do not rescale batch plannedDuration (Inspector.tsx:676-683 vs 1146-1158) so the board silently extends (DirectorTracks.tsx:707-710).

## 3. Prompt alignment

Two independent prompt systems coexist:
- **TIMED PROMPT track** (legacy `prompt_segments`): the visible lane with per-segment text/weight/start/length + reference tokens (DirectorTracks.tsx:1901-1957; Inspector.tsx:902-951). It is the scene prompt (“Scene Prompt” in the Scene Inspector, Inspector.tsx:725-760) plus timed segments.
- **Batch prompt** (`batch.promptSegments`): edited ONLY in the Batch Inspector textarea (Inspector.tsx:1159-1169); this is what actually generates — request_builder.py:69-70 compiles from `batch.promptSegments`, i2v start image from `batch.sourceAnchors` (request_builder.py:82-95,186).
- Migration copies legacy segments into batches **once** (migration.py:96-106); after that, edits on the TIMED PROMPT lane never reach generation. **A creator who types prompts on the lane and presses Generate gets the batch’s old/empty prompt.** Shot association is per-batch via the Batch Inspector, not the lane.

## 4. Batch grouping

- Build: “+ Batch / − Batch” in toolbar (Toolbar.tsx:255-279,439-448) and “+ Batch” on the BATCHES lane header (DirectorTracks.tsx:1633-1637); API `POST /batches` with plannedDuration (router.py:74-84).
- Clarity: batches render as labeled blocks with time range + status badge + continuity chip in the BATCHES lane (DirectorTracks.tsx:1688-1725); batch label/time editable in Batch Inspector (Inspector.tsx:1142-1158). Selecting a batch opens the Batch Inspector in the right drawer.
- Switching: click a batch block; there is no dedicated batch switcher, and **the right drawer does not auto-open on batch selection** — drawers default closed (workspaceLayout.ts:104-105) and no focus event fires (DirectorTracks.tsx:1696). A spec had to click the drawer handle manually (timeline-timed-prompt-track.spec.ts:139-146).
- Fresh batches get **no generator** (`add_batch` uses `master.sceneGeneratorId`, which is never written anywhere — service.py:102; orchestrator.py:1255 reads only) — see §5/§10.

## 5. Generator selection & aspect

- **Scene level** (Scene Inspector → Generation, Inspector.tsx:763-776): a **static, ungated** dropdown (auto / minimax-h3 / ltx / wan / fal_seedance / fal_kling / fal_veo / fal_runway). It writes `scene.engine` only; nothing propagates it to batches (`sceneGeneratorId` is never set; orchestrator.py:1255 reads it as None). **Selecting WAN, Veo or Runway has zero effect on Timeline batch generation**, and WAN has no Timeline adapter at all (capabilities.py:123 — “available for scene render only”; no wan adapter in registry.py:32-38).
- **Batch level** (Batch Inspector → Generator, Inspector.tsx:1206-1234): the real control. Registry-driven from `GET /director-timeline/generators` → `payload.timelineAdapters` (service.py:255-266), non-executable options disabled (Inspector.tsx:1218). Executable adapters: minimax-h3-t2v-local, minimax-h3-i2v-local (adapters/minimax_h3_local.py:45; minimax_h3_i2v_local.py:45), ltx-local (ltx_local.py:62, draftPathway local_live).
- **Availability honesty defect**: the batch dropdown’s `executable` flag comes from **adapter** capabilities, where Seedance and Kling report `executable=True` (adapters/seedance_api.py:48; adapters/kling_api.py:45) — while the capability **registry** lists them `executable=False` (capabilities.py:165,181). So hosted generators appear selectable/enabled in the batch dropdown but are not genuinely runnable (orchestrator.py:260-267 looks up the registry by id; “seedance-api” is not even in that list, so the gate is skipped and failure surfaces only at provider level). Violates “never show unavailable as available”.
- **Aspect ratio**: Picture Shape select is wired end-to-end (scene.aspect_ratio → request_builder.py:159 → resolution), with a warning when the generator’s supported ratios don’t match (Inspector.tsx:777-791,1259-1266).

## 6. Retake

Two disconnected systems:
- **Toolbar “Re-take” → TimelineRetakeDrawer** (mounted at EditorShell.tsx:1005-1012): hardcoded baseline prompt “A glowing glass bottle…” (EditorShell.tsx:1011; RetakeDrawer.tsx:5-9), hardcoded engine “MiniMax H3” (RetakeDrawer.tsx:57,122-124), synthetic shot id `scene-{id}-shot-1` (EditorShell.tsx:1008), `durationSec:5` hardcoded (RetakeDrawer.tsx:77). Takes are stored in a **separate JSON file** (timeline_retakes/store.py:19) that nothing in the Timeline reads; “Replace Current Take” (RetakeDrawer.tsx:213-238) never updates `batch.approvedClip` or the video clips. After “Add as Alternate” the user does see original vs new take and can choose (RetakeDrawer.tsx:253-281), but the choice is meaningless to the actual timeline.
- **Batch Inspector “New take”** (Inspector.tsx:1388-1412 → `POST /batches/{id}/retake`, router.py:376-393): the real, candidate-aware retake flow (adds candidateVersion, immutable snapshot; orchestrator.py:1349-1420). It is the one wired path but is hidden inside the batch inspector.

## 7. Result feedback

- **During generation**: Preview Monitor shows live/streamed draft frames with stage+progress overlay and DRAFT badge (PreviewComposer.tsx:269-283; LivePreviewMonitor.tsx:444-492); Render Queue lists Job-row-based renders with per-batch linkage (CompactRenderQueue.tsx:79-103).
- **After completion**: batch status → CandidateReady/Approved; take buttons (text only, no thumbnails/video) in Batch Inspector (Inspector.tsx:1356,1413-1430); the generated mp4 is registered as a Library asset tagged `batch_<id8>` (queue_worker.py:1105-1129) and mirrored into `video_clips` as `bbclip_…` clips (completion.py:306; verified by timeline-two-batch-final-certification.spec.ts:343-349).
- **Preview Monitor after completion**: uses `scene.output_path` (PreviewComposer.tsx:255-267,286-297). The LTX batch worker **sets** `scene.output_path` to each batch’s output (queue_worker.py:1098) and a comment says it must not be authoritative but nothing reverts it (queue_worker.py:1103-1104). In a multi-batch scene the monitor therefore shows the **last-generated** batch regardless of playhead — per-batch take is not surfaced in the monitor.
- **Stuck “queued”**: batches can sit in Queued/Generating (sequential chain stages snapshots, orchestrator.py:1295-1302); Stop/Resume controls exist (EditorShell.tsx:915-932; Toolbar.tsx:541-560) but there is no stuck-state timeout indicator. MiniMax batch jobs create **no Job row** (only LTX does, ltx_local.py:141-161), so MiniMax failures show only as a lane badge — no overlay, no queue entry, no Dismiss (matches 02-TRACK_WIRING_MATRIX §2.9).

## 8. Preview monitor

- TimelinePreviewComposer is the sole source of truth (PreviewComposer.tsx:12-33; LivePreviewMonitor.tsx:48-54,113-116). Resolution order: selected reference clip → pinned Library asset → failed/cancelled (unless dismissed) → done → queued/running draft → scene output → timeline frame at playhead → idle (PreviewComposer.tsx:181-319).
- At a playhead it shows the intersecting image/video clip with clip-local time and a lower-third prompt overlay (PreviewComposer.tsx:299-318; LivePreviewMonitor.tsx:311-340,523-532).
- **Stale media on clip replacement: none** — mediaSrc changes remount the media element (key={mediaSrc}, LivePreviewMonitor.tsx:398-434). The Library pin (composed.kind “library”, PreviewComposer.tsx:225-234) is the only intentional hold, cleared via “Clear library preview”.
- **Gap**: after a completed batch the monitor keys off scene.output_path, not the active batch’s approved take — see §7.

## 9. Right drawer / Advanced controls

- Right drawer = Inspector tabs + Render Queue (EditorShell.tsx:1087-1195). **TimelineSettingsDrawer (⚙)** is workspace/layout preferences only (display mode, density, thumbnails, snap, playhead-follow, guidance priority, empty-track tips — SettingsDrawer.tsx:85-179) and **does not contain LoRA/aspect/runtime controls**; all its controls are wired.
- LoRA: LoRASelector in Scene Inspector → Advanced (Inspector.tsx:890-896) persists to **every batch** via PATCH lora (Inspector.tsx:433-448; router.py:103-116) and reaches LTX params (ltx_local.py:118; queue_worker.py:804-842). Wired.
- Generator-specific: camera motion/rig catalogs + speed/intensity/subject-lock/stabilization (Inspector.tsx:1021-1135) persist to camera_clips but **do not reach generation** (request_builder.py:188-189 sends cameraMotion=None, seed=None); execution-strategy disclosure is honest (Inspector.tsx:1077-1086). Partial — advanced camera/seed controls are effectively planning-only for batch generation.
- Draft mode + Promote to Final / Reject take (Inspector.tsx:1235-1352) are wired to the batch API (draftPathway gating + finalRequiresNewGeneration copy).
- **Dead/decoupled**: the Scene Generator dropdown (§5), the TIMED PROMPT lane vs batch prompt (§3), the toolbar Re-take drawer (§6). The Co-Director right tab is a button stub (EditorShell.tsx:1172-1188) — intentional placeholder.

## 10. Error states

- **Missing generator (most common first failure)**: backend returns HTTP 200 `{ok:false, error:"GENERATOR_REQUIRED"}` (orchestrator.py:246-252; generate_scene aggregates errors at 1295-1325) but **every UI call site discards the result**: header Generate (EditorShell.tsx:911, `.then(afterMutation)` only), toolbar Generate/Gen Batch (Toolbar.tsx:398-406 → run() has no catch; 530-540), batch Inspector Generate Draft/Final (Inspector.tsx:1272-1277,1286-1289, `.then(onRefresh)` only). **Result: clicking Generate with a default (generator-less) batch does nothing, with zero feedback.** Preflight does not check for missing generator either (orchestrator.py:979-1043 has no generatorId finding), so preflight won’t warn.
- **Source image missing**: batch Start Image select is explicit “No start image” (Inspector.tsx:1195-1204); i2v adapters honor no-start-image as t2v or fail honestly (H3_I2V_DOWNGRADED_TO_T2V etc., minimax_h3_i2v_local.py:270-300).
- **Generator unavailable**: batch select disables non-executable options with titles (Inspector.tsx:1218-1219); backend gates WAN with GENERATOR_UNSUPPORTED_FOR_TIMELINE (orchestrator.py:254-267, certified by spec D). Seedance/Kling mismatch (§5) undermines this.
- **Batch incomplete**: sequential chain stages snapshots with status Queued (orchestrator.py:1295-1302); Stop/Resume buttons (EditorShell.tsx:915-932); continuity-bridge failure offers Retry / Continue without matching (Inspector.tsx:1360-1387). Failed overlay + Dismiss works only for Job-row failures (PreviewComposer.tsx:241-252; service.py:48-80).

## 11. Reliability verdict per question

- (a) **Blocks core use**: silent GENERATOR_REQUIRED (§10), TIMED PROMPT lane ↔ generation disconnect (§3), VISUAL-track image placement does not feed i2v (§4/§2 note), disconnected Re-take drawer (§6), monitor showing last batch’s output for multi-batch (§7).
- (b) **Cosmetic**: generator banner is a title-only strip (TimelineGeneratorBanner.tsx:3-14); integer-second ruler ticks; drawer auto-open absence.
- (c) **Already good**: drag/trim/snap/overlap-clamp editing (DirectorTracks.tsx:734-852), duration-math consistency (board vs resolver, §2), timeline-driven preview with lower-third (PreviewComposer.tsx:299-318), no stale media on clip swap (LivePreviewMonitor.tsx:398-434), batch clip isolation (router.py:134-146), no-silent-substitution hard lock (orchestrator.py:340-354), LoRA persistence to all batches (Inspector.tsx:433-448), backend capability gating for WAN (orchestrator.py:254-267), honest execution-strategy disclosure (Inspector.tsx:1077-1086).

---

## 2. UX defect list (severity-ranked)

### BLOCKER (breaks the primary creator flow)
1. **Silent generation failure on the default path.** New batches have no generator (service.py:102 — `sceneGeneratorId` never set anywhere); every Generate call site discards `ok:false` (EditorShell.tsx:911; Toolbar.tsx:398-406; Inspector.tsx:1272-1289); preflight never flags it (orchestrator.py:979-1043). Add Batch → Generate = nothing happens, no message. (Evidence: orchestrator.py:246-252; service.py:83-134)
2. **TIMED PROMPT lane does not drive generation.** The most visible prompt surface is a planning layer; only the Batch Inspector prompt generates (request_builder.py:69-70 vs DirectorTracks.tsx:1901-1957; migration.py:96-106 one-time copy). Prompt alignment breaks end-to-end.
3. **Toolbar “Re-take” is a disconnected demo flow.** Hardcoded glass-bottle prompt / MiniMax H3 / synthetic shot / separate JSON take store; Replace Current Take never touches the batch (RetakeDrawer.tsx:5-9,57,213-238; EditorShell.tsx:1005-1012; timeline_retakes/store.py:19). The wired retake lives only in the Batch Inspector (Inspector.tsx:1399-1412).
4. **VISUAL-track image placement does not feed generation.** i2v start image comes from batch sourceAnchors (request_builder.py:82-95), not the VISUAL lane (image_clips) and not batch.visualClips (persisted orchestrator.py:820, never rendered, never consumed). Placement on the most obvious surface is inert for generation.

### MAJOR
5. **Scene Generator dropdown is static/ungated and ineffective** for timeline batches (Inspector.tsx:766-775; sceneGeneratorId never written — orchestrator.py:1255). WAN/Veo/Runway selectable with zero effect; WAN has no timeline adapter (capabilities.py:123).
6. **Generator availability honesty mismatch**: adapter caps say Seedance/Kling executable=True (seedance_api.py:48; kling_api.py:45) while the registry says False (capabilities.py:165,181) — the batch dropdown advertises unusable hosted generators.
7. **Multi-batch result feedback**: monitor shows last-completed batch’s output via scene.output_path (queue_worker.py:1098 with warning comment 1103-1104) not the take at the playhead; batch inspector take list is text-only (Inspector.tsx:1413-1430); MiniMax batch failures are Job-row-invisible (no overlay/queue/Dismiss — ltx_local.py:141-161 vs minimax adapters).
8. **Zero-batch scene Generate** returns `{ok:true, jobs:[], errors:[]}` (orchestrator.py:1295-1325) — no guidance, no message.
9. **Error surfacing overall**: ok:false-in-200 responses are never rendered anywhere in the Timeline; the only guard (header preflight disable, EditorShell.tsx:871-911) requires the user to have run preflight first and doesn’t cover missing generators.

### MINOR
10. Video clip asset cannot be changed in shell (no Inspector select — Inspector.tsx:971-978; inline selects shell-hidden — DirectorTracks.tsx:1788-1808).
11. Uploads disabled in Timeline tray (EditorShell.tsx:1060); must leave to project page (ProjectEditor.tsx:366).
12. Right drawer does not auto-open on batch selection; both drawers default closed (workspaceLayout.ts:104-105; DirectorTracks.tsx:1696).
13. Playhead clamp inconsistency keyboard vs scrub (EditorShell.tsx:628-631 vs DirectorTracks.tsx:1116).
14. Scene duration edits do not rescale batch plannedDuration (Inspector.tsx:676-683 vs 1146-1158; board extends silently — DirectorTracks.tsx:707-710).
15. `hasOutput` treats a planned video clip as output for Send-to-Editor (DirectorTracks.tsx:606).
16. Advanced camera/seed controls persist but never reach generation (request_builder.py:188-189).
17. Reference lanes retired from board (DirectorTracks.tsx:1899) while reference-clip selection kinds remain handled (Inspector.tsx:193-223) — dead-end selection states if legacy data exists.

### INFO
18. E2E preview-monitor cert test H targets the retired :8760 stack (timeline-multi-batch-preview-monitor-cert.spec.ts:166) vs AGENTS.md §15.
19. TimelineGeneratorBanner is title-only (TimelineGeneratorBanner.tsx:3-14).
20. Client clip ids are Math.random() strings; no client idempotency keys on POSTs (DirectorTracks.tsx:147-149; api.ts:3627-3704).

---

## 3. Would a Beta user make a short production end-to-end without hitting unfinished wiring?

**Honest answer: NO on the default UI path — YES only if they follow the exact API-shaped recipe the certification spec uses.**

The certified path (timeline-two-batch-final-certification.spec.ts:108-151,243-308) configures batches **via API first** (generatorId + promptSegments + sourceAnchors), then uses “Gen Batch” per batch in the UI. A Beta user who instead does the natural UI flow — open Timeline → “+ Batch” → drop an image on the VISUAL lane → type prompts on the TIMED PROMPT lane → click Generate — hits three blockers in sequence with **no visible error**: (1) Generate silently no-ops (no generator — §10/B1); (2) even after picking a generator in the Batch Inspector, the lane prompts/images never reach the request (B2/B4); (3) “Re-take” appears to work but changes nothing real (B3). Multi-batch result review is further muddied by the monitor showing the last batch’s output (M7).

A determined user can complete a short production if they discover that the **Batch Inspector (right drawer) is the real control surface** — select generator, type the batch prompt, pick the Start Image, click “Generate Final”, approve the take, and use the Library for playback. That is a workable but hidden workflow, not the surface the UI presents. **Verdict for this review: NOT Beta-ready on the default creator path until the four blockers are closed (surface GENERATOR_REQUIRED, sync lane→batch prompt/image, wire Re-take to the batch take system, or remove the decoupled drawer).** Consistent with 02-TRACK_WIRING_MATRIX priority list (§3 items 1,2,4,9).
