# M3.0a Phase 3 - Full-Stack Wiring Matrix

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Date | 2026-07-26 |
| Inputs | `NATIVE_PLATFORM_INVENTORY.md` (Phase 0), `MOCK_AND_SCAFFOLD_AUDIT.md` (Phase 0 + Phase 1/3 remediation log), repository code, existing pytest and Playwright suites |
| Method | Code reading plus existing automated coverage. No status below is inferred from a feature name or a document; every PASS names something that executes. |

---

## 1. How to read this

One row per native production platform from the Phase 0 inventory, plus a second table for
the top-level routes. Each column is one link in the full-stack chain, and the value is the
status of *that link* for *that platform*.

| Code | Meaning |
|------|---------|
| PASS | The link is wired on the production (non-fixture) path and something in this repository exercises it: a pytest case, a Playwright spec, or a code path with no fixture branch and no way to short-circuit. |
| PARTIAL | The link exists but is incomplete: fixture-only execution, a subset of the platform, or a capability the baseline itself declares unavailable. |
| FAIL | The link is present and does the wrong thing on the production path. |
| NOT_TESTED | The code path looks correct and has no fixture escape, but nothing executed it during M3.0a. Generative links that need a real ComfyUI render or a real fal job are the main population here. |
| N/A | The link does not apply, because the platform has no such stage or the platform is absent. |

**NOT_TESTED is not a soft PASS.** Where a real artifact has never been observed, the artifact
column says NOT_TESTED and `REAL_ARTIFACT_VERIFICATION.md` says the same thing in more detail.

### Chain links

| Column | Link | Question it answers |
|--------|------|---------------------|
| UI | UI action | Is there a reachable native control that starts this? |
| API | Backend endpoint | Does a real endpoint receive it? |
| CAP | Capability | Is the capability declared and enforced, and is its declared status truthful? |
| PROV | Provider | Does a real provider execute the work, or does the path refuse honestly? |
| PROG | Progress | Can the caller observe the work in flight? |
| ART | Artifact | Is a real artifact produced? |
| DB | Persist | Is the result written to the database or disk? |
| RET | UI return | Does the result get back to the native UI? |
| CD | Co-Director | Can the Co-Director see and act on this platform inside its authorized range? |
| XP | Cross-platform | Does the output hand off to another platform (timeline, library, editor)? |
| APR | Approval | Are mutations gated on explicit human approval where the design requires it? |
| RST | Restart | Does in-flight or completed work survive an API restart? |

### A note on the "Cooldown" column

The task brief asks for a Cooldown / Co-Director column. There is **no subsystem named
Cooldown anywhere in this repository** - the string does not appear in any source file. The
CD column therefore measures the Co-Director loop only: whether the model can read the
platform's state, propose against it, and observe the outcome. `CODIRECTOR_CAPABILITY_COVERAGE.md`
breaks that down per verb.

---

## 2. Native production platforms

18 platforms, matching the Phase 0 inventory section 5.

| Platform | UI | API | CAP | PROV | PROG | ART | DB | RET | CD | XP | APR | RST |
|----------|----|-----|-----|------|------|-----|----|----|----|----|-----|-----|
| image | PASS | PASS | PASS | NOT_TESTED | PARTIAL | NOT_TESTED | PARTIAL | PASS | PARTIAL | PARTIAL | PASS | FAIL |
| video | PASS | PASS | PASS | NOT_TESTED | PARTIAL | NOT_TESTED | PARTIAL | PASS | PARTIAL | PARTIAL | PASS | FAIL |
| animation | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | PARTIAL | N/A | N/A | N/A |
| refs | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 3D (M2.13) | PASS | PASS | PARTIAL | PARTIAL | N/A | PARTIAL | PASS | PASS | PARTIAL | PARTIAL | PASS | PASS |
| VP / virtual stage | PASS | PASS | PARTIAL | N/A | N/A | N/A | PASS | PASS | PARTIAL | PARTIAL | N/A | PASS |
| blocking / spatial | PASS | PASS | PASS | NOT_TESTED | PARTIAL | NOT_TESTED | PASS | PASS | PARTIAL | PASS | N/A | PASS |
| camera | PARTIAL | PASS | PARTIAL | PARTIAL | N/A | PARTIAL | PASS | PASS | PARTIAL | PARTIAL | PASS | PASS |
| lighting | PARTIAL | PARTIAL | PARTIAL | N/A | N/A | N/A | PASS | PARTIAL | PARTIAL | N/A | PASS | PASS |
| storyboard | PASS | PASS | PASS | NOT_TESTED | PARTIAL | NOT_TESTED | PASS | PASS | PASS | PASS | PASS | FAIL |
| screenplay | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | PARTIAL | PASS | N/A | PASS |
| sound | PASS | PASS | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | PARTIAL | PARTIAL | PASS | FAIL |
| timeline | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | PARTIAL | PASS | PASS | PASS |
| edit | PASS | PASS | PASS | PASS | N/A | PASS | PASS | PASS | PARTIAL | PASS | PASS | PASS |
| color | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| comp | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | PARTIAL | N/A | N/A | N/A |
| subs | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| delivery | PASS | PASS | PARTIAL | PARTIAL | PARTIAL | NOT_TESTED | PASS | PASS | PARTIAL | PARTIAL | N/A | FAIL |

### Per-platform evidence and reasoning

**image** - `studio-web/src/components/ImageGenPanel.tsx` -> `POST /api/projects/{id}/imagegen`
-> `queue_worker._imagegen`. The provider is real ComfyUI; `executive/imagegen_adapter.py`
refuses to fabricate a completion even with `ADEPT_MOCK_IMAGEGEN` set (Phase 0 IMG-01/IMG-02),
so PROV cannot silently pass - but no M3.0a run produced an image, hence NOT_TESTED. M2.9
`m29/image/service.py` is covered only in fixture mode
(`tests/test_m29_production_suite.py::test_fixture_jobs_via_api`), which is why PROG and DB are
PARTIAL. CD is PARTIAL: there is no image-generation tool in the registry; the model reaches
image generation only through `propose_storyboard_generation` or the Production Executive.
RST is FAIL - see section 4.

**video** - `Txt2VidPanel.tsx` and scene render -> `queue_worker._txt2vid` /
`_build_and_run_fal_scene`. Both a local Comfy route and a fal route exist and both fail
closed without their provider (`m29/providers.py::run_video` raises `ProviderUnavailable`).
No M3.0a run produced a video locally or on fal.

**animation** - No native workspace and no API package. Only the `animation-supervisor` and
`choreographer` specialist contracts exist, so the Co-Director can advise about animation and
nothing else can happen. Everything else is N/A rather than FAIL: there is nothing wired to
be broken.

**refs** - `studio-api/app/references/api.py` plus the timeline-reference subsystem. This is a
data platform, so PROV and PROG are N/A; the "artifact" is a persisted reference set or
binding. Covered by `tests/e2e/projects/references.spec.ts` and
`tests/e2e/director/timeline-references.spec.ts`, and by six read tools and five
proposal tools in the Co-Director registry. Bindings mutate only through proposals, so APR is
PASS.

**3D (M2.13)** - `EnvironmentStudioWorkspace.tsx` -> `/api/codirector/m213/*`. CAP is PARTIAL
because `m213/kinds.py` registers its capability IDs as `unavailable`, which is the honest
declaration. PROV and ART are PARTIAL: after the Phase 3 remediation the camera-spin route
refuses to fabricate frames outside `ADEPT_M213_FIXTURE_MODE` / `STUDIO_E2E`, the
reconstruction route defaults to `detect` and never silently picks the fixture adapter, and
the real COLMAP / Nerfstudio / gsplat adapters remain detection-only. RST is PASS on the
strength of `m213/persistence.py::restart_recovery` and `selective_restore`, both covered by
`tests/test_m213_virtual_environment_studio.py`.

**VP / virtual stage** - `VirtualStageWorkspace.tsx` -> `m28/virtual_stage/service.py`. CRUD
and camera state only; `virtual_stage.render` is declared unavailable in the capability
baseline, so there is no provider, no artifact and nothing to approve.

**blocking / spatial** - `SpatialSceneWorkspace.tsx` -> `getSceneSpatial` / `putSceneSpatial` /
`spatialGenerate` / `spatialSendDirector`. Persistence and the handoff to the director
timeline are real; generation borrows the image path, so its provider and artifact inherit
image's NOT_TESTED.

**camera** - Split across three owners: M2.13 camera-spin, M2.8 location spin, and shot
profiles. UI is PARTIAL because there is no single camera workspace. PROV and ART are PARTIAL
because both spin routes are fixture-only and, as of Phase 3, both refuse outside a fixture
run rather than emitting `fixture-spin-*` assets that look like coverage.

**lighting** - No native lighting workspace. What exists is M2.13 scene-state lighting presets
with an approval gate (`m213/scene_state.py`) and the `lighting-supervisor` specialist. There
is no generative relight on the production path.

**storyboard** - `ScriptStoryboardWorkspace.tsx` -> `storyboardGenerate` -> executive
`STORYBOARD_GENERATE`. CD is PASS here and only here among the generative platforms:
`propose_storyboard_generation` is a real preview/apply mutation tool that produces an
approval-gated proposal, and `tests/e2e/codirector/intelligence-storyboard.spec.ts` covers it.

**screenplay** - Script segments, panels and import. Text only, so PROV/PROG are N/A and the
artifact is the persisted script.

**sound** - `AudioStudioWorkspace.tsx` plus M2.9 audio and the M2.10b adapters. PROV is
PARTIAL and honest in both directions: `m210b/adapters/kokoro.py` runs for real when Kokoro is
installed and refuses when it is not, `generic_sandbox.py` raises unavailable, and
`fixture_ci.py` emits a deterministic WAV only under an explicit fixture env. The capability
baseline classifies Audio/SFX/Music as PARTIAL, which matches.

**timeline** - `Timeline.tsx`, `DirectorTracks.tsx`, `GenerateTimelinePanel.tsx` and
`/api/projects/{id}/timeline/*`. Propose and apply are separate, and apply is approval-gated
(`tests/test_m29_production_suite.py` asserts `PermissionError` before approval). No provider
is involved, so the artifact is the persisted director timeline.

**edit** - The only generative-adjacent platform with a PASS in the provider and artifact
columns, because "the provider" is the director timeline itself:
`m29/editing/service.py::execute_job` mutates real clips with undo/redo, and
`tests/test_m29_production_suite.py::test_edit_apply_trim_and_undo` runs it with
`ADEPT_M29_FIXTURE_MODE` explicitly deleted. After the Phase 3 remediation `propose_edit` no
longer returns a fixture proposal outside a fixture run.

**color / subs** - Absent. No UI, no API, no capability, no specialist that owns them.

**comp** - Only the `compositing-supervisor` and `vfx-supervisor` specialist contracts.

**delivery** - Project and pack export through `queue_worker._export`, M2.9 render, and the
M2.14 `delivery` stage. Export runs on the studio job queue, so it inherits the restart gap.

---

## 3. Top-level routes

| Route | UI | API | CAP | Persist | Return | Approval | Notes |
|-------|----|-----|-----|---------|--------|----------|-------|
| `/` (Home) | PASS | PASS | PASS | PASS | PASS | N/A | `tests/e2e/projects/project-crud.spec.ts` covers create/update/duplicate/archive/delete |
| `/project/:id` | PASS | PASS | PASS | PASS | PASS | N/A | Workspace shell; per-workspace status is the table above |
| `/co-director` | PASS | PASS | PASS | PASS | PASS | PASS | Chat, tools and proposals; `tests/e2e/codirector/*` |
| `/source-manager` | PASS | PASS | PASS | PASS | PASS | N/A | `tests/e2e/setup/source-manager.spec.ts` |
| `/model-radar` | PASS | PASS | PARTIAL | PASS | PASS | PASS | Discovery is fixture-only without live sources; sandbox install/validate refuse outside CI after Phase 1 |
| `/virtual-stage` | PASS | PASS | PARTIAL | PASS | PASS | N/A | Capability declared unavailable |
| `/environment-studio` | PASS | PASS | PARTIAL | PASS | PASS | PASS | Covered by `studio-web/e2e/m213-environment-studio.spec.ts`, now included in the default Playwright run |
| `/production-suite` | PASS | PASS | PARTIAL | PARTIAL | PASS | PASS | All nine sections are flag-gated OFF by default; fixture-mode coverage only |

---

## 4. Cross-cutting findings

### 4.1 Studio job queue does not survive a restart (RST = FAIL)

`studio-api/app/main.py` starts the studio job queue with `job_queue.start()`, and
`queue_worker.JobQueue` is an in-process asyncio queue fed by `enqueue(job_id)`. Nothing
re-reads `Job` rows left in `queued` or `running` at shutdown, so a render, imagegen, lipsync
or export interrupted by an API restart stays in the database forever in a non-terminal state
and is never picked up again.

Two neighbouring subsystems do handle this, which is what makes the gap visible rather than
theoretical:

- The Production Executive worker calls `recover_running_jobs` inside `start()`.
- The download queue has an explicit recovery step in the same lifespan block.

This is a real defect, not a fixture problem, and it is the reason every queue-backed platform
above carries RST = FAIL. It is listed as a condition in the M3.0a task report.

### 4.2 Approval gates hold

No platform mutates canon, a timeline, or a sandbox without an explicit approval signal. The
Phase 0 audit found four fake-success paths that reported `installed` / `applied` /
`completed` without doing the work; Phase 1 and Phase 3 closed all of them by refusing outside
an env-gated fixture run. The gates themselves were never the weakness - the weakness was work
that never happened being reported as done.

### 4.3 Co-Director cannot bypass anything

Every mutating tool in `studio-api/app/codirector/tools/registry.py` is a preview/apply pair
that produces a proposal. There is no approve tool, no job-enqueue tool, and no way to
register a tool at runtime - the registry refuses to import if a declared tool has no binding.
Detail in `CODIRECTOR_CAPABILITY_COVERAGE.md`.

### 4.4 Generative artifacts are unproven (updated 2026-07-27 for stills)

Eight of the eighteen platforms have a NOT_TESTED or PARTIAL in their PROV or ART column:
image, video, 3D, blocking, camera, storyboard, sound and delivery. That is the honest
headline of Phase 3 - the wiring is real and refuses to lie, but almost nothing has been
proven end to end against a real provider. `REAL_ARTIFACT_VERIFICATION.md` is the detail.

---

## 5. Tallies

Counted directly from the section 2 grid (18 platforms x 12 links = 216 cells).

| Status | Count |
|--------|------:|
| PASS | 90 |
| PARTIAL | 46 |
| N/A | 66 |
| NOT_TESTED | 9 |
| FAIL | 5 |

| Rollup | Count | Platforms |
|--------|------:|-----------|
| Chain complete on the production path (every non-N/A column PASS) | 1 | `refs` |
| Real provider never exercised (a NOT_TESTED anywhere in the row) | 5 | image, video, blocking, storyboard, delivery |
| Fixture-only provider execution (PROV = PARTIAL) | 4 | 3D, camera, sound, delivery |
| Absent, or specialist advice only | 4 | animation, color, comp, subs |
| Restart-recovery FAIL | 5 | image, video, storyboard, sound, delivery |


## Post-fix snapshot -  2026-07-27

| Platform | Provider/artifact reality | Cross-platform reality |
|---|---|---|
| image | PASS for verified local Z-Image with Asset/Job/file inspection | Co-Director remains indirect |
| video | PARTIAL: reused registered fal artifact, no new queue job | Timeline/export handoff not scenario-complete |
| sound | PASS for real imported WAV placement; generated audio remains partial | B4 closed for import path |
| timeline/edit | PASS for persisted edits and imported audio clips | Approval boundary remains PASS |
| Bible | PASS for covered approval/rejection lifecycle | B10 fixed |
| delivery | PARTIAL: queue/persistence exists; retained situation export absent | Manual beta gate remains closed |

Queue recovery is implemented and test-covered. The matrix does not infer a complete situation
from a component PASS. The completion tally remains 0 EXECUTED / 12 PARTIAL / 0 FAILED / 0 NOT_RUN.
No paid fal job was resubmitted.

---

## 6. Post-fix update (M3.0 completion, 2026-07-27)

Evidence: `docs/m3.0-completion/SITUATION_RERUN_RESULTS.md`, `artifacts/m30-situations/`.

### Wiring that is now proven end to end (fixtures OFF)

| Chain | Result |
| --- | --- |
| M2.9 image generate → Production Executive → ComfyUI Z-Image → Asset + file → version approve → publish-reference → Director timeline | 12/12 |
| Audio import → `place-cue` → Director timeline `audio_clips` / `sfx_clips` | 12/12 (B4 closed for import) |
| Timeline propose → apply-before-approve 403 → approve → apply | 12/12 |
| M2.5 vision validate (local/OpenCV) → vision approve on real PNG | 12/12 |
| Fal Seedance artifact register (no resubmit) → timeline propose/approve/apply on video track | 5/5 targeted situations |
| Export pack of real assets | 12/12 packs; timeline omitted (B18) |

### Wiring that remains broken or unproven

| Chain | Result |
| --- | --- |
| M2.9 video generate `image_to_video` | 0/12 - `sceneId` dropped (B17) |
| Native LTX / WAN scene render | Failed with models present (B20) |
| Audio / music / ambience / SFX generate | `providerMissing: true` |
| M2.11 specialist → user-visible finding | Model runs; finding discarded (B15) |
| M2.14 Storyteller / Sound Producer → provider | Structurally unbound (`honesty: unavailable`) |
| Export → approved timeline in pack | Pack omits `director_json` (B18) |

### Section 4.1 note

RST = FAIL for the studio job queue was fixed in M3.0b (R1) and is not re-opened by this
rerun. The generative-artifact claim in §4.4 is narrowed: still images are proven; video and
generated audio are not.

### Tallies after the rerun

Native production platforms with at least one fixtures-off real-artifact success: **image,
timeline (placement), vision validation, export (assets only), fal reuse handoff**.
Platforms still without a real generative success: **video, animation, lipsync, generated
audio/music/SFX/ambience**.

