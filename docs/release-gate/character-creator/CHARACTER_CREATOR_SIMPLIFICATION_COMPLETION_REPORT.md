> **HISTORICAL — SUPERSEDED BY CHARACTER CREATOR V2.** Four-view / collage default is retired. See `CHARACTER_CREATOR_V2_ARCHITECTURE.md`.

# ADEPT UI — Character Creator Simplification + Character Sheet Pipeline + Advanced Workspaces

**Completion Report** · Branch `beta` · Base SHA `867067c` · Date 2026-08-13

## Verdict: **GO**

All mandatory gates passed. The 23-tab engineer-style standalone Character Creator and the separate Co-Director Express surface are replaced by ONE shared Character Profile workflow backed by the existing `character_identity` backend. The 4-view Character Sheet pipeline, shared Local/API generator selection, and four advanced workspaces (Voice Studio, PoseCraft, Props & Accessories, Variants) are implemented, integrated, tested, and live-verified on Beta.

---

## Scope delivered

### Phase 1 — Shared Character Profile core (frontend)
New module `studio-web/src/components/character/`:
- `types.ts` — canonical `CharacterProfile`, `CharacterReference`, `CharacterCandidate`, `GeneratorOption`, `GeneratorSourceState`; shared style/gender option lists.
- `useCharacterProfile.ts` — load/save/patch/reset/delete hook consolidating the previously duplicated debounced-save logic.
- `CharacterProfileForm.tsx` — Name / Gender / Style / Profile fields.
- `CharacterReferenceControl.tsx` — thumbnail, Upload / Add from Library / Change / Remove, and the explicit **Use as Character Identity** checkbox (approve-gated, not auto-approve).
- `GeneratorSourceSelector.tsx` — Local + API rows with enable checkbox, dropdown, status, and capability-driven credits.
- `CharacterSheetGenerator.tsx` + `CharacterCandidateGrid.tsx` — generate + composed-sheet candidate cards with provenance labels (LOCAL — Illustrious XL / LOCAL — Z-Image / API — provider/model).
- `CharacterActions.tsx` — Save / Reset / Delete (Delete only for saved characters).
- `CharacterCore.tsx` — the single composed workflow used by both surfaces; `characterCore.css`; `index.ts` barrel.

### Phase 2 — Completeness law + top-level UX
- Backend: a saved character with a valid name is valid. `service.py` clamps profile status so `INCOMPLETE` is **never** surfaced on the profile (clamped to `DRAFT`) at all three sync points (reference attach, reference detach, and `update_profile`). The detailed coverage report stays internal for advanced views.
- Standalone top-level: `[ + Create Character ]` + `Load Character [ Saved Character Dropdown ▼ ]`. Create starts a blank profile (no "New Character" prefilled input) and auto-focuses the name field.

### Phase 3 — Rewire both surfaces to the shared core
- Express (`CharacterCompactView.tsx`): `CharacterDetail` body replaced with shared `CharacterCore`; Co-Director mounting, `onOpenFull` deep-link, and `onDeleted → "__delete__"` preserved. No advanced buttons on Express.
- Standalone (`CharacterProfileWorkspace.tsx`): primary body is `CharacterCore`. All 23 legacy tabs (Visual Gates, Visual Identity, Character Sheet, Close-Ups, Poses, Expressions, Skin, Hair, Wardrobe, Personality, Motion, Emotion, Performance Bible, Relationships, Prompt Package, Approved Look, Continuity, Versions, Generated Assets, Voice tabs) are nested behind ONE `Advanced / More` `<details>` disclosure — preserved, not deleted. Seed Korri / Promote to Identity / coverage % / version UUID / INCOMPLETE removed from primary chrome (relocated into Advanced).
- Parity: both surfaces read/write the same `character_identity` profile + references; hydration verified across save/reload by Playwright.

### Phase 4 — Generator source selection
- `GeneratorSourceSelector` populates Local from `/api/imagegen/models` + style-aware `/api/image-product/recommend`, and API from `/api/hosted-providers/discovered-models?modality=image`.
- **Routing hierarchy (explicit, enforced backend-side):** reference attached → reference-capable Certified first (`zimage.ref_edit`), never text-only Illustrious; no reference → style recommendation first (anime → Illustrious XL).
- **Capability-driven credits:** numeric balance only when the provider exposes one (Fal); otherwise `Connected` / `Balance unavailable`. Never invented.
- **User Control Law:** `generatorSources` is now threaded through `VisualSheetStartBody` → `start_visual_sheet_generation` → `_build_candidate_routing_plan`; an explicit all-disabled selection refuses generation (zero jobs) instead of silently falling back.

### Phase 5 — Character Sheet pipeline (extended `visual_sheet.py`)
Per candidate: generate the 4 required views (front / side / back full body + front close-up, no rendered text) → structural identity-consistency validation → compose ONE canonical 2x2 Character Sheet (PIL) → ingest into the Library as the candidate asset → retain the 4 source views as lineage (`sourceAssetIds` + asset-graph edges) → candidate approval selects the composed sheet. Reference-first law enforced; Use-as-Character-Identity records `generationUsed=false`, `sourceType=upload|library`, and preserves the original Library asset id (no binary duplication).

### Phase 6 — Advanced workspaces (gated by save)
- **Voice Studio** and **PoseCraft** buttons navigate to the existing routed workspaces with `characterId` + `returnWorkspace=characters`. No rebuild.
- **Props & Accessories** (`PropsWorkspace.tsx`): max 4 enforced (`MAX_PROPS_PER_CHARACTER`), character-associated Library assets via `assign_asset(entity_type=character, entity_id=characterId)` (no duplicate binary), reference-locked generation reusing `enqueue_imagegen_job` against the canonical hero sheet.
- **Variants** (`VariantsWorkspace.tsx`): Original (canonical sheet, immutable) + up to 12 variants = 13 looks, built on the existing `continuity` identity_variants backend (`character_identity/variants.py`). Each variant generation is reference-locked to the **Original canonical sheet** as the PRIMARY reference (identity locked) and produces a composed 4-view sheet via the same pipeline. Deleting a variant never alters the Original.
- Both panels are wired into the standalone's advanced section via `?advanced=props|variants` and are disabled until the character is saved.

### Phase 7 — Migration safety
Existing saved characters load unchanged. No advanced identity data deleted. hero_identity, references, Voice Studio links, PoseCraft data, and generated assets remain valid. Complexity is hidden/internalized, not removed. The `generation_job_id` prop column uses a legacy `ALTER TABLE` guard in `ensure_character_identity_tables` (non-destructive).

---

## Tests (exact counts)

| Suite | Result |
|---|---|
| Backend integrated (`test_character_sheet_composition`, `test_character_props`, `test_character_variants`, `test_character_candidate_routing`, `test_m33_character_identity`, `test_m42_w5_identity_continuity`) | **83 passed, 0 failed** |
| Frontend typecheck (`tsc --noEmit`) | **exit 0** |
| Frontend node test (`characterCompact.test.ts`) | **28 passed, 0 failed** |
| Playwright E2E (`tests/e2e/character-creator-simplification.spec.ts`) on live local Beta | **1 passed** |
| Production build (`studio-web` `npm run build`) | **passed** |

New backend tests added: 18 (sheet composition) + 11 (props) + 6 (variants) + 3 (User Control Law) + 2 (completeness law) = **40 new tests**.

### Pre-existing failures (NOT this mission; confirmed failing on clean baseline via `git stash`)
- `test_m33_character_creator.py::test_create_character_intent_routes_character_creator` — Co-Director `IntentClassification.route_decision` AttributeError.
- `test_m42_w3_image_product.py::test_recommend_why_and_cost`, `::test_compile_no_workflow_preference` — legacy `qwen`/`flux` routing assertions superseded by the `qwen2512`/`illustrious` registry.

These are out of scope (Law #29) and documented here for the record.

## Independent verification
An independent verifier subagent (second-pass, did not write the code) reviewed all 8 mission claims against source and re-ran the suites. Result: all claims PASS; it flagged two narrow wiring gaps (D1: `update_profile` missing the INCOMPLETE clamp; D2: `generatorSources` dropped by the API schema). **Both were repaired by the primary with regression tests** and the integrated suite re-run green (83 passed) before this verdict.

## Beta verification (Build Law #1)
- `studio-web` rebuilt; Beta restarted via `Restart-AdeptUI-Beta.ps1 -NoBrowser -Force`.
- HTTP 200 confirmed on `http://127.0.0.1:8760/` (web) and `http://127.0.0.1:8758/api/health` (API).
- Playwright re-run against the refreshed stack: **passed**.
- **Creator UI:** http://127.0.0.1:8760/ · **Studio API:** http://127.0.0.1:8758/

## Evidence artifacts
- `tests/e2e/screenshots/char-simple-01-top-level.png` — clean Create/Load top-level.
- `tests/e2e/screenshots/char-simple-02-named.png` — shared profile form.
- `tests/e2e/screenshots/char-simple-03-advanced-open.png` — legacy tabs nested under "Advanced / More".
- `tests/e2e/screenshots/char-simple-04-identity-persisted.png` — identity persisted after reload (no generation).
- `tests/e2e/screenshots/char-simple-05-props.png`, `char-simple-06-variants.png` — advanced workspaces.

## Limitations (honest)
- Identity-consistency validation across the 4 views is **structural** (shared seed/family/workflow/reference-lock + all-4-done), not an ML visual validator — deferred to a later vision-tooling pass.
- Variant sheet state is persisted in a reserved `__variant_sheet__` namespace inside `IdentityVariantRow.trait_overrides_json` to avoid a schema migration; a future migration can add dedicated columns transparently.
- Prop and Variant generation require an approved canonical Character Sheet first (reference-locked by design, so props/variants stay on-identity).
- Variant generation polling is client-side; no server-push.
- Express surface no longer shows an inline Voice section; Voice is reachable via the standalone's Voice Studio advanced button (per the "Express shows no advanced buttons" requirement).

## Manual review path
1. Open http://127.0.0.1:8760/ → open a project → Characters workspace.
2. Click **+ Create Character**, type a name, pick a Style — the shared form autosaves.
3. Optionally add a Character Reference (Upload / Add from Library) and tick **Use as Character Identity** to set the look without generation.
4. Enable a Local and/or Cloud generator and **Generate Character Sheet** to see composed 4-view candidates with provenance labels; **Use This Look** to approve.
5. With the character saved, use the Advanced buttons: **Voice Studio**, **PoseCraft**, **Props & Accessories**, **Variants**.
6. Open **Advanced / More** to reach the legacy power tabs (gates, versions, continuity, generated assets).
