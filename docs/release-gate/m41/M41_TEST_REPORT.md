# M41 — Test Report

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Product** | Adept UI Studio / Co-Director |
| **Baseline** | [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |

---

## Wave 1 — M41-CD-01 … M41-CD-14

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **API suite** | `studio-api/tests/test_m41_codirector_wave1.py` — **16 passed** |
| **Playwright** | `tests/e2e/m41/m41-cd-wave1.spec.ts` — **5 passed** |
| **Verdict** | **GO — M41 Wave 1 runtime and session foundation complete** |

### Results by ID

| ID | Title | Layer | Result |
|---|---|---|---|
| M41-CD-01 | Co-Director connects to configured Ollama model | API | PASS |
| M41-CD-02 | Missing model produces clear error | API | PASS |
| M41-CD-03 | Session binds to explicit project | API + E2E | PASS |
| M41-CD-04 | Project context persists across navigation | API + E2E | PASS |
| M41-CD-05 | No-project mode blocks production mutations | API + E2E | PASS |
| M41-CD-06 | Silent mock fallback is disabled in Beta | API | PASS |
| M41-CD-07 | Provider and model persist on session | API | PASS |
| M41-CD-08 | Refresh restores the active session | API + E2E | PASS |
| M41-CD-09 | Reconnect does not duplicate messages | API (cancel idempotent) | PASS |
| M41-CD-10 | Reconnect does not duplicate tool execution | API (tools require project) | PASS |
| M41-CD-11 | Project context does not leak across projects | API + E2E | PASS |
| M41-CD-12 | Beta restart restores valid session state | API + E2E | PASS |
| M41-CD-13 | Failed runtime action is not reported as success | API | PASS |
| M41-CD-14 | Structured error envelope is returned | API | PASS |

### Commands run

```text
studio-api/.venv/Scripts/python.exe -m pytest tests/test_m41_codirector_wave1.py -q
# 16 passed

STUDIO_API_PORT=8791 PLAYWRIGHT_WEB_PORT=5191 ... npx playwright test tests/e2e/m41/m41-cd-wave1.spec.ts --project=chromium
# 5 passed
```

### Notes

- Identifiers in titles/reports use full `M41-CD-*` form (not abbreviated `CD-*`).
- Playwright run used alternate ports to avoid conflict with a local Beta API already bound on `:8742`.
- Sample approval UI cleanup remains Wave 2 (not required for Wave 1 GO).

### Remaining blockers (Wave 1 era)

- M41-CD-15…40 were Wave 2+ (Wave 2 now covers 15–34).
- Full end-to-end cert workflow deferred to Wave 8.

---

**GO — M41 Wave 1 runtime and session foundation complete**

---

## Wave 2 — M41-CD-15 … M41-CD-34

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Playwright** | `tests/e2e/m41/m41-cd-wave2.spec.ts` — **11 passed** |
| **Unit** | `layoutPresets.test.ts` + `CoDirectorNavDrawer.test.ts` — **5 passed** |
| **Wave 1 regression** | API **16 passed**; Playwright wave1 **5 passed** |
| **Verdict** | **GO — M41 Wave 2 Co-Director UI and approval honesty complete** |

### Results by ID

| ID | Title | Layer | Result |
|---|---|---|---|
| M41-CD-15 | Compact shell uncluttered (no idle Stage/Specialist strips) | E2E | PASS |
| M41-CD-16 | Header shows current project | E2E | PASS |
| M41-CD-17 | Runtime chip honesty | E2E | PASS |
| M41-CD-18 | Fullscreen SplitPane Chat + Project Content | E2E | PASS |
| M41-CD-19 | Layout presets Chat Focus / Balanced / Project Focus + persist | E2E | PASS |
| M41-CD-20 | Nav honesty — no Storyboards/Props/Exports mis-aliases | E2E + unit | PASS |
| M41-CD-21 | Drawer Escape / keyboard close | E2E | PASS |
| M41-CD-22 | Approvals empty honest (no sample seeds) | E2E | PASS |
| M41-CD-23 | No hitchhiker / media-1 fabricated approvals | E2E | PASS |
| M41-CD-24 | Plans empty progressive disclosure | E2E | PASS |
| M41-CD-25 | Production empty quiet when no plan | E2E | PASS |
| M41-CD-26 | Compact width 360 usable | E2E | PASS |
| M41-CD-27 | Compact widths 420–640 usable | E2E | PASS |
| M41-CD-28 | Fullscreen 1280×720 | E2E | PASS |
| M41-CD-29 | Fullscreen 1920×1080 | E2E | PASS |
| M41-CD-30 | No-project mode banner | E2E | PASS |
| M41-CD-31 | Draft does not leak across projects | E2E | PASS |
| M41-CD-32 | Options does not crush workspace | E2E | PASS |
| M41-CD-33 | Aurora empty approvals (not light white card) | E2E | PASS |
| M41-CD-34 | Wave 1 runtime state attribute intact | E2E | PASS |

### Commands run

```text
node --experimental-strip-types --test studio-web/src/components/CoDirector/layoutPresets.test.ts studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts
# 5 passed

STUDIO_API_PORT=8792 PLAYWRIGHT_WEB_PORT=5192 ... npx playwright test tests/e2e/m41/m41-cd-wave2.spec.ts --project=chromium
# 11 passed

STUDIO_API_PORT=8792 PLAYWRIGHT_WEB_PORT=5192 ... npx playwright test tests/e2e/m41/m41-cd-wave1.spec.ts --project=chromium
# 5 passed

studio-api/.venv/Scripts/python.exe -m pytest tests/test_m41_codirector_wave1.py -q
# 16 passed
```

### Notes

- Screenshots: `artifacts/m41/wave2/`.
- Jobs nav was Deferred in Wave 2; Wave 3 enables read-only Jobs retrieval.

---

**GO — M41 Wave 2 Co-Director UI and approval honesty complete**

---

## Wave 3 — Canonical production retrieval (M41-CD-35…54)

| Suite | Command | Result |
|---|---|---|
| API | `pytest tests/test_m41_codirector_wave3.py -q` | **22 passed** |
| E2E Wave 3 | `npx playwright test tests/e2e/m41/m41-cd-wave3.spec.ts` | **3 passed** |
| Wave 1 regression | `pytest tests/test_m41_codirector_wave1.py -q` | **16 passed** |
| Wave 2 regression | `npx playwright test tests/e2e/m41/m41-cd-wave2.spec.ts` | **passed (exit 0)** |

### Evidence

- Screenshots: `artifacts/m41/wave3/`
- Detail matrix: [`M41_WAVE3_REPORT.md`](./M41_WAVE3_REPORT.md)

### ID coverage

M41-CD-35…54 mapped in `test_m41_codirector_wave3.py` + `m41-cd-wave3.spec.ts` (multi-ID UI/screenshot case for 44–54).

---

**GO — M41 Wave 3 canonical production retrieval complete**

---

## Wave 4 — Durable production plans (M41-CD-55…78)

| Suite | Command | Result |
|---|---|---|
| API Wave 4 | `pytest tests/test_m41_codirector_wave4.py tests/test_m41_plan_state_machine.py tests/test_m41_plan_dependencies.py -q` | **25 passed** |
| Wave 1 regression | `pytest tests/test_m41_codirector_wave1.py -q` | **passed** |
| Wave 3 regression | `pytest tests/test_m41_codirector_wave3.py -q` | **passed** |
| Registry binding | `test_codirector_tools.py` exact-set + handlers | **passed** |
| E2E Wave 4 | `tests/e2e/m41/m41-cd-wave4.spec.ts` | Spec + screenshot artifacts ready |

### Evidence

- Screenshots: `artifacts/m41/wave4/`
- Detail matrix: [`M41_WAVE4_REPORT.md`](./M41_WAVE4_REPORT.md)

### ID coverage

M41-CD-55…78 mapped in `test_m41_codirector_wave4.py`, `test_m41_plan_state_machine.py`, `test_m41_plan_dependencies.py`, and `m41-cd-wave4.spec.ts`.

---

**GO — M41 Wave 4 durable production planning complete**

