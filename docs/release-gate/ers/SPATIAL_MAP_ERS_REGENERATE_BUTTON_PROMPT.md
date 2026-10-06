# Spatial Map — Regenerate Environment Reference Sheet

**Historical for regenerate-vs-restitch.** Normal GPT Image 2 API generation mode is now governed by `ERS_FULL_SHEET_GPT_IMAGE_2_CERTIFICATION.md` (`ers_pipeline=full_sheet`). This document still governs Regenerate vs targeted Retry.

**Governing prompt for this repair.** Do not edit Character Creator, Scene Creator Mini, Atlas, or Panel 9 geometry.

## Product law

The teal **Regenerate Environment Reference Sheet** button is the creator action. Click must start a real Environment Reference Sheet run, show Generating, persist a new result, and survive reload. An existing complete sheet must not swallow the click.

Named project only: SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`. Observatory map `477b450c-734d-49ae-a40a-51402e0a832f`. Do not recreate Jacob. Do not spawn a new project.

## Root cause

The button already POSTed `ers.generate`. The backend treated a complete matching sheet as done and **recomposed in ~250ms**. The UI stayed on complete. Creators saw nothing.

Retry stays targeted. Regenerate is a full start.

## Required repair

1. Primary button `data-testid="ers-generate"` calls `startErsGeneration()` → `ers.start()` with `forceFull` and no `retry_component`.
2. Monitor **Regenerate** uses the same path. Failed **Retry** stays `ers.retry()`.
3. Backend: `forceFull` skips recompose shortcuts. GPT API Regenerate starts one new `full_sheet` job (not Master→Occupied sequencing).
4. Dirty map: Save Gate, then start. Never silent-return without a visible error.
5. Do not auto-save or auto-regenerate from camera Enabled.

## Gates

- Source/unit: force-full helper; primary testid; start payload includes `forceFull`; retry omits it.
- Smoke: click or POST proves Master (or first missing component) enqueues — not `ers-recompose-*` complete in one tick.
- Playwright: Observatory map; click `ers-generate`; POST `ers.generate` with `forceFull`; monitor `queued|generating`; complete; image changes; reload keeps the sheet.

## Review

Recycle Studio API only after Python changes. Vite HMR for FE. URLs: `http://127.0.0.1:5173/` · `http://127.0.0.1:8758/`.

## Live evidence (2026-08-28)

| Gate | Result |
| --- | --- |
| Pipeline + isolation | **13 passed** |
| FE unit | **37 passed** |
| Playwright | **1 passed** — `tests/e2e/codirector/spatial-map-ers-regenerate-button.spec.ts` (12.3 min) |
| Execution | `f3f20774-f8a4-4bce-bc6e-29bfbf305e40` completed in 730s |
| Result assets | 8 (Master through occupied + composite `98e31374-…`) |
| Prior dead click | `28770a37-…` completed in 240ms (silent recompose) |

### E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — primary **Regenerate Environment Reference Sheet** (`ers-generate`) |
| Frontend | PASS — POST `ers.generate` with `forceFull`, no `retry_component`; Generating visible |
| API | PASS — Studio API `:8758` accepted the execution |
| Backend | PASS — Master enqueued; not `ers-recompose` |
| Persistence | PASS — 8 result assets |
| Runtime | PASS — GPT Image 2 component run ~12 min |
| Result | PASS — new composite; image src changed |
| Reload | PASS — monitor complete, same sheet |
| Downstream | N/A — Mini / CC not reopened |

Review: `http://127.0.0.1:5173/` · `http://127.0.0.1:8758/` (healthz 200). Studio API recycled only.

`GO — SPATIAL MAP REGENERATE ENVIRONMENT REFERENCE SHEET LIVE E2E CERTIFIED`
