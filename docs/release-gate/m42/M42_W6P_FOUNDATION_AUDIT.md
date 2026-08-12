# M42 Wave 6P — Foundation Audit

| Field | Value |
|---|---|
| **Phase** | M42-W6P Phase 0 |
| **Branch** | `phase2/m42-production-beta-w6p` |
| **Starting SHA** | `f758744` (from Wave 5 tip) |
| **Wave6pMayBegin** | `wave1Go ∧ … ∧ wave5Go` |

## Prerequisite gates

All prior M42 wave gate artifacts verified GO (not fabricated). Evidence: `artifacts/m42/w6p/prerequisites.json`.

## Ownership map — Scene References

| Concern | Current | Wave 6P owner | Action |
|---|---|---|---|
| Project media | Asset Library / `Asset` | Asset Library | CANONICAL |
| Identity refs | `continuity` ApprovedReference | Identity Registry / continuity | CANONICAL |
| Timeline ReferenceSet | `director_references` | Scene Reference Binding | MIGRATE / COMPATIBILITY_ALIAS |
| Scene attachment | ad-hoc / UI only | `scene_references` | GREENFIELD canonical |
| Continuity packets | `continuity` | Continuity | CANONICAL — consume bindings |
| Timeline display | Timeline UI | Timeline projection | REUSE — no second DB |

## Classification

- **CANONICAL:** ImageEditIntent path, Continuity domain, Asset rows, Wave 5 VisualIdentity
- **MIGRATE:** `director_references` bindings → scene_references scopes (shot/scene)
- **COMPATIBILITY_ALIAS:** Internal `director` workspace id → Timeline
- **REMOVE:** Standalone “Director monitor” / “Director tracks” product wording on certified UI

## Bypass baseline

W4B/W5 bypass audits remain at zero unresolved runtime bypasses. Wave 6P must not introduce new UI→Comfy or second enqueue paths.
