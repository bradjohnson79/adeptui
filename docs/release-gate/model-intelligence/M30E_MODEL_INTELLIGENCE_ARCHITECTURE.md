# M30E MODEL INTELLIGENCE ARCHITECTURE

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `5af34eff0a5207febf05ef6cc4a3e4f7d572eb15` |
| Implementation SHA | `bdc43f8e70cc69d767089f9ed2b0358c7fb82f42` |
| Documentation SHA | `6a77a2b40779c84700573214a3740d45dca5a853` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |

## Architecture

Module: `studio-api/app/codirector/model_intelligence/`

Canonical flow: intent → audio normalize → Bible package → selector → pack resolve → compiler → preflight → Studio job params → evaluator → experience → m212 candidates.

Does not create a parallel provider registry. Binds to `ltx`/`wan`/`zimage`/`fal_*` engines and capability IDs.

## Verdict

Architecture implemented and wired to Co-Director API + fal queue params.
