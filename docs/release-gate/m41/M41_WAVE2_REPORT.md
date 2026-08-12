# M41 Phase 4.1 — Wave 2: Co-Director UI and Approval Honesty

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Wave** | 2 — Co-Director UI and Approval Honesty |
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Baseline** | [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) · Wave 1 GO |
| **Related** | [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) · [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) · [`M41_WAVE1_REPORT.md`](./M41_WAVE1_REPORT.md) |
| **Verdict** | **GO — M41 Wave 2 Co-Director UI and approval honesty complete** |

---

## 1. Objective

Polish Co-Director compact and fullscreen UI architecture with progressive disclosure, honest Approvals, Aurora-compliant cards/empty states, and layout presets — without claiming production intelligence that is not yet wired.

Wave 2 does **not** include specialist tool execution, Director 2.0 handoff, generation wiring, Editor place/subtitle tools, or full cert (M41-CD-35…40 / Waves 3–8).

---

## 2. Acceptance criteria

| Criterion | Status |
|---|---|
| Compact default = conversation + runtime status + project + composer | Met |
| No permanent StageStrip / SpecialistStrip in compact | Met |
| Progressive disclosure — inactive systems do not reserve chrome | Met |
| Fullscreen Chat + Project Content via shared `SplitPane` | Met |
| Layout presets: Chat Focus 70/30, Balanced 50/50, Project Focus 30/70 | Met |
| Manual resize still persists | Met |
| Fake / sample approval seeds removed | Met |
| Honest Approvals empty copy | Met |
| Proposal Approve gated when `!productionCapable` | Met |
| Aurora dark cards / empty states (no light sample chrome) | Met |
| Honest nav (no Storyboards/Props/Exports mis-aliases) | Met |
| Narrow widths 360–640 usable | Met |
| Fullscreen 1280×720 and 1920×1080 usable | Met |
| Wave 1 runtime / binding / reconnect safeguards intact | Met |
| Composer draft does not leak across projects | Met |
| M41-CD-15 … M41-CD-34 pass | Met |

---

## 3. What shipped

### 3.1 Progressive Disclosure Rule

Co-Director reveals complexity only when needed.

**Default state (always):**

- Conversation
- Runtime status
- Current project (or `No Project Selected`)
- Composer

**Contextual only:** proposal cards, production plans, job monitoring, timeline proposals, character inspectors, continuity warnings — when real data / selection exists.

Compact popup no longer mounts `CoDirectorStageStrip` or `CoDirectorSpecialistStrip`. Fullscreen keeps StageStrip only when an active plan stage exists and SpecialistStrip only when a character profile is selected.

Empty states stay compact and visually quiet — short title, one sentence, at most one action; no fabricated example records.

### 3.2 Compact polish

- Header shows project name beside Co-Director identity
- Runtime chip from Wave 1 retained
- Composer remains the production entry (Send/Stop/attach/Options) — no permanent production toolbar under the input
- Certified usable at 360, 420, 520, 640 widths

### 3.3 Fullscreen SplitPane + layout presets

Replaced CSS-grid workspace with Phase 4.0 `SplitPane`:

| Preset | Chat (primary) | Project Content |
|---|---|---|
| Chat Focus | 70% | 30% |
| Balanced | 50% | 50% |
| Project Focus | 30% | 70% |

Persistence:

- Size: `adept_codirector_split_primary`
- Preset id: `adept_codirector_split_preset`
- `contextPanelOpen` (Wave 1) still controls secondary collapse

Accessible labeled preset group in the fullscreen header; keyboard resize on the SplitPane separator.

### 3.4 Navigation honesty

`buildNavEntries` rewritten to honest surfaces only:

Current Project, Overview, Project Content, Conversation, Scripts, Characters, Production Bible, Assets/Library, Plans, Approvals, Jobs (**Deferred** / disabled), Settings, System Status.

Removed mis-aliases: Storyboards → script, Props → characters, Exports → editor.

Drawer Escape + focus return retained via shared `Drawer`.

### 3.5 Approval honesty

| Surface | Wave 2 action |
|---|---|
| `ApprovalsList` hardcoded `story-1` / `media-1` | **Removed** — loads real `listProposals` |
| `ApprovalCenterPanel` hitchhiker seeds | **Removed** — real proposals or honest empty |
| Empty Approvals copy | Exact intent below |
| Proposal card Approve | Disabled when `!productionCapable`; no Approve after terminal states |

Empty copy:

```text
No approvals are waiting.
Co-Director will place proposed production changes here before applying them.
```

### 3.6 Shared Aurora card primitives

Under `studio-web/src/components/CoDirector/cards/`:

`CoDirectorContentCard`, entity/asset/plan/approval/warning/job variants, `CoDirectorEmptyState`, `CoDirectorErrorState`.

Cinematic CSS overrides kill light `.codirector-plan` / `.codirector-task` / `.codirector-cta-card` fills inside `.codirector-shell.cinematic`.

### 3.7 Draft project scope (Wave 1 regression hardening)

Composer drafts persist per project:

```text
adept_codirector_draft_<projectId>
adept_codirector_draft__none   (no-project)
```

Legacy global `adept_codirector_draft` is cleared and no longer written. Draft swaps on project bind change so text cannot leak across projects.

---

## 4. Files changed

### Frontend

| File | Change |
|---|---|
| `studio-web/src/components/CoDirector/CoDirectorShell.tsx` | Progressive disclosure compact; SplitPane + presets |
| `studio-web/src/components/CoDirector/layoutPresets.ts` | Preset ratios / persist helpers (new) |
| `studio-web/src/components/CoDirector/CoDirectorHeader.tsx` | Project label + layout preset controls |
| `studio-web/src/components/CoDirector/navEntries.ts` | Honest nav entries (new) |
| `studio-web/src/components/CoDirector/CoDirectorNavDrawer.tsx` | Uses honest nav; Jobs deferred |
| `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` | Real proposals; quiet empties; Plans tab |
| `studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx` | Meta fields; productionCapable gate |
| `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` | Passes productionCapable into proposal cards |
| `studio-web/src/components/CoDirector/ApprovalCenterPanel.tsx` | No sample seeds |
| `studio-web/src/components/CoDirector/cards/*` | Empty/error/content card kit (new) |
| `studio-web/src/components/CoDirector/codirector-cinematic.css` | SplitPane host; Aurora card overrides; compact polish |
| `studio-web/src/components/ui/SplitPane.tsx` | Preset size requests; keyboard resize |
| `studio-web/src/components/CoDirector/types.ts` | Project-scoped draft keys |
| `studio-web/src/components/CoDirector/CoDirectorSession.tsx` | Draft swap on project bind |

### Tests / docs / artifacts

| File | Role |
|---|---|
| `tests/e2e/m41/m41-cd-wave2.spec.ts` | M41-CD-15…34 Playwright coverage |
| `studio-web/src/components/CoDirector/layoutPresets.test.ts` | Preset ratio unit tests |
| `studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts` | Nav honesty unit tests |
| `docs/release-gate/m41/M41_IMPLEMENTATION_REPORT.md` | Wave 2 audit + implementation log |
| `docs/release-gate/m41/M41_TEST_REPORT.md` | Wave 2 test log |
| `docs/release-gate/m41/M41_WAVE2_REPORT.md` | This consolidated Wave 2 report |
| `artifacts/m41/wave2/*.png` | Screenshot evidence |

---

## 5. Test results

### 5.1 Suite totals

| Suite | Path | Result | Exit code |
|---|---|---|---|
| Wave 2 Playwright | `tests/e2e/m41/m41-cd-wave2.spec.ts` | **11 passed** | 0 |
| Wave 2 component/unit | `layoutPresets.test.ts` + `CoDirectorNavDrawer.test.ts` | **5 passed** | 0 |
| Wave 1 Playwright (regression) | `tests/e2e/m41/m41-cd-wave1.spec.ts` | **5 passed** | 0 |
| Wave 1 API/unit (regression) | `studio-api/tests/test_m41_codirector_wave1.py` | **16 passed** | 0 |
| **Total** | | **37 passed** | **all 0** |

Commands:

```text
node --experimental-strip-types --test studio-web/src/components/CoDirector/layoutPresets.test.ts studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts
# 5 passed · exit 0

STUDIO_API_PORT=8792 PLAYWRIGHT_WEB_PORT=5192 PLAYWRIGHT_BASE_URL=http://127.0.0.1:5192 STUDIO_API_BASE=http://127.0.0.1:8792 \
  npx playwright test tests/e2e/m41/m41-cd-wave2.spec.ts --project=chromium
# 11 passed · exit 0

STUDIO_API_PORT=8792 PLAYWRIGHT_WEB_PORT=5192 ... npx playwright test tests/e2e/m41/m41-cd-wave1.spec.ts --project=chromium
# 5 passed · exit 0

studio-api/.venv/Scripts/python.exe -m pytest tests/test_m41_codirector_wave1.py -q
# 16 passed · exit 0
```

### 5.2 M41-CD-15 … M41-CD-34 ID matrix

Eleven Playwright cases cover twenty certification IDs (some cases assert multiple IDs). Unit tests provide additional nav/preset evidence. Each ID maps to evidence below.

| ID | Test | Result | Evidence |
|---|---|---|---|
| M41-CD-15 | Compact popup renders without overflow / idle strips | PASS | Playwright: `M41-CD-15 Compact shell is uncluttered…`; screenshot `m41-cd-15-compact.png` |
| M41-CD-16 | Header shows current project | PASS | Playwright: `M41-CD-16 / M41-CD-17 Header shows project + runtime chip honesty` |
| M41-CD-17 | Runtime chip remains truthful | PASS | Same case as M41-CD-16 (`codirector-runtime-chip` visible, non-fabricated Ready) |
| M41-CD-18 | Fullscreen SplitPane Chat + Project Content | PASS | Playwright: `M41-CD-18 / M41-CD-19 Fullscreen SplitPane + layout presets persist` (`ds-split-pane`) |
| M41-CD-19 | Layout presets Chat Focus / Balanced / Project Focus persist | PASS | Same case as M41-CD-18; unit: `layoutPresets.test.ts`; screenshot `m41-cd-19-split-balanced.png` |
| M41-CD-20 | Nav honesty — no Storyboards/Props/Exports mis-aliases | PASS | Playwright: `M41-CD-20 / M41-CD-21 Nav honesty…`; unit: `CoDirectorNavDrawer.test.ts` |
| M41-CD-21 | Drawer Escape / keyboard close | PASS | Same case as M41-CD-20 (`Escape` closes drawer) |
| M41-CD-22 | Approvals empty is honest | PASS | Playwright: `M41-CD-22 / M41-CD-23 Approvals empty is honest…`; screenshot `m41-cd-22-approvals-empty.png` |
| M41-CD-23 | No hitchhiker / media-1 / Storyteller sample seeds | PASS | Same case as M41-CD-22 (asserts those strings absent) |
| M41-CD-24 | Plans empty progressive disclosure | PASS | Playwright: `M41-CD-24 / M41-CD-25 Progressive disclosure…` (`codirector-plans-empty`) |
| M41-CD-25 | Production empty quiet when no plan | PASS | Same case as M41-CD-24 (`codirector-production-empty` or real stage list) |
| M41-CD-26 | Compact width 360 usable | PASS | Playwright: `M41-CD-26 / M41-CD-27 Compact widths 360–640 usable`; screenshot `m41-cd-26-width-360.png` |
| M41-CD-27 | Compact widths 420 / 520 / 640 usable | PASS | Same case as M41-CD-26 (loop over 420, 520, 640) |
| M41-CD-28 | Fullscreen 1280×720 usable | PASS | Playwright: `M41-CD-28 / M41-CD-29 Fullscreen responsive…`; screenshot `m41-cd-28-1280x720.png` |
| M41-CD-29 | Fullscreen 1920×1080 usable | PASS | Same case as M41-CD-28; screenshot `m41-cd-28-1920x1080.png` |
| M41-CD-30 | No-project mode banner | PASS | Playwright: `M41-CD-30 / M41-CD-31 No-project mode + draft project scope…` |
| M41-CD-31 | Draft does not leak across projects | PASS | Same case as M41-CD-30 (project-scoped `adept_codirector_draft_*`) |
| M41-CD-32 | Options does not crush workspace | PASS | Playwright: `M41-CD-32 Options does not crush workspace` |
| M41-CD-33 | Aurora empty approvals (not light white card) | PASS | Playwright: `M41-CD-33 / M41-CD-34 Aurora cards + Wave 1 runtime…` |
| M41-CD-34 | Runtime and project status remain truthful after UI changes | PASS | Same case as M41-CD-33 (`data-runtime-state` present) |

---

## 6. Visual evidence

| Artifact | Covers |
|---|---|
| `artifacts/m41/wave2/m41-cd-15-compact.png` | Compact uncluttered popup |
| `artifacts/m41/wave2/m41-cd-19-split-balanced.png` | SplitPane + Balanced preset |
| `artifacts/m41/wave2/m41-cd-22-approvals-empty.png` | Honest Approvals empty |
| `artifacts/m41/wave2/m41-cd-26-width-360.png` | Narrow 360 width |
| `artifacts/m41/wave2/m41-cd-28-1280x720.png` | Fullscreen 1280×720 |
| `artifacts/m41/wave2/m41-cd-28-1920x1080.png` | Fullscreen 1920×1080 |

---

## 7. Wave 1 regression results

Wave 1 suites were re-run after Wave 2 UI changes. All commands exited with code **0**.

| Suite | Result |
|---|---|
| `studio-api/tests/test_m41_codirector_wave1.py` | **16 passed** |
| `tests/e2e/m41/m41-cd-wave1.spec.ts` | **5 passed** |

Wave 1 IDs M41-CD-01 … M41-CD-14 remain PASS (see [`M41_WAVE1_REPORT.md`](./M41_WAVE1_REPORT.md) / [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md)).

---

## 8. Remaining blockers and deferrals

There are no blockers to the Wave 2 gate.

The following are intentionally deferred and must not be interpreted as completed:

- canonical production read tools;
- specialist tool execution;
- Director 2.0 timeline handoff;
- image, video, voice, music, and SFX generation wiring;
- Editor placement operations;
- subtitle operations;
- job inspection and reconnection;
- full M41 certification.

Jobs nav entry is labeled **Deferred** and disabled until later-wave job monitoring exists.

**Next step:** Wave 3 — canonical read tools, `@` resolve, and provider honesty.

Do not treat Wave 2 GO as Phase 4.1 complete — later waves remain required for full Co-Director production certification.

---

## 9. Final verdict

**GO — M41 Wave 2 Co-Director UI and approval honesty complete**
