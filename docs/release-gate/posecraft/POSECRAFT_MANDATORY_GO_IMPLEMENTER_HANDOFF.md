# PoseCraft — Mandatory GO Corrective Program
## Implementer Handoff for Independent Verifier

> **Status (governing):** `NO-GO — POSECRAFT MASTER REQUIREMENTS NOT YET INDEPENDENTLY VERIFIED`
>
> The implementer (glm-5.2-high) has completed all gates A–J and a live Playwright run
> reports `ALL GATES PASS`. The implementer **cannot self-certify**. This document hands
> the evidence pack and Beta to a **separate, independent verifier agent** (to be
> assigned by the coordinator) for binary GO / NO-GO certification.

---

## 1. Beta runtime (live, ready for manual + automated review)

| Item | Value |
|---|---|
| Beta Web URL | http://127.0.0.1:8760/ |
| Studio API URL | http://127.0.0.1:8758/ |
| API process | env-loaded uvicorn `app.main:app` on 127.0.0.1:8758 (Beta env from `config/beta-local.env`) |
| Web server | `scripts/beta_runtime/web_server.py` serving `studio-web/dist` on 127.0.0.1:8760 (proxies `/api` → 8758) |
| Web bundle | freshly rebuilt (`npm --prefix studio-web run build` → `✓ built in 1.49s`) |
| Comfy (image gen) | running (Comfy-Desktop python on default port) — required only if verifier re-runs image-gen steps |

**To review PoseCraft manually:** open http://127.0.0.1:8760/, open/create a project,
navigate to the PoseCraft workspace (GenerationTools → PoseCraft).

## 2. Project path for review

The Playwright run creates a **disposable** project per run (created via `POST /api/projects`,
deleted at the end of the spec). For independent verification, the verifier should either:
- re-run the focused corrective spec (it self-provisions a fresh disposable project), **or**
- open any existing project at the Beta URL and exercise the gates manually.

Recommended disposable project name pattern used by the spec:
`PoseCraft Mandatory GO Corrective <timestamp>`.

## 3. Artifact locations

Latest run (all gates PASS):

```
docs/release-gate/posecraft/artifacts/mandatory-go-corrective/
  POSECRAFT-MANDATORY-GO-2026-08-04T20-41-37-498Z/
```

Per-gate artifacts in that directory:

| Gate | Artifacts |
|---|---|
| A | `A-layout-default.json`, `A-shell-open.png`, `A-fullscreen.json`, `A-fullscreen.png` |
| B | `B-divider-drag.json`, `B-layout-collapsed.json`, `B-both-collapsed.png` |
| C | `C-accordions.json` |
| D/E | `D-figures.json`, `D-two-figures.png` |
| F | `F-move-before.json`, `F-move-after.json`, `F-move-after.png`, `F-move-debug.json`, `F-pose-before.json`, `F-pose-after.json`, `F-pose-after.png`, `F-pose-debug.json` |
| G | `G-pose-library.json` |
| H | `H-furniture.json`, `H-furniture.png` |
| I | `I-reloaded-doc.json`, `I-persistence.json` |
| J | `J-per-gate-verdict.json`, `J-master-verdict.txt` |

The full reloaded PoseCraft document (post-reload) is captured in `I-reloaded-doc.json`
(top-level keys: `schemaVersion, currentScene, savedVersions, layoutPrefs`).

## 4. Playwright results (latest run)

```
Command:
  npx playwright test tests/e2e/posecraft/posecraft-mandatory-go-corrective.spec.ts \
    --project=chromium --reporter=list --workers=1 --retries=0
Env:
  ADEPT_BETA_TARGET=1
  PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
  STUDIO_API_BASE=http://127.0.0.1:8758

Result: 1 passed (33.9s)   exit_code=0
```

Per-gate verdict (`J-per-gate-verdict.json`):

| Gate | Result |
|---|---|
| Gate A — measurable viewport (1920×1080) | PASS |
| Gate B — resizable/collapsible panes | PASS |
| Gate C — accordions (Left: Cast/Pose Library/Furniture/Scene; Right: Figure/Transform/Pose/Camera/Export) | PASS |
| Gate D — adult male + female figures | PASS |
| Gate E — six staging colors | PASS |
| Gate F — visible Move/Rotate/Pose gizmos + real pointer drag (root X change + joint override change) | PASS |
| Gate G — pose library ≥50 + sticky filters + professional cards | PASS |
| Gate H — furniture (table + 2 chairs) as Babylon objects | PASS |
| Gate I — persistence (figures + furniture + layoutPrefs survive reload) | PASS |
| Gate J — per-gate GO/NO-GO verdict strings emitted | PASS |

Master verdict (`J-master-verdict.txt`):
`ALL GATES PASS — pending independent verifier sign-off`

## 5. What the independent verifier must verify (per gate A–J)

The verifier must **independently** confirm each gate (do not rely solely on the
implementer's Playwright run). Recommended approach: re-run the focused spec, then
spot-check artifacts and the live Beta.

- **Gate A — Measurable viewport (1920×1080):**
  - Default viewport width ≥60% of PoseCraft workspace (`A-layout-default.json`).
  - Both panes collapsed → viewport ≥88% (`B-layout-collapsed.json`).
  - Viewport height fills workspace beneath header.
  - Internal camera-frame margins 4–6% per side.
  - Fullscreen Viewport mode + floating toolbar (Move/Rotate/Pose/Camera/Save/Exit) (`A-fullscreen.json`/`.png`).

- **Gate B — Resizable panes:**
  - Drag Left divider → Left pane width changes within 260–520 (`B-divider-drag.json`).
  - Drag Right divider → Right pane width within 280–560; Viewport ≥50%.
  - Collapse/expand via edge tabs (`posecraft-collapse-left/right`, `posecraft-expand-left/right`).
  - Layout persists across reload (Gate I).

- **Gate C — Accordions:** Left = Cast, Pose Library, Furniture, Scene; Right = Figure, Transform, Pose, Camera, Export (`C-accordions.json`).

- **Gate D — Figures:** adult-male + adult-female present (`D-figures.json` archetypes array).

- **Gate E — Colors:** six color options (Sea Glass, Blue, Green, Red, Purple, Orange) on a selected figure (`D-figures.json` colorOptions=6).

- **Gate F — Real 3D gizmos + pointer drag (CRITICAL — real pointer gestures, not API calls):**
  - Move: `F-move-debug.json` shows `down.gizmo.kind=move, axis=x`, `moveCount>0`, `up` fired; `F-move-after.json` figure `position.x` differs from `F-move-before.json` (root X changed by real mouse drag ≥40px).
  - Pose: `F-pose-debug.json` shows pose drag occurred; `F-pose-after.json` joint override differs from `F-pose-before.json`.
  - Before/after screenshots: `F-move-after.png`, `F-pose-after.png`.
  - Verifier should re-run and confirm the drag is a **real pointer gesture** (mouse down → move → up on the gizmo handle / figure body), not a direct API write.

- **Gate G — Pose library UI:** `G-pose-library.json` totalPoses ≥50; professional cards (88px thumb left, title+desc right); sticky filters; no clipping (spot-check live Beta).

- **Gate H — Furniture:** `H-furniture.json` kinds contains `table-medium` and ≥2 `block-chair`; Babylon objects visible (`H-furniture.png`).

- **Gate I — Persistence (API SoT):** `I-persistence.json` figures≥2, primitives≥3, layoutPrefs=true; `I-reloaded-doc.json` top-level `layoutPrefs` object present after reload (figures/furniture/colors/joints/camera/layout prefs survive refresh).

- **Gate J — Playwright:** spec emits per-gate GO/NO-GO strings (`J-per-gate-verdict.json`) and master verdict (`J-master-verdict.txt`).

## 6. Implementer cannot self-verify

Per Adept UI Build Law #4 (Subagents double-check) and Law #24 (Binary certification),
the implementer **must not** issue the Master GO. The implementer's Playwright run is
**evidence**, not certification. The independent verifier (separate agent, assigned by
the coordinator) owns the final **GO** or **NO-GO** verdict and must record it in the
Master completion/tracker docs and `POSECRAFT_AMALGAMATED_REPORT.md`.

## 7. Remaining todos for the independent verifier / coordinator

- [ ] Assign a **separate** verifier agent (glm-5.2-high or coordinator-designated) to independently re-run the spec and spot-check the live Beta.
- [ ] Verifier records binary GO / NO-GO in `docs/release-gate/posecraft/POSECRAFT_AMALGAMATED_REPORT.md` and Master completion/tracker docs.
- [ ] `pc-master-verdict` todo is left for the coordinator to assign after the independent verifier signs off.

## 8. Known limitations / notes for the verifier

- The corrective spec is focused and disposable: it creates and deletes its own project each run. It does **not** mutate long-lived project state.
- Co-Director `add_figure` tool calls depend on the live LLM provider configured in `config/beta-local.env`. If the provider is rate-limited or down, Gate D figure adds can flake. The API must be started with the Beta env loaded (the implementer restarted it accordingly).
- The web bundle must be rebuilt (`npm --prefix studio-web run build`) after any frontend change before re-running the spec, because the Beta web server serves the static `dist` build (no Vite HMR).
- Debug counters (`globalThis.__pcDown/__pcMoveCount/__pcUp/__pcManipulate`) and `document.body.dataset.dividerDragging` remain in the client for traceability; they are harmless and used by the spec's evidence capture.
