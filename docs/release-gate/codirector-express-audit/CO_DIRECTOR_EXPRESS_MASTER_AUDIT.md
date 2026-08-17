# Adept UI — Co-Director Express Pipeline Master Audit

> Authoritative read-only audit deliverable for the Cursor repair queue.
> Nothing in this document was modified by the auditor; every finding cites disk state at audit time.
> Findings use the CDX register. Placeholder confidence rules: CONFIRMED = direct source/runtime evidence; NEEDS VERIFICATION = meaningful evidence, safe reproduction still required.

## 1. Audit identity

| Field | Value |
|---|---|
| Branch | `beta` |
| HEAD | `3980b6051269514b5b3c38eb066c005a1a5fe850` |
| Audit start (local) | 2026-08-16 12:32:48 -07:00 |
| Working tree | DIRTY (modified + untracked — see below); all current changes treated as protected |
| Mode | Read-only. No source/test/config/runtime/db/asset changes were performed. |

**Working-tree state (Phase 0).** Modified tracked files of interest: `studio-api/app/codirector/capabilities/handlers/ers_generate.py`, `codirector/knowledgebase/ers_compiler.py`, `codirector/vision/router.py`, `image_core/capability.py`, `image_core/recommend.py`, `image_product/compile.py`, `image_runtime/workflow_execute.py`, `magi/timeline_handoff.py`, `main.py`, `scene_creator/generation.py`, `scene_creator/timeline_handoff.py`, `storyboard_jobs.py`, `workflows/qwen_image_2512.py`, `fal_catalog.py`, `avatar_studio.py`; frontend `AgentWorkSurface.tsx/.css`, `SceneCreator/regionEdit/*`, `SpatialMap/{ERSGenerationMonitor.tsx,ersGenerator.ts,useErsGeneration.ts}`, `styles.css`; `config/image-workflows/certified-registry.json`; `docs/release-gate/scene-creator/SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md`; beta-backend scripts. Untracked: large probe/evidence surface under `.runtime/`, `logs/`, new tests (`test_qwen_i2i_ers.py`, `test_timeline_continuity_contracts.py`, `test_avatar_studio_phase1.py`, `ersGenerator.eligibility.test.ts`, `useErsGeneration.test.ts`), new E2E specs (`korri-switch-place.spec.ts`, `prop-creator-coffee-cup*.spec.ts`, `spatial-e2e-smoke.spec.ts`).

**Concurrent workstreams (protected, not interfered with):**
1. **Qwen/ERS Phase 2** — ERS handler/compiler/frontend + `qwen_image_2512.py` + certified-registry are mid-flight in-tree. Findings touching those files (CDX-035, CDX-036, CDX-039, CDX-040) audit disk as-is; Cursor must re-verify after Phase 2 lands.
2. **Scene Creator Final Production Certification** — governing doc modified in-tree; latest recorded verdict NO-GO (2026-08-15 run, Nano Banana 2 Add napkin pixel FAIL; Remove/Modify/Replace PASS). Grounding + Integrity baseline treated as protected (see §14).
3. **Krea Phase 1** — owned by Cursor; not re-audited.
4. **Localized Add** — `regionEdit/*` modified in-tree; separate workstream.

**Limitations.** Static source audit; no live runtime reproductions (no service restart, no job submission, no DB writes, no Playwright runs). "CONFIRMED" means source evidence is conclusive; anything needing a live reproduction is NEEDS VERIFICATION. Surface audited: 178 Co-Director frontend files, 618 codirector backend modules, plus cross-cutting image/library/runtime layers — the register holds the highest-value evidence-grounded defects, not an exhaustive line-level enumeration.

## 2. Executive summary

**97 findings (CDX-001 … CDX-097).** P0: **0** · P1: **11** · P2: **43** · P3: **43** · NEEDS VERIFICATION: **3** (CDX-029, CDX-044, CDX-057). All other findings CONFIRMED.

**Headline:** The Co-Director Express pipeline is genuinely wired end-to-end — real API calls, real DB persistence, real provider routing, honest job submission (no mock-success in production paths found), and the historical Scene-Creator sheet/package resolution is repaired on the production UI path (`resolve_ers_for_sheet`). No destructive P0 and no cross-project mutation was confirmed. However, the pipeline carries: three P1-class text-store divergences in Script Writer, two P1 provider-truth defects (fake local readiness, silent model substitution), a P1 library deletion-cascade gap, a P1 legacy batch surface that both loses ERS grounding and bypasses approval, a P1 approval-identity dead channel in Library retrieval, and one P1 wrong-asset adoption race (needs verification). The dominant systemic themes are: (1) **parallel authorities** — second specialist selection paths, second scene engine, second execution authority (Production Executive), legacy ERS tool pipeline, dormant frontend planner; (2) **dual persistence** — HTML-vs-elements script, script_segments-vs-v2, file-sheet-vs-trait-package ERS, two lineage stores; (3) **side-effecting reads** — GET /workspace, GET /notes, GET /scriptwriter|/story all mutate canonical state; (4) **dead legacy surfaces** retained next to live ones (dead batch UI, dead Standard spatial-map tree, dead CharacterCreatorEmbedded, dead ScriptwriterCompactView, dead batch client); (5) **dishonest readiness** — static catalogs claim Certified/ready without weights-on-disk verification, and selectors default missing fields to available.

**Top 10 highest-value repairs** (see §15 for packets):
1. CDX-063 Library asset deletion without entity-link cascade (P1)
2. CDX-076 silent Z-Image→other model substitution in queue worker (P1)
3. CDX-075 local generator readiness from static catalog, not disk (P1)
4. CDX-034 legacy `/batches` + regenerate resolve sheetId as package UUID → silent zero grounding (P1)
5. CDX-043 legacy batch send-to-timeline without approval gate (P1)
6. CDX-051/052/053 Script Writer HTML/elements split + duplicate script store + missing project scoping (P1×3)
7. CDX-064 Library approval-state channel dead → retrieval reports approved assets as drafts (P1)
8. CDX-029 cross-execution Atlas adoption race (P1, NV)
9. CDX-044 MAGI export CLIP_NOT_FOUND conditional break of Send-to-Timeline (P1, NV)
10. CDX-013/012 Spatial placement identity: unvalidated writes + silently-dropped non-PropEntity placements (P2)

## 3. Current Co-Director architecture map

```text
Browser (studio-web)
└─ Route /co-director → CoDirectorPage → CoDirectorFullScreen → CoDirectorShell
   └─ CoDirectorProjectContent — Express content tabs (navEntries.ts / CONTENT_NAV):
      wiki | notes | story | scriptwriter | characters | prop_creator |
      spatial_map | scene_creator | library  (+ casting/bible/plans/approvals/jobs/vision)
   └─ CoDirectorSession (session/SSE/execution state, project binding via route)
   └─ Agent Work Surface (execution packs) · Plans · Approvals · Chat/Conversation
        │  api.ts gateway (never calls providers directly — invariant GREEN)
        ▼
Studio API (:8758) — /api/codirector gateway (routers/codirector.py) + /api subsystem routers
├─ Co-Director core: routing (RouteDecision/unified intent) → capabilities registry
│    → execution packs (dispatcher/advance/pending_store) → handlers
│    → specialist stack (intelligence + foundation) → SynthesisEngine (single voice)
│    → Production State projection (read-through, 14 domains, never persisted — Law 4)
├─ Character Creator Express: CharacterCompactView → shared CharacterCore/useCharacterProfile
│    → character_identity api/service/visual_sheet (pack pipeline) → image_product/queue_worker
├─ Prop Creator Express: PropCreatorPanel → PropCreatorCore/usePropCreator
│    → prop_creator router/service → canonical PropEntity (spatial_map/ers_contracts + ers_persistence trait)
├─ Spatial Map: SpatialMapPanel (Express) → spatial_map router/service (document JSON)
│    → Atlas (atlas.generate handler → imagegen) · ERS (ers.generate → sheet/package)
├─ Scene Creator Express: launcher → SceneCreatorCore/useSceneCreator (shared with Standard)
│    → scene_creator router/service (shots/candidates/approve/Re-Take) → timeline_handoff → MAGI/W46
├─ Story/Script/Wiki/Notes: story_entries · script_documents_v2 (+ legacy script_segments/story_documents)
│    · Project.settings_json snapshot (knowledgeEntries/workingNotes/compiledWiki) · Production Bible SQL
├─ Library: project_library service/taxonomy/classify + asset_graph + m29_asset_versions (second lineage)
│    — approval truth lives on Asset.production_approval (not AssetLibraryMeta)
├─ Providers/runtime: image_core preflight/recommend → image_product compile/pin →
│    storyboard_jobs.enqueue_imagegen_job → queue_worker (_imagegen/_imagegen_fal/_imagegen_kie)
│    → ComfyUI workflows / fal / Kie · readiness authorities: Setup/Source Manager components,
│    /api/capabilities, static model_registry._CATALOG, certified-registry.json (NOT reconciled)
└─ Second authorities (see findings): Production Executive (/jobs worker) · wiki_intelligence
     specialist assignment (cap 6–8) · foundation/creative roster (cap 4) · legacy ers.* tool pipeline
```

**Shared cores (Express ↔ Standard):** `CharacterCore/useCharacterProfile` (character), `PropCreatorCore/usePropCreator` (props), `SceneCreatorCore/useSceneCreator` (scene), `useErsGeneration` + SpatialMapPanel (ERS, Express+Standard same panel), `ScriptwriterInlineEditor` vs `ScriptwriterStudio` (different editors, same backend), `LibraryMediaGrid` (Express) vs `LibraryPanel` (Standard, richer).

**Fragile seams (master view):** (1) Spatial Map document JSON ↔ entity stores (no referential integrity, CDX-013); (2) ERS sheet (file store) ↔ EnvironmentReferencePackage (trait store) — two records with a metadata.sheet_id bridge (CDX-034/036/037/038); (3) script text: 2 stores + 2 representations (CDX-051/052); (4) approval truth split: Asset.production_approval vs AssetLibraryMeta (CDX-064); (5) readiness: 4 authorities (CDX-075/081); (6) settings_json single blob (CDX-057); (7) execution: pack system + executive + legacy frontend planner + batch subsystem (CDX-085/089/088/046).

## 4. Express system inventory

| Express system | FE entry | Shared core/hook | API client | Backend route/service | Canonical persisted store | Generation/provider path | Library path | Downstream handoff | Standard equivalent |
|---|---|---|---|---|---|---|---|---|---|
| Character Creator Express | CoDirectorProjectContent → CharacterCompactView | CharacterCore/useCharacterProfile | api.ts characterIdentity* | character_identity/api.py + visual_sheet.py | CharacterProfile rows + pack (visual sheet) | storyboard_jobs.enqueue_imagegen_job → image_product → worker | project_library assign + labels | promotion.py → continuity VisualIdentity + Bible | components/character (full workspace) |
| Prop Creator Express | PropCreatorPanel | PropCreatorCore/usePropCreator | propCreatorApi | prop_creator/router.py + service.py | PropEntity via ProjectTraitRow prop_entity (ers_persistence) | enqueue_imagegen_job (honest fail on API w/o route) | production_approval + approved_prop label | Spatial Map (approved-only) → Scene Creator (_placed_project_prop_ids) | components/prop-creator (same core) |
| Spatial Map | SpatialMapPanel | gridGeometry/placementArm/useErsGeneration | spatialMapApi | spatial_map/router.py + service.py | spatial_map_documents (document_json) | Atlas: atlas.generate handler | backgroundAssetId + reference_bundle | ERS + Scene Creator production_handoff (reads only) | components/spatial-map (DEAD — CDX-027) |
| Atlas Shot | SpatialMapPanel startAtlasGeneration | scene_intent.py | startExecution | capabilities/handlers/atlas_generate.py | sceneIntent snapshot in map document | imagegen txt2img (fixed 1280×1280) | queue_worker commit + prompt_meta | map background → ERS source pixels | — |
| ERS | ERSGenerationMonitor | useErsGeneration/ersGenerator | environmentReferenceSheet client + execution client | ers_generate handler + environment_reference_sheet/api.py | Sheet (file JSON) + Package (trait spatial_ers, metadata.sheet_id) | image-product compile ERS branch → qwen2512.ref / GPT-Image-2 | ers_composite_asset_id + lineage edges | scene_creator ers_resolver → shots | same panel (Express+Standard) |
| Scene Creator Express | SceneCreatorExpressLauncher | SceneCreatorCore/useSceneCreator | sceneCreatorApi | scene_creator/router.py + service.py | SceneGenerationBatch/SceneShot/candidates (traits) | _enqueue_shot_candidates → enqueue_imagegen_job | _set_asset_approval labels | timeline_handoff → magi export (approved only) | components/scene-creator (same core) |
| Story | StoryEntryEditor (embedded) | — | api.storyEntries | story_entries/api.py | story_entries SQL | — | wiki compile (manual publish) | Wiki/Production Bible | same component in ProjectEditor |
| Script Writer | ScriptwriterInlineEditor (+ dead CompactView) | — | api.scriptwriter | scriptwriter/api.py + service.py | script_documents_v2 (+ legacy script_segments) | — | — | timeline_prep/bible proposals (STALE — CDX-051) | ScriptwriterStudio |
| Wiki | ProjectWikiPanel/CompiledWikiReader | — | wiki/compile/promote/correct | routers/codirector.py + wiki_intelligence | Project.settings_json compiledWiki | LLM editor (conservative fallback) | — | production_state invalidation | same |
| Notes | NotesPanel | — | api.notes | codirector/notes/service.py | Project.settings_json workingNotes | — | — | promote → wiki compile | same |
| Library | LibraryMediaGrid | assetModel | api.library | project_library + routers/extra.py | Asset rows + settings_json LibraryState | — | — | entity folder links; delete guards (GAP CDX-063) | LibraryPanel (richer: tree/global) |
| Agent Work Surface | AgentWorkSurface | buildPack | execution client | execution/api.py + dispatcher | execution pack (ProjectTraitRow) | handlers → enqueue_imagegen_job | artifact_persist | scene/storyboard handoffs | — |

## 5. Express scorecard

| Express System | UI | API | Canonical State | Persistence | Provider/Runtime | Library | Downstream | Reload | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Character Creator Express | YELLOW | GREEN | YELLOW | GREEN | YELLOW | YELLOW | YELLOW | GREEN | **YELLOW** |
| Prop Creator Express | YELLOW | YELLOW | GREEN | GREEN | GREEN | YELLOW | YELLOW | GREEN | **YELLOW** |
| Spatial Map Express | YELLOW | YELLOW | YELLOW | GREEN | YELLOW | YELLOW | YELLOW | GREEN | **YELLOW** |
| Atlas Shot | GREEN | GREEN | GREEN | GREEN | GREEN | YELLOW | YELLOW | GREEN | **YELLOW** |
| ERS | YELLOW | YELLOW | GREEN | YELLOW | YELLOW | GREEN | YELLOW | GREEN | **YELLOW** |
| Scene Creator Express (shot flow) | GREEN | GREEN | GREEN | GREEN | GREEN | YELLOW | YELLOW | GREEN | **YELLOW** |
| Scene Creator legacy batch flow | RED (dead UI) | RED (no approval; grounding loss) | YELLOW | YELLOW | GREEN | RED | RED | N/A | **RED** |
| Story | YELLOW | GREEN | GREEN | GREEN | — | — | GREEN | YELLOW | **YELLOW** |
| Script Writer | YELLOW | YELLOW | RED | GREEN | — | — | YELLOW | GREEN | **RED** (P1×3) |
| Wiki | GREEN | GREEN | YELLOW | YELLOW | GREEN | — | GREEN | GREEN | **YELLOW** |
| Notes | GREEN | YELLOW | YELLOW | YELLOW | — | — | GREEN | GREEN | **YELLOW** |
| Library | YELLOW | YELLOW | YELLOW | GREEN | — | — | RED | GREEN | **YELLOW** |
| Agent Work Surface | GREEN | GREEN | GREEN | GREEN | GREEN | GREEN | GREEN | GREEN | **GREEN** |
| Co-Director execution/approval | GREEN | YELLOW | GREEN | GREEN | GREEN | GREEN | YELLOW | GREEN | **YELLOW** |
| Specialist delegation | YELLOW | GREEN | YELLOW | GREEN | YELLOW | — | — | — | **YELLOW** |
| Provider routing/capabilities | YELLOW | YELLOW | — | — | YELLOW | — | — | — | **YELLOW** |
| Co-Director Vision (visual canon) | RED | RED | RED | GREEN | YELLOW | — | RED | — | **RED** |
| Dead/legacy surfaces (Standard spatial-map tree, batch UI, CharacterCreatorEmbedded, CompactView, ProfileItem prop, :8760 E2E pins) | RED | YELLOW | RED | — | — | — | — | — | **RED** |

GREEN = audited path is internally coherent per evidence (never "code exists"). No system earned a fully GREEN verdict except Agent Work Surface; the shot-flow Scene Creator core is the strongest GREEN-adjacent surface. No P0.
## 6. Confirmed defect register

### Character Creator Express (Phase 5)

**CDX-001** — P2 · CONFIRMED · Character Creator Express · Provider routing (Local/Cloud truth)
Files: `studio-api/app/character_identity/visual_sheet.py` `advance_visual_sheet_pack` (:2345–2521), `_enqueue_txt2img` (:2855–2927)
Defect: creator's Local/Cloud generator selection is honored only for hero candidates; coverage ×6 (and details ×6 / performance ×2 when enabled) are enqueued with default local `qwen2512` regardless of `generatorSources` — `_enqueue_txt2img` defaults `provider_kind="local"`, `model_family_preference="qwen2512"` and `advance_visual_sheet_pack` never reads the pack's generator sources.
Evidence: `visual_sheet.py:2345` enqueues coverage with no provider args; signature defaults at 2855–2860.
Expected: every enqueued phase honors enabled source pools (Cloud-only → no local jobs), or the local-only fallback is disclosed.
User impact: Cloud-only selection silently generates 6+ views on local qwen2512/Z-Image — hidden GPU load, cost surprises, hard failures when local runtime is down.
Root cause: routing was bolted onto the hero stage after the pack pipeline was written.
Repair boundary: 2–3 files. Proof: Playwright — Cloud-only → assert coverage jobs carry hosted provider ids or an explicit local-only disclosure.

**CDX-002** — P2 · CONFIRMED · Character Creator Express · Approval/canon (wrong entity content)
Files: `visual_gates.py` `propose_visual_directions` (:55–56), `default_korri_directions` (:208–267); `api.ts` `ownerApproveCharacterVisualSheet` (default `wild_sun_sprite`); `CharacterCore.tsx` `handleApprove` (:152–153)
Defect: every character — not just Korri — receives Korri-specific concept directions ("LOCKED: black twin ponytails, purple eyes, pointed Sun Sprite Elf ears…"), and the Express approve auto-approves the concept gate without showing any concept UI.
Evidence: `visual_gates.py:55-56` falls back to `default_korri_directions()`; `CharacterCore.tsx:153` owner-approves with the default direction id.
Expected: concept directions derived from the actual profile; concept gate explicitly selected by owner.
User impact: gate state records a Korri canon description as the approved concept for any character; downstream gate consumers read wrong-character content.
Root cause: Korri seed-flow default never generalized; Express approve shortcut reused.
Repair boundary: 2–3 files. Proof: API test — non-Korri character start → gate_concept.directions are not the korri lock string.

**CDX-003** — P2 · CONFIRMED · Character Creator Express · Approval/canon (stale candidate ownership)
Files: `visual_sheet.py` `advance_visual_sheet_pack` (:2238–2241), `owner_approve_visual_sheet_gates` (:2578–2619); `service.py` `approve_character_candidate` (:618–671); `CharacterCore.tsx` `handleApprove`
Defect: with batchCount>1 the pack auto-attaches the FIRST completed candidate as `roleAssets["hero_identity"]`; approving a different candidate demotes that row and creates a new canonical row, but `pack.roleAssets` is never updated, so owner-approve stamps the gate with the first candidate's asset id.
Evidence: `visual_sheet.py:2238-2240` first-completed wins; `service.py:629-634` demotes others; owner-approve reads `pack.roleAssets` (:2579).
Expected: gate asset ids reflect the exact asset the owner approved.
User impact: gate/dashboard state claims candidate #1's sheet is the approved hero while canonical reference is candidate #3; downstream gate readers get wrong pixels.
Root cause: pack roleAssets and canonical reference rows are never reconciled after approval.
Repair boundary: 2–3 files. Proof: API test — 3 candidates → approve index 2 → owner-approve → gate assetId == approved candidate's assetId.

**CDX-004** — P3 · CONFIRMED · Character Creator Express · Approval/canon (approved-vs-created confusion)
Files: `useCharacterProfile.ts` `getHeroIdentity` (:10–29); `CharacterCore.tsx` (:50–53, 251–256); `CharacterCandidateGrid.tsx` (:54, 142); `schemas.py` `ReferenceAttach.approval_status="draft"` (:314)
Defect: a generated sheet auto-attaches as `hero_identity` with `canonical=False, approval_status="draft"`; `getHeroIdentity`'s final fallback (any hero row) makes that unapproved asset the UI "hero", so the candidate card shows "Selected" before any approval.
Expected: "Selected" means canonical+approved; otherwise a "pending review" state.
User impact: creator may believe the look is saved when it is only an auto-attached draft.
Repair boundary: one file. Proof: unit test on `getHeroIdentity` with draft-only row → undefined; E2E asserts "Use This Look" before approval.

**CDX-005** — P2 · CONFIRMED · Character Creator Express · Capability (orphaned contracts layer)
Files: `app/character_consistency/*` (`generation_recipe.py`, `multi_view.py`, `reference_roles.py`, `seed_policy.py`, `correction_loop.py`, `deviation_report.py`)
Defect: the `character_consistency` package defines its own competing reference-role taxonomy (`identity/face/hair/…` vs live `roles.py` `hero_identity/full_body_front/…`) and is consumed by no production path — only its own tests and a knowledgebase markdown pick.
Evidence: grep — only `knowledgebase_api.py:102` (markdown) + own `__init__` import it; `visual_sheet.py` implements its own routing with `roles.py`.
Expected: one authoritative reference-role system.
User impact: none today; invites divergence — an engineer reading `reference_roles.py` builds against a role set the runtime never sees.
Root cause: contract-first work never integrated.
Repair boundary: architectural decision required. Proof: after integration/removal, grep proves zero orphaned imports.

**CDX-006** — P3 · CONFIRMED · Character Creator Express · Downstream handoff (promotion)
Files: `CharacterCore.tsx` (no promote call); `CharacterProfileWorkspace.tsx:490-494` (only caller); `character_identity/api.py:861-870` `/promote`
Defect: Express approve marks the pack OWNER_APPROVED but never invokes promotion; `promote_canonical` (VisualIdentity + Bible + Prompt Package) is reachable only from the Standard workspace's explicit Promote button.
Expected: Express either promotes on owner-approve or clearly signals the missing step.
User impact: creator approves in Express and believes the character is production-synced; continuity/VisualIdentity/Bible never reflect it.
Repair boundary: 2–3 files. Proof: E2E — approve in Express → query continuity VisualIdentity → present or visible "promote required" affordance.

**CDX-007** — P3 · CONFIRMED · Character Creator Express · Canonical store (validation gap)
Files: `service.py` `approve_character_candidate` (:597–671), `attach_reference` (:500–542)
Defect: neither validates that `asset_id` exists, belongs to the project, or is an image; a crafted request can make a foreign/nonexistent asset the canonical `hero_identity`.
Expected: canonical identity references point at real project image assets.
User impact: canonical store can carry a broken hero id that `resolve_approved_reference`/continuity propagate.
Repair boundary: one file. Proof: API test — approve-candidate with absent assetId → 4xx, no canonical row.

**CDX-008** — P3 · CONFIRMED · Character Creator Express · Pack state consistency
Files: `characterSheetGenerate.ts:66-67` (hardcoded `includeDetails:false, includePerformance:false`); `visual_sheet.py` `owner_approve_visual_sheet_gates` (:2606–2619), `GATE_ROLE_GROUPS` (:291–304)
Defect: pack reaches `OWNER_APPROVED` while detail/performance gates remain NOT_STARTED (owner-approve skips gates without assets; the frontend never generates them).
Expected: pack status consistent with gate states.
User impact: Standard gates panel shows OWNER_APPROVED pack with NOT_STARTED gates; `promote_to_canonical` refuses (missing-gate guard) — confusing, not destructive.
Repair boundary: 2–3 files. Proof: API test — Express-style start → advance → owner-approve → status not OWNER_APPROVED while gates NOT_STARTED.

**CDX-009** — P3 · CONFIRMED · Character Creator Express · Plan honesty
Files: `characterGeneratorPlan.ts` `summarizeGenerationPlan` (:166–178); `characterSheetGenerate.ts` `characterGenerateBlockReason` (:33–39)
Defect: plan counts Auto Select sheets without consulting local inventory; with empty local inventory and cloud off the plan still claims "1 Character Sheet · Auto Select" and Generate is enabled — job fails at runtime with an engine/checkpoint error.
Expected: plan reflects executable sources (matches backend Certified-executability gating).
Repair boundary: one file. Proof: unit test — empty localOptions + autoSelect → block reason returns a message.

**CDX-010** — P3 · CONFIRMED · Character Creator Express · Stale legacy path
Files: `CoDirector/CharacterCreatorEmbedded.tsx` (800+ lines) + css
Defect: second, older character surface writing legacy `personality.cd_*` fields — never imported/mounted anywhere; coexists with live `CharacterCompactView`→`CharacterCore`.
Repair boundary: one file (delete/archive). Proof: grep proves no references; E2E characters tab still passes.

### Prop Creator Express (Phase 6)

**CDX-011** — P2 · CONFIRMED · Prop Creator Express · Creator action → canonical store (dead-end write)
Files: `ImageGenPanel.tsx:591` `promote("profile", {profile_kind:"prop"})`; `routers/extra.py:1291-1305`
Defect: Image Generation's "Prop" promote writes `ProfileItem(kind="prop")` into the legacy `profiles` table. No consumer (Prop Creator, Spatial Map, Scene Creator, ERS) reads it — a ghost record.
Expected: "Save as Prop" creates a canonical `PropEntity` (appears in Prop Creator/Spatial Map/Scene Creator) or the button is removed with an honest message.
User impact: creator "saves" a prop image, finds nothing in Prop Creator, no identity binding.
Repair boundary: cross-layer. Proof: Playwright — generate → click Prop → PropEntity appears and is placeable, or button gone.

**CDX-012** — P2 · CONFIRMED · Prop Creator Express → Spatial Map → Scene Creator · Downstream handoff
Files: `SpatialMapPanel.tsx:200-253,636-676`; `SpatialMap/types.ts:202-210` `propPlacementIdentity`; `scene_creator/service.py:1465-1530` (`_placed_project_prop_ids`/`_union_spatial_map_project_props`); `spatial_map/service.py:447-489` `place_prop`
Defect: Spatial Map dropdown groups "Character Props" and "Library" create placements with `propId:null` (only label+assetId). Both Scene Creator consumers skip `propId=null` rows, so those placed props silently never reach shots/ERS (they appear only as name strings). A `prop_reference` upload (tag contains "prop") lands in the Library group and is equally dead-ended. No UI warning.
Expected: every placement binds to an approved PropEntity or is clearly labeled map-only (non-propagating).
User impact: prop placed from Library/character group renders on map, absent from Scene Creator shots with no explanation.
Root cause: nullable `propId` fallback in the schema vs downstream hard filters.
Repair boundary: frontend/backend; architectural decision on whether library placeholders should exist. Proof: Playwright — place Library-group prop → Scene Creator shows it absent + UI warned; place approved project prop → present in shots.

**CDX-013** — P2 · CONFIRMED · Spatial Map · Backend route/service → canonical store (placement write)
Files: `spatial_map/service.py` `place_character` (:405), `place_prop` (:447), `update_prop` (:511–534); `schemas.py:360` (`characterId: str = Field(min_length=1)`); tests `test_m411_spatial_map.py:66-88`
Defect: placement writes perform NO canonical entity validation — `place_character` accepts any non-empty id (no CharacterProfileRow lookup, no project membership); `place_prop` accepts arbitrary `propId`/category/assetId. The project's own tests place synthetic "char-0"/"prop-0" ids. Same class: `attach_prop` validates only slot/relationship shape, never that the holder character is actually placed (attachment.py:149-192, service.py:648-668).
Expected: placements reference canonical project-owned entities or are rejected with typed errors.
User impact: deleted/renamed characters leave dangling placements; ERS/Scene Creator degrade to bare names (off-identity generation with no warning); empty-slot attachments flow into prompts as "held by character N".
Root cause: document treated as a self-contained JSON blob; referential integrity never wired server-side.
Repair boundary: 2–3 files (service.py + schemas.py + errors.py). Proof: pytest — place UUID not in project → typed 4xx; attach to empty slot → 4xx.

**CDX-014** — P3 · CONFIRMED · Prop Creator Express → Scene Creator · Canonical store (snapshot staleness)
Files: `scene_creator/service.py:1465-1493` `_placed_project_prop_ids`; `ers_resolver.py:66-96` `_find_existing_package`
Defect: `_placed_project_prop_ids` prefers the persisted ERS package placement snapshot; once a package has ≥1 placement the live Spatial Map is never consulted, so approved props placed after ERS generation are excluded from shot auto-union until ERS regeneration.
Expected: union reflects current approved placements (or snapshot staleness surfaced).
Repair boundary: one file. Proof: backend integration — package with 1 placement → add 2nd approved prop on map → both ids returned.

**CDX-015** — P3 · CONFIRMED · Scene Creator / production handoff · Placement → shot handoff (approval filter)
Files: `production_handoff.py:218-224,296-303` `_prop_ids_from_map` vs `service.py:1484-1492` approved filter
Defect: `synchronize_production_handoff` unions ALL map propIds onto shots without the approved-entity filter `_placed_project_prop_ids` applies — drafts/deleted entities can be written into `shot.prop_entity_ids`.
Expected: every placement→shot layer applies the same approved-only rule.
Repair boundary: one file. Proof: backend test — handoff with draft propId → shot.prop_entity_ids excludes it.

**CDX-016** — P3 · CONFIRMED · Prop Creator Express · API contract
Files: `api.ts:4536-4553` upsert body; `prop_creator/router.py:35-44` `UpsertBody`; `usePropCreator.ts:150-161`
Defect: frontend sends `approved_asset_id`/`library_asset_id` which `UpsertBody` doesn't define (silently ignored); identity is applied via `use_as_identity`+`identity_asset_id` which the frontend then redundantly re-calls via `/use-as-identity`.
Expected: typed API surface matches backend; single identity path.
Repair boundary: 2–3 files. Proof: contract test — upsert with approved_asset_id applies it; remove redundant call.

**CDX-017** — P3 · CONFIRMED · Prop Creator Express → Library · Approval visibility
Files: `prop_creator/service.py:484-501` `_set_asset_approval`; `TimelineReferencesPanel.tsx:72` (only consumer)
Defect: approval writes `production_approval="approved"` + `approved_prop` label, but no Library UI surfaces it — approved props indistinguishable from any other image.
Repair boundary: frontend only. Proof: Playwright — approve prop look → Library shows approved badge.

**CDX-018** — P3 · CONFIRMED · Spatial Map (legacy UI) · Stale legacy path
Files: `EntityPicker.tsx:250-354` `PropPickerBody` (kind="prop" dead variant — both call sites use kind="environment")
Repair boundary: one file. Proof: static contract test — kind="prop" not wired to production call sites.

**CDX-019** — P3 · CONFIRMED · Spatial Map backend · Placement write (attachment referential integrity)
Files: `attachment.py:149-192` `validate_prop_attachment`; `service.py:648-668` `attach_prop`; `capture_intelligence.py:56-94`
Defect: `attach_prop` validates format only (slot 1–4, relationship enum), never that the holder character/slot is placed on the document.
Repair boundary: 2–3 files. Proof: pytest — attach to slot 4 with 2 characters placed → 4xx `ATTACHMENT_INVALID`.

### Spatial Map Express (Phase 7)

**CDX-020** — P2 · CONFIRMED · Spatial Map Express · Document ownership → Scene Creator handoff
Files: `SpatialMapPanel.tsx` createMap calls (:323–327, 476–481, 1114–1119 — no sceneId); `spatialMapApi.ts:49-58` `getMostRecentMap`; `scene_creator/production_handoff.py:271-278`; `scene_creator/service.py:168-181` `ensure_scene_id`
Defect: Express maps are never assigned to a scene; the panel auto-loads only the most-recent map with no map selector; on "Use in Scene Creator", `ensure_scene_id(db, project_id, "")` resolves to the first project scene or implicitly creates "Scene 1".
Expected: explicit creator-controlled map→scene binding before Scene Creator writes shots.
User impact: multi-scene projects silently bind shots to the first scene (wrong-scene risk); older maps/variants unreachable from UI.
Repair boundary: frontend/backend. Proof: Playwright — two scenes, create map, use in Scene Creator → shot scene_id matches creator's choice.

**CDX-021** — P2 · CONFIRMED · Spatial Map Express · Reset/atlas replacement → persistence/UI
Files: `SpatialMapPanel.tsx:451-463` `handleRemoveAtlas`; `:315-330` atlas completion `createMap`
Defect: Remove Atlas clears only `backgroundAssetId` (placements kept); "Create Atlas Shot with Co-Director" then calls `createMap` → a brand-new document; the old document (with all placements) remains in DB but is unreachable (no picker) — placements effectively lost with no warning.
Expected: regenerate in empty state reuses the existing document, or warns before orphaning.
Repair boundary: one file (+ optional map picker). Proof: Playwright — place char, Remove Atlas, Generate New → placement still visible or confirm dialog.

**CDX-022** — P2 · CONFIRMED · Spatial Map Express · Frontend state / reload (ERS state latch)
Files: `useErsGeneration.ts:555-583` (sheet-refresh effect); `SpatialMapPanel.tsx:315-330,451-463`
Defect: the ERS hook never resets `compositeAssetId`/sheetId/phase on map-document change; the refresh effect early-returns when `compositeAssetId` is set. Repro: generate ERS → Remove Atlas → Create Atlas Shot → panel shows the PREVIOUS map's ERS composite as current (or stale banner only when lineage differs).
Expected: ERS state scoped to the active map document.
Repair boundary: one file. Proof: browser test — generate ERS on map A, Remove Atlas, Generate New → monitor resets, no ERS until a new sheet exists.

**CDX-023** — P3 · CONFIRMED · Spatial Map backend · API error contract
Files: `limits.py:7` (`CAMERA_LIMIT = 4`); `errors.py:62` ("can only hold eight cameras"); `components/spatial-map/SpatialMapStudio.tsx:73` ("eight cameras")
Defect: camera limit enforced at 4; typed 409 recovery copy and dead Standard UI say eight.
Repair boundary: one file. Proof: pytest — 409 payload text matches CAMERA_LIMIT.

**CDX-024** — P3 · CONFIRMED · Spatial Map backend · Persistence (destructive fallback)
Files: `service.py:96-120` `_parse_document`
Defect: if stored `document_json` fails Pydantic validation, `_parse_document` silently substitutes a blank document and the next write overwrites `document_json` — permanent placement loss, no quarantine/error.
Repair boundary: one file. Proof: pytest — corrupted document_json → typed error/quarantine; raw row not overwritten.

**CDX-025** — P3 · CONFIRMED · Spatial Map Express + capture intelligence · Placement state → provider prompt
Files: `SpatialMapPanel.tsx:606-618` (create body omits x/y/z); `schemas.py:93` (`x: float = 0.0`); `capture_intelligence.py:34-44` `_finite_world_xz`
Defect: unplaced characters default to (0,0) (never null) and are reported as standing at world origin in 360 capture plans ("Character X visible ahead", "midground center"). Props use null coords — characters are the asymmetry.
Repair boundary: 2–3 files. Proof: pytest — unplaced character must not produce a position label in the capture plan.

**CDX-026** — P3 · CONFIRMED · Spatial Map Express · Placement asset identity
Files: `SpatialMapPanel.tsx:597-605` `handleAddCharacter`
Defect: character placement falls back to a draft/unapproved canonical reference when no approved one exists (`items.find(approved) || items.find(canonical)`), while the prop path is approved-only.
Repair boundary: one file. Proof: browser test — character with only draft refs cannot be placed with an asset (or UI warns).

**CDX-027** — P3 · CONFIRMED · Standard workspace (legacy) · Stale legacy path
Files: `components/spatial-map/SpatialMapStudio.tsx`, `SpatialCanvas.tsx`, `Collage360Panel.tsx`, `CameraInspector.tsx`
Defect: entire Standard spatial-map workspace is dead code (no importers). If ever mounted it writes dishonest placement data: fake character ids (sceneId-derived strings), props with no propId, auto-creates a map on open, "eight cameras" copy.
Repair boundary: frontend (delete or quarantine). Proof: grep asserts no imports; deletion.

### Atlas Shot (Phase 8)

**CDX-028** — P2 · CONFIRMED · Co-Director Vision (environment visual canon) · CD vision → ERS prompt consumption
Files: `codirector/vision/router.py:114` `analyze_environment_canon`; `visual_canon.py` `canon_is_stale`; `ers_generate.py:938-943`; `ers_compiler.py:317-337`; `spatial_map/scene_intent.py:128`
Defect: the endpoint calls `build_scene_intent(db, project_id, document)` with a wrong signature (`build_scene_intent(description, …)`), the exception is swallowed, `intent` is always None → the stored `groundingFingerprint` never matches the ERS handler's fingerprint → `canon_is_stale` always True → canon dropped → AI-inferred environment invariants never reach the ERS prompt. Endpoint has zero callers in the product flow.
Evidence: `vision/router.py:114` vs `scene_intent.py:128`; `ers_generate.py:940-941`.
Expected: ERS consumes the persisted visual canon when lineage unchanged.
User impact: entire Co-Director Vision environment-canon feature silently inert; wasted re-analysis; ERS prompts lack hard invariants.
Repair boundary: one file. Proof: unit test — router-stored canon fingerprint == ERS `_resolve_ers_grounding` fingerprint; `canon_is_stale` False after fresh analyze.

**CDX-029** — P1 · NEEDS VERIFICATION · Spatial Map — Atlas adoption · Frontend state → map creation
Files: `SpatialMapPanel.tsx:291-346` (terminal-execution effect); `startAtlasGeneration` (:349–369)
Defect: the terminal-execution effect adopts `result_asset_ids[0]` as the Atlas whenever `busyOp==="atlas"` — it never checks `activeExecution.capability === "atlas.generate"`. `activeExecution` is session-shared; if any other execution (e.g. chat `image.generate`) completes while the atlas is in flight, its first result asset becomes the map background → wrong environment authority for ERS/Scene Creator.
Evidence: `:294-298` — no capability check anywhere in the effect.
Expected: only `atlas.generate` executions may populate the map background.
User impact: wrong asset becomes the Spatial Map background → ERS pixel authority → downstream scenes inherit the wrong environment.
Repair boundary: one file. Proof: browser test — start atlas, complete a different execution, assert map background unchanged. (Interleaving not reproduced — NV.)

**CDX-030** — P2 · CONFIRMED · CD routing → Atlas generation · Scene Intent authority
Files: `codirector/service.py:1375` `_build_execution_context`; `atlas_generate.py:66-77`; `scene_intent.py:151-157`
Defect: chat path sets `prompt` to the entire user message; atlas handler takes `description = (scene_description or "") or user_prompt`, so "create an atlas shot of…" becomes the canonical `SceneIntent.summary`/sourcePromptSummary, baked into atlas prompt, ERS prompt and the semantic-gate text.
Repair boundary: one file. Proof: unit test — atlas sceneIntent.summary equals the description without the routing prefix.

**CDX-031** — P3 · CONFIRMED · Atlas Shot · Provider/runtime request body
Files: `atlas_generate.py:101-106`; `image_product/compile.py:449-452`
Defect: handler hardcodes 1280×1280; `aspectRatio` is informational — wide requests silently produce square images.
Repair boundary: one file. Proof: unit test — body dimensions derive from requested aspect.

**CDX-032** — P3 · CONFIRMED · Atlas Shot → Library · Asset lineage
Files: `queue_worker.py:3432-3434` `_imagegen_commit_asset`; `atlas_generate.py:121-122`
Defect: CD atlas from creator reference images carries no `source_asset_id` → no `parent_asset_id`/derived_from edge; lineage exists only as JSON in prompt_meta.
Repair boundary: one file. Proof: unit test — derived_from edge from atlas asset to each source id.

### ERS (Phase 9)

**CDX-033** — P2 · CONFIRMED · ERS (chat tool path) · Duplicate pipeline exposure
Files: `codirector/tools/registry.py:1101-1115`; `tools/exposure.py:59,179`; `tools/handlers/environment_reference_sheet.py`; `service.py:2544-2547`
Defect: the legacy 4-direction ERS tool pipeline (`ers.create_sheet/attach_spatial_map/generate_directional_views/approve_direction/compose_sheet/export_sheet`) remains exposed in the chat tool catalog and writes the same sheet store with different artifact semantics (4 approved views + render_png composite vs one AI composite).
Expected: one ERS pipeline per product; chat "generate the ERS" produces the same artifact shape as the Express button.
Repair boundary: frontend/backend. Proof: chat-generated vs Express-generated packages share the same composite semantics.

**CDX-034** — P1 · CONFIRMED · Scene Creator (legacy batch API) · ERS grounding (downstream handoff)
Files: `scene_creator/router.py:198-244` `api_create_batch`, `:261-315` `api_regenerate_shot`; `capabilities/handlers/scene_generate.py:101-113`; `entity_resolver.py:635-639`; `ers_persistence.py:165-173` `load_ers_package`; E2E `tests/e2e/codirector/spatial-scene-creator.spec.ts:887,968`
Defect: `POST /batches` and regenerate-shot resolve ERS only as package UUID (`load_ers_package`); passing the creator-facing `sheetId` (the only external identity per the frozen contract) returns None with no error → every batch shot compiles with `ers_package=None`: no directional refs, no composite, no placements, no style context. The certified E2E suite passes `ers_package_id: sheetId` and only asserts job counts — blessing the broken contract.
Expected: every ERS-accepting endpoint resolves through `resolve_ers_for_sheet` or rejects loudly; no silent zero grounding.
User impact: batch flows produce scene shots with no environment conditioning at all, no error shown.
Root cause: two parallel resolution paths never unified; legacy surface never migrated or removed.
Repair boundary: 2–3 files. Proof: Playwright/API — batch with sheetId → captured job params contain resolved ersPackageId; regenerate compiles with grounding.

**CDX-035** — P2 · CONFIRMED · ERS generation (GPT Image 2 path) · Provider/request honesty
Files: `ers_generate.py:196-217` `_force_ers_honest_t2i`, call at :990; `:1030-1044` GPT pixel carve-out; dead `_choose_operation` (:186–193)
Defect: for GPT Image 2 the handler appends "…not pixel image-to-image" to the prompt, then attaches `input_urls` with `referenceGrounding.mode="pixel"` — the model is told pixels are not used while pixels are delivered. (Concurrent workstream — re-verify after Qwen/ERS Phase 2.)
Expected: prompt text matches the actual execution mode.
User impact: GPT ERS sheets may ignore Atlas/source pixels; executed prompt record is dishonest.
Repair boundary: one file. Proof: unit test — GPT body has no "not pixel image-to-image" text when input_urls present.

**CDX-036** — P2 · CONFIRMED · ERS (Express single-image flow) · Canonical state + directional assets
Files: `ers_generate.py:962` (`direction="sheet"`), `:1064` (`directional_assets={d: None}`); `environment_reference_sheet/api.py:28-31`; `exports.py:57-125` `render_png`; `ErsSelector.tsx:48` ("Directions: {n}/4"); `ers_contracts.py:64-65` ("NOT image-generated" claim)
Defect: Express ERS generates ONE whole-sheet AI image; `directional_assets` stay all-None and `directionalViews` stay planned — "Directions: 0/4" is permanently misleading, per-orientation conditioning never fires (falls back to whole-sheet composite), `render_png` (Amendment #2 programmatic composite) is never called on the Express path and would render four "No approved image yet" panels; the frozen contract comment claims the composite is "programmatically assembled … NOT image-generated" while the implementation is AI-generated.
Expected: one consistent model — real per-direction assets or dropped per-direction claims with the composite as sole representation; contract/UI copy truthful.
Repair boundary: architectural decision required. Proof: Playwright — generate ERS in Express → directional_assets populated or UI/downstream no longer claim per-direction assets.

**CDX-037** — P2 · CONFIRMED · ERS → Scene Creator handoff · Wrong-sheet risk
Files: `SpatialMapPanel.tsx:174-186` `handleUseInSceneCreator`; `AgentWorkSurface.tsx:216-231`; `persistThenOpenSceneCreator.ts:38-48`; `production_handoff.py:182-206,271-281` `_pick_sheet`
Defect: both "Use in Scene Creator" entry points omit `sheetId` (even though the hook holds it); `_pick_sheet` never filters by `spatial_map_id` — it matches sceneId then `with_composite[0] or sheets[0]`. Multi-map projects can hand the creator the WRONG environment's sheet.
Repair boundary: 2–3 files. Proof: Playwright/API — two maps/sheets; handoff from map A yields sheet A's composite.

**CDX-038** — P2 · CONFIRMED · ERS persistence · Duplicate commit hooks + dead symbols
Files: `ers_generate.py:301-382` (lenient hook — no asset validation, `has_reference: bool(asset_id)` even for fabricated ids); `spatial_map/ers_persistence.py:340-420` (strict hook — validates Asset + project, raises; production-dead); `queue_worker.py:3556-3564`; dead: `_choose_operation`, `ErsResultDisplay.tsx`, `ErsSelector.tsx`
Defect: production calls the lenient hook; strict implementation is dead; duplicated logic already drifted. False `has_reference` possible.
Repair boundary: 2–3 files. Proof: unit test — production hook with non-existent asset id → raises/records false; grep dead-code check.

**CDX-039** — P2 · CONFIRMED · ERS (Qwen/ERS Phase 2, mid-flight) · Eligibility truth + dispatcher pin loss
Files: `config/image-workflows/certified-registry.json:859-961` (`qwen2512.ref` "Certified" while limitations require "Phase 2R live runtime proof"); `ers_generate.py:775-790`; `test_qwen_i2i_ers.py:88-98`; `model_registry.py:234-246` (static `supports=["…reference_conditioning"]`); `ersGenerator.ts:87-93`; `dispatcher.py:219-256` (kwargs whitelist drops `forceWorkflowKey`/camel `hostedModelId`/provider — frontend's `forceWorkflowKey:"qwen2512.ref"` never reaches handle)
Defect: (a) registry claims Certified before the live runtime proof exists; (b) frontend I2I eligibility (provider metadata.supports) and backend gate (certified-registry status) are two sources of truth that can disagree; (c) the client's explicit workflow pin is silently discarded at the dispatcher boundary (benign today because the handler self-pins).
Repair boundary: architectural decision required. Proof: live Qwen ERS run through qwen2512.ref with the source Atlas image + test that startExecution context forceWorkflowKey reaches the handler.

**CDX-040** — P3 · CONFIRMED · Scene Creator (downstream ERS consumption) · Provider truth
Files: `scene_creator/reference_packet.py:31-38,252-263` (`family_pixel_slots("qwen2512")==0`); `useSceneCreator.ts:758-765` (final-render guard checks character/prop ticks only)
Defect: scene shots on the default local qwen2512 never send ERS composite pixels (environment consumption = semantic_only, referenceIds emptied) with no UI disclosure — the final-render guard only blocks on character/prop pictures.
Repair boundary: 2–3 files. Proof: E2E — qwen2512 + ERS composite → final render blocked with advisory, or captured job provably has no referenceImage while UI states it.

**CDX-041** — P3 · CONFIRMED · ERS frontend contracts · Type honesty
Files: `contracts/environmentReferenceSheet.ts:110-133` (omits ers_composite_asset_id/provenance); `useErsGeneration.ts:241-258,263-290` (`asRecord` any-casts)
Repair boundary: one file. Proof: tsc strict + unit test parsing a full backend model_dump through the typed contract.

**CDX-042** — P3 · CONFIRMED · ERS canonical store · Selection ordering
Files: `environment_reference_sheet/store.py:69-79` `list_sheets` (filename order, not updatedAt); `production_handoff.py:206` `sheets[0]`
Repair boundary: one file. Proof: unit test — two sheets out of UUID order → newest-first by updatedAt.

### Scene Creator Express (Phase 10)

**CDX-043** — P1 · CONFIRMED · Scene Creator (legacy batch flow) · Timeline handoff / approval
Files: `scene_creator/router.py:325-395` `api_send_to_timeline`; `timeline_handoff.py:35-102` `send_scene_batch_to_timeline`, `build_scene_shot_clips` (:168–214)
Defect: `POST /batches/{bid}/send-to-timeline` pushes every non-failed result asset to the Timeline with NO approval gate and no approval concept — unlike the shot flow's `NO_APPROVED_TAKE` contract. The batch surface is still used by the E2E suite (not purely latent).
Evidence: router.py:342-357 builds clips from `batch.result_asset_ids` skipping only failed_*; timeline_handoff.py:183-214 filters only on asset_id presence.
Expected: only creator-approved takes enter the Timeline.
User impact: script/agent/future-UI invocations can place unapproved images on the Timeline (wrong downstream assets).
Repair boundary: 2–3 files (gate or delete batch routes). Proof: pytest — batch with completed-but-unapproved assets → NO_APPROVED_TAKE / 400.

**CDX-044** — P1 · NEEDS VERIFICATION · Scene Creator / MAGI-W46 handoff · Timeline handoff (downstream)
Files: `magi/timeline_handoff.py:123-136` `export_to_timeline` (CLIP_NOT_FOUND guard); `scene_creator/timeline_handoff.py:131-149` (invents scene-shot clipIds); `magi/sequence/store.py:91-97` `has_saved_sequence`
Defect: `export_to_timeline` refuses with CLIP_NOT_FOUND when a saved MAGI sequence's clips list lacks every referenced clipId; Scene Creator never registers its invented clip ids in the NLE sequence. On projects where the sequence document exists with clips, Send-to-Timeline fails.
Expected: certified handoff accepts Scene Creator exports regardless of NLE editor state, or clip ids are registered.
Repair boundary: cross-layer. Proof: pytest seeding a saved sequence with clips → send_approved_shot_to_timeline ok; Playwright on a project with an existing NLE sequence. (Runtime frequency of the trigger not observed — NV.)

**CDX-045** — P2 · CONFIRMED · Scene Creator → Library · Scene Shots collection
Files: `codirector/execution/scene_shot_collection_builder.py` (`create_scene_shots_collection` :27, `add_scene_shots_to_collection` :79); `scene_creator/router.py:198-244`; `SceneCreator/types.ts:35` `collection_id?`
Defect: Amendment #49 Scene Shots collection is implemented with ZERO callers repo-wide; `SceneGenerationBatch.collection_id` never populated — scene-shot assets never grouped in Library.
Repair boundary: 2–3 files. Proof: pytest — approved scene shot creates a scene_shots collection containing the asset.

**CDX-046** — P2 · CONFIRMED · Scene Creator (legacy batch UI/API surface) · Stale legacy path
Files: `SceneResultGrid.tsx`, `SceneResultCard.tsx`, `ShotRequestInput.tsx`, `ErsSelector.tsx` (no importers); `api.ts:4196-4260` batch client (zero production callers); `router.py:187-395` batch routes (live)
Defect: complete legacy batch-flow UI + API ships beside the shot flow — a second, approval-less generation model; `SceneResultCard.isRealAssetId` returns true for any non-empty id (would render job UUIDs as images).
Repair boundary: frontend/backend (delete or formally deprecate). Proof: grep no imports; route list without /batches.

**CDX-047** — P3 · CONFIRMED · Scene Creator frontend · API contract typing
Files: `sceneCreatorApi.ts:144-169` (facade omits `shot`); `useSceneCreator.ts:733,789` (`applyShot(res.shot)`); `api.ts:4473-4499`
Repair boundary: one file. Proof: tsc --noEmit passes.

**CDX-048** — P3 · CONFIRMED · Scene Creator · Candidate status sync
Files: `scene_creator/service.py:1237-1261` `_sync_candidate_jobs`, `:1264-1280` `_job_asset_id`; `useSceneCreator.ts:219-248` `startPoll`
Defect: candidate can remain `generating` forever when its Job is done but unparseable, or the Job row is missing (`continue` leaves status untouched) — stuck "Generating…" tile, perpetual polling.
Repair boundary: one file. Proof: pytest — done Job without parseable asset id → candidate failed; missing Job → failed.

**CDX-049** — P3 · CONFIRMED · Scene Creator workspace · REST semantics (side-effecting GET)
Files: `scene_creator/service.py:271-278,297-298,436-446` `hydrate_workspace`; `ers_resolver.py:25-63` (`persist_runtime=True` default)
Defect: GET /workspace persists the spatial-profile selection, creates `runtime-{sheetId}` ERS packages, and saves cinematographer packs — a read endpoint mutates canonical state.
Repair boundary: 2–3 files. Proof: pytest — workspace GET leaves trait/pack state unchanged on a fresh project.

**CDX-050** — P3 · CONFIRMED · Scene Creator Express/Standard · Dead prop
Files: `SceneCreatorCore.tsx:39-46` (destructures only projectId/onGoTab); `useSceneCreator.ts:34` `SceneCreatorVariant`
Repair boundary: one file. Proof: tsc clean after removal.
### Story / Script Writer / Wiki / Notes (Phase 11)

**CDX-051** — P1 · CONFIRMED · Co-Director Script Writer + Standard Scriptwriter Studio · Canonical store → frontend state → downstream analysis
Files: `scriptwriter/service.py` `autosave_html` (:120–127), `navigator_scenes` (:482–501), `analyze_scene` (:451–470), `prepare_timeline` (:374–433); `stats.py` `_stats_from_html` (:49); `ScriptwriterStudio.tsx:119-123`; `ScriptwriterInlineEditor.tsx:53-57`; `codirector/tools/handlers/wave3_reads.py:311-331`
Defect: the primary typing path persists ONLY sanitized HTML (`contentType="html"`); `elements[]` is never updated. Every element-based feature — navigator scene list, scene/stat counts, continuity, Bible detection, scene analysis, Timeline-prep, scene linking — reads stale/default `elements[]`, so for any script actually typed, these features show/use the default `INT. LOCATION - DAY` placeholder content.
Expected: canonical HTML content drives navigation/stats/analysis/continuity/Bible/Timeline-prep (or elements sync on every HTML save).
User impact: navigator/stats/analysis/Timeline-prep and Bible proposals are built from non-existent scene blocks for real typed scripts.
Root cause: two representations layered without a sync/derivation rule; only the CD tool handlers got an HTML-text fallback.
Repair boundary: frontend/backend (2–3 files). Proof: Playwright — type multi-scene script in inline editor → navigator lists those scenes, stats match, Timeline-prep contains typed dialogue; reload → same.

**CDX-052** — P1 · CONFIRMED · Script Writer / Shotlist / Storyboard / Co-Director · Duplicate canonical store
Files: `app/script_storyboard.py` (`script_segments` table); `scriptwriter/store.py:27-28` (`script_documents_v2`); `migration.py:69-145` (one-way snapshot); `storyboard_jobs.py:29-49`; `storyboard_studio/timeline_prep.py:13,81`; `wave3_reads.py:374-383` `script_search`; `ScriptStoryboardWorkspace.tsx:93,116,122,211`
Defect: two live script text stores. Legacy `script_segments` is still written by Shotlist and read by storyboard_jobs, storyboard timeline-prep, and the Co-Director `script_search` tool. `script_documents_v2` is written by Script Writer. Migration is a one-way snapshot only when no v2 doc exists — edits never cross stores.
Expected: one canonical script store; timeline/shotlist/CD reads reflect the script the creator edits in Script Writer.
User impact: creator edits the screenplay in Script Writer; Shotlist, storyboard prep, storyboard jobs, and Co-Director "search the script" see a different script — downstream assets derive from the wrong text.
Root cause: M4.7 introduced the v2 store without migrating legacy consumers.
Repair boundary: architectural decision required. Proof: Playwright — type in Script Writer → script_search + shotlist see the typed text.

**CDX-053** — P1 · CONFIRMED · Script Writer (API layer) · Backend route → project scoping
Files: `scriptwriter/api.py` (all `/documents/{document_id}/...` routes: 117–288); `scriptwriter/service.py:70-74` `get_document`
Defect: every document-level endpoint accepts `document_id` and never verifies it belongs to the path `project_id` — any caller knowing a document id can read or mutate another project's script (autosave, undo, revisions, timeline metadata, bible proposals). Verified: `get_doc` → `service.document_bundle(db, document_id)` with no ownership check; contrast `story_entries/api.py:52` and `bible/proposals.py:221-228` which do scope.
Expected: script documents are project-scoped; cross-project access → 404/PROJECT_SCOPE_VIOLATION.
User impact: hosted multi-project: crafted request overwrites/reads another project's screenplay.
Repair boundary: one file. Proof: API test — two projects; GET/autosave A's doc id under B's path → 404.

**CDX-054** — P2 · CONFIRMED · Script Writer & Story · Frontend state → API (GET with side effect)
Files: `scriptwriter/service.py:49-67` `get_or_create_document`; `story/api.py:15-26` + `story/store.py:54-75` `get_or_create_document`
Defect: `GET /projects/{id}/scriptwriter` and `GET /projects/{id}/story` CREATE canonical documents when none exist (scriptwriter also runs the legacy migration and saves the default placeholder script). Merely opening the tab writes rows.
Expected: reads side-effect free; creation on explicit creator action.
Repair boundary: 2–3 files. Proof: API test — GET on fresh project → no v2/story row until POST autosave.

**CDX-055** — P2 · CONFIRMED · Script Writer · Save/conflict recovery
Files: `scriptwriter/service.py:103-127,77-100`; `store.py:320-338` (`set/get/clear_recovery`); `ScriptwriterStudio.tsx:81,127-149`; `ScriptwriterInlineEditor.tsx:64-83`
Defect: on SCRIPT_CONFLICT the backend stores the client's unsaved edit in `recovery_json`, but both editors fetch the fresh document, overwrite the editor, and drop the in-progress edit. No UI path restores the stored recovery payload — the recovery mechanism is dead code.
Expected: "Restore my unsaved changes" affordance from `bundle.recovery`.
User impact: two-tab/multi-device edit silently loses up to a debounce batch of screenplay text.
Repair boundary: 2–3 files. Proof: Playwright — edit A → save; edit B → conflict → B offers restore and restores A's lost text.

**CDX-056** — P2 · CONFIRMED · Notes · API read → canonical store (side effect)
Files: `routers/codirector.py:1294-1298` `GET /notes`; `codirector/notes/service.py:88-100` `list_notes`; `conversation/snapshot.py:155-175` `save_snapshot`
Defect: GET /notes bridges knowledgeEntries→workingNotes and persists via `save_snapshot` (incrementing the snapshot revision) — a read path writes canonical state.
Repair boundary: one file. Proof: API test — two consecutive GET /notes → revision unchanged after first bridge.

**CDX-057** — P2 · NEEDS VERIFICATION · Wiki/Notes/conversation intelligence · Canonical store (single-blob concurrency)
Files: `conversation/snapshot.py:155-175` `save_snapshot`; `project_cache.py:86-97`; `wiki_intelligence/compiled/page_compiler.py:370-371,407-409`; `creative_operating/persistence.py`; `Project.settings_json`
Defect: knowledgeEntries, workingNotes, compiledWiki (whole compiled wiki), project intelligence cache, and creative-operating bundles all live in one `settings_json` blob rewritten whole (load→mutate→save). Concurrent writers can clobber unrelated fields; blob grows without bound.
Repair boundary: architectural decision required. Proof: concurrency test — N parallel saves/compiles → no field loss, monotonic revision; measure blob growth over 50 compiles. (Race not reproduced — NV.)

**CDX-058** — P2 · CONFIRMED · Standard Script Writer · Scene linkage
Files: `ScriptwriterStudio.tsx:338-348` `linkScene`
Defect: "Link to Scene" always links to `project.scenes[0]` regardless of the chosen script scene (`:340` `const sceneId = project.scenes[0]?.id`).
Repair boundary: one file. Proof: Playwright — 2+ scenes; link scene 2 → API asserts sceneId = scene 2.

**CDX-059** — P3 · CONFIRMED · Story · Dirty state honesty
Files: `StoryEntryEditor.tsx:33,117-156` (`lastPublished` in-memory snapshot)
Defect: "unpublished changes" derives from a local snapshot that resets on reload — after any reload a published story is reported as having unpublished changes.
Repair boundary: frontend/backend (persist published revision). Proof: Playwright — publish → reload → no banner until edit.

**CDX-060** — P3 · CONFIRMED · Story/Wiki · Duplicate text store (stale legacy path)
Files: `app/story/api.py`, `story/store.py` (`story_documents`); unmounted `StoryEditor.tsx`; `story_entries/store.py:142-175` `migrate_from_legacy`; `project_foundation/service.py:54-56`
Defect: legacy `story_documents` store remains fully wired server-side (GET/PUT /story) with one-time copy into story_entries; residual writers create content Wiki/Co-Director never sees.
Repair boundary: frontend/backend. Proof: API test — PUT /story on a project with entries → no divergence (or 410).

**CDX-061** — P3 · CONFIRMED · Wiki · Correction preview persistence
Files: `routers/codirector.py:1178,1240,1256-1270` `_CORRECTION_PREVIEWS` in-process dict
Defect: preview-apply dies on backend restart (404 preview_not_found).
Repair boundary: one file. Proof: API test — preview → restart worker → apply succeeds.

**CDX-062** — P3 · CONFIRMED · Co-Director Script Writer (compact view) · Dead code
Files: `ScriptwriterCompactView.tsx` (no importers; previews stale `doc.elements`)
Repair boundary: one file. Proof: unit test resolvePreview or delete.

### Library (Phase 12)

**CDX-063** — P1 · CONFIRMED · Studio Project Library · Persistence → downstream handoff (deletion safeguards)
Files: `routers/api.py:1125-1209` `delete_asset`/`bulk_delete_assets`; `scene_references/service.py:420-429` `asset_usage`; `prop_creator/service.py:215-263`; `character_identity/service.py:944-970`; `scene_creator/service.py:1080-1111`; `ers_generate.py:553-572`; `spatial_map/reference_bundle.py:54-70`
Defect: deletion is guarded only by `scene_references` bindings. Assets that are a character's/prop's `library_asset_id`/`approved_asset_id`, an ERS-registered asset (incl. the Spatial Map `backgroundAssetId` in document_json), or a scene visual reference are deleted with no guard/cascade; `AssetVersion`/`AssetEdge` rows never cleaned; `force=true` bulk skips even the binding check. ERS grounding still returns the stale atlas id → ERS submitted against a missing asset.
Expected: delete blocked (or cascade with disclosure) for any asset referenced by characters/props/ERS/scene visuals; approval state preserved or explicitly revoked.
User impact: deleting a take silently breaks character/prop identity images, ERS source pixels, and scene visuals; Force Delete leaves references pointing at missing files.
Root cause: `asset_usage` guards one reference store only; generic delete route never learned the entity-link pattern.
Repair boundary: cross-layer. Proof: Playwright — delete identity image → blocked with named entity; force-delete → entity link nulled or render blocked with clear error; versions cleaned.

**CDX-064** — P1 · CONFIRMED · Co-Director library retrieval · Search/retrieval → approved-vs-created preference
Files: `project_library/codirector.py:189-195` `_asset_sort_key`, `:226-232`; `project_library/schema.py:107-110,167-168`; `prop_creator/service.py:484-489`; `director_references/service.py:339-353`
Defect: `search_library_assets` ranks/reports approval from `AssetLibraryMeta.approval_state`/`is_canonical` — fields nothing ever writes (verified: only schema readers + templates_presets, a different store). Real approval lives on `Asset.production_approval`. Result: every asset sorts draft/non-canonical; "approved first" preference dead; Co-Director tools report `approvalState:"draft"` for approved assets; `meta.version` never incremented.
Expected: retrieval prefers approved/canonical and reports truthful approval state.
User impact: newest draft outranks the approved identity asset; the tool tells the model every asset is a draft → wrong-asset selection risk in generation flows.
Root cause: approval implemented on the Asset column while retrieval reads AssetLibraryMeta.
Repair boundary: frontend/backend. Proof: API test — approve prop candidate → search returns it first with approvalState "approved".

**CDX-065** — P2 · CONFIRMED · Project Library scope handling · Discoverability
Files: `routers/extra.py:966-995,1137-1144`; `project_library/codirector.py:213-214`; `LibraryMediaGrid.tsx:407,430`; `LibraryPanel.tsx:143,337-341`; `capabilities/registry.py:248-252`
Defect: global-scope assets are undiscoverable from other projects: default `scope="project"` filters to project rows, `search_library_assets` drops non-project rows, and the Express library surface never sends a scope — while the capability declares "Search project or global assets". `promote_asset_global` silently makes the asset invisible outside its home project.
Repair boundary: frontend/backend. Proof: API test — promote in A → B's library?scope=global returns it; CD search in B finds it.

**CDX-066** — P2 · CONFIRMED · Project Library entity folders · Canonical store identity
Files: `project_library/service.py:273-280` `_find_entity_folder`, `:193-261`; `codirector.py:364-389`; `schema.py:61`
Defect: entity folders matched by `entityId == eid or entityName == entity_name` — two same-named entities share one folder; rename without passing entity_id forks a second folder; no rename endpoint despite `isRenamable=True`.
Repair boundary: 2–3 files. Proof: API test — two "Korri" characters → two folders; rename propagates.

**CDX-067** — P2 · CONFIRMED · Library search backend · Retrieval
Files: `asset_graph.py:109-132` `search_assets` (limit 500 most-recent; substring match; 100 hits)
Defect: >500 assets → older assets invisible in Library grid and unsearchable ("assets generated but not discoverable").
Repair boundary: one file. Proof: API test with >500 assets — oldest asset still returned by ?q=tag.

**CDX-068** — P2 · CONFIRMED · Project Library persistence · Duplicate binaries
Files: `project_library/service.py:343-351` `find_duplicates_by_hash` (no callers); `routers/api.py:1057-1100` `upload_asset`
Defect: dedupe helper is dead; `upload_asset` copies bytes unconditionally, never content-hashes, never classifies — duplicate uploads create duplicate binaries and unclassified "Library item" rows.
Repair boundary: 2–3 files. Proof: API test — upload identical bytes twice → second flagged/deduped and classified.

**CDX-069** — P2 · CONFIRMED · Media delivery / project isolation · Persistence → runtime (file serving)
Files: `main.py:626-629` (/media StaticFiles), `:726-735` (/api/file?path=), `:645-667`; `project_security/middleware.py:42-72`; `project_security/permissions.py:42-49`; `api.ts:6656-6666` `mediaUrl`
Defect: project-password lock covers project-scoped API paths and /api/assets, but /media and /api/file?path= serve every file under data_dir with no lock check; `mediaUrl()` (scene renders, lipsync, thumbnails, job previews) emits those URLs — a locked project's media is fetchable without unlock.
Repair boundary: 2–3 files. Proof: E2E — lock project → /media/... and /api/file?path= → 403 without unlock token.

**CDX-070** — P2 · CONFIRMED · Co-Director library tool (`propose_asset_library_assignment`) · Approval/canon
Files: `codirector/tools/handlers/library.py:136-148` (default `override=True`); `tools/definitions.py:4436-4441` ("respects manual overrides"); `project_library/service.py:368-370`
Defect: apply defaults `override=True`, bypassing the manual-override guard the contract claims to respect; preview never discloses an existing override will be clobbered.
Repair boundary: one file. Proof: API test — manual override → apply without override → assignment unchanged.

**CDX-071** — P3 · CONFIRMED · Library media grid · UI → frontend state
Files: `LibraryMediaGrid.tsx:249-250` (prints raw entity UUIDs: "Linked Character: <uuid>")
Repair boundary: 2–3 files. Proof: Playwright — preview shows human-readable names.

**CDX-072** — P3 · CONFIRMED · ERS generation hook · Isolation (project/map switch)
Files: `useErsGeneration.ts:75,214,311,329` module-level `let lastErsGeneratorId`
Defect: module global persists generator choice across remounts AND projects; a new project's ERS seeds with the previous project's generator.
Repair boundary: one file. Proof: Playwright — set generator in A → new project B defaults (or B's stored choice).

**CDX-073** — P3 · CONFIRMED · Project Library tests · Verification
Files: `test_project_library_taxonomy.py:76-83`; `test_project_library_service.py:68-99`; `classify.py:59-75`
Defect: tests assert `subtype=="NOT_APPLICABLE"` + "USD" in reason, but classify.py returns `DEFERRED_VERSION_1_2` with no "USD" — assertions cannot pass; stale test/code mismatch.
Repair boundary: 2–3 files. Proof: run both pytest files — green.

**CDX-074** — P3 · CONFIRMED · Library surfaces + lineage stores · UI → canonical store
Files: `LibraryMediaGrid.tsx:407-408` (uses only payload.items, discards tree/folderMap); `project_library/service.py:581-597`; `LibraryPanel.tsx:143,183-199,337-341`; `asset_graph.py:29-51` vs `codirector/m29/store.py:57` (`m29_asset_versions`)
Defect: (a) Express grid discards the taxonomy tree/global scope the backend computes (Express/Standard divergence, no shared store); (b) two independent asset-version lineage stores with no reconciliation.
Repair boundary: architectural decision required. Proof: Playwright — Co-Director Library tab folder-tree/global behavior matches Standard.

### Provider and generation honesty (Phases 13 + 18)

**CDX-075** — P1 · CONFIRMED · All Express imagegen surfaces · Capability/readiness truth → generator selection
Files: `imagegen_workflows.py:71-73` `build_local_generator_models` (Certified ⇒ executable); `production_control/model_registry.py:233-272` (static `_CATALOG` claims Certified/Installed/executable); `image_studio/providers.py:150-162` `_map_local_readiness`; `scene_creator/generation.py:51-78,103-104`; `capabilities/registry.py:645-652` vs `studio-web/src/capabilities.ts:1-8`
Defect: local generators are reported "ready"/"executable" purely from registry certification / a hard-coded static catalog — never weights-on-disk verification (only krea2_models and the worker's runtime `_zimage_stack_ready` check gate anything). Dual readiness systems confirmed: /api/capabilities (gated on Setup components) declares itself "the single answer" but NO Co-Director selector consults it.
Expected: a model is available only when its weights verify on disk (Setup/Source Manager component verification).
User impact: Z-Image/Qwen/FLUX shown ready with weights absent → job dies at Comfy load with an opaque error (or silently swaps — CDX-076).
Root cause: three parallel readiness authorities never reconciled.
Repair boundary: cross-layer. Proof: Playwright — clean project without zimage_models → Z-Image not offered in Scene Creator/ERS; with weights → offered.

**CDX-076** — P1 · CONFIRMED · Image Runtime / QueueWorker · Provider/runtime execution
Files: `queue_worker.py:2734-2749` `_imagegen`; `_resolve_ready_still_model` (:2200–2229); `_zimage_stack_ready` (:2165–2172)
Defect: when the pinned model is Z-Image but `verify_component("zimage_models")` fails at execution time, the worker SILENTLY substitutes another model (flux/hidream/sd35/custom) and rewrites `intent.enginePreference`; the swap is recorded only in `job.history_json["reasons"]` which no Express surface renders. In the pinned path the swap is inert but dishonest — `job.message` advertises the alternate checkpoint while the graph still builds the zimage workflow; in legacy unpinned paths the alternate model genuinely executes.
Expected: never silently substitute (Laws #18/#6); fail pre-enqueue with an actionable message or disclose the swap before executing.
User impact: creator believes Z-Image runs; a FLUX checkpoint name appears in the job/provenance or a different model executes. No consent, no disclosure.
Repair boundary: frontend/backend (preflight readiness + disclosure channel). Proof: unit test — preflight returns MODEL_NOT_INSTALLED when zimage_models verification fails; Playwright shows "Z-Image not installed" before enqueue.

**CDX-077** — P2 · CONFIRMED · Scene Creator Express (Region Edit → Preview) · Selection state → API payload
Files: `RegionEditPanel.tsx:246-263` (`Use {recLabel}` → onSwitchFamily); `image_core/recommend.py:10-15` (`_RECOMMENDED_FAMILY["add"]="nano-banana-fal"`); `scene_creator/generation.py:103-134` `build_candidate_plans`
Defect: "Use Nano Banana 2" switches to `nano-banana-fal`, a family NOT in the local roster (`build_local_generator_models` emits only zimage/flux/qwen2512/illustrious/krea2). The local-family select has no matching option; next Preview/Final computes `preferred=[]` → falls back to ALL executable local families → silently generates with Z-Image/FLUX instead of the chosen Nano Banana.
Expected: a recommended/selectable generator must be routable; unrecognized family must not silently expand to "any ready family".
User impact: creator picks Nano Banana 2 for an Add; gets Z-Image/FLUX results with no indication; select shows "Auto Select".
Repair boundary: 2–3 files. Proof: unit test — `build_candidate_plans(local_family="nano-banana-fal")` honors or rejects; Playwright asserts select retains Nano Banana 2.

**CDX-078** — P2 · CONFIRMED · Image Core / Region Edit (Add) · Preflight → enqueue
Files: `image_core/preflight.py:86-120`; `image_core/generate.py:43-50`; `queue_worker.py:3257-3262` (credential raise)
Defect: Nano-Banana Add forces `providerPreference="cloud"` and enqueues a fal job with NO check that a fal API key exists; preflight validates only hosted_model_id presence; failure surfaces only at worker execution.
Repair boundary: one file. Proof: unit test — preflight with fal key unset → ok=False PROVIDER_AUTH_FAILED.

**CDX-079** — P2 · CONFIRMED · Scene Creator Express (Cloud previews/finals) · Frontend → preflight → payload
Files: `image_core/preflight.py:197-208`; `image_core/generate.py:66-86`; `scene_creator/service.py:787-797`; `useSceneCreator.ts:708-714`
Defect: when identity/reference images are present but the family has no Certified visual-edit path, preflight silently downgrades to `image.generate` (txt2img) and references never reach the graph. For `family="hosted"` this is unconditional — every cloud preview/final with characters/props/ERS references drops them.
Expected: reference conditioning reaches the graph or is refused/honestly disclosed.
User impact: cloud previews/finals of scenes with placed characters/props render without those characters, no warning.
Repair boundary: 2–3 files. Proof: unit test + Playwright with a placed character → cloud preview conditions or warns.

**CDX-080** — P2 · CONFIRMED · Scene Creator Express (Cloud Generators) · Readiness truth → UI offering
Files: `hosted_providers/discovery.py:604-623` (`_dock_api_models_all_keyed` modality-only filter), `:243-244` (`flux-kontext-fal` `adapterAvailable=False`); `scene_creator/service.py:427-434`; `SceneCreatorCore.tsx:687-701`
Defect: rows the catalog marks `adapterAvailable=False`/`executable=False` (e.g. flux-kontext-fal) are returned as api_models and rendered as selectable cloud generators — backend then fails or refuses.
Repair boundary: 2–3 files. Proof: unit test — adapter-unavailable rows excluded; Playwright asserts FLUX Kontext Pro absent.

**CDX-081** — P2 · CONFIRMED · Character/Prop Creator Express (GeneratorSourceSelector) · UI availability claim
Files: `components/generators/GeneratorSourceSelector.tsx:121-132,168-179`
Defect: selector defaults missing readiness to available: `executable: m.executable !== false`, `status: m.status || "Certified"`, API options always `executable: true` with `availability:"Connected"` when no balance exposed — the reverse of "not available solely because its UI entry exists".
Repair boundary: one file. Proof: unit test — row lacking executable → disabled option.

**CDX-082** — P3 · CONFIRMED · Image Runtime · Job status text
Files: `queue_worker.py:2148-2163` `_checkpoint_for_model` (no qwen2512 branch → flux checkpoint name); `:2810` `job.message`
Defect: Qwen Image 2512 runs display "ImageGen · qwen2512.txt2img · flux1-kontext-dev.safetensors" — the checkpoint name is FLUX while the graph uses the qwen unet.
Repair boundary: one file. Proof: unit test `_checkpoint_for_model("qwen2512")` returns the qwen unet name.

**CDX-083** — P3 · CONFIRMED · Image Runtime provider inventory · Readiness truth
Files: `image_runtime/provider_registry.py:63-73` `probe_provider_availability` (key-presence ⇒ available; "live API probe deferred to execution")
Repair boundary: one file. Proof: unit test with fake key env → available reflects the probe, not key presence.

### Co-Director orchestration (Phase 17)

**CDX-084** — P2 · CONFIRMED · Co-Director execution contract · Approval / execution
Files: `execution/dispatcher.py:358-467` `approve_and_execute`, `:470-531` `_dispatch_tool`; `tools/execution.py:438-462` `execute_audited`; `service.py:1689-1754` `_handle_pending_execution_confirmation`; `capabilities/registry.py` (NEEDS_CHOICE TOOL capabilities: story.refine, script.propose_edit, character.assign_reference, voice.assign, timeline.prepare)
Defect: TOOL-kind capabilities whose approval_policy is not DIRECT can never complete: dispatch returns PREVIEW; approve hard-rejects non-CAPABILITY_HANDLER ("APPROVE_FAILED: non-capability handler", :390-394); the chat confirmation re-dispatches pre_approved=True → `execute_audited` rejects `requires_approval` proposals ("requires an approved proposal"); `_dispatch_tool` also passes `ctx.get("tool_params", {})` which the deterministic context never populates.
Expected: confirmed NEEDS_CHOICE capabilities create a proposal (→ ProposalService.approve) or execute the propose-tool.
User impact: "edit the script"/"refine the story" → confirmation → hard error instead of a proposal (deterministic path only).
Repair boundary: 2–3 files. Proof: dispatch script.propose_edit deterministically → confirm via /approve and chat → Proposal row exists (or honest actionable error).

**CDX-085** — P2 · CONFIRMED · Scene generation · Capability routing / duplicate engines
Files: `capabilities/handlers/scene_generate.py`; `scene_creator/router.py` (batches); `api.ts:4186-4314`
Defect: two parallel scene-generation engines — Co-Director `scene.generate` execution pack vs the standalone /api/scene-creator batch subsystem — with different contracts, approval/handoff semantics, and planning code.
Repair boundary: architectural decision required. Proof: same shot via chat pack and via batch → identical resolution/provenance/handoff or documented separate products.

**CDX-086** — P2 · CONFIRMED · Specialist delegation · Hard-max-3 invariant
Files: `foundation/creative/routing.py:76-120` (`selected[:4]`); `foundation/pipeline.py:59-123`; `intelligence/specialist_selector.py:9` (`MAX_SPECIALISTS = 3`); `wiki_intelligence/assignment.py:17` (default `max_specialists=8`), `orchestrator.py:52` (calls with 6)
Defect: the live foundation specialist path can select and run up to FOUR specialists; the wiki_intelligence path assigns up to 6–8 (same SpecialistRegistry via `available_specialist_ids`) — both violate the frozen "HARD MAXIMUM THREE specialists" invariant the certification docs assert.
Expected: at most 3 specialists per turn, runtime-enforced, across ALL specialist paths.
User impact: higher latency/cost; more conflicting advice; certification claims inaccurate.
Repair boundary: 2–3 files. Proof: for every intent/profile combination assert len(select) ≤ 3; wiki assignment ≤ 3.

**CDX-087** — P2 · CONFIRMED · Specialist registry authority · Duplicate registries
Files: `foundation/creative/roster.py:5-18` (12 ids); `intelligence/specialist_registry.py:54-97` (40 ids); `conversation/orchestrate.py:582-587` (hard-coded candidates)
Defect: three distinct specialist selection authorities with different id vocabularies — violates "no second specialist registry/state authority".
Repair boundary: architectural decision required. Proof: single exported roster imported by all call sites.

**CDX-088** — P3 · CONFIRMED · Frontend legacy action/plan path · Direct action / duplicate planning
Files: `src/codirector/execute.ts` (`queueImageGeneration`→api.imageProduct.generate etc.; stubs at :199, :202-210, :374-376); `types.ts` (`RECIPE_STUBS`, `planFromIntention` — zero callers); `CoDirectorSession.tsx:2721-2774` `runSteps`, :1831 (`setPlan(null)`)
Defect: a complete legacy frontend direct-action engine remains wired and renderable (browser-side mutations bypassing capability/approval/provenance), dormant only because `plan` is always null in the live flow.
Repair boundary: frontend/backend. Proof: assert plan can never become non-null (grep setPlan callers) or Playwright that the legacy task UI never renders.

**CDX-089** — P2 · CONFIRMED · Production Executive · Second execution authority
Files: `codirector/executive/{api,service,worker,store}.py`; `main.py:265-281`; `config/beta-local.env:23` (flag ON); `CoDirectorProductionExecutive.tsx`
Defect: a second, parallel production-job authority (own queue/worker/approval/store/dashboard) is wired end-to-end and enabled in the beta runtime alongside execution packs.
Repair boundary: architectural decision required. Proof: document which engine owns each capability; no double-creation across both stores.

**CDX-090** — P3 · CONFIRMED · Foundation specialist path · Honesty
Files: `foundation/creative/runners.py:389-404` ("lightweight heuristic specialist"), `:310-386` (`status="validated"`, confidence 0.62–0.76); `intelligence/service.py:176-182` ("Consulting creative foundation")
Defect: deterministic keyword heuristics are surfaced as consultant specialist work (specialist id lists, "validated" findings) without labeling them heuristic.
Repair boundary: one file. Proof: foundation-path events say "heuristic review"; findings carry source="heuristic".

**CDX-091** — P3 · CONFIRMED · Intent routing · RouteDecision / capability routing
Files: `routing/orchestrator.py:103-176`; `deterministic.py:339,503-586`; `unified_intent.py:92-140,155-215`; `conversation/foundation/intent.py`
Defect: intent classification computed by up to four stacked mechanisms with two capability-resolution locations; the same utterance can classify differently per layer.
Repair boundary: architectural decision required. Proof: property test — deterministic/semantic/unified agree on EXECUTION vs non-EXECUTION.

**CDX-092** — P3 · CONFIRMED · Agent Work Surface state mapping · Frontend state/API
Files: `AgentWorkSurface.tsx:64-90` `buildPack` (:72 `focused_artifact_ids: res.result_asset_ids || []`); `types.ts:58`
Defect: `focused_artifact_ids` is an alias of the result list, never actually "focused" — dishonest vs its contract (backend ExecutionPlan has no such field).
Repair boundary: one file. Proof: buildPack with distinct result/focus payloads → not aliased.

### Test/evidence system (Phase 19)

**CDX-093** — P2 · CONFIRMED · All API test layers · Verification
Files: `studio-api/tests/conftest.py` (mocks `job_queue.start` → no-op, `api.job_queue.enqueue` → AsyncMock in the shared client fixture)
Defect: no API test can prove real job execution — every queue/provider/runtime boundary is mocked; live proof exists only via opt-in flags (ADEPT_M30A_LOCAL_LIVE, ADEPT_BETA_TARGET, ADEPT_REQUIRE_REAL_IMAGEGEN, live-pinned specs).
Expected: at least one per-subsystem live-runtime integration path runs in CI (or a documented certification gate).
Repair boundary: frontend/backend (tests). Proof: one live ERS + one live Scene shot + one live Prop job through real worker → Library asset.

**CDX-094** — P2 · CONFIRMED · E2E harness · Stale legacy environment
Files: ~15 specs incl. `spatial-map-ers-generator.spec.ts`, `spatial-e2e-smoke.spec.ts`, `prop-creator-coffee-cup*.spec.ts`, `spatial-map-grid-camera-blocking.spec.ts`, `character-creator-*simplification.spec.ts`, `korri-switch-place.spec.ts`, `library-checkbox-certification.spec.ts` — hard-pinned to the RETIRED :8760/:8761 stack and explicitly refusing :8758.
Defect: the E2E suite certifies against a legacy environment contrary to AGENTS.md §15 (hosted Beta path = Vercel → Cloudflare → :8758).
Repair boundary: tests only. Proof: migrate specs to the :8758 harness; run green.

**CDX-095** — P3 · CONFIRMED · Test inventory · Clean-clone coverage
Files: untracked `test_avatar_studio_phase1.py`, `test_qwen_i2i_ers.py`, `test_timeline_continuity_contracts.py`; modified `test_ers_image_product.py`, `test_image_core.py`, `test_v11_3d_scope_deferral.py`
Defect: committed-HEAD coverage is below working-tree coverage; clean-clone law violated for these tests.
Repair boundary: 2–3 files. Proof: clean checkout → tests present and green.

**CDX-096** — P3 · CONFIRMED · Coverage gaps · Verification
Files: Notes (no dedicated tests anywhere — transitive only); Agent Work Surface API endpoints (advance/regenerate/cancel — zero direct API tests; only E2E execution-state.spec.ts + all-mock operator units); dispatcher/`approve_and_execute`/`advance_execution_pack` (no direct unit/integration tests); wiki/plans web units absent; jsdom/RTL harness absent repo-wide (component render coverage delegated to Playwright).
Repair boundary: frontend/backend (tests). Proof: add the named tests; run green.

**CDX-097** — P3 · CONFIRMED · E2E observe-only · Provider execution proof
Files: `spatial-map-ers-generator.spec.ts` ("must not POST", HOLD Generate); `spatial-map-ers-scene-handoff.spec.ts` (HOLDs Generate); `scene-creator/scene-creator-finishing-reliability.spec.ts` (asserts only ONE send-to-timeline POST; does not assert a clip landed on the Timeline)
Defect: the strongest ERS E2E specs are observe-only and never prove provider pixels; no E2E asserts actual Timeline clip placement from Scene Creator.
Repair boundary: tests only. Proof: E2E with real generation asserting Library asset + Timeline clip presence.
## 7. Needs Verification

| ID | Why NV | Safe reproduction required |
|---|---|---|
| CDX-029 | Code path confirmed (no capability guard in the terminal-execution effect) but the cross-execution interleaving was not observed | Browser test: start atlas, complete a different execution, assert map background unchanged |
| CDX-044 | CLIP_NOT_FOUND guard + invented clipIds confirmed; whether the trigger fires depends on NLE sequence state in real projects | pytest with a seeded saved sequence; Playwright on a project with an existing NLE sequence |
| CDX-057 | Whole-blob settings_json rewrite confirmed; concurrent-writer clobbering not reproduced | Concurrency test: N parallel save_snapshot/compile → no field loss, monotonic revision; blob growth measurement |

All other findings are CONFIRMED from source. No runtime reproduction was performed anywhere (read-only law).

## 8. Canonical-state / duplication risks

**Dual stores (live, divergent):**
1. Script text: `script_segments` (shotlist/storyboard/CD script_search) vs `script_documents_v2` (Script Writer) — CDX-052; plus `story_documents` legacy vs `story_entries` — CDX-060.
2. ERS: file-JSON `EnvironmentReferenceSheet` + trait `EnvironmentReferencePackage` bridged by `metadata.sheet_id` — the bridge works on the production UI path (CDX-034 keeps it broken on the batch surface); two commit hooks for the composite — CDX-038.
3. Approval: `Asset.production_approval` (written) vs `AssetLibraryMeta.approval_state/is_canonical` (read, never written) — CDX-064.
4. Asset lineage: `asset_graph.AssetVersion` vs `m29_asset_versions` — CDX-074.
5. Specialist authority: foundation roster (12) + prompt-library registry (40) + hard-coded conversation candidates — CDX-087; cap violations 4/6–8 vs hard 3 — CDX-086.

**Shadow/local state pretending to be truth:** `lastErsGeneratorId` module global (CDX-072); `StoryEntryEditor.lastPublished` in-memory dirty flag (CDX-059); pack `roleAssets` vs canonical reference rows (CDX-003); `focused_artifact_ids` alias (CDX-092).

**Legacy stores still wired:** `profiles.ProfileItem(kind="prop")` ghost writes (CDX-011); `story_documents` GET/PUT live (CDX-060); legacy `ers.*` chat tools (CDX-033); batch scene routes + client (CDX-046); dormant frontend planner (CDX-088).

**Single-blob risk:** `Project.settings_json` holds knowledgeEntries/workingNotes/compiledWiki/cache/bundles with whole-document rewrites — CDX-057.

## 9. Provider and generation honesty

| Claim | Reality | Finding |
|---|---|---|
| "Generator ready" | Certified-registry status / static catalog, no weights-on-disk check | CDX-075 |
| Pinned Z-Image execution | Silent alternate-model substitution in worker (legacy paths); dishonest job message in pinned path | CDX-076 |
| Nano Banana 2 recommended for Add | Family unroutable; falls back to any ready local family | CDX-077 |
| Cloud Add enqueue | No fal-credential preflight; fails at execution | CDX-078 |
| Cloud preview/final with identity refs | Refs silently dropped (txt2img downgrade for family "hosted") | CDX-079 |
| FLUX Kontext Pro offered | Catalog marks adapter unavailable | CDX-080 |
| Cloud/local availability in selectors | Missing fields default to available | CDX-081 |
| ERS Qwen I2I ready | Static metadata.supports; certified-registry claim outruns Phase 2R live proof; dual eligibility sources; client workflow pin dropped at dispatcher | CDX-039 |
| ERS GPT pixel conditioning | Prompt says "not pixel image-to-image" while pixels are attached | CDX-035 |
| Qwen scene shots conditioned on ERS | Environment pixels never sent; no disclosure | CDX-040 |
| Job message checkpoint | FLUX checkpoint named for qwen runs | CDX-082 |
| Provider inventory "available" | Key-presence proxy, probe deferred | CDX-083 |
| Character sheet phases honor source pools | Only hero candidates honor Local/Cloud selection | CDX-001 |
| Frontend plan executability | Auto Select counted without inventory; Generate enabled with zero executable sources | CDX-009 |
| Atlas aspect ratio | Fixed 1280×1280 | CDX-031 |
| Provider provenance (positive) | `ImageProvenance` stamps and `_pin_hosted_image_job` refusal gates are honest; browser never calls providers directly (invariant GREEN); resolver refuses silent swaps at compile | — |

## 10. Approval / persistence / lineage risks

- **Unapproved → Timeline:** legacy batch send-to-timeline has no approval gate (CDX-043). Shot flow is gated (`NO_APPROVED_TAKE`), and manual + agent handoffs converge on one helper — the protected path is sound.
- **Approval identity drift:** pack roleAssets vs canonical rows after multi-candidate approval (CDX-003); concept gate auto-approved with Korri content (CDX-002); draft hero shown as "Selected" (CDX-004); OWNER_APPROVED with NOT_STARTED gates (CDX-008); Express approval never promotes to continuity/Bible (CDX-006).
- **Approval not visible:** Library never displays approved state (CDX-017, CDX-064).
- **Persistence loss:** Script conflict recovery dead (CDX-055); spatial `_parse_document` destructive fallback (CDX-024); Remove-Atlas orphans placements (CDX-021); candidate stuck generating (CDX-048); notes/wiki/script GETs mutate state (CDX-049/054/056); wiki correction previews in-memory (CDX-061).
- **Deletion/lineage:** asset delete lacks entity-link cascade; versions/edges never cleaned (CDX-063); atlas lineage missing derived_from edges (CDX-032); ERS snapshot staleness excludes newer approved props (CDX-014).
- **Reload:** ERS hook latch shows previous map's composite (CDX-022); story dirty flag false-positive (CDX-059); generator choice leaks across projects (CDX-072).

## 11. Express ↔ Standard parity findings

| Surface | Express | Standard | Verdict |
|---|---|---|---|
| Character | CharacterCompactView + CharacterCore (shared) — coherent | Full workspace; only place promotion exists (CDX-006) | Shared core OK; approval semantics diverge (CDX-002/003/004) |
| Prop | PropCreatorCore shared | PropCreatorCore shared | Shared OK; ImageGen "Prop" promote ghost (CDX-011); Library approval invisible (CDX-017) |
| Spatial Map | CoDirector/SpatialMap panel | components/spatial-map — DEAD code, writes fake ids (CDX-027) | Express is canonical; legacy must be removed |
| Scene | Launcher only (per superseded audit: Express is launcher, Standard is the single workspace) | SceneCreatorCore shared | Shared OK; legacy batch UI/API retained (CDX-046); dead `variant` prop (CDX-050) |
| ERS | Same SpatialMapPanel/useErsGeneration | Same | Shared; directional-assets model vs single-image flow (CDX-036); legacy 4-direction tool path (CDX-033) |
| Script Writer | ScriptwriterInlineEditor (HTML-only) | ScriptwriterStudio (same backend; navigator/stats stale, CDX-051); dead CompactView (CDX-062) | Same backend, same representation split |
| Library | LibraryMediaGrid — flat list, no tree/global (CDX-074) | LibraryPanel — tree, global scope, promoteGlobal | Capability divergence on one backend |
| Story | StoryEntryEditor embedded | same component | Shared; dirty-flag bug (CDX-059) |

Express intentionally exposes fewer controls — acceptable. **Different state authority is not acceptable and was found in:** Script Writer elements/HTML (CDX-051), script stores (CDX-052), library approval channel (CDX-064), specialist registries (CDX-087), execution authorities (CDX-089), readiness authorities (CDX-075).

## 12. Co-Director orchestration findings

- **Invariants:** browser→provider isolation GREEN (no direct provider calls found; only /api gateway + fal.ai dashboard links). Specialist truth mutation GREEN (`mayExecuteTools=False`, proposal-gated writes). Production State read-through GREEN (Law 4 projection, never persisted). Single synthesis voice GREEN (`SynthesisEngine` only). Approval boundaries YELLOW (CDX-084 TOOL-kind dead-end; otherwise real). Specialist max-3 VIOLATED (CDX-086); single registry VIOLATED (CDX-087).
- Execution packs, capability registry, plans, status/SSE buses are coherent and GREEN-adjacent.
- Duplication: second scene engine (CDX-085), Production Executive (CDX-089), legacy frontend planner (CDX-088), layered intent classifiers (CDX-091), heuristic specialists presented as consultants (CDX-090).
- Execution chain has no direct tests (CDX-096).

## 13. Test/evidence coverage map

| Subsystem | Coverage | Notes |
|---|---|---|
| Character Creator Express | unit + integration + API mocked + web unit + E2E | enqueue mocked; real imagegen not proven live |
| Prop Creator Express | integration (fake enqueue) + web unit + E2E | coffee-cup E2E live-pinned to :8760/:8761 |
| Spatial Map / Atlas | API + 10 web units + E2E | no real runtime; atlas no dedicated router test |
| ERS | handler unit (fake enqueue) + real qwen workflow graph (new untracked test) + observe-only E2E | no live qwen2512.ref run; "Certified" is registry self-consistency (CDX-039) |
| Scene Creator Express | integration (generation availability stubbed off) + web + E2E | E2E does not assert Timeline clip placement (CDX-097) |
| Story / Script Writer | unit/integration + web + E2E m47 | no test proves HTML typing → navigator/stats; scoping untested (CDX-053) |
| Wiki | API unit + 6 E2E certs | no web unit tests |
| Notes | NONE (transitive only) | CDX-096 |
| Agent Work Surface / execution | all-mock operator units + E2E execution-state | dispatcher/advance/regenerate untested (CDX-096) |
| Library | API + web + E2E | delete-cascade and 500-cap untested; stale taxonomy tests (CDX-073) |
| Providers/capabilities | strong fail-closed units; live opt-in only | mock provider never yields locally_verified |

**Systemic:** `conftest.py` mocks `job_queue.enqueue` for every API test (CDX-093) — no API test proves real execution; default Playwright harness uses `ADEPT_CODIRECTOR_PROVIDER=mock` + fixture providers; ~15 specs pin the retired :8760/:8761 stack (CDX-094); 6 test files untracked/modified vs committed HEAD (CDX-095). Do not inflate confidence from raw test counts — deterministic breadth is excellent, real-runtime proof is almost entirely opt-in.

## 14. Protected certification assessment

| Certification | Assessment |
|---|---|
| **Scene Creator Grounding + Integrity** (protected baseline) | **REMAINS VALID for what it certified.** Audit found grounding/reference_packet/readiness/integrity paths coherent (GREEN); no regression in the governing path. The governing doc's own latest verdict is NO-GO (2026-08-15, Nano Banana 2 Add napkin pixel FAIL) — a documented runtime state, not an audit discovery. **Boundary:** CDX-044 (CLIP_NOT_FOUND) touches the certified Timeline handoff path under a specific NLE-sequence condition — reopen ONLY that handoff segment after verification, not the baseline. CDX-043 (batch endpoint) lies outside the shot-flow certification scope but shares its Timeline destination — gate it independently. |
| **Prop Creator Express** (2026-08-14 APPROVED) | Core scope (PropEntity canon, approval, persistence, approved-only spatial/scene consumption) **remains intact**. New defects lie adjacent: ImageGen promote ghost (CDX-011), Library-group placements (CDX-012), handoff approval filter (CDX-015), stale snapshot union (CDX-014). **Contradiction:** CDX-015 shows the "approved-only downstream" claim is not uniformly enforced at the handoff layer — scope-reopen a focused re-verification of `production_handoff._prop_ids_from_map`, not the full certification. |
| **Qwen/ERS Phase 2** | CONCURRENT workstream (files modified in-tree). CDX-035/036/039 audit the in-flight implementation; do not repair until Phase 2 lands, then re-verify. CDX-039 explicitly requires the Phase 2R live runtime proof before "Certified" is trustworthy. |
| **Krea Phase 1** | Owned by Cursor; untouched by this audit. |
| **Localized Add** | Separate; regionEdit files modified in-tree; no regression found in the governing region-edit paths (concurrent refinements only). |

## 15. Cursor repair packets

| Packet | Defects | Severity | Authorized scope | Expected files | Depends on | Concurrent-work concerns | Tests required | Real-path certification |
|---|---|---|---|---|---|---|---|---|
| P1 · Library deletion cascade | CDX-063 | P1 | backend routes + services only | routers/api.py, scene_references, prop_creator/character_identity/scene_creator/ERS usage checks, queue_worker cleanup | none | avoid touching ERS handler while Phase 2 in flight (use ers_persistence strict hook) | pytest block/force-delete matrix | Playwright delete identity image |
| P2 · Model substitution + readiness | CDX-075, CDX-076, CDX-082 | P1 | image_core/queue_worker/imagegen_workflows | preflight.py, queue_worker.py, imagegen_workflows.py, model_registry.py | none | queue_worker.py is modified in-tree by other workstreams — coordinate | unit preflight MODEL_NOT_INSTALLED; unit _checkpoint_for_model | Playwright ready-state truth |
| P3 · Script Writer truth | CDX-051, CDX-052, CDX-053 | P1 | scriptwriter backend + both editors | scriptwriter/service.py, api.py, stats.py, wave3_reads.py; storyboard consumers | none | none | API scoping test; HTML→stats test | Playwright typed-script navigator/Timeline-prep |
| P4 · Legacy batch gate + grounding | CDX-034, CDX-043, CDX-046 | P1 | scene_creator router/timeline_handoff + batch client | router.py, timeline_handoff.py, scene_generate.py, api.ts | none | spatial-scene-creator E2E asserts batch behavior — update it | pytest NO_APPROVED_TAKE; sheetId→package test | E2E batch with sheetId compiles with grounding |
| P5 · ERS honesty (post-Phase-2) | CDX-035, CDX-036, CDX-038 | P2 | ers_generate + contracts + store | ers_generate.py, ers_contracts.py, exports.py, ErsSelector/ErsResultDisplay | **WAIT for Qwen/ERS Phase 2** | files mid-flight; do not touch until workstream lands | unit prompt/request consistency; dead-code greps | Playwright directional/composite consistency |
| P6 · Spatial handoff correctness | CDX-012, CDX-013, CDX-019, CDX-020, CDX-021, CDX-022 | P2 | spatial_map backend + SpatialMapPanel + scene_creator unions | service.py, schemas.py, errors.py, SpatialMapPanel.tsx, useErsGeneration.ts, types.ts | P1 (delete cascade) | useErsGeneration.ts modified in-tree — coordinate | pytest placement 4xx; ERS reset test | Playwright multi-map/scene handoff |
| P7 · Atlas adoption + vision canon | CDX-028, CDX-029, CDX-030, CDX-031, CDX-032 | P1/P2 | vision/router.py + SpatialMapPanel + atlas handler | vision/router.py, SpatialMapPanel.tsx, atlas_generate.py | none | vision/router.py modified in-tree — coordinate | unit fingerprint equality; capability-guard test | Playwright cross-execution adoption |
| P8 · Library retrieval truth | CDX-064, CDX-065, CDX-066, CDX-067, CDX-068, CDX-073 | P1/P2 | project_library backend | codirector.py, schema.py, service.py, asset_graph.py, extra.py, tests | none | none | API approval-ranking test; >500 assets; dedupe | Playwright approved-first retrieval |
| P9 · Provider offering honesty | CDX-077, CDX-078, CDX-079, CDX-080, CDX-081 | P2 | image_core + scene_creator + selectors | recommend.py, preflight.py, generation.py, discovery.py, SceneCreatorCore.tsx, GeneratorSourceSelector.tsx | P2 | scene_creator/generation.py modified in-tree — coordinate | unit preflight credential; candidate-plans family | Playwright unroutable-family block |
| P10 · Character approval canon | CDX-001, CDX-002, CDX-003, CDX-004, CDX-007, CDX-008, CDX-009 | P2/P3 | character_identity backend + CharacterCore | visual_sheet.py, visual_gates.py, service.py, useCharacterProfile.ts, characterGeneratorPlan.ts | none | none | API gate/candidate tests | E2E approve→gate ids |
| P11 · Orchestration boundaries | CDX-084, CDX-086, CDX-087, CDX-088, CDX-089, CDX-090, CDX-091, CDX-092 | P2/P3 | codirector execution/intelligence/foundation + frontend | dispatcher.py, routing.py, roster/registry consolidation, execute.ts, AgentWorkSurface.tsx | none | none | dispatch approval test; specialist cap property test | Playwright TOOL-kind approval |
| P12 · Text-system side effects & recovery | CDX-054, CDX-055, CDX-056, CDX-058, CDX-059, CDX-061 | P2/P3 | scriptwriter/story/notes routers + editors | api.py/service.py, notes/service.py, StoryEntryEditor.tsx, ScriptwriterStudio.tsx | P3 | none | GET-no-write tests; recovery restore test | Playwright conflict restore |
| P13 · E2E harness migration | CDX-094, CDX-095, CDX-093, CDX-096, CDX-097 | P2/P3 | tests only | ~15 specs, e2e-start.mjs, conftest.py, new tests | none | none | CI green on :8758 harness | one live run per subsystem |
| P14 · Dead code quarantine | CDX-010, CDX-018, CDX-027, CDX-046(UI), CDX-060, CDX-062 | P3 | frontend delete/archive only | CharacterCreatorEmbedded, EntityPicker prop variant, components/spatial-map/*, SceneResult*, ShotRequestInput, StoryEditor, ScriptwriterCompactView, story/api.py | none | none | grep no-imports; route removal | E2E tabs still pass |
| P15 · Scene Shots collection + CLIP_NOT_FOUND | CDX-045, CDX-044 | P2/P1 | execution builder + magi handoff | scene_shot_collection_builder.py wiring, magi/timeline_handoff.py | none | magi/timeline_handoff.py modified in-tree — coordinate | collection test; seeded-sequence test | Playwright Timeline clip presence |
| P16 · Project-lock media bypass | CDX-069 | P2 | security middleware + main.py | middleware.py, main.py | none | none | E2E lock → 403 matrix | Playwright locked-project media |

Do NOT create a "fix everything" packet. Each packet above is 1–6 related defects with independent scope.

## 16. Recommended repair order

1. **Corruption/data-loss risk:** P1 (CDX-063), CDX-024, CDX-021, CDX-057 (verify first), CDX-055.
2. **Wrong-provider/wrong-asset risk:** P2 (CDX-075/076), P7 (CDX-029), P4 (CDX-034), P5 (CDX-039), P9 (CDX-077/079/080).
3. **Persistence/approval integrity:** P4 (CDX-043), P15 (CDX-044), P10 (CDX-002/003/004/008), CDX-006.
4. **Canonical-state duplication:** P3 (CDX-052/051), P11 (CDX-086/087/089/085), P14 (dead code), CDX-033/060.
5. **Broken handoffs:** P6 (CDX-012/013/020), P7 (CDX-037/028), CDX-045/014/015.
6. **Creator-facing error honesty:** CDX-023/030/035/036/040/081/082/083/090, CDX-009.
7. **Polish:** P14 remainder, P13.

**Parallelizable now:** P1, P2, P3, P7, P8, P9 (backend-only, disjoint files), P10, P11, P14, P16 — no shared files. **Serial/coordinated:** P4 after P1 (delete cascade touches same assets); P5 only after Qwen/ERS Phase 2 lands; P6/P15 coordinate on in-flight `useErsGeneration.ts`/`magi/timeline_handoff.py`; P13 after P4 changes the batch E2E contract.

## 17. Out-of-scope observations

1. `studio-api/app/queue_worker.py.bak-kie-extract-20260814-180710` — stale ~3.5k-line backup inside the app package (greps pick it up).
2. `POST /api/e2e/feature-flags` allows runtime flag toggling — security-sensitive surface outside this audit.
3. `repositories/` (contracts.py/sqlite.py) — inert boundary scaffold for a "future persistence cutover"; nothing imports it.
4. `_imagegen_commit_asset` thumbnails path mismatch (`thumbs` vs `.thumbs`) in scene_creator delete — adjacent to CDX-063.
5. `hero_portrait → hero_identity` migration still wired in main.py:205 (read-time alias exists in roles.py).
6. `visual_sheet.py` is a 3,152-line monolith (routing/prompts/polling/gates/library) — maintainability risk, not a defect.
7. Storyboard "Scene 12" literal string scene ids in storyboard add-image paths — loose linkage semantics.
8. `fal_catalog.py` FAL_IMAGE_MODELS={} documented honest, but FAL_IMAGE_ENDPOINT_BY_DOCK maps nano-banana-2-fal etc. — partial externally-visible wiring.
9. 2,500-token context budget for wiki specialists is small and safe; the cap violation (CDX-086) is structural, not a context-budget risk.
10. The retired-:8760 stack still appears in docs/release-gate evidence; AGENTS.md §15 declares it retired — E2E migration (P13) should also update stale doc references.

## Final verdict

**CO-DIRECTOR EXPRESS AUDIT COMPLETE — CURSOR REPAIR QUEUE READY**

97 findings (0 P0 · 11 P1 · 43 P2 · 43 P3 · 3 NEEDS VERIFICATION). The Express pipeline is real: canonical stores, real job submission, honest provenance stamps, protected Grounding + Integrity baseline intact, and the historical sheet/package mismatch is repaired on the production UI path. The repair queue (16 packets) is scoped, dependency-ordered, and respects the Qwen/ERS Phase 2, Scene Creator certification, Krea Phase 1, and Localized Add workstreams.



