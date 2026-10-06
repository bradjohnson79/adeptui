# ADEPT UI — Canonical Reference Tag Convergence

Governing document for one prompt-facing tag per identity.

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Date:** 2026-09-17

## Law

Every identity has exactly one generator-facing tag:

| Kind | Example name | Canonical tag |
| --- | --- | --- |
| Character | Korri | `@Korri` |
| Prop | Venture Spaceship | `%VentureSpaceship` |
| Environment | Earth Horizon | `#EarthHorizon` |

`canonical_tag` is prompt-facing. Database slug, collision suffix, display label, and scope-local alias are not.

Forbidden as prompt identity when the original exists:

`VentureSpaceship2`, `VentureSpaceship3`, `venture-spaceship-4`, `EarthHorizon2`, `CadeSStarfighter2`, `CadeSStarfighter3`

## Drift sources (classified)

| Value | Class | Mint site |
| --- | --- | --- |
| `%VentureSpaceship` | canonical tag | identity grammar from display name |
| `venture-spaceship-4` | db slug | `prop_creator.unique_tag()` kebab collision |
| `VentureSpaceship2` / `VentureSpaceship3` | collision alias | `scene_references.unique_alias()` after attach-by-asset |
| `%venture-spaceship-4` | corrupt prompt use of db slug | Prop Creator UI prefixed `prop.tag` |
| `#EarthHorizon2` | collision alias | same unique_alias path |
| `%CadeSStarfighter3` | collision alias | same unique_alias path |
| `UploadSmokeAdvancedShip Advanced PRS.png` on Venture rows | corrupt duplicate asset | bind-by-asset, no `identity_id` |

## Repair

Authoritative Venture:

- id `2601f525-a32e-401a-bc1a-b17b1fe92817`
- owner Korri `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
- name `Venture Spaceship`
- canonical tag `%VentureSpaceship`
- db slug remains `venture-spaceship-4` (internal only)
- Global `true`
- approved still `24fa824d-…`
- PRS `8593f29e-…` (Korri) / Cade local copy `a09b2413-…`

Cade's Starfighter: `6868078f-…` → `%CadeSStarfighter` (db slug `cade-s-starfighter-2`).

Earth Horizon: library image `9a23b664-…` frozen as `#EarthHorizon` (no ERS sheet).

Cade scene bindings now point Venture at the local PRS `a09b2413`, not the smoke-test ship `579355ac`.

Unrelated view aliases (`KorriFront2`, `Anadriya3`, `VentureCorridor4`) were restored. Convergence only rewrites the three target families.

## Architecture

- `creator_scope/identity_tag.py` — single prompt grammar; `sanitize_generator_tag` never emits kebab, suffix, sheet/PRS filename, or the wrong `@/#/%` prefix
- Prop / Environment save freezes `canonical_tag` unless the owner renames; a stored collision suffix is repaired once
- Scene attach finds by `identity_id` first and does not suffix identity aliases
- Co-Director `prompt_facing_tag` delegates to `sanitize_generator_tag`; it does not `uniqueTag(name)` and does not trust a prefixed stored tag unchanged
- Timed Prompt / H3 compile: `binding_id` → identity → approved PRS → `ref_image_N`
- Compile entity metadata uses `canonicalTag` (`%VentureSpaceship`), never `"@" + alias`
- `resolve_binding_id` display is `identity_name` only — never `asset_name`
- One-time master migration of legacy suffixed tags

## Fresh-scene evidence

Scene `e955b068-7395-4e4d-a239-6e626ef47bbb` in Cade `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`.

Co-Director before Timeline:

- `#EarthHorizon` FOUND
- `%VentureSpaceship` FOUND — Global PRS
- `%CadeSStarfighter` FOUND

Timed Prompt after create and after reload:

- `#EarthHorizon`
- `%VentureSpaceship`
- `%CadeSStarfighter`

H3 compile (Direct Reference):

| Tag | identity_id | asset | file |
| --- | --- | --- | --- |
| `#EarthHorizon` | `9a23b664-…` | `9a23b664-…` | `earth horizon.png` |
| `%VentureSpaceship` | `2601f525-…` | `a09b2413-…` | `VentureSpaceship Advanced PRS.png` |
| `%CadeSStarfighter` | `6868078f-…` | `6e8da820-…` | `CadeSStarfighter Advanced PRS.png` |

No blocked sockets. No suffixed identities. Artifact: `studio-api/.runtime/canonical_tag_fresh_scene.json`.

GPU pixel generate was not queued. Identity compile is the authority for this gate.

## Tests

33 passed: `test_canonical_reference_tag_convergence.py` + `test_prompt_token_bindings.py` + `test_scene_intent_cinematic_synthesis.py` + `test_direct_reference_route.py`.

Hard fails on `VentureSpaceship2/3`, `venture-spaceship-4`, `EarthHorizon2`, `CadeSStarfighter2/3` when the originals exist. Also covers sheet-filename display, prefixed-suffix stored tags, and compile entity metadata.

## Runtime

- Local UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (`/api/healthz` 200)
- `COMFY BEFORE:` PID 34484 / health 200
- `COMFY AFTER:` PID 34484 / health 200
- `COMFY RESTARTED?:` NO
- API recycle only (`scripts/restart_studio_api_only.py`); Comfy left untouched

## Peer gate

**Question:** Does this implementation guarantee one canonical reference tag per identity across Creator, Global scope, Co-Director, Timeline, Timed Prompt, reload, and generation, while ensuring database aliases or collision suffixes can never replace generator-facing identity?

| Reviewer | Verdict |
| --- | --- |
| Kimi K3 | AGREE |
| GLM 5.2 | AGREE |
| GPT-5.6 Sol | AGREE |

Unanimous.

## Verdict

**GO** — one canonical prompt-facing tag per identity. Database slugs and collision suffixes cannot replace generator-facing identity.
