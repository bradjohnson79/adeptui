# Timeline Reference Persistence + Hydration Certification

**Governing document for this gate.**  
Co-Director orchestration remains GO in `docs/release-gate/codirector/CODIRECTOR_TIMELINE_ORCHESTRATION_CONVERGENCE.md`. That GO does not cover Timed Prompt hydration or canonical identity persistence.

| Field | Value |
| --- | --- |
| Date | 2026-09-16 |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Project | Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| Fresh scene | `Hydration Repair Fresh 1789583789145` `b18a8a49-8594-40f9-a9f5-2f1accb2ff80` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

## Verdict

**GO — TIMELINE REFERENCE PERSISTENCE + HYDRATION CERTIFIED**

Detect → attach → persist Timeline JSON → Timed Prompt FOUND → reload same IDs → generate / reference-transport uses the same three asset IDs.

This is Case A hybrid repair. Generation already resolved `scene_reference_bindings` by binding UUID. Timed Prompt was listing project-scoped rows only, so scene-scoped Co-Director attaches showed “Missing from References.”

## Root cause

1. **Two catalogs.** Generate used `resolve_binding_id` (any scope). Timed Prompt / Inspector / `DirectorTracks` listed `scopeType=project` only.
2. **Names-only persist.** Co-Director wrote `{binding_id, prompt_name, type}` and left `tag` / `asset_id` / `identity_id` empty.
3. **Project-wide alias uniqueness.** A second scene uniquified `%VentureSpaceship` to `VentureSpaceship2`.
4. **Attach was insert-first.** Duplicate `(scope, asset, type)` could poison the session.
5. **Venture identity.** Venture’s approved PRS lives on the visible global prop `2601f525-…`. `_project_local_asset_id` remapped that foreign sheet by the generic tag `advanced_prop_reference_sheet` onto Upload Smoke `579355ac-…`.

“This name is no longer in References. It was not redirected.” is static copy. There is no redirect pipeline. Fresh binds must never hit it.

## Architecture (unchanged contracts)

- Identity authority: `SceneReferenceBinding`
- Timed Prompt clip surface: `PromptNameBinding` / `TimedPromptNameBinding`
- Lookup: `binding_id` first, then `GET /api/projects/{id}/references/id/{bindingId}`
- Library environment is valid: `reference_type=environment`, `identity_id=null`, `asset_id` = Library image

No `TimelineReferenceBinding` type was added.

## Implementation

- Timed Prompt catalog loads scene + inherited bindings, then fetches missing IDs.
- Prompt segments now persist `tag`, `asset_id`, `identity_id`, `reference_sheet_id`.
- `attach` is get-or-create on `(project, scope, asset, type)`. Alias uniqueness is scope-local (`uq_srb_scope_alias`, M037).
- Prop resolve prefers exact display label / tag (after stripping “reference sheet”). Distinctive words such as `venture` cannot bind Upload Smoke.
- Cross-project visible sheets are adopted by distinctive filename, never by generic tag.
- Director load backfills empty `tag` / `asset_id` from `resolve_binding_id` once.

## Live evidence (fresh scene, not `bb_734b09c1124b`)

| Binding | Alias | asset_id | identity_id | File |
| --- | --- | --- | --- | --- |
| Earth Horizon | EarthHorizonPng | `9a23b664-fdb6-4bab-a2ed-f4d432247d44` | null (Library environment, no ERS) | `earth horizon.png` |
| Venture Spaceship | VentureSpaceship | `a09b2413-3bfc-447d-bef8-4b3449ceecb9` | `2601f525-a32e-401a-bc1a-b17b1fe92817` | `VentureSpaceship Advanced PRS.png` (adopted into Cade Scenes) |
| Cade's Starfighter | CadeSStarfighter | `6e8da820-7c8a-4dc8-825a-15c6d3bf7f59` | `6868078f-cda7-4427-8f85-fd318cf4a141` | `CadeSStarfighter Advanced PRS.png` |

Reference-transport compiled those three asset IDs. Upload Smoke `579355ac-…` was not selected.

Playwright Timed Prompt modal: three FOUND rows, no “Missing from References”, no “was not redirected”. Same IDs after reload. Generate submit returned `ok: true` with the same asset IDs in `normalizedRequest`.

## Tests

| Suite | Result |
| --- | --- |
| `test_timeline_reference_persistence.py` + prompt-token backfill | **15 passed** |
| Scene-reference attach / alias / token / name-binding targeted | **27 passed** |
| `test_migrations.py` (includes 0037) | **5 passed** |
| Vitest `timedPromptNameBindings` + `loadTimelineReferenceCatalog` | **16 passed** (2 files) |
| Playwright `timeline-reference-persistence-hydration.spec.ts` | **1 passed** |

Pre-existing, out of scope: `test_timeline_reference_aliases.py` `test_unsupported_video_ref_is_not_consumed` (retired `ltx-local`) and `test_image_reference_compile_canonical_id`.

## E2E TRACE

| Step | Result |
| --- | --- |
| User action — Cade Scenes Co-Director “build a scene in Timeline named Hydration Repair Fresh …” | PASS |
| Frontend — Timeline Timed Prompt opens three FOUND rows | PASS |
| API — scene+inherited catalog + GET-by-id | PASS |
| Backend — attach get-or-create, scope-local alias, full PromptNameBinding persist | PASS |
| Persistence — reload keeps binding_id / asset_id / tag | PASS |
| Runtime — MiniMax H3 generate compile uses adopted Venture PRS + Earth Horizon + Cade PRS | PASS |
| Result — transport and generate JSON contain the same three asset IDs | PASS |
| Reload — still FOUND, no Missing / redirect copy | PASS |
| Downstream — reference-transport sockets `ref_image_0/1/2` | PASS |

## Beta / runtime

- Studio API `http://127.0.0.1:8758/api/healthz` **200** (PID 43748 after API-only recycle)
- Creator UI `http://127.0.0.1:5173/` **200**
- Comfy `GET http://127.0.0.1:8188/system_stats` **200**

```text
COMFY BEFORE: PID 34484 / healthy
COMFY AFTER:  PID 34484 / healthy
COMFY RESTARTED?: NO
WHY?: Ordinary Studio API recycle only. :8188 left alone. MiniMax :8192 not restarted.
```

## Limitations (disclosed, not blockers)

- Venture’s original PRS file lives on the global prop’s owning project. Cade Scenes now holds an adopted local copy `a09b2413-…` of `VentureSpaceship Advanced PRS.png`. Identity remains Venture `2601f525-…`.
- The certified fresh scene alias for Earth Horizon was `EarthHorizonPng` (filename stem included `.png` at prepare time). Prompt tags still matched `#EarthHorizon`. Stem strip is in source for the next prepare.
- Playwright generate asserts submit + compiled asset IDs. It does not wait for the MiniMax job to finish encoding.
- Establishing Shot `bb_734b09c1124b` was not recertified. That shot was Cursor-overwritten after Co-Director create.

## Manual review

1. Open Cade Scenes at `http://127.0.0.1:5173/`
2. Open scene **Hydration Repair Fresh 1789583789145**
3. Double-click the Timed Prompt clip — three FOUND rows: Earth Horizon, Venture Spaceship, Cade's Starfighter
4. Reload — same rows, same IDs
5. Do not restart Comfy
