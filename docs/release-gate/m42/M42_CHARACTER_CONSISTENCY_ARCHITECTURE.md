# M42 Character Consistency Architecture

## Scope

This document defines the package-local contracts added under
`studio-api/app/character_consistency/` for M42 Qwen-2512 character consistency work.
The implementation is intentionally filesystem-first so the sprint can ship clear
contracts without expanding into a database migration.

## Package Modules

- `reference_roles.py`
  - Canonical role vocabulary for identity, face, hair, wardrobe, body proportions,
    ears, markings, accessory, art style, lighting, camera, and environment.
  - Splits roles into `identity_lock` vs `style_context` so identity can remain
    distinct from render style.
- `generation_recipe.py`
  - Pydantic contract for persisted generation recipes.
  - Stores model key, workflow version, prompt package version, reference asset ids
    and roles, seed policy, seed, sampler, scheduler, steps, guidance, resolution,
    VAE, LoRA settings, style notes, and negatives.
  - Provides JSON save/load helpers for package-local persistence.
- `seed_policy.py`
  - Defines `explore`, `refine`, and `production_continuity`.
  - `production_continuity` requires approved anchors from the same project library.
- `multi_view.py`
  - Encodes Method A (`method_a_unified_sheet`) vs Method B
    (`method_b_anchored_sequential`).
  - Selection stays honest about prerequisites instead of pretending both methods
    are always available.
- `deviation_report.py`
  - Defines `CharacterDeviationFinding` and `CharacterDeviationReport`.
  - Uses comparative labels such as `aligned`, `minor_drift`, `clear_drift`, and
    `not_assessable` rather than fake decimal precision.
- `correction_loop.py`
  - Builds targeted correction instructions from actionable drift/review findings.
  - Recommends `refine` for corrective passes and preserves escalation notes when
    evidence is insufficient.

## Key Decisions

### Identity vs style separation

Identity-critical roles are kept separate from style/context roles so the system can
lock who the character is without conflating that with camera language, lighting, or
environment decisions.

### Honest scoring

The deviation report intentionally avoids a numeric continuity score. Comparative
labels are easier to defend and match the addendum requirement to avoid fake
precision. `not_assessable` is a first-class outcome, not a hidden low score.

### Local persistence

Generation recipes are currently stored with JSON helpers only. This keeps the scope
inside the allowed files and makes the contract easy to integrate later.

## Evidence

Representative JSON artifacts live under:

- `artifacts/m42/w43-qwen-2512/consistency/reference-role-manifest.json`
- `artifacts/m42/w43-qwen-2512/consistency/generation-recipe-example.json`
- `artifacts/m42/w43-qwen-2512/consistency/deviation-report-example.json`
- `artifacts/m42/w43-qwen-2512/consistency/correction-plan-example.json`

## Escalation

If recipes or reports need durable cross-session querying, indexing, or joins with
existing identity/generation records, that should escalate to the primary owner for a
database-backed persistence design. This subtask intentionally stops at package-local
contracts and JSON helpers.

## Prompt Coverage Note

The checked-in addendum file currently exposes sections through `Gate flags` only.
This implementation therefore follows the explicit assignment contract and the
available addendum text in-repo, while preserving room for the primary owner to align
any additional section 13-19 wording from parent-chat history.
