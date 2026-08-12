# Timeline UI Repair + Network/Console Audit (Phases 9–10)

- **Date:** 2026-08-07
- **Milestone:** Timeline Full End-to-End Audit, Repair & Final Hardening — todo `t5-ui`
- **Baseline:** [TIMELINE_UI_INTERACTION_AUDIT.md](TIMELINE_UI_INTERACTION_AUDIT.md) (defects D1–D11) and [TIMELINE_GENERATION_WIRING_AUDIT.md](TIMELINE_GENERATION_WIRING_AUDIT.md) (W3)
- **Method:** repair each confirmed defect, typecheck + lint + unit tests, rebuild `studio-web`, restart Beta, verify live at `http://127.0.0.1:8760/` with browser tooling and a Playwright network/console capture (`scripts/audit_timeline_network_console.mjs`).

---

## Defect repair ledger

| # | Defect | Verdict | Repair | Evidence |
|---|--------|---------|--------|----------|
| D1 | Raw float durations in `TimelineMasterPanel` | **FIXED** | Shared `formatDurationSeconds` (`studio-web/src/lib/formatDuration.ts`) applied to planned/generated/visible durations (`TimelineMasterPanel.tsx:275,283,285,288`) | Live: batch chips render `5.00 s · ltx-local` |
| D2 | Raw floats in Inspector inputs | **FIXED** | Batch Planned Duration input rounds to 2dp (`TimelineInspector.tsx`); Repair Start/Length use `formatDurationSeconds`; Scene Duration draft field rounds (`String(Number(scene.duration_sec.toFixed(2)))`) | Live: Planned Duration shows `5`; scene Duration no longer `5.004000000000001` |
| D3 | No cancelled-state overlay in Preview Monitor | **FIXED** | `LivePreviewMonitor.tsx` renders `Render cancelled` overlay (`data-testid="live-preview-cancelled-overlay"`) with draft-preservation note | code + unit tests |
| D4 | Failed overlay renders empty message line | **FIXED** | `{activeJob?.message ? <div>…</div> : null}` conditional | code |
| D5 | Batch status raw in Inspector vs humanized in Panel | **FIXED** | Shared `formatBatchStatus` in `studio-web/src/timelineMaster/contracts.ts`; used by Inspector, MasterPanel `statusHint`, and the new batch clip badge | Live: `Status: Ready` |
| D6 | Render queue shows raw truncated `batchBlockId` | **FIXED** | `CompactRenderQueue.tsx` fetches the Timeline master and maps `batchBlockId → batch.label`; falls back to truncated id only while labels load | code |
| D7 | No per-batch status badge on batch clips | **FIXED** | `DirectorTracks.tsx` batch clip renders `formatBatchStatus(batch.status)` badge (`track-clip__badge`, warn/good/bad variants) for any non-Ready/Draft status | Live: Batch 1 shows red `Failed` badge |
| D8 | Disabled buttons lack plain-language reasons | **FIXED** | `TimelineMasterPanel.tsx` Generate Current/Selected/Full Scene, Stop, Resume all carry descriptive `title` attributes; `TimelineToolbar` already modelled the pattern (Inpaint) | code |
| D9 | Batch lane windowing not scroll-aware | **FIXED** | `DirectorTracks.tsx` unions the playhead/selection-centered window with the visible scroll range (`onScroll` → `boardScroll` state → time-range → batch index range) | code; 100+ scale re-verified by wiring cert scale gate (t6) |
| D10 | Polling loops not visibility-gated | **FIXED** | `document.visibilityState === "hidden"` guard added to all three pollers: `TimelinePreviewComposer.tsx` (2.5s), `LivePreviewMonitor.tsx` (2.5s legacy), `CompactRenderQueue.tsx` (3s) | code |
| D11 | N parallel `getTimelineReferences` per `tl` change | **FIXED** | 600 ms debounce + visibility gate on the refs-count prefetch in `DirectorTracks.tsx` | code |
| W3 | Hardcoded generator dropdown | **FIXED** | Backend `/generators` payload now includes `timelineAdapters` (full capability records); Inspector builds options from it, filters `cert-stub-local`, disables non-executable adapters with honest capability labels, keeps legacy ids selectable | Live: dropdown shows `MiniMax H3 Text-to-Video (Local)`, `MiniMax H3 Image-to-Video (Local)`, `LTX 2.3 (Local)`, `Seedance (Hosted API)`, `Kling (Hosted API)` — registry labels, not hardcoded strings |

### Additional live-audit findings repaired

| # | Finding | Root cause | Repair |
|---|---------|-----------|--------|
| L1 | Inspector showed **"Scene not found"** as the Production Readiness blocker for a scene that exists | `scene_production_package` returns `{"ok": False, "error": "Scene not found"}` when the scene has no readiness record; `timeline_context/service.py` surfaced the raw error as `blockerSummary` | `timeline_context/service.py` maps that error to `Readiness not assessed yet — run Co-Director Preflight to assess this scene.` (status/gate semantics unchanged) — verified live |
| L2 | `GET /api/codirector/providers/active/health` returned **500** twice during page load | `NameError: MODEL_NOT_FOUND is not defined` in `codirector/providers/ollama.py:191,246` — constant used but never imported; triggered whenever the selected Ollama model is not installed | Added `MODEL_NOT_FOUND` to the `app.codirector.errors` import — verified live: endpoint now returns **200** with honest `Model Missing` payload |

---

## Phase 10 — Network/console audit against live Beta

**Harness:** `scripts/audit_timeline_network_console.mjs` (Playwright; captures `console` error/warning, `pageerror`, `requestfailed`, `response >= 400`; drives batch select, batch-lane scroll, Co-Director rail open/close, page refresh, re-select).
**Artifact:** [`artifacts/timeline-network-console-audit.json`](artifacts/timeline-network-console-audit.json)

### Result (post-repair run)

| Metric | Count | Classification |
|--------|-------|----------------|
| Timeline-critical failures | **0** | — |
| Bad responses (HTTP ≥ 400) | **0** | provider-health 500 eliminated by L2 fix |
| Page errors | 1 | `ApiError: Studio API is currently unavailable…` — UI outage state triggered by the ERR_NETWORK_CHANGED burst (below) |
| Console errors | 7 | all `net::ERR_NETWORK_CHANGED` resource entries |
| Failed requests | 13 | 7 × `ERR_NETWORK_CHANGED`, 6 × `ERR_ABORTED` |

### In-scope classification list (published per plan)

- **Timeline-critical routes (must be clean):** `/api/projects/:id/scenes/:sid/director*` family, `/api/director-timeline*`, `/api/projects/:id/jobs`, `/api/projects/:id/preview/stream`, `/api/codirector/timeline*`, `/api/codirector/context*`, `/api/assets*`. **All clean in both runs.**
- **Noise (expected, not defects):** `/api/health` `ERR_ABORTED` (React Query/SSE cancellation on refresh), `/preview/stream` `ERR_ABORTED` (SSE close on navigation), favicon, install/setup probes.
- **Unrelated but noteworthy:** `/api/production-control/resolve`, `/api/codirector/status/*`, `/api/codirector/conversations/:id/revision` — all victims of the same `ERR_NETWORK_CHANGED` burst, not route defects.

### ERR_NETWORK_CHANGED — root-cause evidence (feeds t9-stability)

Run 1 fired the burst seconds after a Beta **restart**; run 2 fired it against a **stable, fully healthy** server (started 21:08:30Z, audit 21:09+Z, zero restarts in between — supervisor log confirms). Conclusion: the bursts are **client-side** — Chrome aborts in-flight loopback requests when Windows raises a network-change notification (adapter/VPN/Parsec). The server never logged a disconnect; the API kept serving 200s throughout (api.log).

The visible "flicker" is the UI amplifying a sub-second OS-level blip into a full `Studio API is currently unavailable` outage state. Hardening (retry-on-`ERR_NETWORK_CHANGED` with backoff before declaring outage) is scoped to **t9-stability**, which owns the ERR_NETWORK_CHANGED correlation work.

---

## Verification

- `npx tsc -b` clean; `npx oxlint` — only pre-existing fast-refresh/exhaustive-deps warnings.
- `npx vitest run src/components/timeline-master/TimelinePreviewComposer.test.ts` — **13/13 passed**.
- Beta rebuilt + restarted; `http://127.0.0.1:8760/` and `http://127.0.0.1:8758/api/health` both **200**.
- Live evidence screenshots: `artifacts/ui-audit-batch-inspector-generator-dropdown.png` (capability-driven dropdown + batch Inspector), `artifacts/ui-audit-fresh-timeline-state.png` (fresh load, Failed badge on Batch 1, readiness panel).

## Remaining known limitations (honest)

- `ERR_NETWORK_CHANGED` console noise persists until t9-stability lands the health-retry hardening (client OS-level trigger; server-side proven healthy).
- Batch lane windowing union can render more than `WIN=80` nodes when the viewport genuinely shows more batches; bounded by viewport size, verified acceptable at 101-batch scale in the wiring cert.
