# MAGI Post-Production Workspace UX — Certification

**Governing document for this UX milestone (Law 30).** Does not replace MAGI finishing pipeline certification (`docs/release-gate/magi-finalization/05-MAGI_EDITOR_FINAL_COMPLETION_CERTIFICATION.md`).

Date: 2026-09-14  
Branch: `feat/character-creator-final-closure`  
HEAD SHA (working tree; UX changes not committed): `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
Live project: **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Scene 12B: `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
Published master on VIDEO: `a85c2632-dd04-4450-be5d-214aa191e209`  
Local creator UI: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi`  
Studio API: `http://127.0.0.1:8758/` (PID 17964, healthz 200)

## Verdict

**GO — MAGI POST-PRODUCTION WORKSPACE UX CERTIFIED**

## Owner law (preserved)

- Timeline owns production: generate, Timed Prompts, Re-Take, continuity repair.
- MAGI owns post: color, upscale, assembly/trim, music, SFX, delivery.
- MAGI does not regenerate a performance. Line/take problems return to Timeline.

Certified MAGI processing was not rebuilt.

## Field verdicts

| Field | Verdict |
| --- | --- |
| LEFT DRAWER | PASS — Timeline drawer contract; closed = no reserved column; center expands |
| RIGHT DRAWER | PASS — Inspector / finish controls; internal scroll only |
| VIEWER | PASS — stays in the Adept shell; MAGI 50/50 keys only |
| VIDEO | PASS — 12B Quarters Interview — Published Master present |
| AUDIO | PASS — `character_voice` placed |
| MUSIC | PASS — `Tension_Underscore_v1` (`aa52820c-5ff5-45f6-ad48-80b3939a7529`) placed |
| SFX | PASS — `sfx_gen` placed |
| INPAINT REMOVED | PASS — no Mask tab; command parse never proposes inpaint |
| RE-TAKE REMOVED | PASS — MAGI chrome has no Re-Take; command copy routes to Timeline |
| TIMELINE PRODUCTION OWNERSHIP | PASS — `expose(timeline)` still includes `timeline.propose_retake` |
| MAGI POST OWNERSHIP | PASS — MAGI surface keeps `magi.color.apply` / `magi.upscale` / `magi.audio.generate` / `magi.render` |
| RESET WORKSPACE | PASS — both drawers open, Default preset, 50/50 MAGI split, queue collapsed |
| RESPONSIVE GEOMETRY | PASS — 1318×843, 1920×1080, 2560×1440; no page-height explosion |
| CD ROUTING | PASS — hard denylist on MAGI surface; Timeline still owns Re-Take |
| COLOR REGRESSION | PASS — Inspector Color (presets, exposure, Apply Grade) present; pipeline not re-run |
| UPSCALE REGRESSION | PASS — Inspector Upscale accordion present; pipeline not re-run |
| SOUND REGRESSION | PASS — Inspector Audio / ambience controls present; pipeline not re-run |
| MUSIC REGRESSION | PASS — MUSIC lane accepts score assets; generate controls present; pipeline not re-run |

## Geometry (observed)

Page `scrollHeight` equals viewport height at every size. Render Queue stays a 39px collapsed dock and does not push tracks off the Adept page.

| Viewport | Shell / stack | Viewer | Four tracks in view | `scrollHeight` |
| --- | --- | --- | --- | --- |
| 1318×843 | shell 764 / stack 609–621 | 311px @ 50/50 | YES (SFX above queue) | 843 |
| 1920×1080 | shell 1001 / stack 846 | 381–423px | YES | 1080 |
| 2560×1440 | stack 1206 | 603px @ 0.5 | YES | 1440 |

Root cause of the old 1674px explosion: unbounded `TimelineWorkspaceStack` plus a non-flex `MagiFocusProvider` wrapper. Fix: `.app-shell-fixed .magi-focus-root` / `.magi-shell` flex-lock; no `calc(100dvh - 72px)` on MAGI.

MAGI split keys: `adept_magi_center_split_v1`, `adept-ui.magi.preview-height.{projectId}`. Timeline Large Viewer key `adept_timeline_workspace_layout_v1` stayed `null` during MAGI cert.

## Drawer cert (1920×1080)

- Both open: center ~1289px; Viewer + four tracks usable.
- Left closed: center ~1569px (+280); no 40px reserved column.
- Both closed: center ~1869px; margins 0; four tracks still in view.
- Hard refresh: `leftDockCollapsed` / `rightDockCollapsed` persisted `true`.
- Reset Workspace: both open, `activePreset=default`, MAGI split `viewerHeight: 0.5`, queue collapsed.

Right `.magi-dock-scroll`: `overflow-y: auto` (example 833 client / 1123 scroll). Left bins same. Inspector never grew page height.

## Expand

Expand changes viewer share **inside** the MAGI stack only. Bins stay (`Hide bins` still available). At 1318×843 Expand: viewer 353px (ratio 0.568 after 268px track floor), VIDEO/AUDIO/MUSIC/SFX all in view, SFX above the queue. Does not apply `viewer-focus`.

## Co-Director routing

`expose(workspace_surface="magi", intent="Re-take this part because Korri said Anadriya's line.")`:

- `timeline.propose_retake` absent
- no `retake` / `inpaint` tool ids
- MAGI finishing tools remain: `magi.color.apply`, `magi.upscale`, `magi.audio.generate`, `magi.render`

Same intent on `workspace_surface="timeline"` still includes `timeline.propose_retake`.

MAGI Command pane (live):

- Re-Take / inpaint speech → “That is a production correction. Return to Timeline for Re-Take — MAGI only finishes completed takes.”
- “Give this scene a professional cinematic grade, improve the sound mix, and upscale the finished video.” → finishing proposal (`image.upscale` first-match; not inpaint / Re-Take)

Live `POST /api/codirector/chat` with `workspaceTab=magi` returned `fallbackUsed: true` (generic onboarding stub, empty `toolInvocations`). Hard denylist still held — no Re-Take tool ran. Honest limitation: the foundation LLM turn did not produce a MAGI-specialist prose reply.

## Tests (observed)

From `studio-web`:

`magi-editor.css.test.ts`, `magiCommandParse.test.ts`, `tracks.test.ts`, `magiCenterSplit.test.ts`, `MagiLayoutPersistence.test.ts` — **5 files, 16 passed**.

API (earlier this mission): `test_empty_sequence_is_four_post_tracks`, `test_magi_surface_blocks_retake_and_inpaint_even_when_intent_asks` — PASS.

Out of scope / not used as a MAGI UX blocker: `test_timeline_export_to_existing_batch_places_and_ledgers` 502 on a second Timeline append.

## Runtime

```text
COMFY BEFORE: PID 45624 / GET :8188/system_stats 200 / Comfy 0.34.5 / RTX 5090
COMFY AFTER:  PID 45624 / GET :8188/system_stats 200
COMFY RESTARTED?: NO
WHY?: MAGI UX only. Vite HMR. Studio API was recycled earlier in this mission (PID 17964); Comfy was not touched.
```

## Limitations

- Color / 2K upscale / music generate / final render jobs were not re-executed. Inspector + command + expose presence is the regression bar for this UX gate.
- MAGI sequence chrome (timecode / snap strip) is hidden so four tracks fit the constrained stack. Playhead remains on the ruler; play controls remain on the MAGI timeline toolbar.
- Co-Director live chat used a provider fallback; routing truth is the exposure denylist + MAGI Command pane.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi`
2. Confirm Viewer + VIDEO / AUDIO / MUSIC / SFX without scrolling the page.
3. Close / open bins and Inspector; Reset Workspace.
4. Type a Re-Take phrase in Command — expect Timeline handoff copy, not a MAGI generate.
