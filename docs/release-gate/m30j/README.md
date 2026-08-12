# M3.0j — Full Platform Beta Readiness (Canonical)

**Status:** IN PROGRESS — Phase 0 + partial library/routes/Playwright; **NOT M3.0j YES**.

**Hard gate:** M3.0i Native Production Readiness must reach **YES** (WAN + LatentSync studio-queue still open) before M3.0j final certification may stamp YES. M3.0i is **not** stamped YES in this milestone pack.

**Progress report (canonical):** [`docs/M3.0J_FULL_PLATFORM_BETA_READINESS_REPORT.md`](../../M3.0J_FULL_PLATFORM_BETA_READINESS_REPORT.md)

M3.0j proves Adept UI Studio is beta-ready as a **full platform**: project library, Co-Director awareness, route coverage, Playwright regression, Director/Editor workflows, export/recovery, accessibility, errors, security, and subagent certification — on top of native production (M3.0i).

fal.ai remains out of scope for native production proof. Historical fal evidence stays archived and protected.

## Hard dependencies

| Gate | Status | Notes |
|------|--------|-------|
| M3.0i YES | **OPEN** | WAN Shot2 + LatentSync face-forward studio-queue pending |
| M3.0j YES | **NOT CLAIMED** | Library/routes/Playwright partial; a11y + subagents open |

## Evidence layout

Canonical artifact root: `artifacts/m30j/`

| Directory | Phase / purpose |
|-----------|-----------------|
| `baseline/` | Phase 0 — branch, SHA, manifest lock, provider probe, flags, routes, M3.0i evidence protection |
| `route-audit/` | Studio-web route and workspace coverage audit |
| `playwright/` | Deterministic browser regression (`REAL_LOCAL` pending where noted) |
| `codirector/library-awareness/` | LIBRARY-CD matrix proof |
| `project-library/` | Studio Project Library API/taxonomy certification |
| `director/` | Director timeline / production suite certification |
| `editor/` | Editor workspace certification |
| `projects/` | Project lifecycle (create, open, migrate) |
| `assets/` | Asset library assignment and authority fields |
| `recovery/` | Reload / repair / recovery paths |
| `export/` | Playable AV export certification |
| `accessibility/` | Keyboard, screen reader, RTL, axe |
| `errors/` | Error surfaces and operator messaging |
| `security/` | Secrets, evidence audit, isolation |
| `subagents/` | Subagent / specialist certification |
| `final-certification/` | Consolidated M3.0j verdict (when all phases GREEN) |

## Reports

| Report | Status |
|--------|--------|
| [`M3.0J_FULL_PLATFORM_BETA_READINESS_REPORT.md`](../../M3.0J_FULL_PLATFORM_BETA_READINESS_REPORT.md) | **IN PROGRESS** — NO for Manual Beta |
| [`M30J_PROJECT_LIBRARY_REPORT.md`](M30J_PROJECT_LIBRARY_REPORT.md) | API/tests **PASS**; DETERMINISTIC Playwright partial |
| [`M30J_CODIRECTOR_LIBRARY_AWARENESS_REPORT.md`](M30J_CODIRECTOR_LIBRARY_AWARENESS_REPORT.md) | 10/22 LIBRARY-CD PASS |
| [`M30J_ROUTE_MATRIX.md`](M30J_ROUTE_MATRIX.md) | Route/workspace matrix; DETERMINISTIC smoke recorded |

## M3.0i evidence protection

Historical fal backup must remain intact at `artifacts/m30i/historical/fal-backup/`.  
Protection record: [`artifacts/m30j/baseline/m30i-evidence-protection.json`](../../../artifacts/m30j/baseline/m30i-evidence-protection.json)
