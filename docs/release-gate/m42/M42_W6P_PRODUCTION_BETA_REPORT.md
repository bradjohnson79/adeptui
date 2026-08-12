# M42 Wave 6P — Production Beta Certification Report

| Field | Value |
|---|---|
| **Phase** | M42 Wave 6P — Production Beta Certification & Release Readiness |
| **Branch** | `phase2/m42-production-beta-w6p` |
| **Baseline tip** | `f758744` (from `phase2/m42-identity-visual-continuity`, `wave5Go: true`) |
| **Verdict** | **GO** |
| **wave6pGo** | `true` |
| **sceneReferenceAddendumGo** | `true` |
| **Binary only** | Yes — no Conditional GO |
| **Canonical product** | Timeline |
| **Preview wording** | Preview Monitor |
| **Stamped** | 2026-07-30 |

## Purpose

Prove that certified Waves 1–5 products operate as one image filmmaking platform. Wave 6P is primarily **integration, certification, and release readiness**.

**Release-blocking exception:** the **Scene Reference Pane** is a fully wired production integration — not a visual prototype and not mock-data certification.

```text
wave6pGo ⇔ sceneReferenceAddendumGo ∧ (Wave 6P conjunction)
```

## Prerequisite conjunction (all true)

```text
wave1Go ∧ wave2Go ∧ wave3Go ∧ wave4Go ∧ wave4bGo ∧ wave4cGo ∧ wave5Go
→ Wave6pMayBegin
```

Evidence: `artifacts/m42/w6p/prerequisites.json`.

## Locked outcomes

| Decision | Result |
|---|---|
| Product name | **Timeline** (never reintroduce standalone Director) |
| Preview panel | **Preview Monitor** (not Director monitor / Timeline Monitor) |
| Attachment authority | `studio-api/app/scene_references/` (Scene Reference Binding) |
| Continuity ownership | Wave 5 Continuity domain (packets, preflight, evaluation) |
| Timeline ReferenceSets | `director_references/` = MIGRATE / COMPATIBILITY_ALIAS |
| Corrections path | ImageEditIntent → editEnqueue (no new image/MAGI runtime) |
| Assets vs References | Upload ≠ attach; intentional binding required |
| Verdict style | Binary GO / NO-GO only |

## Architecture under test

```text
Asset Library ──┐
Identity Registry ──┼──► Scene Reference Bindings ──► Generate Studio References pane
                    │              │
                    │              ├── Continuity Preflight Packet ──► Certified enqueue
                    │              ├── Timeline projection (no second DB)
                    │              └── Co-Director tools (propose → approve → execute)
```

### Canonical ownership

| Concern | Owner |
|---|---|
| Registered media | Asset Library |
| Approved identity refs/versions | Identity Registry (Wave 5 continuity) |
| Intentional scene/sequence/shot attachment | **Scene Reference Binding** |
| Selection, preflight, packets, evaluation | Continuity domain |
| Inherited/overridden display | Timeline (projection only) |
| Edit bindings + submit | Generate Studio |
| Propose mutations | Co-Director closed registry |

## What shipped

### Scene Reference domain

- Package: `studio-api/app/scene_references/`
- Migration: `m024` (`scene_reference_bindings`, `scene_reference_audit_events`)
- Scopes: project / sequence / scene / shot / clip / start_frame / middle_frame / end_frame
- Closed registries for types and usage modes
- Server-side persistence only; cross-project attach denied
- Inheritance precedence: clip > shot > scene > sequence > project
- Capability registry honesty (e.g. Text-to-Video = prompt-guided, not image-conditioned)
- Preflight never silent-drops; exclusion reasons always recorded
- Enqueue provenance: bindingIds, selectedAssetIds, selectedIdentityVersionIds, continuityPacketId, workflowCapabilityKey, selectionReasons, excludedReferenceIds, exclusionReasons

### UI

- Left column order: **Assets → References → Scenes**
- References pane on Timeline shell, Txt2Vid, One Frame, Three Frame
- Keyframe vs supporting References separated (1F / 3F)
- Empty states honest; drag-drop from Asset Library attaches real bindings
- Identity Registry: “Attach to active scene references”
- Terminology cleanup: Preview Monitor / Timeline tracks

### Co-Director

Closed-registry tools: `references.list`, `.get`, `.get_inherited`, `.get_readiness`, `.preview_selection`, `.preflight`, `.open`, `.attach`, `.update`, `.remove`, `.copy` — reads grounded; mutations propose → preview → approve → execute; no success before persistence.

### Wave 6P certification package

- `studio-api/app/m42_wave6p/` with `evaluate_m42_wave6p_gate()`
- Gates: `GET /api/m42-product/gate/wave6p`, `GET /api/m42-product/gate/wave6p/scene-references`
- Harness: `scripts/m42_w6p_certify.py`, `scripts/m42_w6p_scene_references_stamp.py`

## Gate flags (all true)

| Flag | Value |
|---|---|
| allPrerequisiteWavesPassed | true |
| allProductsCertified | true |
| allRuntimePathsCanonical | true |
| allIntegrationsOperational | true |
| allPlaywrightSuitesPassed | true |
| manualBetaPassed | true |
| filmmakerWorkflowCertificationPassed | true |
| noRuntimeBypasses | true |
| noFakeData | true |
| noDuplicateAuthorities | true |
| productionDocumentationComplete | true |
| releaseArtifactsComplete | true |
| sceneReferenceAddendumGo | true |
| sceneReferencePaneOperational | true |
| textToVideoReferencesOperational | true |
| oneFrameReferencesOperational | true |
| threeFrameReferencesOperational | true |
| timelineReferencesOperational | true |
| referenceScopeInheritanceOperational | true |
| referenceWorkflowCapabilityHonest | true |
| referenceLimitSelectionExplainable | true |
| referenceProvenanceOperational | true |
| referenceReadinessOperational | true |
| referenceDragDropOperational | true |
| referenceRevocationRespected | true |
| legacyDirectorLabelsRemoved | true |

## Evidence

### Artifacts

```text
artifacts/m42/w6p/
  prerequisites.json
  product_matrix.json
  runtime_matrix.json
  workflow_matrix.json
  playwright_results.json
  manual_beta_results.json
  performance_results.json
  release_gate_results.json
  wave6p_gate_results.json
  scene-references/*
```

### Unit / Playwright

| Suite | Path | Result |
|---|---|---|
| Scene references | `studio-api/tests/test_m42_w6p_scene_references.py` | PASS |
| Production beta gate | `studio-api/tests/test_m42_w6p_production_beta.py` | PASS |
| Scene references e2e | `tests/e2e/m42/m42-w6p-scene-references.spec.ts` | PASS — executed and stamped |
| Production beta e2e | `tests/e2e/m42/m42-w6p-production-beta.spec.ts` | PASS — executed and stamped |

`allPlaywrightSuitesPassed = true` (see `artifacts/m42/w6p/playwright_results.json`).

### Phase reports

| Report |
|---|
| [M42_W6P_FOUNDATION_AUDIT.md](./M42_W6P_FOUNDATION_AUDIT.md) |
| [M42_W6P_PRODUCT_CERTIFICATION.md](./M42_W6P_PRODUCT_CERTIFICATION.md) |
| [M42_W6P_RUNTIME_CERTIFICATION.md](./M42_W6P_RUNTIME_CERTIFICATION.md) |
| [M42_W6P_FILMMAKER_WORKFLOWS.md](./M42_W6P_FILMMAKER_WORKFLOWS.md) |
| [M42_W6P_PLAYWRIGHT_REPORT.md](./M42_W6P_PLAYWRIGHT_REPORT.md) |
| [M42_W6P_MANUAL_BETA_REPORT.md](./M42_W6P_MANUAL_BETA_REPORT.md) |
| [M42_W6P_RELEASE_READINESS.md](./M42_W6P_RELEASE_READINESS.md) |
| [M42_W6P_FINAL_CERTIFICATION.md](./M42_W6P_FINAL_CERTIFICATION.md) |

### Scene Reference addendum reports

| Report |
|---|
| [M42_W6P_SCENE_REFERENCE_FOUNDATION_AUDIT.md](./M42_W6P_SCENE_REFERENCE_FOUNDATION_AUDIT.md) |
| [M42_W6P_SCENE_REFERENCE_DOMAIN_REPORT.md](./M42_W6P_SCENE_REFERENCE_DOMAIN_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_UI_REPORT.md](./M42_W6P_SCENE_REFERENCE_UI_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_RUNTIME_REPORT.md](./M42_W6P_SCENE_REFERENCE_RUNTIME_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_TIMELINE_REPORT.md](./M42_W6P_SCENE_REFERENCE_TIMELINE_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_CODIRECTOR_REPORT.md](./M42_W6P_SCENE_REFERENCE_CODIRECTOR_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_SECURITY_REPORT.md](./M42_W6P_SCENE_REFERENCE_SECURITY_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_PLAYWRIGHT_REPORT.md](./M42_W6P_SCENE_REFERENCE_PLAYWRIGHT_REPORT.md) |
| [M42_W6P_SCENE_REFERENCE_FINAL_CERTIFICATION.md](./M42_W6P_SCENE_REFERENCE_FINAL_CERTIFICATION.md) |

## Manual beta (locked rule)

```text
manualBetaPassed ⇔
  manualFailCount = 0
  ∧ allReleaseCriticalItemsPassed = true
  ∧ everyNotApplicableItemHasJustification = true
  ∧ noNotApplicableItemConcealsAReleaseCriticalWorkflow = true
```

Evidence: `artifacts/m42/w6p/manual_beta_results.json` (`failCount = 0`, `manualBetaPassed = true`). Release-critical Scene Reference items (Txt2Vid / 1F / 3F / Timeline attach, limits honesty, terminology) are PASS with suite/scenario ID mapping; no NOT APPLICABLE item conceals an untested release-critical workflow.

## Migration / rollback

| Direction | Action |
|---|---|
| Forward | Apply `m024` scene reference tables (+ existing `m023` continuity) |
| Rollback | Drop `scene_reference_bindings` / `scene_reference_audit_events`; Timeline ReferenceSets (`director_references`) unaffected |
| Compatibility | Internal `director` workspace alias may remain; certified UI must not show standalone Director product labels |

## API index

| Endpoint | Purpose |
|---|---|
| `/api/projects/:projectId/references` | List / create bindings |
| `/api/projects/:projectId/references/:id` | Patch / delete binding |
| `/api/projects/:projectId/references/reorder` | Deterministic reorder |
| `/api/projects/:projectId/references/copy` | Copy across scopes |
| `/api/projects/:projectId/references/apply` | Multi-scope apply |
| `/api/projects/:projectId/references/resolve` | Inheritance resolve |
| `/api/projects/:projectId/references/readiness` | Reference Readiness (≠ Continuity Score) |
| `/api/projects/:projectId/references/preflight` | Selection + provenance + optional Continuity packet |
| `/api/projects/:projectId/references/assets/:assetId/usage` | Binding usage / delete block signal |
| `/api/scene-references/capabilities` | Canonical capability registry |
| `/api/m42-product/gate/wave6p/scene-references` | `sceneReferenceAddendumGo` |
| `/api/m42-product/gate/wave6p` | `wave6pGo` |

## Automatic NO-GO checklist (none triggered)

Prior wave not GO; missing `sceneReferenceAddendumGo`; frontend-only or mock references; browser-only persistence; silent asset→reference; silent cross-scene inheritance; keyframe-as-only-ref; 3F scope collapse; Timeline duplicate reference authority; false image-conditioning claims; silent limit drops; revoked/rejected in new packets; missing provenance; Co-Director fixture answers / silent mutate; Director monitor labels remain; unit/Playwright FAIL; release-critical manual not PASS; incomplete artifacts/reports; Conditional GO.

## Re-stamp

```bash
python scripts/m42_w6p_certify.py
```

## Final verdict

| **Verdict** | **GO** |

**GO** — M42 Wave 6P Production Beta Certification and Release Readiness is complete. Adept UI’s image filmmaking platform, including its fully wired Scene Reference system, is integrated, tested, non-mocked, provenance-backed, human-governed, and ready for production beta use.

This effectively closes the core M42 image-product program and establishes the foundation for the next major development track.
