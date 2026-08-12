# Co-Director Persistent Memory and Evolution — Certification

## CURRENT

```text
GO — CO-DIRECTOR CONVERSATION MEMORY DURABLE
GO — CO-DIRECTOR COMPLETE PROJECT MEMORY READY
GO — CO-DIRECTOR REMEMBERS, LEARNS, AND EVOLVES ACROSS TASKS
GO — CO-DIRECTOR PERSISTENT MEMORY AND EVOLUTION READY
```

Primary issues these after implementer evidence + independent Composer 2.5 review.

## Evidence

| Layer | Result |
| --- | --- |
| Wave A (prior) | GO — `verifier-20260805T042330Z` primary accepted |
| Waves B–E unit | `test_codirector_waves_b_e.py` — **8 passed** |
| Layer 3 learning | `test_codirector_layer3_learning_evolution.py` — **1 passed** (10 critique→promote cycles, isolation, export/import, retire) |
| Layer 3 UI | `codirector-memory-layer3-ui.spec.ts` — **1 passed** (View/Audit/Compact) |
| Reload persistence | `codirector-reload-persistence-race.spec.ts` — **1 passed** |
| Tool events | Wired via `_safe_append_tool_event` after tool success |
| Memory UI | `CoDirectorMemoryPanel` in Project Settings → AI Learning |
| Flags (Beta) | `STUDIO_FEATURE_CODIRECTOR_ADAPTIVE_LEARNING_V1=1`, production intelligence v1=1 |

## Scope delivered

- Compaction + fold skip (`conversation_compaction.py`)
- Revision poll + SSE route
- Memory export/import + intelligence snapshot
- Audit/repair
- M2.12 10-cycle promote/retire with project isolation

## Limitations

- Client uses revision polling (SSE available)
- Compaction UI uses message-count heuristic for `beforeSequence`
- Layer 2 full 100-iter race not re-run in this Finale pass (Wave A already green; reload + Layer 3 + B–E unit cover regression)

Independent verifier must corroborate before program freeze.
