# M3.0 Completion - Situation Rerun Results (Phases 9-10)

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-27 |
| API under test | `http://127.0.0.1:8760`, isolated data dir `C:\Users\bradj\AppData\Local\Temp\adept-m30-sit-data` |
| Fixtures | OFF. `STUDIO_E2E` and `ADEPT_M29_FIXTURE_MODE` unset; every image job recorded `fixture: false` and `mockAdapter: false` |
| Providers | ComfyUI 0.28.2 (RTX 5090) reachable; Ollama Ready with `gemma4:31b-it-qat` |
| Evidence | `artifacts/m30-situations/` - 12 production records, 12 intelligence records, `situation-finish.json`, `situation-vision.json`, `persistence-check.json`, `situation-03-music-sync.json`, `run-environment.json` |
| fal.ai | No job submitted. The one paid Seedance artifact from M3.0a was re-registered into 5 projects and never regenerated. |
| Commits | None. |

## 1. Tally

| Status | Count | Situations |
| --- | --- | --- |
| EXECUTED | 0 | - |
| PARTIAL | 12 | 1-12 |
| FAILED | 0 | - |
| NOT_RUN | 0 | - |

**No situation is EXECUTED, and the reason is narrow enough to state in one sentence:**
every one of the twelve situations is a moving-image brief, and no situation produced a
moving image of its own. Local video generation failed 12/12 with the same error, the two
native render engines both fail inside their ComfyUI workflows, and fal was deliberately
not re-run because that would have re-spent money on a job already paid for.

That is the same headline count as M3.0b, and it would be misleading to leave it there,
because almost everything underneath it changed. M3.0b recorded twelve situations in which
nothing at all was produced. This run produced, persisted, inspected and approved a real
artifact in every one of the twelve.

| Chain link | M3.0b | This run |
| --- | --- | --- |
| Real artifact generated for this brief by a real provider | 0/12 | **12/12** (ComfyUI Z-Image) |
| Artifact persisted and re-readable out of process | 0/12 | **12/12** |
| Co-Director inspected the actual pixels | 0/12 | **12/12** (M2.5 local vision validation) |
| Human approval recorded against the artifact | 0/12 | **12/12** (version approve + publish reference) |
| Artifact handed off onto the Director timeline | 0/12 | **12/12** |
| Audio on the Director timeline | 0/12 | **12/12** (imported, not generated) |
| Moving image on the Director timeline | 0/12 | 5/12 (reused fal artifact, not brief-matched) |
| Moving image generated for the brief | 0/12 | **0/12** |
| Export pack containing the real assets | 0/12 | **12/12** |
| Export pack containing the approved timeline or a rendered cut | 0/12 | **0/12** |

### How the grade was assigned

EXECUTED required all five links - real artifact, persisted, Co-Director inspect, human
approval, handoff - **completed in the medium the situation is about**. All five links now
hold for the still-image department in all twelve. None of the twelve is a still-image
brief. Grading on the frame instead of the shot would have produced a 12/12 that no
reviewer watching the output would recognise, so it was not done.

## 2. What is actually real this time

### 2.1 Twelve generated images, verified four ways

Each situation submitted its own shot prompt to `POST /api/codirector/m29/image/generate`,
which queued a Production Executive job that ran the local ComfyUI Z-Image workflow.
Verification for each: the job reported `provider: comfy` and `mockAdapter: false`; the file
came back over HTTP with a PNG magic number and a sha256; the `Asset` row and the file were
read back from a **separate read-only SQLite connection outside the API process**; and the
bytes were decoded by OpenCV during vision validation.

| # | Situation | Image bytes | Job seconds | Vision score | Band | Measured sharpness |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Live-action dramatic | 1,183,967 | 15.1 | 96.0 | approve | 45.5 |
| 2 | Suspense/thriller | 1,065,351 | 9.1 | 96.0 | approve | 79.6 |
| 3 | Music video | 1,755,008 | 6.0 | 96.0 | approve | 595.5 |
| 4 | Animated | 1,102,782 | 6.1 | 96.0 | approve | 55.4 |
| 5 | Commercial | 894,691 | 6.0 | 96.0 | approve | 182.5 |
| 6 | Dialogue-heavy two-person | 1,026,364 | 6.1 | 96.0 | approve | 142.0 |
| 7 | Action/chase | 1,469,255 | 6.0 | 96.0 | approve | 304.2 |
| 8 | Fantasy/sci-fi | 1,717,445 | 6.1 | 96.0 | approve | 1835.3 |
| 9 | Documentary/interview | 1,042,907 | 6.0 | 96.0 | approve | 117.7 |
| 10 | Stylized 2D/anime | 984,988 | 6.1 | 96.0 | approve | 108.6 |
| 11 | Product/location reconstruction | 1,322,515 | 9.1 | 96.0 | approve | 317.4 |
| 12 | Full short-form capstone | 990,560 | 6.0 | 79.99 | reject | 29.3 |

Two were opened and looked at rather than only measured. Situation 1 returned a dawn-lit
kitchen two-shot of a man and a younger woman across a table, which is the brief. Situation
3 returned a dancer mid-spin in an autumn field, which is also the brief. The images are
competent and on-prompt, not placeholders.

Total media written across the twelve projects: 22,570,831 bytes over 29 assets, all present on disk.

### 2.2 The Co-Director inspected the pixels, and said what it could not judge

`POST /api/codirector/vision/validate` with `provider: local` ran seven validators over each
real PNG. The technical validator decoded the file with OpenCV and reported measured values -
dimensions, mean luma, Laplacian variance - and the scores differ per image because the
images differ. Situation 12 scored 79.99 and banded `reject` with the recommendation *"Image appears soft (laplacian variance=29.3)"*, against 96.0 for situation 1. That is a real machine judgement about a real frame, and it is the first time in this programme that the Co-Director has been shown to look at generated output rather than at a record of it.

It is equally clear about its limits. Four of the seven validators - identity, camera,
composition and colour - return `inconclusive` with `Identity ML unavailable` and similar,
because `LocalVisionProvider` sets every `ml*Available` flag to `False` rather than inventing
a pass. Only the technical validator is measuring anything. A 96.0 here means "nothing
measurable is wrong with the file", not "this is a good shot".

**Defect found while doing this.** Situation 12's report banded `reject`, and
`POST /api/codirector/vision/approve` accepted it with `override: false` and recorded the
decision as `approved` rather than `override_approve`. The override concept exists in the
schema and nothing enforces it, so a failing frame can be signed off as if it had passed.
Filed as B19.

Separately, every generated image is 1024x1024 while the projects are 1280x720. No validator
compares the artifact's aspect ratio to the project's, so a frame that cannot be cut into the
timeline as-is scores 96.

### 2.3 Audio reaches the timeline in all twelve (B4 holds under load)

Each situation synthesised a real PCM WAV locally, imported it, and placed it as a cue. The
import path put a clip on the Director timeline every time: eleven on the audio track, one on
the SFX track for the action situation. Read back out of process, `director_json` carries the
clip and the asset id for all twelve. B4 is closed for the import path and stays closed across
twelve consecutive projects.

The honest boundary: **no audio was generated**. `audio/generate` still answers
`providerMissing: true` with a `queued` cue and no asset, exactly as in M3.0b. The WAVs are
stdlib-synthesised tones supplied by the harness, so they prove the import-place-persist path,
not a sound department.

### 2.4 Approval gates held twelve times out of twelve

Each situation attempted `timeline/{id}/apply` before approving. All twelve were refused with
HTTP 403 `timeline apply blocked: human approval required`, then applied after an explicit
approve. The same pattern held for the second, video-track proposal in the 5 fal situations.
The M2.14 storyteller handoff and the sonic concept both had to be approved before they
reported `approved: true`. Nothing mutated a timeline or the Bible without a human step.

## 3. The intelligence finding, which is worse than it looks

With `ADEPT_CODIRECTOR_PROVIDER=ollama`, `gemma4:31b-it-qat` Ready, and the M3.0 fix that
turns on `use_provider` when the provider is healthy, all twelve orchestrations ran against a
real model. This was not a cheap call: **112 specialist runs over 30 minutes of wall clock**,
with per-specialist durations of 7-51 seconds recorded in the trace. The model genuinely ran.

**Of 112 specialist runs, 1 produced any surviving model-authored content.**

Every other specialist returned its own display name as both its summary and its
recommendation:

```json
"summaries":       ["Story Analyst", "Production Bible Manager", "Continuity Analyst", ...]
"recommendations": ["Story Analyst", "Production Bible Manager", "Continuity Analyst", ...]
```

### 3.1 Root cause: the analysis is produced and then thrown away

The model is not failing. It is answering well, and the answer is being discarded.

Asked to analyse the situation-1 brief, `gemma4:31b-it-qat` returned this
(`artifacts/functional-audit/m30-ollama-raw.json`, captured directly from Ollama with the
same system and user prompt the runner builds):

```json
{
  "specialist-finding-v1": {
    "analysis": {
      "core_premise": "A reunion and communication event between a father and daughter
                       following a ten-year period of total estrangement.",
      "narrative_tension": "High; driven by the weight of unsaid words, accumulated
                            resentment, and the uncertainty of the other party's receptiveness.",
      "themes": ["Forgiveness", "The passage of time", "Family trauma", ...],
      "potential_plot_beats": ["The initial awkwardness of the first words", ...]
    }
  }
}
```

That is exactly the story understanding M3.0b recorded as absent. It never reaches the user.
`SpecialistRunner._validate_or_repair` calls `SpecialistFinding.model_validate(raw)`, which
fails because the payload is nested under a `specialist-finding-v1` wrapper and uses the
model's own field names instead of `summary` / `recommendation`. The `except ValidationError`
branch then does this:

```python
repaired["summary"] = str(repaired.get("summary") or definition.display_name)
repaired["recommendation"] = str(repaired.get("recommendation") or repaired["summary"])
```

`raw` has no `summary`, so the summary becomes `"Story Analyst"`, the recommendation becomes
the summary, and the analysis is dropped on the floor. The finding is then stamped
`status: "validated"` and the response reports `honesty: "provider"`. Nothing anywhere
records that a model response was discarded.

This is a regression in what the user sees. M3.0b's heuristic path at least said
*"Director recommends proceeding with bounded Production Bible context"* and labelled itself
`honesty: unavailable`. This run shows a bare display name labelled `honesty: provider`.
Filed as B15.

### 3.2 So the analysis still does not depend on the brief

M3.0b's central finding survives intact, for a new reason. Digests differ across the twelve
runs, but only because different specialists survived. Restricting to the 8 runs where all 
ten specialists completed, the analysis content - every summary, every recommendation, every
missing-asset line - collapses to **1 digest**.

### 3.3 The scaffold that fills the gap is scenery from another film

Because the findings are sparse, `ProductionIntelligenceOrchestrator` calls
`_heuristic_enrichment(brief)`, which branches on three keywords (`lab`, `alien`,
`scientist`) and otherwise returns a hard-coded literal. None of the twelve briefs contains
those words, so all twelve received the same fallback. The father-daughter kitchen
reconciliation, the music video, the coffee commercial and the diner reconstruction were all
told they were missing:

- Approved Maya character reference
- Lab corridor architecture plate
- Containment cylinder hero prop reference
- Emergency strobe practical reference
- Radio prop + UI overlay still (optional)

with a shot plan built around a corridor, a containment cylinder and emergency strobes. This
is more damaging than the M3.0b constant, which was at least generic. A beta user reading
`missingAssets` would go and source props for a film they are not making. Filed as B16.

### 3.4 Three specialists still never run, and now some time out

`storyteller`, `sound-producer` and `virtual-production-coordinator` failed in all twelve runs
with a bare `KeyError` on their own id - they are declared in `DEFAULT_PIPELINE` and absent
from `SpecialistRegistry`. That is B8, unchanged, 37 occurrences.

New under real inference: **7 specialist timeouts** at the 50-second cap, concentrated in the
runs that overlapped GPU work. Situation 7 finished with 7 of 10 specialists and situation 4
with 8. In every case the run still returned HTTP 200 with `status: completed_with_errors`,
and the top-level analysis was silently backfilled by the same enrichment scaffold, so a
caller cannot tell a 10-specialist run from a 7-specialist one by looking at the analysis.

### 3.5 M2.14 is not covered by the provider fix at all

The idea intake, the Storyteller arc and the Sound Producer concept reported
`honesty: "unavailable"` in all twelve runs with Ollama Ready. This is not a health check
failing - `m214/honesty.py::default_honesty` returns `unavailable` unconditionally outside
E2E, because the M2.14 specialists are structurally unbound to any provider. Every situation
received the same arc: `spark -> tension -> turn`, `intimate`, `personal`. The M3.0
`use_provider` change reaches M2.11 specialists only.

## 4. Motion: the one thing that would have made a situation EXECUTED

### 4.1 M2.9 video generate fails 12/12 on a dropped field

Every situation called `POST /api/codirector/m29/video/generate` in `image_to_video` mode with
`sceneId` and `firstFrameAssetId` set, having just generated that first frame. Every job
failed with:

```
image_to_video requires sceneId with frame assets
```

`VideoService.generate` accepts `sceneId`, but the executive job payload it enqueues does not
carry it through to `run_video`, so the check sees `None`. The caller did supply the field.
Filed as B17.

### 4.2 Both native engines fail inside their ComfyUI workflows

Situation 1 additionally drove `POST /api/projects/{id}/render` directly, once per engine,
bypassing M2.9:

- **LTX** - job `failed`. ComfyUI job failed: [['execution_start', {'prompt_id': 'e292b89b-742c-4977-a18d-31476f2e400c', 'timestamp': 1785139390971}], ['execution_cached', {'nodes': [], 'prompt_id': 'e292b89b-742c-4977-a18d-31476f2e400c', 'timestamp': 1785139390973}], ['execution_error
- **WAN** - job `failed`. ComfyUI prompt rejected (400): {"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation", "details": "", "extra_info": {}}, "node_errors": {"4": {"errors": [{"type": "value_not_in_list", "message": "Value not in list"

Neither is a missing-model problem: ComfyUI reports the LTX checkpoint and the WAN models
present and readable. Both are defects in the workflow graphs the API submits.

### 4.3 The fal artifact was reused, never regenerated

The Seedance text-to-video clip paid for during M3.0a was registered as an `Asset` in 5 projects (S01, S03, S04, S11, S12) by `scripts/m30_register_fal_artifact.py`, which copies the existing file and writes the row. Every run printed `no fal job was submitted`. In those 5 projects the clip was then proposed onto the video track, refused with 403 until approved, and applied - so the motion handoff path is proven end to end. What it does not prove is motion generation, and the clip's content has nothing to do with those briefs.

## 5. Music video (situation 3): what sync actually does

Driven as its own experiment at 120 BPM, 2.0s per bar
(`artifacts/m30-situations/situation-03-music-sync.json`).

**What works.** The audio bed is on the timeline at 0.0s for 8.0s. Four bar-line accents were
placed at 0.0, 2.0, 4.0 and 6.0 seconds and all four landed exactly, and a tempo-cut proposal
placing image clips on the same grid was refused before approval, approved, applied, and read back with `image_clips` starting at [0.0, 0.0, 2.0, 4.0, 6.0]. If you compute the grid yourself, the timeline will hold it precisely.

**What does not.** There is no tempo primitive anywhere in the system.

- `AudioPlaceCueBody` has no `syncEvent` field at all, so a `syncEvent` sent to `place-cue` is
  dropped by the schema before any handler sees it.
- `audio/plan/propose` **does** accept and echo it - the probe got back placements carrying
  `syncEvent: "bar-2"` and `syncEvent: "downbeat"`, `validated: true` - and nothing
  downstream ever reads it.
- Nothing detects beats. The BPM in this experiment came from the harness, not from the audio.

So beat sync is not merely unimplemented, it is implied by two schemas and confirmed by a
validation pass. That is B13, and this run sharpens it: the field is accepted and validated on
one endpoint and does not exist on the other.

## 6. Capstone (situation 12): honest PARTIAL

The full chain was driven: brief, idea intake, storyteller profile, approved handoff, approved
sonic concept, real WAV imported and placed, real image generated, vision-validated and
approved, published as a reference, the reused fal clip proposed and applied to the video
track after a 403, and an export.

The timeline at the end holds one audio clip, one image clip and one video clip, each pointing at an asset that exists on disk. The export job reported `done` and wrote a pack of 4 files, 2,189,165 bytes: the three real media files and `project.json`.

**It is PARTIAL for two reasons, both verified rather than assumed:**

1. **The pack does not contain the timeline.** `project.json`'s scene object carries only
   ``duration_sec`, `engine`, `id`, `index`, `lipsync_output_path`, `name`, `output_path`, `prompt``. `QueueWorker._export` serialises those eight scene fields and never touches `director_json`, so the placements a human just approved - the whole point of the session - are absent from the deliverable. Re-importing this pack would produce three loose assets and no edit. Filed as B18.
2. **There is no cut.** `output_path` is `null` for every scene, because no video was rendered.
   The pack is an asset bundle, not a film.

A three-minute short was asked for. What exists is one frame, one tone, one unrelated clip, and
a set of correctly-gated approvals over them.

## 7. Per-situation results

All twelve: real image generated, persisted, vision-inspected, version-approved, published as
a reference, placed on the timeline, audio placed, apply-before-approve refused 403, export
`done`. The column below records only what is specific to that situation.

| # | Situation | Status | Why not EXECUTED | Situation-specific finding |
| --- | --- | --- | --- | --- |
| 1 | Live-action dramatic | PARTIAL | No moving image; both native engines failed | The strongest image of the twelve (sharpness 45.5) and the only one that also probed LTX and WAN directly. A held performance beat cannot be judged from a still. |
| 2 | Suspense/thriller | PARTIAL | No moving image; no generated sound | Sound-led dread with no sound department. The imported tone is a harness artifact, and `fal_seedance`'s 12s duration - the only engine long enough - was not re-run. |
| 3 | Music video | PARTIAL | No moving image; cuts are hand-computed | Bar-line placement is exact, but the grid came from the harness. `syncEvent` is accepted by `plan/propose` and does not exist on `place-cue`. |
| 4 | Animated | PARTIAL | No moving image; style consistency untestable | Styling held across frames is the whole demand and there is only one frame. Two specialists also timed out here, leaving 8 of 10. |
| 5 | Commercial | PARTIAL | No moving image; no 30s structure | Product accuracy is judgeable on the still, but nothing validates it against a product reference, and a 30s spot needs blocks that do not exist. |
| 6 | Dialogue-heavy two-person | PARTIAL | Lipsync NOT_RUN | No TTS and no lipsync provider, so the two lipsync tracks stayed `enabled: false` with null audio. The dialogue demand was never reachable. |
| 7 | Action/chase | PARTIAL | No moving image; fastest-motion brief | Finished with 7 of 10 specialists - the worst of the twelve - after three timeouts. Its audio landed on the SFX track rather than the audio track, the only such case. |
| 8 | Fantasy/sci-fi | PARTIAL | No moving image; camera moves untestable | The image carries the world-building well. 8 of 10 specialists completed. |
| 9 | Documentary/interview | PARTIAL | No moving image; room tone imported not generated | Closest to judgeable on a still - static realism is the demand - but ambience generation still returns `providerMissing: true`. |
| 10 | Stylized 2D/anime | PARTIAL | No moving image; stylised motion untestable | 9 of 10 specialists completed. |
| 11 | Product/location reconstruction | PARTIAL | No moving image; **references never supplied** | The honest scope: the brief says rebuild a diner from three reference photographs and no reference photographs were provided, so reference fidelity was not exercised at all. A diner interior was generated from a text prompt. That is not a reconstruction. |
| 12 | Full short-form capstone | PARTIAL | No cut; export omits the timeline | Full chain driven and approved. The export pack carries the three real assets and neither the approved timeline nor a rendered cut. |

## 8. Persistence and durability

Checked from a second process against the same SQLite file opened read-only, so nothing was
read out of the API's own session.

| Table | Rows |
| --- | --- |
| `projects` | 13 |
| `assets` | 31 |
| `jobs` | 32 |
| `m29_audio_cues` | 30 |
| `m29_asset_versions` | 26 |
| `m29_timeline_proposals` | 13 |
| `m211_decision_records` | 24 |
| `m211_execution_traces` | 4 |

Every asset row resolved to a file that exists, 22,570,831 bytes in total, and every `director_json` re-parsed with its clips intact.

## 9. Speed

| Stage | Wall clock |
| --- | --- |
| Production stage, 12 situations | 132 seconds total (9.1s median per situation) |
| Local Z-Image per frame | 6-15 seconds |
| Intelligence stage, 12 orchestrations | 30 minutes total (81s-268s per situation) |

The production path is fast enough to be pleasant. Orchestration at one to four and a half
minutes per brief, to produce a list of specialist display names, is not a trade a user would
make if they knew what they were getting.

## 10. New and updated blockers

| ID | Severity | Summary |
| --- | --- | --- |
| B15 | BLOCKER | Real specialist analysis is discarded by `_validate_or_repair` and replaced with the specialist's display name, then labelled `honesty: provider`. |
| B16 | MAJOR | `_heuristic_enrichment` fills the gap with a hard-coded lab-corridor scaffold, so every brief is told it is missing containment-cylinder and emergency-strobe references. |
| B17 | BLOCKER | `sceneId` is dropped between `VideoService.generate` and `run_video`; every `image_to_video` job fails with `requires sceneId with frame assets`. |
| B18 | MAJOR | The export pack omits `director_json`, so an approved timeline is not in the deliverable. |
| B19 | MAJOR | A `reject`-band vision report can be approved with `override: false` and is recorded as a plain `approved`. |
| B20 | MAJOR | Both native video engines fail inside their ComfyUI workflows (LTX null CLIP; WAN VAE path separators) with all required models present. |
| B21 | MINOR | Specialist timeouts silently reduce the roster and the analysis is backfilled by the scaffold, so a 7-specialist run is indistinguishable from a 10-specialist one. |

Updated: **B4 closed** for the import path, held across twelve projects. **B13 sharpened** - `syncEvent` is accepted and validated by `plan/propose` and absent from `place-cue`. **B7 partially addressed and newly mislabelled** - the provider now runs, and B15 discards it. **B5 partially closed** - a real image provider works; audio, video and dialogue have none. **B8 unchanged**, 37 occurrences across twelve runs.

## 11. Constraints honoured

- No commit was made, and the plan file was not edited.
- Fixtures were off for every situation run; `fixture: false` and `mockAdapter: false` are
  recorded on each image job.
- No fal job was submitted. The existing artifact was copied and re-registered.
- No fal key material was printed, logged or written to any artifact.
- No claim of 12/12 EXECUTED, and no claim that any moving image was generated.
