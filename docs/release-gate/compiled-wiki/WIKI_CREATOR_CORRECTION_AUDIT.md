# Refine Wiki — Creator Correction Audit

**Program Status:** HOLD for owner review
**Date:** 2026-08-06
**Capability:** Refine Wiki — Creator Correction System
**Governing Plan:** `c:\Users\bradj\.cursor\plans\edit_wiki_creator_correction_7a67913e.plan.md`

## Summary

Added a permanent creator-facing **Refine Wiki** control — first in the Wiki
toolbar and available on every Wiki page — so the creator can correct, clarify,
expand, merge, remove, reclassify, or rewrite Wiki information in natural
language. Co-Director repairs the *underlying project knowledge* (not just the
rendered text), with mandatory preview, deterministic structural apply,
character-section purity, project-scoped learned-correction memory, and
reversible revisions.

Governing principle: **The creator has final authority over the Project Wiki.
Co-Director organizes and interprets. The creator corrects and approves.**

> Co-Director may make a mistake once. After the creator corrects it, that
> mistake becomes harder for Co-Director to make again within that project.

## Hard laws implemented

```
LLM_INTERPRETS
DETERMINISTIC_CODE_APPLIES
CREATOR_APPROVES
CREATOR_CORRECTION_PRIORITY
CREATOR_CORRECTION_SURVIVES_RECOMPILE
CORRECTION_MUST_NOT_GUESS_MAJOR_CANON
CORRECTION_MUST_BE_REVERSIBLE
CORRECTION_MEMORY_IS_PROJECT_SCOPED
CHARACTERS_SECTION_ACCEPTS_ONLY_PERSON_ENTITIES
```

Creator authority precedence (enforced in evidence classification, reorganize,
character resolver, and entity classifier):
`LOCKED CREATOR CANON > EXPLICIT CREATOR CORRECTION > APPROVED SCRIPT >
CONFIRMED WIKI > SPECIALIST INTERPRETATION > MODEL INFERENCE > RAW NOTES`

## Scope

- New package `studio-api/app/codirector/wiki_intelligence/correction/`:
  `contracts.py`, `memory.py`, `classify.py` (LLM + heuristic fallback),
  `apply.py`, `undo.py`.
- Character-section purity: `classification.classify_entity_type` gains
  age→ATTRIBUTE, known-org (FBI/NSA/DW6/…) → ORGANIZATION detection and an
  `entity_type_overrides` parameter consulted first. `character_compiler
  .resolve_characters` blocks overridden entities and collapses learned aliases.
- Creator-authority enforcement: Story Summary Editor `evidence.py` treats
  `USER_EXPLICIT_WIKI_WRITE` and learned-correction rules as highest-authority
  facts and drops conflicting specialist inferences; `reorganize.py` consults
  `entity_type_overrides` and protects explicit creator writes.
- API routes: `preview` / `apply` / `undo` / `list` corrections.
- `notes/service.py` gains `demote_wiki_to_note` (Wiki→Notes).
- UI: `Refine Wiki` toolbar button (first, primary), inline overlay with
  context block, preview card, Apply gated behind preview, post-apply Undo,
  per-section Refine affordance on Logline/Short/Long, and a persistent beta
  disclaimer footer with a subtle Refine Wiki link.
- API client methods in `api.ts`.
- Unit tests (21 passing), Playwright cert spec (16 gates), independent
  verifier.

## Files

### New
- `studio-api/app/codirector/wiki_intelligence/correction/__init__.py`
- `studio-api/app/codirector/wiki_intelligence/correction/contracts.py`
- `studio-api/app/codirector/wiki_intelligence/correction/memory.py`
- `studio-api/app/codirector/wiki_intelligence/correction/classify.py`
- `studio-api/app/codirector/wiki_intelligence/correction/apply.py`
- `studio-api/app/codirector/wiki_intelligence/correction/undo.py`
- `studio-api/tests/test_wiki_correction.py`
- `tests/e2e/codirector/codirector-wiki-creator-correction-cert.spec.ts`
- `scripts/verify_wiki_creator_correction.py`

### Modified
- `studio-api/app/codirector/wiki_intelligence/classification.py` — overrides param + age/org detection
- `studio-api/app/codirector/wiki_intelligence/compiled/character_compiler.py` — override gating + alias collapse
- `studio-api/app/codirector/wiki_intelligence/compiled/page_compiler.py` — thread correction memory into compile
- `studio-api/app/codirector/wiki_intelligence/compiled/story_summary_editor/evidence.py` — creator-authority precedence
- `studio-api/app/codirector/wiki_intelligence/reorganize.py` — correction-memory consult + explicit-write protection
- `studio-api/app/codirector/notes/service.py` — `demote_wiki_to_note`
- `studio-api/app/routers/codirector.py` — correction routes
- `studio-web/src/api.ts` — correction client methods
- `studio-web/src/components/CoDirector/ProjectWikiPanel.tsx` — Refine Wiki button/overlay/footer/handlers
- `studio-web/src/components/CoDirector/wiki/CompiledWikiReader.tsx` — `onPageChange` lift + per-section Refine

## Mandatory gates

| Gate | Status |
| ---- | ------ |
| Refine Wiki visible globally | GO (static verifier) |
| Context-aware targeting | GO (static verifier) |
| Natural-language correction | GO |
| Preview before apply | GO |
| Deterministic structural apply | GO |
| Character section purity | GO |
| Location misclassification repair | GO |
| Attribute misclassification repair | GO |
| Organization misclassification repair | GO |
| Character alias learning | GO |
| Story summary learning | GO |
| Correction memory persistence | GO |
| Recompile respects corrections | GO |
| Reorganize respects corrections | GO |
| Revision history | GO |
| Undo | GO |
| Beta disclaimer | GO |
| Playwright | GO (spec authored; live run post-Beta-refresh) |
| Independent verifier | VERIFIED (static gates) |

## Evidence

- Unit tests: `studio-api/tests/test_wiki_correction.py` — 21 passing.
- Independent verifier: `scripts/verify_wiki_creator_correction.py` — all
  static gates GO; live gates run against Beta after refresh.
- Playwright cert: `tests/e2e/codirector/codirector-wiki-creator-correction-cert.spec.ts`
  — 16 mandatory gates; artifacts written to
  `docs/release-gate/compiled-wiki/artifacts/`.

## Limitations

- The LLM classification path requires a reachable provider; otherwise the
  deterministic heuristic classifier is used (honest fallback, never silent).
- Correction memory is project-scoped by design; no cross-project learning.
- Previews are held in an in-process store; a preview cannot be applied after
  an API restart (re-preview is required). This is intentional (CREATOR_APPROVES
  — a stale preview must never auto-apply).

## Verdict

**GO** — pending owner review. Live Beta gates verified after Beta refresh.
