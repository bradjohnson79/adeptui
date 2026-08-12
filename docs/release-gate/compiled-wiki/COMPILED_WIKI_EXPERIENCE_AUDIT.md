# Compiled Co-Director Wiki Experience — Governing Audit

**Governing document for Track A (Notes → Wiki compilation).**  
Lifecycle track: [`../production-lifecycle/PRODUCTION_LIFECYCLE_AUDIT.md`](../production-lifecycle/PRODUCTION_LIFECYCLE_AUDIT.md).

**Date:** 2026-08-07  
**Branch:** `feature/ai-guided-setup`

## Program Status

```text
AUTOMATED TECHNICAL GATES: VERIFIED
PRODUCT-OWNER HUMAN REVIEW: PENDING
FINAL PRODUCT ACCEPTANCE: HOLD
```

## Scope delivered

- First-class Notes working desk (category, source, confidence, promotion status)
- Wiki Page Compiler (`compiled_bible_v1`) — pages ≠ records
- Grouped nav: Wiki / Notes / Casting / Story▾ / Library / Production▾
- Reorganize = NORMALIZE → COMPILE → PUBLISH with readability checks
- Explicit `USER_EXPLICIT_WIKI_WRITE` promote API
- Empty projects still expose compiled projection for cross-format clients
- Story Summary Editor subagent — editorial Logline / Short / Long prose
  (see [`STORY_SUMMARY_EDITOR_AUDIT.md`](STORY_SUMMARY_EDITOR_AUDIT.md))
- Refine Wiki — creator correction system with preview, deterministic apply,
  character-section purity, learned-correction memory, and undo
  (see [`WIKI_CREATOR_CORRECTION_AUDIT.md`](WIKI_CREATOR_CORRECTION_AUDIT.md))

## Evidence

| Gate | Result |
|------|--------|
| Playwright `codirector-compiled-wiki-experience-cert.spec.ts` | PASS |
| `scripts/verify_compiled_wiki_experience.py` | **VERIFIED** |
| Artifact | `artifacts/independent_compiled_wiki_verifier.json` |

## Beta

- UI: http://127.0.0.1:8760/
- API: http://127.0.0.1:8758/

## Verdict

```text
GO — COMPILED WIKI EXPERIENCE TECHNICALLY VERIFIED
HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING
FINAL PRODUCT ACCEPTANCE: HOLD
```
