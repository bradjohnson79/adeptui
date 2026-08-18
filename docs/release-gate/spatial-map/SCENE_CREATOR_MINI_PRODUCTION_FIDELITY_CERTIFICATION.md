# Scene Creator Mini — Production Fidelity + Qwen Closure Certification

**Status:** NO-GO — SCENE CREATOR MINI PRODUCTION FIDELITY NOT CERTIFIED (see §11)

**Date:** 2026-08-18
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` version **175** (saved 175)

Supersedes: `docs/release-gate/spatial-map/SCENE_CREATOR_MINI_CERTIFICATION.md` (Option 1, NO-GO).

---

## 1. Root Cause Report (Part 42) — why previous Mini output failed

Verified by repository audit (Subagent A) + Qwen runtime audit (Subagent B). The prior
NO-GO (C2-B lounge/entrance plant) was not a prompt-tuning problem; it was five
conditioning/architecture deficiencies:

| # | Deficiency | Fix shipped this milestone |
|---|-----------|---------------------------|
| 1 | **No deterministic shot packet** — Mini compiled a flat prompt fragment list; character identity, shot size, primary subject, camera↔fixture relations did not exist as data | `camera_shot_packet.py` — deterministic `CameraShotPacket` compiled from saved state only |
| 2 | **Character presence suggestive, never explicit** | `requiredCharacterIds` derivation + `KORRI MUST BE PRESENT.` locked fact |
| 3 | **Character identity conditioning absent** — no identity facts or approved reference in the prompt/request | identity facts (appearance/wardrobe) now compile into the prompt; approved reference resolved into the packet (single-reference hierarchy where the generator supports it) |
| 4 | **Camera conditioning text-only** — no per-camera viewpoint reference; one hero crop biased every camera | `camera_reference.py` — per-camera Camera Shot References (C1–C4) with metadata + staleness |
| 5 | **Job completion == success** — no continuity validation; C2-B failure was displayed as selectable | `mini_validation.py` + fal/Kie vision review — GENERATING → VALIDATING → PASS / CONTINUITY_FAILED / GENERATION_FAILED; non-PASS results are not selectable, not Library-ingestable |
| 6 | **Shot-size metadata did not exist** | `SpatialCamera.shotSize` (auto…extreme_close) persisted + camera-card UI |
| 7 | **Qwen Mini path uncertified** — source-plate guarantee missing (chrome composite could reach the generator) | `_mini_source_asset` now NEVER returns the full composite; hero-inset plate guaranteed |
| 8 | **ERS revision not stamped** | take JSON carries `ersSheetId`/`ersRevision` (grounding fingerprint) |

## 2. What Changed

- **Data model**: `SpatialCamera.shotSize` + `primarySubject`; `anchors` on map update (fixture anchors for placement locks).
- **CameraShotPacket** (`studio-api/app/spatial_map/camera_shot_packet.py`): environment (ids/versions/ERS revision/north lock/anchors), camera (cell/normalized/world/orientation/yaw/pitch/FOV/shotSize/region/relational facts/anti-substitution), characters (identity + approved asset + cell/region/coords + mandatory + side relations), props, scene intent, `requiredCharacterIds`, `primarySubject`, locked vs flexible facts.
- **Production prompt compiler** (`mini_production_compiler.py`): locked facts + shot-size framing language (never camera relocation) + `KORRI MUST BE PRESENT.` + identity facts + generator presentation. No LLM in the compile path.
- **Placement locks derived from map geometry** (Part 6): fixture-side relations computed from world coords + anchors — no hardcoded Schnick rules.
- **Character identity conditioning** (Parts 5/19/22): identity facts in prompt; approved character reference resolved into packet; live Kie gpt-image-2 I2I rejects multi-image requests (proven: 5/7 jobs failed) so the supported hierarchy is single authoritative environment reference + text identity — recorded honestly as `referenceConsumption: single_authoritative_only`.
- **ERS Camera Shot References** (`camera_reference.py` + endpoints + strip UI): per-camera viewpoint/framing canon; independently replaceable; staleness (camera data / ERS revision) enforced; low-overhead (only the changed camera regenerates).
- **Candidate validation** (`mini_validation.py` + `vision_review.py` + queue-worker hook): fal-ai any-llm/vision (google/gemini-2.5-flash-lite) with public asset URLs; Kie Gemini fallback; honest VALIDATION_UNAVAILABLE when no provider.
- **Qwen closure**: clean-plate guarantee; Mini route certified end-to-end; capability gating verified; per-camera validation.
- **Save gate regression**: shot-size/primary-subject edits dirty the map (Mini disabled) until Save.

## 3. Evidence

| Item | Value |
|------|-------|
| Branch | feat/scene-creator-mini-production-fidelity |
| HEAD SHA | see §9 |
| Map saved version | 175 |
| Camera Shot Packet example | §4 |
| Saved Spatial Camera JSON | §4 |
| shotSize persistence proof | §4 |
| primarySubject proof | §4 |
| Character reference lineage | §5 |
| Camera reference lineage | §5 |
| Co-Director compiled production prompt | §4 |
| GPT 8-image take | §6 — **8/8 PASS** |
| Qwen live result | §6 — operational; candidates honestly CONTINUITY_FAILED (Korri absent) |
| Validation results | §6 |
| Library before/after | §7 — 51 → 53 (+2, selected-only) |
| Dirty/save gating | §7 + Playwright |
| Unit/API tests | §8 |
| Browser certification | §7 (Playwright vs live Beta) |
| Independent visual report | §10 |
| Deployment evidence | §9 |

## 4. Packet / camera JSON / prompt evidence

Saved map (version 175) camera JSON (authoritative saved state):

```json
[
  {"label": "C1", "cameraSlot": 0, "gridColumn": 11, "gridRow": 11, "orientation": "N",  "fovPreset": "medium", "shotSize": "wide",         "primarySubject": "auto",  "visible": true},
  {"label": "C2", "cameraSlot": 1, "gridColumn": 13, "gridRow": 11, "orientation": "NW", "fovPreset": "medium", "shotSize": "medium",       "primarySubject": "c49371ed-ba6b-4c16-ba98-a8b28b72118b", "visible": true},
  {"label": "C3", "cameraSlot": 2, "gridColumn": 9,  "gridRow": 11, "orientation": "NE", "fovPreset": "medium", "shotSize": "medium_close", "primarySubject": "c49371ed-ba6b-4c16-ba98-a8b28b72118b", "visible": true},
  {"label": "C4", "cameraSlot": 3, "gridColumn": 11, "gridRow": 13, "orientation": "N",  "fovPreset": "medium", "shotSize": "close_up",     "primarySubject": "auto",  "visible": true}
]
```

Korri placement: cell (11,9), normalized (0.15, -0.05), world (0.75, 0, -0.25) — behind the
Service Counter anchor (0.75, 1.0, 0.25) relative to all cameras. miniPrompt:
"standing behind the barista bar beside the espresso station on the staff side".

C2 CameraShotPacket (full JSON in `.runtime/camera_mini_cert/packet_evidence.json`):

```json
{
  "environment": {
    "projectId": "2347bf46-…", "spatialMapId": "6bc36d92-…", "mapVersion": "175",
    "savedVersion": "175", "ersSheetId": "db095959-…",
    "ersCompositeAssetId": "2c4d59f2-…", "ersRevision": "a759c5d50d02741a",
    "northLock": "north", "environmentIdentity": "neighborhood coffee shop",
    "anchors": [{"id": "anchor-service-counter", "label": "Service Counter", "x": 0.75, "z": 0.25}]
  },
  "camera": {
    "label": "C2", "cell": "N12", "normalizedX": 0.35, "normalizedY": 0.15,
    "orientation": "NW", "yawDegrees": 315.0, "fovPreset": "medium",
    "shotSize": "medium", "region": "eastern side"
  },
  "requiredCharacterIds": ["c49371ed-ba6b-4c16-ba98-a8b28b72118b"],
  "primarySubject": {"type": "character", "characterId": "c49371ed-…", "name": "Korri"}
}
```

Locked facts compiled for C2 (25 facts): `Camera C2 is at grid cell N12.`, `Camera C2
region: eastern side.`, `Camera C2 faces NW (yaw 315).`, `Shot size: medium. Shot size
changes framing, crop and composition only — it does NOT move the camera.`,
`KORRI MUST BE PRESENT.`, `Korri is placed at L10.`, `From this camera: Korri visible
ahead.`, `Korri is behind the Service Counter from this camera (far side, away from the
camera).`, `Korri remains on the far side of the Service Counter; must not move to the
near side in front of the Service Counter.`, anti-hero / anti-mirror / anti-substitution
rules, `Character identity (Korri): appearance: … twin ponytails …`.

Co-Director compiled production prompt (C2-A, GPT) — first lines:

```
Still photograph from Spatial Map camera C2.
OUTPUT: Photorealistic cinematic still, natural lens perspective, clean production photography.
OUTPUT: one continuous photographic still filling the entire frame.
Do not draw an Environment Reference Sheet, contact sheet, storyboard, map, grid, camera glyphs, C1-C4 labels, checklists, or any multi-panel layout.
CAMERA PLACEMENT IS CANONICAL. Do not relocate the camera, rotate the room, or mirror the environment.
NORTH LOCK: NORTH. Same grid as the Spatial Map.
Frame size: 16:9.
…
Camera C2 is at grid cell N12.
Camera C2 region: eastern side.
Camera C2 faces NW (yaw 315).
Shot size: MEDIUM — the subject is framed from the waist up; the environment remains clearly readable around them.
KORRI MUST BE PRESENT.
…
```

Full packet + prompts: `.runtime/camera_mini_cert/packet_evidence.json`.

## 5. Reference lineage

- Environment plate: ERS hero-inset crop asset `f0eeceb2-ca10-479c-83f1-9c682e328fa6`
  (tag `scene_creator_mini_hero_inset`, 467×220, parent = ERS composite `2c4d59f2-…`,
  sheet `db095959-…`) — chrome-free (Subagent B pixel analysis).
- Character identity: Korri approved hero_identity reference `b6ab91dd-9d0a-4e4b-98b4-b26d268950dc`
  (korri_four_view_c2, approved 2026-08-15, canonical) — resolved into the packet;
  recorded as considered reference for GPT (Kie multi-image rejection documented).
- Camera Shot References (regenerated against map v175, all `stale: false`):
  C1 `a4de18a9-…`, C2 `54c89c6e-…`, C3 `ba930122-…`, C4 `4446dcd6-…` — all
  1280×720, parent = hero-inset plate, tag `scene_creator_mini_camera_ref`.
- GPT jobs carry `referenceGrounding.assetIds = [hero inset]`,
  `referenceConsumption: single_authoritative_only`, `consideredReferenceAssetIds`.

## 6. Generation + validation results

**GPT Image 2 full take** `512d88ef-3781-4ee2-92c7-83e3a70a4741` (take 19; map v175, ERS
`db095959`, revision `a759c5d50d02741a`): 8/8 candidates PASS the automated
validator (fal google/gemini-2.5-flash-lite) — **but independent review fails
character identity on 7/8** (see §10). The automated PASS is therefore NOT
sufficient for the GO gate.

| Camera | Size | Primary | A | B |
|--------|------|---------|---|---|
| C1 | wide | auto | PASS | PASS |
| C2 | medium | Korri | PASS | PASS |
| C3 | medium_close | Korri | PASS | PASS |
| C4 | close_up | auto | PASS | PASS |

**Qwen Image (local) C2 pair** `f3d4c8b0-…` + regenerate + fresh take `9e0f6c2d-…`:
Qwen executes locally (1280×720, correct frame size, hero-inset reference, no ERS
typography contamination), but every candidate is honestly **CONTINUITY_FAILED**
("The required character, Korri, is not present…") — the certified single-reference
`qwen2512.ref` graph reproduces the empty café and cannot introduce the required
character. **Qwen full take** (all 4 cameras): same honest CONTINUITY_FAILED outcome.

Per Part 37 (Qwen failure truthfulness): this is a **model/workflow capability
limitation, not an infrastructure failure**. Qwen is selectable only when genuinely
ready, executes, validates honestly, and its failed candidates are never selectable or
Library-ingestable. The blocker for Qwen character-presence fidelity is documented in
the Verdict section.

## 7. Library + save-gate regression

- Library before Mini generation: **51** visible. After generation (drafts
  `libraryVisible: false`): **51** — no leak. After Send Selected (C1A + C4B PASS
  candidates): **53** (+2 exactly). Failed/unselected candidates absent.
- Save gate: shot-size edit → dirty → Mini Generate disabled + Use in Scene Creator
  disabled → Save → enabled again (Playwright spec, live Beta).

## 8. Tests

- Backend: `studio-api/tests/test_scene_creator_mini.py` (15) +
  `test_scene_creator_mini_fidelity.py` (25) = 40 tests green; plus
  `test_ers_scene_intent_grounding.py` (17) and the wider suite (see §9).
- Frontend: `sceneCreatorMiniApi.test.ts`, `types.test.ts` — 126 tests green in the
  SpatialMap suite.
- Playwright (live Beta, ADEPT_BETA_TARGET=1):
  `savegate-cert.spec.ts` — 9 passed, 1 flaky-then-passed (F: transient save blip
  under concurrent generation load); `mini-fidelity-cert.spec.ts` — 4/4 passed
  (camera cards shot size + primary subject, dirty→save gate, camera reference strip,
  Mini accordion + take provenance).

## 9. Deployment

- Branch: feat/scene-creator-mini-production-fidelity (cut from current HEAD carrying
  the in-flight Option 1 Mini changes).
- Commit scope: Mini/ERS/Spatial Map/Qwen files + tests + this doc. Unrelated
  Timeline/MAGI/character-variant work excluded.
- **Pre-existing baseline failure (NOT caused by this milestone; reproduced at HEAD)**:
  `tests/test_character_variants.py::test_variant_generation_uses_canonical_sheet_as_reference`
  — `app/character_identity/variants.py` calls `_negative_rules_for_view` without
  importing it (NameError); the file is unmodified vs HEAD and belongs to the
  lora-support workstream.
- Studio API restarted via managed `Restart-AdeptBetaBackend.ps1` (owned process);
  web bundle rebuilt (`studio-web/dist`) and served at :8760; verified live via
  Playwright + API.

## 10. Independent visual review (Subagent C)

`.runtime/camera_mini_cert/independent_review_pack.json` (8 GPT candidates + facts) +
Qwen candidates — see Subagent C report (attached).

## 10. Independent visual review

The implementation agent's model and subagents cannot read images in this
environment (read_image rejected: "model does not declare image input"), so the
independent visual review was performed with vision models distinct from the
automated validator, using an independent per-field rubric:

- **Reviewer 1 — google/gemini-2.5-flash** (fal any-llm/vision): GPT candidates —
  environment PASS 8/8, camera geography PASS 8/8, shot size PASS 8/8, no-mirror
  PASS 8/8; **korri_present PASS 2/8** (C1A, C2A), **korri_identity PASS 0/8**;
  notes: "The character is not Korri; she does not have black hair in high twin
  ponytails and is not an elf."
- **Reviewer 2 — openai/gpt-4o** (tiebreak, different vendor): GPT candidates —
  korri_present PASS 8/8, korri_placement PASS 8/8, environment/geography PASS
  8/8; **korri_identity PASS 1/8** (only C1B); notes: "The visible person does
  not match Korri's description of elf-like features and twin ponytails."
- **Automated validator (google/gemini-2.5-flash-lite)** — the validator's fact
  card previously omitted the character identity facts, so identity was judged
  without the description; after this milestone shipped the fact-card fix +
  stricter identity rubric, flash-lite still PASSes identity on 5/8.

Consensus: a person IS present and correctly placed behind the counter in the GPT
candidates, but **the person is not recognizably Korri** (2 of 3 frontier
reviewers fail identity on 7/8). Qwen candidates lack any person (all reviewers
agree).

**Subagent C consolidated independent review** (four vision reviewers — local
qwen3.8:27b + gemma4:31b-it-qat via workflow agents, reconciled with the frontier
gpt-4o + gemini-2.5-flash passes; full report
`.runtime/camera_mini_cert/INDEPENDENT_MINI_FIDELITY_REVIEW.md`):

- **GPT take: 1/8 PASS** (C1-B only). Identity substitution on 6 candidates —
  the figure behind the counter is not Korri (single bun/updo instead of high
  twin ponytails, apron/staff tee instead of black crop top + layered skirt, no
  visible elf traits). C3-A shows a different barista. C4-A/C4-B show a shot-size
  mismatch (medium framing instead of the locked CLOSE UP). No mirror/layout
  corruption anywhere.
- **Qwen take: 0/8 PASS** — Korri entirely absent in all eight frames; the
  automated CONTINUITY_FAILED verdicts are visually confirmed.
- **Camera references:** geography + environment continuity PASS; shot scale
  judged wrong (and the review pack's stale flags came from the pre-staleness-
  fix artifact file — live state is stale:false).

The automated validator (flash-lite) PASSed all eight GPT candidates while four
independent vision reviewers FAIL 7/8 — a validation-strictness gap (Part 45
stop condition) that this milestone tightened in code (identity facts in the
validation fact card + stricter identity rubric), but the certified candidates
still fail the identity gate.

## 11. Verdict

`NO-GO — SCENE CREATOR MINI PRODUCTION FIDELITY NOT CERTIFIED`

GO was not issued because the eight GPT images do not fully behave like shots of
the production character. Exact blockers (Part 42/45):

1. **Character identity fidelity (Part 35 fails).** The generated character is a
   generic barista, not recognizably Korri (Sun Sprite Elf, twin ponytails).
   Independent reviewers gemini-2.5-flash (0/8) and gpt-4o (1/8) fail
   korri_identity; the automated validator (flash-lite) is too lenient on
   identity and passed candidates the independent reviewers failed — a
   validation-strictness gap (Part 45 stop condition).
2. **Identity conditioning channel unavailable.** The approved hero_identity
   reference is a four-view character sheet; the live Kie gpt-image-2 I2I
   rejects multi-image requests (verified: 5/7 jobs failed) and the certified
   qwen2512.ref graph is single-reference — so no pixel identity channel exists
   with the current certified adapters. Text identity facts alone did not
   produce a recognizable Korri.
3. **Qwen required-character presence (Part 36/37).** Qwen executes locally with
   correct frame size and clean reference, but every C1–C4 candidate is honestly
   CONTINUITY_FAILED ("Korri is not present") — the certified single-reference
   graph reproduces the empty café. This is a model/workflow capability
   limitation, not an infrastructure failure; Qwen candidates are never
   selectable or Library-ingestable.

What IS certified this milestone: the CameraShotPacket compiler, production
prompt compiler (locked facts, KORRI MUST BE PRESENT, shot-size framing without
camera relocation, map-derived placement locks), shotSize/primarySubject
persistence, camera reference system with staleness, the validation state
machine + honest gates (Library +2 regression, save-gate regression, Playwright),
and the Qwen runtime closure (clean-plate guarantee, honest gating, honest
failure surfacing). These remain correct; the GO gate fails on character
identity + Qwen character presence.

