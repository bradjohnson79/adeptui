# M41 Phase 4.1 — Wave 1 Report

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Wave** | 1 — Runtime Honesty, Project-Bound Sessions, and Reconnect |
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Baseline** | [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |
| **Related** | [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) · [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) |
| **Verdict** | **GO — M41 Wave 1 runtime and session foundation complete** |

---

## 1. Objective

Make Co-Director’s runtime, model state, project context, session persistence, and reconnect behavior reliable and truthful.

Co-Director must never claim it is connected, project-aware, or operational when the required runtime or project context is unavailable.

Wave 1 does **not** include Wave 2+ UI polish, fake-approval cleanup, tool-registry expansion, specialists, or full cert (M41-CD-15…40).

---

## 2. Acceptance criteria

| Criterion | Status |
|---|---|
| Runtime state accurately shown | Met |
| Ollama / model failures clear | Met |
| Silent mock fallback disabled in Beta | Met |
| Every production session has explicit project binding | Met |
| No-project mode safely blocks production actions | Met |
| Project context persists correctly | Met |
| Sessions reconnect without duplicate actions | Met |
| Project context does not leak | Met |
| Failures remain failures | Met |
| M41-CD-01 … M41-CD-14 pass | Met |

---

## 3. What shipped

### 3.1 Runtime and model state

User-facing states:

- Connected  
- Loading Model  
- Ollama Unavailable  
- Model Unavailable  
- Reconnecting  
- Degraded  
- Tool Execution Unavailable  

Implementation:

- Frontend mapper: `studio-web/src/components/CoDirector/runtimeState.ts`
- Shell/header/Options driven by real health (hardcoded Ready removed)
- Compact chip: **model · connection state · project name** (+ degraded styling)
- Mock provider health marked `testOnly: true` / `honesty: "mocked"` (E2E only)
- Mock provider remains blocked when `STUDIO_E2E` is off (Beta/production)

### 3.2 Production fallback honesty

| Path | Wave 1 action |
|---|---|
| Mock Co-Director outside E2E | Hard-blocked; covered by M41-CD-06 |
| FE `planFromIntention` offline plan success | Removed — surfaces planning unavailable instead |
| Enhance `stub_copy` | Still raises outside E2E; E2E-only residual documented |
| Failed chat/tool | Remains failed; `partial_work_created: false` |

Sample/fake approval cards in Approval Center are **deferred to Wave 2**.

### 3.3 Explicit project binding

- Canonical bind from **active route** or **explicit user action** only (`bindWorkspace` / Select / Create / Resume click)
- No project → **No Project Selected** banner; general chat allowed; production mutations blocked
- Server refuses tool use without project via `PROJECT_REQUIRED`
- `last bound project` is **suggestion-only** (Resume button); never silent production permissions
- `CoDirectorPage` unbinds when `?projectId=` is absent

### 3.4 Canonical session-context contract

Composed from existing stores (no duplicate project-context DB):

```text
projectId, projectName, activeDocumentId, activeSceneId, activeWorkspace,
selectedAssets, provider, model, activeProductionPlan,
sessionStatus, lastSuccessfulToolAction, unresolvedBlockers
```

- FE: `CoDirectorSessionContext` in `types.ts`
- API: `GET /api/codirector/session-context`

### 3.5 Persistence and race safeguards

- Server conversations remain authoritative per `project_id`
- Project-scoped client message cache; no cross-project hydrate
- Selected model persisted via `codirectorUpdateConfig`
- Display mode / draft / expertise flags remain local UX-only
- **localStorage allowlist:** no tokens, provider secrets, raw tool payloads, or full technical error traces
- On project switch: **cancel in-flight** chat/tool work **before** clear + hydrate

### 3.6 Reconnect

- Disconnect → Reconnecting with bounded backoff
- Preserve conversation + binding for the same project
- Single-flight send; no duplicate tool execution on restore
- Visible **Reconnect** action when auto-recovery fails

### 3.7 Structured error envelope

`CoDirectorError.to_dict()` always includes:

```text
error_code, category, message, retryable, project_id, provider, model,
technical_evidence, partial_work_created, recommended_action
```

Legacy `code` / `recoverable` retained. Secrets redacted. FE `classifyCoDirectorError` reads both shapes.

---

## 4. Files changed

### Backend

| File | Change |
|---|---|
| `studio-api/app/codirector/errors.py` | Phase 4.1 envelope; `PROJECT_REQUIRED` |
| `studio-api/app/codirector/providers/base.py` | `testOnly` / `honesty` on health |
| `studio-api/app/codirector/providers/mock.py` | Mock health marked test-only |
| `studio-api/app/codirector/service.py` | No-project tool → `PROJECT_REQUIRED`; mock flags |
| `studio-api/app/codirector/session_context.py` | Canonical session-context builder |
| `studio-api/app/routers/codirector.py` | `GET /session-context` |

### Frontend

| File | Change |
|---|---|
| `studio-web/src/components/CoDirector/runtimeState.ts` | Runtime state machine (new) |
| `studio-web/src/components/CoDirector/types.ts` | Session context; safe project-scoped caches |
| `studio-web/src/components/CoDirector/CoDirectorSession.tsx` | Binding, cancel-on-switch, reconnect, honesty |
| `studio-web/src/components/CoDirector/CoDirectorShell.tsx` | Honest status; no-project / reconnect banners |
| `studio-web/src/components/CoDirector/CoDirectorHeader.tsx` | Runtime chip |
| `studio-web/src/components/CoDirector/CoDirectorOverflowMenu.tsx` | Status / model persist / reconnect |
| `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` | “No Project Selected” |
| `studio-web/src/components/CoDirector/CoDirectorNavDrawer.tsx` | “No Project Selected” |
| `studio-web/src/components/CoDirector/codirector-cinematic.css` | Chip / banner styles |
| `studio-web/src/pages/CoDirectorPage.tsx` | Unbind when route has no project |
| `studio-web/src/api.ts` | Envelope + session-context client |

### Tests / docs

| File | Role |
|---|---|
| `studio-api/tests/test_m41_codirector_wave1.py` | M41-CD API/unit coverage |
| `tests/e2e/m41/m41-cd-wave1.spec.ts` | M41-CD Playwright coverage |
| `docs/release-gate/m41/M41_IMPLEMENTATION_REPORT.md` | Living implementation log |
| `docs/release-gate/m41/M41_TEST_REPORT.md` | Living test log |
| `docs/release-gate/m41/M41_WAVE1_REPORT.md` | This consolidated Wave 1 report |

---

## 5. Test results (M41-CD-01 … M41-CD-14)

| Suite | Path | Result |
|---|---|---|
| API / unit | `studio-api/tests/test_m41_codirector_wave1.py` | **16 passed** |
| Playwright | `tests/e2e/m41/m41-cd-wave1.spec.ts` | **5 passed** |

| ID | Title | Result |
|---|---|---|
| M41-CD-01 | Co-Director connects to configured Ollama model | PASS |
| M41-CD-02 | Missing model produces clear error | PASS |
| M41-CD-03 | Session binds to explicit project | PASS |
| M41-CD-04 | Project context persists across navigation | PASS |
| M41-CD-05 | No-project mode blocks production mutations | PASS |
| M41-CD-06 | Silent mock fallback is disabled in Beta | PASS |
| M41-CD-07 | Provider and model persist on session | PASS |
| M41-CD-08 | Refresh restores the active session | PASS |
| M41-CD-09 | Reconnect does not duplicate messages | PASS |
| M41-CD-10 | Reconnect does not duplicate tool execution | PASS |
| M41-CD-11 | Project context does not leak across projects | PASS |
| M41-CD-12 | Beta restart restores valid session state | PASS |
| M41-CD-13 | Failed runtime action is not reported as success | PASS |
| M41-CD-14 | Structured error envelope is returned | PASS |

Commands:

```text
studio-api/.venv/Scripts/python.exe -m pytest tests/test_m41_codirector_wave1.py -q
# 16 passed

# Playwright (alternate ports if Beta API already holds :8742)
STUDIO_API_PORT=8791 PLAYWRIGHT_WEB_PORT=5191 ... npx playwright test tests/e2e/m41/m41-cd-wave1.spec.ts --project=chromium
# 5 passed
```

---

## 6. Remaining blockers (out of Wave 1)

| Item | Wave |
|---|---|
| Sample / fake approval UI cleanup; compact/fullscreen polish | Wave 2 |
| Canonical read tools, `@` resolve, provider honesty | Wave 3 |
| Plan states, confirmation cards, job inspect, kill stub success UX | Wave 4 |
| Specialist matrix + Storyteller / Character Creator / Director 2.0 + Korri | Wave 5 |
| Image/video/voice/music/SFX/lipsync/editor place/subtitle tools | Wave 6 |
| Memory, history, errors, privacy | Wave 7 |
| M41-CD-15…40 + real cert workflow + remaining reports | Wave 8 |

---

## 7. Next step

**Wave 2: Compact/fullscreen UI polish and removal of fake/sample approvals.**

Do not treat Wave 1 GO as Phase 4.1 complete — later waves remain required for full Co-Director production certification.

---

**GO — M41 Wave 1 runtime and session foundation complete**
