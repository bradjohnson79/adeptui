# Adept Production Systems Readiness — Final Summary

**Branch:** `phase2/production-systems-readiness` (worktree `C:\AdeptFilmWorks\AIVideoStudio-psr`)
**Base:** `a5b7106` (M2.1 tip), tagged `checkpoint/production-systems-readiness-start`
**Date:** 2026-07-24

---

## The one-line version

The studio can now tell you, in one place and without lying, what it can actually do right now —
and every UI surface reads that one answer instead of guessing its own.

## Why that mattered

Three surfaces each judged readiness from different evidence and could contradict each other. The
worst case was routine: the chrome strip said "ComfyUI Connected" while a render was guaranteed to
fail on a node type that was not installed, because nothing compared a workflow's requirements
against the live ComfyUI catalogue. Separately, `/api/health` asserted three hardcoded model paths
under one developer's home directory, so on any other machine it reported missing weights that
were present.

## What shipped

| Area | Result |
|---|---|
| Capability registry | 69 capabilities, 20 subsystems, 8 failure-tolerant probes, 4 endpoints. Exactly the 11 statuses the plan specified, enforced by test. |
| Scenes | `SceneService` extracted; `Scene.summary` added (migration `M010`); missing read routes added. Scene CRUD is `locally_verified`. |
| References | Real upload → attach → list → reload verified. `references.remove` and `references.attach.scene` reported `not_implemented`, asserted by test. |
| Source Manager | `source_pending` / unpublished / `not_configured` / installed now map to distinct statuses with distinct actions. |
| ComfyUI + workflows | Structured health, workflow discovery and readiness, and a graph-level guard that refuses to queue a provably invalid graph. |
| Integrations | Chrome badge, Home readiness panel, Setup Wizard blocker gating, Source Manager blocker list — all reading the capability API. |

## Real bug found and fixed along the way

Extracting `SceneService` exposed that `PATCH .../scenes/{id}` dumped the whole request model, so
any field the client omitted was reset to its schema default. A request that only meant to rename a
scene silently blanked its prompt. Fixed to write only the keys present in the request, with an
E2E test asserting a rename preserves the prompt.

## Verification

```
pytest tests/test_capabilities.py tests/test_scene_service.py -q   →  51 passed
pytest tests -q                                                    →  233 passed, 9 failed (all pre-existing at a5b7106)
npx playwright test --grep @critical --retries=0                   →  41 passed
```

The 9 Python failures are exactly the set recorded in the preflight document before any work began:
8 pack/source-state expectations owned by the pack-authoring branch, plus one full-suite-only
test-ordering interaction. None was "fixed" by weakening an assertion.

Live snapshot on the verification machine (ComfyUI down, real Ollama up, LTX checkpoint installed,
Essential Packs unpublished): **35 of 69 capabilities callable, 13 blocked, no probe warnings.**
All 13 blockers trace to two environment facts — ComfyUI not running (11) and one uninstalled
gated model (2) — not to code gaps.

## Co-Director-callable now

35 capability ids, including the scene write set (`project.scenes.create/update/delete`) behind
`requiresApproval`. That is the meaningful unlock: a Co-Director that can create, retitle,
re-prompt, and delete scenes with approval, backed by a verified slice. Full list in
`ADEPT_PRODUCTION_SYSTEMS_READINESS_REPORT.md` §4.

## What we deliberately did not claim

- **Generation is capped at `partially_wired`**, never `production_ready`, because no real render
  was performed in a verified environment. The optional image/video generation slices were not
  attempted — ComfyUI was unreachable, so workflow readiness could not be exercised end-to-end.
- **No pack download URL was invented.** The Essential Packs remain `not_configured` with
  `MODEL_SOURCE_PENDING` and an "add a Source URL" action.
- **`downloads.queue` stays `mock_verified`.** The only proof is the Playwright fixture provider.
- **Virtual Stage stays `not_implemented`.** It exists in architecture docs, not in code.
- **No Co-Director tool registry / M2.2 orchestration.** This branch publishes the truth source
  M2.2 will read.

## Commits

| Commit | Contents |
|---|---|
| `e1a8e86` | Preflight inventory, baseline suite state, slice selection |
| `91dc3de` | Capability registry, `SceneService`, structured Comfy/workflow readiness |
| `14ddb4f` | Capability-aware Health, Setup Wizard, and Source Manager surfaces; env-driven Vite proxy |
| (this) | Contracts, registry guide, readiness report, final summary, Production Brain pointer |

## Documents

- `ADEPT_PRODUCTION_SYSTEMS_PREFLIGHT.md` — what was true before
- `ADEPT_PRODUCTION_CAPABILITY_MATRIX.md` — baseline per capability, with notes on the unflattering entries
- `ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md` — the API contract, including the rules for M2.2
- `ADEPT_CAPABILITY_REGISTRY.md` — how the registry works and how to change it
- `ADEPT_PRODUCTION_SYSTEMS_READINESS_REPORT.md` — the full report

## The principle worth keeping

`not_implemented` and `blocked` are different claims, and keeping them apart is what makes the
blocker list worth reading. `not_implemented` means there is nothing to fix; `blocked` means an
operator can fix it. The moment a blocker list contains things nobody can act on, operators learn
to ignore it, and the registry becomes decoration.

The corollary is that the hard direction is downward. When a probe shows something believed to work
does not, the fix is to lower the baseline and say why — not to widen the evaluator until the status
comes back green.
