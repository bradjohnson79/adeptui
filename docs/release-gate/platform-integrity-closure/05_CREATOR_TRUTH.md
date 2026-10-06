# 05 — Gate E Creator-facing truth

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-29

## Home library

`Home.tsx` no longer shows “No Projects Yet” while the list is loading or when a filter hides every project.

- Loading → “Loading projects…”
- Fetch error with empty list → failed empty state + Try Again
- Loaded and zero projects → first-use empty state
- Projects exist but filter/search matches none → “No matching projects”

## Comfy status

Reachable + catalog still loading is **Ready · Loading Nodes**, not “Starting…”. Offline / Error / missing models stay distinct.

## Disabled reasons

`EngineAuthoritySelect` shows readiness / disabled reason on every non-ready engine option.

## Spatial Save

`SpatialMapSaveControls` remains one hook, two locations (top cluster + ERS footer). Scene-description Save is a different control.

## Resume

Timeline “Resume Incomplete Jobs” help now says it **requeues** unfinished batches and does not resume mid-diffusion.

## Peer close

- Kimi K3 (`159c851a`): **PASS WITH NON-BLOCKING** — Home states, Comfy “Ready · Loading Nodes”, Resume=requeue. Non-blocking: Models badge can still say Ready when Comfy is offline; scene-description button labeled only “Save”. **ACCEPTED NON-BLOCKING**.
- GLM 5.2 (`784c2ec3`): **PASS WITH NON-BLOCKING** — source matches the four creator-truth claims; most cases lack dedicated Playwright. **ACCEPTED NON-BLOCKING** (Playwright is Gate J/L, not a Gate E source defect).

**Gate E: CLOSED**
