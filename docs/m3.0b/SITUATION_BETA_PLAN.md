# M3.0b Situation Beta Plan

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Gate in | M3.0a verdict `READY FOR M3.0b WITH CONDITIONS` |
| Provider Manifest sha256 | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` (UNCHANGED, 39,547 bytes) |
| fal.ai live | NOT_RUN (no key; see section 4) |

## 1. Why this plan is shaped the way it is

M3.0a closed with a specific, uncomfortable finding: **no generative artifact had been
produced by a real provider**, local or cloud. M3.0b is the situation-beta gate, and the
honest question it has to answer is not "did the twelve situations pass?" but "what
actually happened when we ran them, and what would a human beta user hit?"

So this plan deliberately separates two things that are easy to conflate:

- **Orchestration** - does the system understand the brief, route it through departments,
  build a plan, hold approvals, place cues, and reach export? This is executable today.
- **Realisation** - does a frame, a second of audio, or a rendered cut come out the other
  end? This requires a provider that is not installed.

A situation is only marked `EXECUTED` if **both** halves ran. Anything else is `PARTIAL` or
`NOT_EXECUTED`, named as such, per situation, with the HTTP evidence attached.

## 2. Method

Every situation was driven through the real API in a **production configuration**, not the
E2E fixture configuration. Concretely, each run:

- sets the `STUDIO_FEATURE_*` production flags to `1`, and
- explicitly **unsets** `STUDIO_E2E` and `ADEPT_M29_FIXTURE_MODE`.

That second point is the whole reason the results are usable. The E2E harness
(`scripts/e2e-start.mjs`) turns on fixture paths that synthesise assets; running under it
would have produced twelve green situations that prove nothing about a real user. Running
without it means that when something is missing, it is visibly missing.

Runs were executed in-process against the FastAPI app, each against a throwaway
`STUDIO_DATA_DIR`, so no development database was touched.

### Per-situation sequence

1. Create project and scene from the situation brief.
2. `POST /api/codirector/m214/idea` - idea intake and discovery questions.
3. `POST /api/codirector/m214/storyteller/analyze` - emotional arc.
4. `POST /api/codirector/m214/storyteller/handoff` then `/approve` - approval gate.
5. `POST /api/codirector/m211/orchestrate` - multi-department production intelligence.
6. `POST /api/codirector/m214/sound/concept` then `/approve` - sonic plan.
7. `POST /api/codirector/m29/audio/generate` for music, ambience and SFX.
8. `GET /api/codirector/m29/audio/cues` - cue persistence.
9. `POST /api/codirector/m29/image/generate` and `/video/generate` - asset creation.
10. `GET /api/projects/{id}/scenes/{id}/director` - director timeline.
11. `GET /api/codirector/m214/plan/{id}` - production plan view.
12. `POST /api/projects/{id}/export` - export.

Evidence: `artifacts/functional-audit/m30b-12-situations.json`.

### Status vocabulary

| Status | Means |
| --- | --- |
| `EXECUTED` | Orchestration ran **and** a real, verifiable artifact was produced by a real provider. |
| `PARTIAL` | Orchestration ran end to end; realisation did not happen or could not be verified. |
| `NOT_EXECUTED` | The path could not be driven at all in this environment. |
| `NOT_RUN` | Deliberately not attempted because a required credential or engine is absent. |

## 3. The sound and score requirement

M3.0b requires a dedicated sound path, exercised as its own journey rather than as a
by-product of rendering:

> Open completed sample scene, Storyteller emotional arc, Sound Producer sonic plan,
> Cinematographer and Editor timing, Co-Director score, ambience, SFX, timeline, preview,
> mix revise, export.

This was run as a standalone smoke in the production configuration.

| Hop | Endpoint | Result |
| --- | --- | --- |
| Open scene | `POST /api/projects`, `/scenes` | HTTP 200 |
| Storyteller emotional arc | `m214/storyteller/analyze` | HTTP 200, `honesty: "unavailable"` |
| Handoff and approve | `m214/storyteller/handoff{,/approve}` | HTTP 200, `approved: true` |
| Sound Producer sonic plan | `m214/sound/concept` | HTTP 200, `honesty: "unavailable"` |
| Approve sonic plan | `m214/sound/concept/{id}/approve` | HTTP 200 |
| Cinematographer timing | `m214/messages` | HTTP 200 |
| Editor timing | `m214/messages` | HTTP 200 |
| Score (music) | `m29/audio/generate` | HTTP 200, `providerMissing: true`, cue `draft` |
| Ambience | `m29/audio/generate` | HTTP 200, `providerMissing: true`, cue `draft` |
| SFX | `m29/audio/generate` | HTTP 200, `providerMissing: true`, cue `draft` |
| Audio plan validate | `m29/audio/plan/propose` | HTTP 200, `ok: true` |
| Timeline | `GET .../director` | HTTP 200, but `audio_clips: []` |
| Preview | reads director timeline | No audio to preview |
| Mix revise | `m29/audio/process` | HTTP 200, but a silent no-op |
| Export | `POST /api/projects/{id}/export` | HTTP 200, job queued |

Evidence: `artifacts/functional-audit/m30b-sound-path-smoke.json`, `m30b-mix-revise.json`,
`m30b-audio-ops-contract.json`.

The sound path is therefore **PARTIAL**: every hop answers, the plan and approval structure
is real and persisted, and no audio exists at the end of it. Two hops are worse than merely
empty and are recorded as blockers B3 and B4 in `FINAL_BETA_BLOCKERS.md`.

One genuinely real artifact was produced during this work, and it is worth stating
precisely because it is the only one. ffmpeg loudness normalisation on a supplied WAV stem
produced a real 288,078-byte output resampled from 44,100 Hz to 48,000 Hz. That is real
media **processing**. It is not generation, and it does not realise any situation.

## 4. fal.ai coverage

`fal_key_present()` returns `False`, `FAL_KEY` and `FAL_API_KEY` are unset, and
`ADEPT_M30A_FAL_LIVE` is unset. The live fal Playwright test
(`tests/e2e/m30a/m30a-fal-ai-provider.spec.ts:84`, "live: a real key verifies and unlocks
cloud engines") skipped itself. Every fal row below is therefore `NOT_RUN` - not failed,
and certainly not passed.

### 4.1 Catalogue as wired today

| Engine | Model id | Mode | Durations (s) | End image | Media |
| --- | --- | --- | --- | --- | --- |
| `fal_seedance` | `bytedance/seedance-2.0/image-to-video` | image_to_video | 4-12 | yes | video |
| `fal_kling` | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | image_to_video | 5, 10 | no | video |
| `fal_veo` | `fal-ai/veo3.1/image-to-video` | image_to_video | 4, 6, 8 | no | video |
| `fal_runway` | `fal-ai/runway-gen3/turbo/image-to-video` | image_to_video | 5, 10 | no | video |

Two structural limits follow directly from that table and shape every recommendation below:

- **All four are image-to-video.** There is no text-to-video fal engine, so a first frame
  must exist before fal can be asked for anything.
- **`FAL_IMAGE_MODELS` is empty.** No fal image family has a wired endpoint id, so the first
  frame cannot come from fal either. It has to come from the local ComfyUI ImageGen path,
  which is not installed here.

That is a chain with a missing first link, and it is the most important fact about fal
coverage in M3.0b.

### 4.2 Recommended fal use per situation

| # | Situation | Recommended engine | Why | Status |
| --- | --- | --- | --- | --- |
| 1 | Live-action dramatic | `fal_seedance` | End-image support holds a performance beat across a cut | NOT_RUN |
| 2 | Suspense/thriller | `fal_seedance` | Durations up to 12s sustain a held shot | NOT_RUN |
| 3 | Music video | `fal_kling` | Fluid motion, 10s blocks cut to bar lines | NOT_RUN |
| 4 | Animated | `fal_kling` | Prompt adherence for non-photoreal styling | NOT_RUN |
| 5 | Commercial | `fal_veo` | 8s default matches a 30s spot cut into beats | NOT_RUN |
| 6 | Dialogue-heavy two-person | `fal_veo` | Optional audio; shot-reverse-shot in 4/6/8s | NOT_RUN |
| 7 | Action/chase | `fal_runway` | Fast turnaround for many iteration passes | NOT_RUN |
| 8 | Fantasy/sci-fi | `fal_seedance` | Director control over large camera moves | NOT_RUN |
| 9 | Documentary/interview | `fal_veo` | Static, long-lens realism | NOT_RUN |
| 10 | Stylized 2D/anime | `fal_kling` | Holds flat-shaded styling across frames | NOT_RUN |
| 11 | Product/location reconstruction | `fal_seedance` | End image pins the reconstruction target | NOT_RUN |
| 12 | Full short-form capstone | multi-model (below) | Different demands per sequence | NOT_RUN |

### 4.3 Multi-model chain plan (situation 12)

This is the required chain plan. It is a plan; it has not been run.

1. **Still frames** - local ComfyUI ImageGen produces key frames for three sequences.
   fal cannot do this step, because `FAL_IMAGE_MODELS` is empty.
2. **Sequence A, the paper crane (stylised)** - `fal_kling`, 10s, first frame from step 1.
   Chosen for styling stability over photoreal motion.
3. **Sequence B, the 1970s diner (reconstruction)** - `fal_seedance`, 8s, first frame from
   step 1 and end image from step 1, so the move lands on the verified reconstruction. This
   is the only engine of the four that can be pinned at both ends.
4. **Sequence C, the ferry crossing (documentary)** - `fal_veo`, 8s, static framing.
5. **Assembly** - the three returned clips are placed on the director timeline, scored and
   ambience-treated through the M2.9 audio path, and exported.

The chain exercises three different fal engines plus a local engine, and it is the
strongest available test of cross-provider continuity. It is **blocked at step 1** for two
independent reasons: no fal key, and no local image engine installed.

## 5. Evaluation template

Each situation in `PRODUCTION_SCENARIO_MATRIX.md` is scored against these fifteen
categories. Ratings are `Strong`, `Adequate`, `Weak`, `Absent`, or `Not observable`.
`Not observable` is used deliberately and often: if no asset was produced then visual
consistency was not tested, and claiming otherwise would be the exact dishonesty this
milestone exists to avoid.

| # | Category | What it asks |
| --- | --- | --- |
| 1 | Story understanding | Did the system grasp what the brief is about? |
| 2 | Emotional intelligence | Did it identify the emotional arc and subtext? |
| 3 | Production planning | Did it produce a usable plan with stages? |
| 4 | Department coordination | Did specialists hand off and message each other? |
| 5 | Asset creation | Was anything actually created? |
| 6 | Visual consistency | Do assets hold together across shots? |
| 7 | Audio quality | Is the sound usable? |
| 8 | Continuity | Is state carried across scenes and departments? |
| 9 | Editing | Can cuts and timing be expressed and applied? |
| 10 | Interface clarity | Would a user understand what happened? |
| 11 | Automation reliability | Does the pipeline complete without hand-holding? |
| 12 | Error recovery | What happens when something fails or restarts? |
| 13 | Speed | Is turnaround tolerable? |
| 14 | User control | Can the user steer, approve, and override? |
| 15 | Final result quality | Is the output something a user would keep? |

Alongside the ratings, each situation carries free-form findings under: what worked, what
was confusing, weak assumptions, department disagreement, UI friction, context loss, manual
correction required, races and persistence, generation quality, recovery, and fixes
required before Manual User Beta.
