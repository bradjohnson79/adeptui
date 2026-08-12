# Co-Director Production Lifecycle — Governing Audit

**Governing document for Track B (stage-gated production).**  
Wiki compilation track: [`../compiled-wiki/COMPILED_WIKI_EXPERIENCE_AUDIT.md`](../compiled-wiki/COMPILED_WIKI_EXPERIENCE_AUDIT.md).

**Date:** 2026-08-07  
**Branch:** `feature/ai-guided-setup`

## Program Status

```text
AUTOMATED TECHNICAL GATES: VERIFIED
PRODUCT-OWNER HUMAN REVIEW: PENDING
FINAL PRODUCT ACCEPTANCE: HOLD
```

## Hard laws enforced

```text
NO_FORMAL_CASTING_WITHOUT_SCRIPT
NO_FORMAL_PRODUCTION_WITHOUT_CAST
NO_FINAL_GENERATION_WITHOUT_SCENE_READINESS
NO_POST_WITHOUT_PRODUCTION_ASSETS
NO_COMPLETE_WITHOUT_FINAL_QC
```

## Scope delivered

- `ProjectProductionLifecycle` + `SceneProductionReadiness` + format-aware maps
- Script DRAFT → APPROVED → LOCKED; Casting opens at APPROVED
- Scene readiness matrix in Plans; Scene Production Package gate
- Timeline / MAGI handoff flags; Final QC → Complete → Reopen
- Stage-aware next steps + specialist routing into Creative Operating loop

## Evidence

| Gate | Result |
|------|--------|
| Playwright `codirector-production-lifecycle-cert.spec.ts` | PASS |
| `scripts/verify_production_lifecycle.py` | **VERIFIED** |
| Artifact | `artifacts/independent_production_lifecycle_verifier.json` |

## Beta

- UI: http://127.0.0.1:8760/
- API: http://127.0.0.1:8758/

## Verdict

```text
GO — PRODUCTION LIFECYCLE TECHNICALLY VERIFIED
HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING
FINAL PRODUCT ACCEPTANCE: HOLD
```
