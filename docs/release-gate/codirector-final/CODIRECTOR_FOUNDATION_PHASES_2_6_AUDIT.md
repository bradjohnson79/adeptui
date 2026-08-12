# Co-Director Foundation Audit — Phases 1.5 Through 6

**Branch:** `feature/ai-guided-setup`  
**Workspace HEAD:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Date:** 2026-08-03  
**Beta:** http://127.0.0.1:8760/  
**API:** http://127.0.0.1:8758/api/health  

## Final verdict

**GREEN — CODIRECTOR FOUNDATION READY**

## What was built

| Phase | Package | Role |
|---|---|---|
| Contracts | `foundation/contracts.py` + architecture doc | Frozen shared types / aliases |
| 1.5 Knowledge | `foundation/knowledge/` + `config/codirector/creative-knowledge/` | What Co-Director knows |
| 2 Creative | `foundation/creative/` | How specialists think + Creative Director |
| 3 Production | `foundation/production/` | Readiness, deps, estimates |
| 4 Collaboration | `foundation/collaboration/` | Modes, preferences, review |
| 5 Operations | `foundation/operations/` | Safe workflows, supervisor, retries |
| 6 Domains | `foundation/domains/` + domain-profiles JSON | Format profiles referencing knowledge packs |
| Integration | `foundation/pipeline.py` + `intelligence/service.py` + gateway | Domain → Knowledge → Specialists → Creative Director → Synthesis |

Conversation Core remains the gateway and was not replaced.

## Pipeline (locked)

```text
Creator Input
  → Conversation Core
  → (analysis intents) Intelligence / Foundation path
      → Domain Profile
      → Knowledge consult
      → Foundation specialists
      → Creative Director
      → Synthesis
  → Approvals / Tools / Memory
  → Creator Response
```

Creative intents use the foundation specialist stack alone (legacy M2.4 runner skipped for those turns). Non-creative intelligence intents retain the existing M2.4 runner.

## Reviewer findings repaired

1. Specialists now consult shared KnowledgeFrame principles/patterns (not metadata-only refs).
2. Creative intents no longer merge competing legacy + foundation specialist stacks.
3. Analysis verbs (critique / staging / compare / audit) bypass Conversation Core “tracking” replies and enter foundation intelligence.

## Tests

| Suite | Result |
|---|---|
| Foundation + conversation unit | **51 passed** |
| Foundation Playwright cert | **1 passed** (~1.3m) |
| Failure injection on Beta | SKIP-ENV (`/api/e2e/*` absent) — documented |

## Cleanup

- Disposable `CODIRECTOR-FOUNDATION-*` residue after cert: **0**
- Manual Beta Handoff: untouched (404-tolerant snapshot equality)

## Standing law recorded

No new capability is complete until autonomous Playwright passes against a brand-new disposable project. Documented in `docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md`.

## Limitations

1. Foundation specialists are deterministic heuristics grounded in KnowledgePacks — not deep ML specialists (locked skeleton depth).
2. Multi-domain live journey soft-covers Series/Web Series; other domain profiles are unit-certified via `test_codirector_foundation_domains.py`.
3. Failure-injection / retry duplication proofs require harness (`STUDIO_E2E=1`), not live Beta.
4. Product repairs from this program may not yet be committed as a distinct SHA beyond workspace HEAD.
