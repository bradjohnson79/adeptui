# Co-Director Universal Scene Intelligence Convergence — Completion Report

Date: 2026-09-17 · Branch: `feat/character-creator-final-closure` · HEAD: `64724a53`
Governing design: `docs/release-gate/codirector-scene-intelligence/SCENE_INTELLIGENCE_CONVERGENCE_DESIGN.md`

## Verdict

**NO-GO — PEER REVIEW NOT COMPLETE**

Implementation, unit/API, live disposable samples A–F, and the Scene 3
regression all passed with Co-Director owning prepare. The GO law also
requires independent **AGREE** from Kimi K3, GLM 5.2, and GPT-5.6 Sol.
Those three reviewers could not be launched (Other Models usage limit;
the host would substitute Grok, which this gate forbids). Missing AGREEs
are not AGREEs.

Cursor did not write Scene 3’s Timeline prompt, seed Cade/Venture
bindings, or patch Timeline fields.

## Independence law

| Forbidden | Observed |
| --- | --- |
| Manually finish Scene 3 | Not done |
| Write Scene 3 Timeline prompt | Not done — CD compiled it |
| Populate Timeline fields to force a pass | Not done |
| Seed Cade/Venture bindings | Not done — CD resolved `@CadeOConnor` + `#VentureCorridorScene` (`global_found`) |
| Patch Scene 3 after CD fails | Not done — Scene 3 Playwright passed on CD’s output |
| Fabricate a prepared scene | Not done |

Scene 3 was used only as a read-only baseline, then as a validation case:
the original request was typed into the live Co-Director UI.

## Architecture (three layers)

- **Layer A** — `spec.source_user_prompt` (immutable creator request)
- **Layer B** — `DirectorSceneIntent`: scene type, environment, subjects,
  beats, reveals, dialogue, camera plan, spatial/continuity rules, exclusions,
  end state. Produced by `scene_understanding` (LLM + deterministic fallback)
  mapped onto verified references by `scene_breakdown`.
- **Layer C** — `prompt_compiler` synthesizes MiniMax H3 sections from Layer B
  only. ACTION is assembled from ordered beats. Runtime metadata lives on
  `SceneProductionSpec` and is stripped from creative prose.

No franchise templates. Canonical prompt tags only: `@Character` `%Prop`
`#Environment`.

## This session’s CD repairs (not scene edits)

1. **Repetition cardinality** (`scene_understanding.py`): an explicit
   multiplicity beat (`"buckles twice"`) covers the clustered stagings.
   Flavor words (`"harder"`) no longer spawn a third impact event.
2. **Cross-batch ACTION dedupe** (`prompt_compiler.py`): a discrete event
   sentence is staged in exactly one batch window. Reveal/continuity
   language may persist across windows.
3. **Playwright helper**: the first ACTION sentence was incorrectly treated
   as a cross-batch duplicate (`expect(prior === undefined).toBeFalsy()`).
   Observation-only fix in the sample and Scene 3 specs.

## E2E TRACE

| Stage | Samples A–F | Scene 3 |
| --- | --- | --- |
| User action (NL request into live CD chat) | PASS | PASS |
| Frontend (preparation card + milestones) | PASS | PASS |
| API chat/stream → prepare | PASS | PASS |
| Reference verification | PASS | PASS (`global_found`) |
| Layer B intent | PASS | PASS (16 beats, dialogue, reveal) |
| Layer C compiled prompt | PASS | PASS |
| Persistence / Timeline | PASS | PASS (existing scene `d0162b33`) |
| Reload / downstream | PASS (prompt matches scene row) | PASS |
| Cursor scene repair | None | None |

## Test evidence (exact counts)

| Suite | Result |
| --- | --- |
| `test_scene_understanding_universal.py` | **49 passed** |
| `test_scene_intent_cinematic_synthesis.py` + persistence + `test_codirector_scene_production.py` | **23 passed** |
| Playwright samples A–F (`ADEPT_BETA_TARGET=1`, live UI, no mocks) | **6 passed (1.3m)** |
| Playwright Scene 3 regression (original request, existing scene) | **1 passed (34s)** |

Evidence: `artifacts/functional-audit/universal-scene-samples/sample-{A–F}.json`,
`scene3-regression.json`.

### Sample outcomes (CD-owned)

| Sample | Scene type | Refs | Notes |
| --- | --- | --- | --- |
| A | establishing | `#SaltFlats` | No cast/dialogue; aerial drift ACTION |
| B | suspense reveal | character + harbor | Delayed reveal + camera drift |
| C | dialogue | `@IrisKane` `@DaxMeridian` `#RustMarket` | Exact lines preserved |
| D | prop action | winch + arcade | Scale/spatial staging |
| E | vfx_reveal | `@EchoNine` `#ObsidianGate` | Hidden until energy ring |
| F | multi-beat, 2 batches | `@JunPark` `%SignalKite` `#CanyonCrossing` | Windowed ACTION, 20s / 2×10s |

### Scene 3 (CD-owned)

- Target: existing scene `d0162b33` (not a new scene)
- `@CadeOConnor` + `#VentureCorridorScene` — `global_found`
- Dialogue exact: `Where is the Adept?`
- Reveal: Cade hidden until the laser blast / steam
- Runtime: 30s, 2 batches, 21:9, 1.0 MP, MiniMax H3 — not in ACTION
- Canonical tags stable; no Image1/Image2 leakage

## Residual (not hidden)

Scene 3 batch-1 ACTION still restates the red-hot metal beat in close
paraphrase (“reaching an intense red-orange temperature” then “The metal
reaches an intense red-orange temperature”). Exact-sentence dedupe does
not collapse it. Quality residual; not used to claim GO.

## Peer review

| Reviewer | Result |
| --- | --- |
| Kimi K3 | **NOT RUN** — model usage limit; no substitute |
| GLM 5.2 | **NOT RUN** — model usage limit; no substitute |
| GPT-5.6 Sol | **NOT RUN** — model usage limit; no substitute |

GO law requires all three **AGREE**. Unavailable ≠ AGREE.

To close: relaunch the three named reviewers on the evidence above. Any
DISAGREE → repair CD (not Scene 3) → rerun affected samples → re-review.

## Runtime

- Studio API recycled via `scripts/restart_studio_api_only.py` only
- `GET :8758/api/healthz` → ok · `GET :5173/` → 200
- COMFY BEFORE: up, ~30 GB free · COMFY AFTER: up, 28.6 GB free ·
  COMFY RESTARTED?: **NO**

## Manual review

Local creator UI: `http://127.0.0.1:5173/`
Studio API: `http://127.0.0.1:8758/`
Do not ask Cursor to finish Scene 3. Ask Co-Director.

**NO-GO**
