# M42 Wave 5 — Continuity Foundation Audit

| Field | Value |
|---|---|
| **Phase** | M42-W5 Phase 0 |
| **Branch** | `phase2/m42-identity-visual-continuity` |
| **Starting SHA** | `f758744` |
| **Wave5MayBegin** | `wave1Go ∧ … ∧ wave4cGo` |

## Ownership map

| Concern | Current owner | Canonical Wave 5 owner | Action |
|---|---|---|---|
| Identity record | `character_identity` + draft `image_runtime/identities.py` | `continuity` VisualIdentity | MIGRATE link; DEPRECATE config authority |
| References | M42 ReferenceAsset + char refs + timeline bindings | ApprovedReference → asset_id | REUSE assets; role-aware approval layer |
| Character visual traits | `character_traits` / profile JSON | IdentityVersion traits | MIGRATE via explicit sync |
| Continuity checks | Bible conflicts + mock vision validators | `continuity.evaluator` | REMOVE_FAKE_DATA from prod path |
| Corrections | ImageEditIntent / editEnqueue | `correction_service` | CANONICAL — preserve |
| Version history | VersionGraph | VersionGraph | CANONICAL — preserve |
| Production authority | Output Gate | Output Gate + ContinuityPolicy | EXTEND |
| Scene lock helpers | `scene_continuity_locks.py` (was `continuity.py`) | N/A | DEPRECATE / COMPATIBILITY_ALIAS |
| ContinuityPacket | — | `continuity.packet_compiler` | GREENFIELD |
| ContinuityPolicy | — | `continuity.policy` | GREENFIELD |
| Continuity Workspace | — | `studio-web/.../continuity` | GREENFIELD |

## Classifications

- **CANONICAL:** ImageEditIntent path, VersionGraph, Output Gate, Production Bible domain entities, M42 ReferenceAsset store, character_identity profiles (linked, not replaced).
- **REUSE:** Timeline reference bindings (point at continuity IDs); Asset Library approval metadata.
- **MIGRATE:** Character reference assets → candidate ApprovedReferences; scene `continuity_json` → packet/Bible over time.
- **DEPRECATE:** Config JSON identity registry as authority; orphan scene lock module as continuity authority.
- **REMOVE_FAKE_DATA:** Production use of vision `fixture_score` / mock identity pass for Continuity Workspace.
- **COMPATIBILITY_ALIAS:** `identity_registry_snapshot()` projects continuity domain when enforced.
- **REVIEW_REQUIRED:** Ambiguous character ↔ wardrobe identity collisions during migration.

## Prerequisites

Evidence: `artifacts/m42/w5/prerequisites.json`. All prior wave gates verified GO; no fabricated gate results.
