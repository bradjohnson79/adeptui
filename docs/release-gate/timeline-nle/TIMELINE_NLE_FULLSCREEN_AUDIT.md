# Timeline NLE + Workspace Fullscreen — Completion Audit

**Date:** 2026-08-06  
**Branch:** `feature/ai-guided-setup`  
**Evidence SHA:** `fa09c99d6395c29461cdec4555055faad116c435` (worktree includes Timeline NLE / fullscreen / MiniMax default implementation)  
**Cert fixture:** `The Dreamweaver` (resolved by exact name or `ADEPT_PROJECT_ID`; no Dreamweaver hardcoding in product ontology)

## Verdict

### GO — TIMELINE NLE + WORKSPACE FULLSCREEN VERIFIED

---

## Scope delivered

1. **Shared true full-screen workspace** — Browser Fullscreen API controller under `studio-web/src/workspace/fullscreen/`; Expand vs Full Screen controls; Esc + button exit; restore prior `STANDARD` \| `EXPANDED`; chrome hide via `adept-workspace-fullscreen`; wired Timeline, Co-Director, MAGI.
2. **Inspector / Prompt stability** — Local draft + blur/idle persist; soft mutate avoids `reloadKey` remount stealing focus.
3. **Timeline NLE editing** — Left/right trim + move drag, snap/ghost, live readout, zoom slider + Ctrl+wheel, keyboard undo/redo/duplicate.
4. **MiniMax H3 authoritative video default** — Dock/library `minimax-h3`, Timeline generators `minimax-h3-t2v-local` / `minimax-h3-i2v-local`, `EngineName` includes `minimax-h3`; honest unavailable path; no silent LTX switch; LTX remains selectable.
5. **Certification** — Dual Playwright specs, three independent verifiers, this audit, Beta refresh.

---

## Files (primary)

| Area | Paths |
|------|-------|
| Fullscreen package | `studio-web/src/workspace/fullscreen/*` |
| Timeline shell / inspector | `TimelineEditorShell.tsx`, `TimelineInspector.tsx`, `useDraftField.ts` |
| NLE tracks | `DirectorTracks.tsx`, `TrackClipInteractive.tsx`, `styles.css` |
| Co-Director / MAGI wires | `CoDirectorShell.tsx`, `CoDirectorHeader.tsx`, `MagiEditorWorkspace.tsx` |
| MiniMax defaults | `db.py`, `schemas.py`, `types.ts`, `resolve.py`, `hunyuan_providers.py`, `engine_recommend.py`, UI labels |
| Cert | `tests/e2e/timeline/timeline-nle-usability-cert.spec.ts`, `tests/e2e/workspaces/workspace-fullscreen-cert.spec.ts` |
| Verifiers | `scripts/verify_timeline_nle_usability.py`, `scripts/verify_workspace_fullscreen.py`, `scripts/verify_minimax_video_default.py` |

---

## Evidence

### Playwright (`ADEPT_BETA_TARGET=1`, workers=1, retries=0)

| Spec | Result | Notes |
|------|--------|-------|
| `timeline-nle-usability-cert.spec.ts` | **PASSED** | Dock resolve `minimax-h3`; prompt typing stable; trim drag exercised |
| `workspace-fullscreen-cert.spec.ts` (headed) | **PASSED** | `document.fullscreenElement` → `timeline`; button exit + Esc exit verified |

Artifacts: `docs/release-gate/timeline-nle/artifacts/`

- `dock_video_resolve.json` — `activeModelId: minimax-h3`
- `prompt_typing.json` — `{ ok: true }`
- `trim_drag.json` — `{ ok: true }`
- `timeline_fullscreen_enter.json` — `{ fullscreenElement: "timeline" }` (headed)
- `timeline_fullscreen_esc_exit.json` — `{ ok: true }`

Headless Chromium commonly blocks Fullscreen API; headed Beta run is the authoritative FS evidence.

### Independent verifiers

| Verifier | Result |
|----------|--------|
| `verify_minimax_video_default.py` | **VERIFIED** |
| `verify_workspace_fullscreen.py` | **VERIFIED** |
| `verify_timeline_nle_usability.py` | **VERIFIED** |

### Beta

| Surface | URL | Status |
|---------|-----|--------|
| Creator UI | http://127.0.0.1:8760/ | HTTP 200 |
| Studio API | http://127.0.0.1:8758/ | `/api/health` HTTP 200 |

Rebuild + refresh performed after Esc-exit hardening (`Stop-AdeptUI-Beta` → `studio-web` build → `Start-AdeptUI-Beta -NoBrowser`).

---

## Locked decisions honored

| Decision | Status |
|----------|--------|
| True FS = Fullscreen API (not CSS-only) | Met |
| Ctrl+Shift+F documented; Esc exits | Met (explicit Esc → `exitFullscreen` + native `fullscreenchange`) |
| Exit restores previousViewMode | Met |
| MiniMax H3 IDs as listed | Met |
| No silent MiniMax → LTX | Met |
| Merge/Group clips out of scope | Met |

---

## Limitations (honest)

- Fullscreen API requires a trusted gesture and a non-blocking browser context; headless automation may record `fullscreenElement: null` even when controls are correct — headed cert is required for FS proof.
- Ripple trim ships as same-track shift when ripple mode is on; Merge/Group remain future.
- Live dock resolve for Dreamweaver may show `source: "user"` when the project already selected MiniMax; system default path is covered by static resolve audit + code gates.

---

## Manual review path

1. Open http://127.0.0.1:8760/ → **The Dreamweaver** → Timeline.
2. Confirm zoom slider; drag trim handles on a clip; type in scene prompt without cursor jump.
3. Expand workspace, then **Enter full screen** — Adept chrome hides; Esc or Full Screen button returns to prior Expand/Standard.
4. Repeat Full Screen on Co-Director and MAGI.
5. Footer Dock / video library: default **MiniMax H3**; LTX still choosable; unavailable MiniMax shows blocked reason (no silent LTX).

---

## Checklist

```text
[x] Branch + starting SHA verified
[x] Full-stack implementation completed
[x] Every visible control wired
[x] Real Fullscreen API (headed evidence)
[x] Persistence / draft stability verified
[x] MiniMax default + no silent LTX
[x] Playwright creator workflows passed
[x] Independent verifiers VERIFIED
[x] Production build passed
[x] Beta updated and running; URLs reported
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO
```
