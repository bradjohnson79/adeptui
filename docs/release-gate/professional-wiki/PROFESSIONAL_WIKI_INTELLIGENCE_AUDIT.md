# Professional Wiki Intelligence — Completion Audit

**Date:** 2026-08-06  
**Branch:** `feature/ai-guided-setup`  
**Starting / evidence SHA:** `fa09c99d6395c29461cdec4555055faad116c435` (worktree includes uncommitted Professional Wiki Intelligence implementation)  
**Cert fixture:** `The Dreamweaver` (resolved by exact name; no Dreamweaver hardcoding in product ontology)

## Verdict

### GO — PROFESSIONAL WIKI INTELLIGENCE VERIFIED

### WIKI SPECIALIST DEPARTMENT: GO

### PRODUCT-OWNER HUMAN REVIEW: HOLD

Automated gates are green. Product-owner scoring remains owner-owned.

---

## Scope delivered

1. **Contracts** under `studio-api/app/codirector/wiki_intelligence/` — findings, assignments, decisions, reorganization job/revision/change records, professional TOC roots.
2. **Wiki Intelligence Orchestrator** wired into deferred enrichment (regex extraction is seed, not final SoT).
3. **Specialist department** — curated `mayProposeWikiWrites`; six new roles registered (`costume-designer`, `props-master`, `storyboard-artist`, `worldbuilding-specialist`, `research-specialist`, `marketing-pitch`); live registry **38** enabled specialists; `creatorFacingAllowed=false` for all.
4. **Professional Wiki projection** — nested TOC, empty-section hiding, false-character filter, canon badges; API `professionalToc` as UI SoT.
5. **Reorganize Wiki** — creator confirmation + scopes, specialist-driven job, progress stages, change summary, history, undo snapshot.
6. **Maintenance + tool context** — health report, bounded maintenance job, Wiki context consumed by image creative compile, production-intent compiler (video/script/audio path), voice performance compiler, and Co-Director compact wiki context.
7. **Certification** — dual Playwright specs, dual independent verifiers, roster audit.

---

## Files (primary)

| Area | Paths |
|------|-------|
| Wiki intelligence package | `studio-api/app/codirector/wiki_intelligence/*` |
| Deferred enrichment | `studio-api/app/codirector/conversation/deferred_enrichment.py` |
| Policies / prompts | `specialist_policies.py`, `prompts/specialists/{costume,props,storyboard,worldbuilding,research,marketing}*` |
| Wiki projection | `studio-api/app/codirector/wiki.py` |
| Routes | `studio-api/app/routers/codirector.py` (reorganize/undo/history/health/tool-context/maintenance) |
| Tool consumers | `image_product/compile.py`, `production_intent/compiler.py`, `voice_performance/compiler.py`, `context_enrichment.py` |
| UI | `studio-web/src/components/CoDirector/ProjectWikiPanel.tsx`, `studio-web/src/api.ts` |
| Cert | `tests/e2e/codirector/codirector-professional-wiki-intelligence-cert.spec.ts`, `codirector-wiki-specialist-department-cert.spec.ts` |
| Verifiers | `scripts/verify_professional_wiki_intelligence.py`, `scripts/verify_wiki_specialist_department.py` |
| Docs | `docs/release-gate/professional-wiki/WIKI_SPECIALIST_ROSTER.md`, this audit |

---

## Evidence

### Unit

```text
PYTHONPATH=studio-api python -m pytest studio-api/tests/test_wiki_intelligence_contracts.py -q
→ 8 passed
```

### Playwright (`ADEPT_BETA_TARGET=1`, workers=1, retries=0)

```text
codirector-professional-wiki-intelligence-cert.spec.ts → PASSED
codirector-wiki-specialist-department-cert.spec.ts → PASSED
```

Artifacts: `docs/release-gate/professional-wiki/artifacts/`

### Independent verifiers

| Verifier | Result |
|----------|--------|
| `verify_professional_wiki_intelligence.py` | **VERIFIED** |
| `verify_wiki_specialist_department.py` | **VERIFIED** |

### Beta

| Surface | URL | Status |
|---------|-----|--------|
| Creator UI | http://127.0.0.1:8760/ | HTTP 200, READY |
| Studio API | http://127.0.0.1:8758/ | `/api/health` ok; `specialistCount: 38` |

Sequence executed: `Stop-AdeptUI-Beta` → `npm --prefix studio-web run build` → `Start-AdeptUI-Beta -NoBrowser`.

---

## Mandatory reorganization gates

| Gate | Result |
|------|--------|
| Button visible | GO |
| Confirmation / scopes | GO |
| Specialist activation | GO |
| Character cleanup | GO |
| Entity reclassification | GO |
| Duplicate merging | GO (assignment/detection covered; applied on Dreamweaver live reorganize) |
| Profile enrichment | GO (evidence-bound; no invention path) |
| Canon protection | GO (`preserveLockedCanon`) |
| Continuity review | GO (continuity-analyst / script-supervisor in routing) |
| Media linking | GO (bounded; health exposes unlinkedAssets) |
| TOC rebuild | GO |
| Read-back verification | GO |
| Change summary | GO |
| History | GO |
| Undo | GO (Playwright) |
| Idempotency | GO (Playwright second run) |
| Reload persistence | GO |
| Project isolation | GO |
| Playwright | GO |
| Independent verifier | VERIFIED |

---

## Limitations (honest)

- `knowledgeEntries` remain a staging/legacy bridge; full Bible entity promotion is progressive, not a one-shot migration of every historical note.
- Live specialist LLM calls may be skipped for reorganization heuristics under tight budgets; structured `WikiSpecialistFinding` still required (heuristic path produces structured findings, not free-form chat).
- Media linking counts for unlinked assets are conservative (may report 0 until asset provenance is denser).
- Product-owner human review is **HOLD** until owner scores the Dreamweaver Wiki UX.

---

## Automatic NO-GO checks (honored)

- No empty/fragment cast lists in professional TOC counts (false characters filtered).
- No specialist creator-facing voice.
- No every-specialist-every-message routing (max ≤8).
- No Dreamweaver hardcoding in ontology.
- Locked-canon mutation blocked by reorganize flags.
- Reorganize is not UI-only refresh; specialists activate; undo snapshot supported.

---

## Manual review path

1. Open http://127.0.0.1:8760/ → project **The Dreamweaver** → Co-Director → Wiki.
2. Confirm three actions: Rebuild / Diagnostic / **Reorganize Wiki**.
3. Run Reorganize with default scopes → review summary → optional Undo.
4. Confirm nested TOC + canon badges; empty sections hidden.
5. Score PRODUCT-OWNER HUMAN REVIEW separately.

---

## Checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated
[x] Full-stack implementation completed
[x] Every visible Wiki control wired (Rebuild / Diagnostic / Reorganize / Undo)
[x] Real runtime; no mock completion for cert
[x] Persistence after reload verified (Playwright)
[x] Error/cancel/retry paths present (failed reorganize surfaces error; undo available)
[x] Project isolation verified
[x] Unit + Playwright + independent verifiers passed
[x] Beta updated and running; URLs reported
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO
```
