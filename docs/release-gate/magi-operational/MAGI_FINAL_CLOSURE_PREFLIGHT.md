# MAGI Final Closure — Preflight Audit

| Field | Value |
|---|---|
| **Phase** | F0 — Freeze + read-only state audit |
| **Date** | 2026-08-08 |
| **Branch (current)** | `feature/ai-guided-setup` |
| **Closure branch (planned)** | `phase2/magi-final-closure` (created at F7) |
| **Verdict target** | `GO — MAGI OPERATIONAL INTEGRITY CERTIFIED FOR CREATOR MANUAL BETA` |

---

## 1. Architecture state (read-only snapshot)

| Layer | Path | Status |
|---|---|---|
| Sequence document model | `studio-web/src/magiSequence/types.ts` | Implemented |
| Edit engine (pure reducer) | `studio-web/src/magiSequence/engine.ts` | Implemented |
| Error taxonomy (frontend) | `studio-web/src/magiSequence/errors.ts` | Implemented |
| Focus/keyboard contract | `studio-web/src/magiSequence/focus.ts`, `MagiFocusContext.tsx`, `useMagiKeyboard.ts` | Implemented |
| Undo/redo snapshot stack | `studio-web/src/components/magi/overlays/MagiEditorCommandStack.ts` | Implemented |
| Layout/preset persistence | `studio-web/src/components/magi/layout/MagiLayoutPersistence.ts`, `MagiWorkspaceLayoutProvider.tsx`, `MagiAccordion.tsx` | Implemented |
| Editor shell | `studio-web/src/components/magi/MagiEditorWorkspace.tsx` (1,902 lines) | Implemented |
| Overlay state/inspector/layer | `studio-web/src/components/magi/overlays/` | Implemented |
| Backend routes/store/validation | `studio-api/app/magi/api.py`, `sequence/`, `errors.py`, `readiness.py`, `production_gate.py` | Implemented |
| Overlay composition renderer | `studio-api/app/magi/composition/`, `overlays/` | Implemented |
| Timeline handoff (W46) | `studio-api/app/magi/timeline_handoff.py` | Implemented |
| Co-Director read-only tools | `studio-api/app/codirector/tools/handlers/magi.py` | Implemented |

Sub-milestones m1–m8 are implementation-complete with unit + backend coverage. The M42 Wave 4B wave was stamped **GO** (2026-07-30) with video/audio NLE execution, motion-title burn-in, and Wave 5 identity continuity explicitly deferred.

---

## 2. Remaining discrepancy — Scenario I/K

- `tests/e2e/m42/magi-editor.spec.ts` → "Scenario I/K shell" asserts `magi-command` visible without opening the Command pane.
- **Determination (product intent):** the Default workspace preset intentionally collapses the Command pane.
  - `DEFAULT_LAYOUT.accordionState.command = false` (`MagiLayoutPersistence.ts:77`).
  - Only the `image-editing` preset sets `command: true` (`:246`); `applyPreset("default")` returns `DEFAULT_LAYOUT` (`:280-281`).
  - `MagiAccordion.tsx:34-43` renders panel children only when `open`, so `magi-command` is correctly absent from the DOM under Default.
  - Command is reveal-on-demand: header `#magi-acc-btn-command` is always present; it auto-opens on proposal (`MagiEditorWorkspace.tsx:954`).
  - The old test's `Text & Graphics` button no longer exists (pane is now `Graphics`); that line is dead.
  - The failure reproduces identically with and without the Phase 7 overlay-loop fix — independent of it.
- **Resolution per Law 1:** preserve product behavior; rewrite the stale test to explicitly open the Command pane, assert `magi-command` contents, and keep the original "text graphics + overlay layer hooks" intent. Suite target **5/5**.

---

## 3. Closure scope (in scope)

1. F1 — Scenario I/K test rewrite (test-only; no product behavior change).
2. F2 — Complete MAGI regression matrix (backend pytest, frontend vitest, typecheck, lint, three authoritative Playwright suites).
3. F3 — Evidence-based operational re-certification (persistence, editing, preview, handoff, errors, Co-Director reads, project isolation).
4. F4 — Creator manual-beta preflight (clean Beta restart, fresh project, console/network cleanliness, checklist doc).
5. F5 — Independent evidence-based verifier (subagent that did not implement Phase 7 repairs).
6. F6 — Authoritative final certification report; Law 30 supersede markers on stale MAGI docs.
7. F7 — Git provenance: dedicated branch, MAGI-owned paths + hunk-level shared-file staging, single commit, SHA recorded.

Small repairs exposed by certification ARE allowed where required to satisfy an existing contract, each with a regression test. No feature expansion.

---

## 4. Explicitly excluded work

- New editing systems, generation providers, rendering architecture, Co-Director write tools, Timeline architecture, overlay architecture, frame compositor, speculative NLE ops, unrelated UI redesign.
- GPU generation (no Comfy/fal renders during certification).
- Co-Director MAGI write/proposal/approval (read-only contract).
- `Lift`, `Extract`, `Slip`, `Slide`, `Join`, `AddTrack`, `ReorderTrack` (engine support exists but no UI surface — documented N/A, not fabricated).
- Full frame-accurate canvas composition (explicitly documented future capability).
- Identity continuity (Wave 5) and motion-title burn-in (deferred M42 W4B items).
- `SEQUENCE_NOT_FOUND` remains a defined latent taxonomy entry (normal GET returns an empty canonical sequence); no fake endpoint invented.

---

## 5. Dirty-tree ownership map

### 5.1 MAGI-owned untracked paths (stage wholesale)

```
studio-web/src/components/magi/**                 (incl. layout/, overlays/, magi-editor.css)
studio-web/src/magiSequence/**
studio-api/app/magi/**
studio-api/app/codirector/tools/handlers/magi.py
studio-api/tests/test_m42_w4b_magi.py
studio-api/tests/test_m42_w4b_magi_command_parse.py
studio-api/tests/test_m42_w4b_overlays.py
studio-api/tests/test_magi_sequence_repairs.py
studio-api/tests/test_codirector_magi_read_only_tools.py
tests/e2e/magi/**
tests/e2e/m412-magi/**
tests/e2e/m42/magi-editor.spec.ts
docs/release-gate/magi-operational/**
docs/release-gate/m412-magi/**
docs/release-gate/m42/M42_W4B_MAGI_*.md            (MAGI-owned subset only — NOT the whole m42 folder)
docs/release-gate/m42/M42_W4C_TIMELINE_MAGI_INTEGRATION_REPORT.md
docs/release-gate/m42/M42_W5_MAGI_CORRECTION_REPORT.md
```

### 5.2 Shared tracked files with mixed MAGI/non-MAGI changes (hunk-level staging at F7)

| File | MAGI-relevant hunk | Risk |
|---|---|---|
| `studio-web/src/App.tsx` | MAGI workspace route/mount | Mixed with non-MAGI changes |
| `studio-web/src/api.ts` | MAGI api methods | Mixed |
| `studio-web/src/pages/ProjectEditor.tsx` | MAGI workspace entry | Mixed |
| `studio-web/src/types.ts` | MAGI type additions | Mixed |
| `studio-web/src/styles.css` | `magi-*` style blocks | Mixed |
| `studio-web/package.json` | (verify) | Mixed |
| `studio-api/app/main.py` | MAGI router registration | Mixed |
| `studio-api/app/routers/api.py` | MAGI endpoints | Mixed |
| `studio-api/app/feature_flags.py` | MAGI flags | Mixed |
| `playwright.config.ts` | MAGI suite wiring | Mixed |
| `scripts/e2e-start.mjs` | MAGI flags/env | Mixed |
| `tests/e2e/helpers/app.ts` | MAGI helpers | Mixed |

Every staged shared-file hunk will be inspected via `git diff --staged` before commit. If isolation cannot be proven safely, the commit is blocked and documented rather than forced.

---

## 6. Baseline recorded before any further change

- `tests/e2e/magi/magi-operational-integrity.spec.ts` — 5/5 PASS (2026-08-08, after Phase 7 defects fixed).
- `tests/e2e/m412-magi/m412-magi-editor-nle.spec.ts` — 2/2 PASS.
- `tests/e2e/m42/magi-editor.spec.ts` — **5/5 PASS (2026-08-08, after F1)**; Scenario I/K rewritten per product intent (see §6.1).
- Frontend unit (vitest): `engine.test.ts`, `MagiEditorCommandStack.test.ts`, `MagiLayoutPersistence.test.ts`, `errors.test.ts` — previously green (re-run in F2).
- Backend (pytest): `test_m42_w4b_magi.py`, `test_m42_w4b_magi_command_parse.py`, `test_m42_w4b_overlays.py`, `test_magi_sequence_repairs.py`, `test_codirector_magi_read_only_tools.py` — re-run in F2.
- Overlay render-loop defect (Phase 7): fixed in `useMagiOverlayState.ts` (optionsRef pattern).
- OP-01 `ERR_ABORTED` gate: fixed in `magi-operational-integrity.spec.ts` (intentional StrictMode supersede-fetch abort ignored).

No implementation may begin before this document exists — it does.

---

## 6.1 F1 — Scenario I/K rewrite evidence

**Date:** 2026-08-08 · **Status:** DONE — suite now **5/5 PASS**.

- **Root cause confirmed:** `DEFAULT_LAYOUT.accordionState.command = false` (`MagiLayoutPersistence.ts:70-97`); `MagiAccordion.tsx:34-43` unmounts panel children when collapsed, so `magi-command` is absent from the DOM under Default. The old assertion read product state it never opened.
- **Fix (test-only):** `tests/e2e/m42/magi-editor.spec.ts:111` now (a) seeds a disposable project + one PNG asset and navigates directly to `/project/{id}?workspace=magi`, (b) asserts `magi-editor` + `magi-strip`, (c) opens the collapsed **Graphics** accordion (`#magi-acc-btn-graphics`) and asserts `magi-text-graphics`, "Add Text", "Lower Third" (exact), `magi-overlay-render`, (d) asserts the overlay layer hook `magi-overlay-layer` mounts once the viewer auto-selects the seeded asset, (e) opens the collapsed **Command** accordion (`#magi-acc-btn-command`, `aria-expanded=false`), asserts `magi-command`, its `textarea`, `magi-command-stage` ("Stage:"), fills a parseable command and asserts the "Create Proposal" action, then (f) collapse/reopen to verify clean toggle. Project deleted in `finally`.
- **Product behavior preserved:** no application code changed; panes remain collapsed by default (reveal-on-demand).
- **Command** `npx playwright test tests/e2e/m42/magi-editor.spec.ts` → **5 passed (13.0s)**, exit 0. The other four tests were already green.
- **Typecheck:** `tsc -p tsconfig.e2e.json` — no errors in `magi-editor.spec.ts` or `helpers/app.ts` (repo-wide pre-existing errors in unrelated suites unchanged).
