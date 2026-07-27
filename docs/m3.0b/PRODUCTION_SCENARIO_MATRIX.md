# M3.0b Production Scenario Matrix

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Configuration | Production flags on; `STUDIO_E2E` and `ADEPT_M29_FIXTURE_MODE` unset |
| Evidence | `artifacts/functional-audit/m30b-12-situations.json` |

## 1. Headline

All twelve situations were driven through the full API sequence. Every call answered.
**Zero situations reached `EXECUTED`**, because no situation produced a verifiable
artifact from a real provider. All twelve are `PARTIAL`.

| Status | Count |
| --- | --- |
| EXECUTED | 0 |
| PARTIAL | 12 |
| NOT_EXECUTED | 0 |
| PLANNED-ONLY | 0 |

PLANNED-ONLY is zero because every situation really was run. That distinction matters, and
inflating it in either direction would misrepresent the state of the build.

## 2. The finding that dominates every row

One result has to be stated before the per-situation table, because it changes how every
subsequent row should be read.

**The M2.11 orchestration output is identical for all twelve briefs.** After normalising
UUIDs, the analysis payload from `POST /api/codirector/m211/orchestrate` collapses to a
single digest (`ce0b59f48418`) across a father-daughter reconciliation, a drone chase
through a night market, a coffee commercial, an anime rooftop duel, and eight others.

Every specialist returns the same sentence with only its own name substituted:

> Director recommends proceeding with bounded Production Bible context.
> Cinematographer recommends proceeding with bounded Production Bible context.
> Music Supervisor recommends proceeding with bounded Production Bible context.

The Storyteller is the same story. All twelve briefs produce the identical emotional
profile:

| Field | Value returned for all 12 |
| --- | --- |
| `emotional_arc` | `spark -> tension -> turn` |
| `tone` | `intimate` |
| `stakes` | `personal` |
| `subtext` | `Unspoken need beneath dialogue` |

The only per-situation variation is the brief echoed back verbatim into
`character_beats[0].note` and the context pack. The Sound Producer inherits the constant:
every sonic plan reads `Score supports arc: spark -> tension -> turn`.

To the system's credit, it says so. Storyteller, Sound Producer and the plan view all
carry `honesty: "unavailable"` or `"scaffolded"`, and the specialist assumptions read
`Heuristic specialist output (E2E/mock path)`. The labelling is correct. But it means
**story understanding and emotional intelligence are not partially working, they are
absent** - and the same twelve-word arc would be handed to a beta user pitching a horror
short and a nappy commercial.

Two further contradictions in the same response:

- `modelUsed: "gemma"` at the top level, while every specialist reports `modelId: null`.
  Nothing consulted a model.
- `status: "completed_with_errors"` on all twelve runs, returned under HTTP 200. A caller
  checking the HTTP code sees success.

## 3. Scenario matrix

In the Sound/score column, `REQ` means the situation cannot be judged without sound.

### 3.1 Situations 1-6

| # | Situation | Format | Technical demands | Departments engaged | Native platforms | Providers needed | fal.ai use | Sound/score | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Live-action dramatic | Single scene, 8s | Performance beat, held silence, shot-reverse-shot | Storyteller, Story Analyst, Bible Manager, Continuity, Director, Cinematographer, Sound Designer, Music Supervisor, Editor, QA | M2.14 Unified, M2.11 Intelligence, M2.9 image/video/audio, Director Timeline, Export | Local ImageGen + video engine, or fal I2V | `fal_seedance` (end image holds the beat) | REQ | PARTIAL |
| 2 | Suspense/thriller | Single scene, 8s | Sustained tension, long take, sound-led dread | same 10 specialists | M2.14, M2.11, M2.9, Director Timeline, Export | Local or fal I2V | `fal_seedance` (up to 12s) | REQ | PARTIAL |
| 3 | Music video | Sequence, 8s sample | Beat sync, tempo-locked cuts, continuous move | same 10 specialists | M2.14, M2.11, M2.9 audio + video, Director Timeline | Local or fal I2V; music source | `fal_kling` (10s blocks on bar lines) | REQ | PARTIAL |
| 4 | Animated | Single scene, 8s | Non-photoreal styling held across frames | same 10 specialists | M2.14, M2.11, M2.9 image/video | Local ImageGen + fal I2V | `fal_kling` (prompt adherence) | REQ | PARTIAL |
| 5 | Commercial | 30s spot, 8s sample | Product accuracy, brand-safe framing, tight cut | same 10 specialists | M2.14, M2.11, M2.9, Editing, Export | Local or fal I2V | `fal_veo` (8s default) | REQ | PARTIAL |
| 6 | Dialogue-heavy two-person | Single scene, 8s | Lipsync, dialogue mix, eyeline continuity | same 10 + Lipsync path | M2.14, M2.11, M2.9 audio + lipsync, Director Timeline | TTS/dialogue engine + I2V + lipsync | `fal_veo` (optional audio) | REQ | PARTIAL |

### 3.2 Situations 7-12

| # | Situation | Format | Technical demands | Departments engaged | Native platforms | Providers needed | fal.ai use | Sound/score | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Action/chase | Sequence, 8s sample | Fast motion, spatial coherence across cuts | same 10 specialists | M2.14, M2.11, M2.9 video, Editing | Local or fal I2V | `fal_runway` (fast iteration) | REQ | PARTIAL |
| 8 | Fantasy/sci-fi | Single scene, 8s | World-building consistency, large camera moves | same 10 specialists | M2.14, M2.11, M2.9, M2.13 Environment Studio | Local ImageGen + fal I2V | `fal_seedance` (director control) | REQ | PARTIAL |
| 9 | Documentary/interview | Single scene, 8s | Static realism, long-lens, room tone | same 10 specialists | M2.14, M2.11, M2.9 audio + video | Local or fal I2V; ambience source | `fal_veo` (static realism) | REQ | PARTIAL |
| 10 | Stylized 2D/anime | Single scene, 8s | Flat-shade consistency, stylised motion | same 10 specialists | M2.14, M2.11, M2.9 image/video | Local ImageGen + fal I2V | `fal_kling` | REQ | PARTIAL |
| 11 | Product/location reconstruction | Single scene, 8s | Reference fidelity, camera spin, geometry | same 10 + Virtual Production Coordinator | M2.14, M2.11, M2.13 Environment Studio, M2.9 | Local ImageGen + fal I2V | `fal_seedance` (end image pins target) | REQ | PARTIAL |
| 12 | Full short-form capstone | 3-minute short | All of the above, plus cross-sequence continuity | all specialists | Every platform above + Export | Local ImageGen + 3 fal engines | Multi-model chain (Kling + Seedance + Veo) | REQ | PARTIAL |

### 3.3 What PARTIAL resolves to per situation

Identical across all twelve, which is itself the finding:

| Sub-step | Result |
| --- | --- |
| Project + scene created | HTTP 200 |
| Idea intake, discovery questions | HTTP 200 |
| Storyteller arc | HTTP 200, constant output, `honesty: unavailable` |
| Handoff + approval gate | HTTP 200, `approved: true`, persisted |
| M2.11 orchestration (10 specialists) | HTTP 200, identical output, `completed_with_errors` |
| Sonic plan + approval | HTTP 200, constant output, `honesty: unavailable` |
| Audio generate (music, ambience, SFX) | HTTP 200, `providerMissing: true`, cue `draft`, `assetId: null` |
| Audio cues persisted | HTTP 200, 3 cues per project |
| Cues reach director timeline | **No** - `audio_clips: []` (blocker B4) |
| Image generate | HTTP 200, `status: draft`, phantom `assetId` (blocker B1) |
| Video generate | HTTP 200, `status: draft`, phantom `assetId` (blocker B1) |
| Director timeline | HTTP 200, real prompt and camera segments |
| Production plan view | HTTP 200, 8 stages, `honesty: scaffolded` |
| Export | HTTP 200, job queued |

## 4. Per-situation evaluation

Ratings are `Strong`, `Adequate`, `Weak`, `Absent`, or `Not observable`.
`Not observable` means the category could not be tested because nothing was produced.
It is not a pass.

### 4.1 Ratings common to all twelve

Because orchestration output is identical across briefs, most categories score identically
for every situation. Stating them once is more honest than repeating a copied table twelve
times and implying twelve independent measurements.

| # | Category | Rating | Basis |
| --- | --- | --- | --- |
| 1 | Story understanding | Absent | Same analysis for all 12 briefs; only the brief is echoed |
| 2 | Emotional intelligence | Absent | `spark -> tension -> turn` for all 12, including a coffee ad |
| 3 | Production planning | Adequate | 8-stage plan and 13-stage DAG are real, persisted, ordered |
| 4 | Department coordination | Adequate | 10 specialists run, messages route, approvals gate correctly |
| 5 | Asset creation | Absent | No provider; image and video mint IDs for nothing |
| 6 | Visual consistency | Not observable | No assets exist to be consistent |
| 7 | Audio quality | Not observable | No audio generated; ffmpeg processing works on supplied stems |
| 8 | Continuity | Weak | Continuity analyst emits one generic checklist line, brief-independent |
| 9 | Editing | Weak | Timeline model is real; editing beats are boilerplate |
| 10 | Interface clarity | Weak | Honesty labels are good; `status: draft` plus phantom `assetId` is not |
| 11 | Automation reliability | Adequate | 12/12 completed unattended; all report `completed_with_errors` |
| 12 | Error recovery | Adequate | Queue restart recovery now implemented and tested (7/7) |
| 13 | Speed | Strong | About 1.3s per full situation sequence; 12 situations in 15.5s |
| 14 | User control | Strong | Approval gates hold; no silent mutation of Bible or timeline |
| 15 | Final result quality | Absent | No result to assess |

### 4.2 Situation-specific findings

Where a situation has a demand the common table does not capture:

**1. Live-action dramatic.** The approval gate did exactly what it should: the handoff sat
unapproved until explicitly approved, and nothing mutated in the meantime. The arc it was
gating, though, was the generic one, so a user would be approving boilerplate.

**2. Suspense/thriller.** Depends on sound to work at all. With `providerMissing: true` on
every audio cue and no cue reaching the timeline, there is nothing to evaluate. The one
engine with a long enough duration (`fal_seedance`, 12s) is unreachable without a key.

**3. Music video.** No beat-sync or tempo primitive exists in the audio cue model.
`AudioPlacement` carries `startSec`, `durationSec`, `volume`, `ducking` and `syncEvent`,
but nothing consumes `syncEvent`. Cuts cannot be locked to a bar line today.

**4. Animated.** Styling consistency depends entirely on the first frame, which requires
the local ImageGen path. Not installed.

**5. Commercial.** Product accuracy is the whole job, and it is unverifiable with no image
generation. The 30s structure would need several 8s blocks assembled on the timeline; the
timeline supports that, the assets do not exist.

**6. Dialogue-heavy two-person.** The director timeline correctly exposes two lipsync
tracks with per-character ROI defaults, which is real structure. Both are `enabled: false`
with `audio_asset_id: null`, and no TTS or dialogue provider exists, so lipsync cannot be
exercised end to end.

**7. Action/chase.** Spatial coherence across cuts is exactly what the identical,
brief-independent continuity output cannot help with.

**8. Fantasy/sci-fi.** M2.13 Environment Studio is flag-gated and reachable, but its
outputs feed the same absent image pipeline.

**9. Documentary/interview.** Room tone and ambience are the defining texture, and ambience
generation returns `providerMissing: true`.

**10. Stylized 2D/anime.** Same first-frame dependency as situation 4.

**11. Product/location reconstruction.** The only situation where reference fidelity could
in principle be checked against supplied inputs, and the only fal engine that can pin both
ends of a move (`fal_seedance`) is unreachable.

**12. Full short-form capstone.** Cannot begin. Step 1 of the multi-model chain needs a
still frame, and neither fal (no image models wired, `FAL_IMAGE_MODELS` is empty) nor the
local path (not installed) can produce one.

## 5. Strong qualitative feedback

**What worked.** The skeleton is genuinely sound. Approval gates hold and never silently
mutate the Production Bible or the timeline; `mayMutateBible: false` and
`mayMutateTimeline: false` are enforced, not advisory. The director timeline is a real,
well-shaped data model with prompt segments, camera clips, audio and SFX tracks, and
per-character lipsync ROIs. Cue persistence works. The honesty labelling
(`honesty: unavailable`, `awaitingProvider: true`, `providerMissing: true`) is unusually
disciplined and is the reason this audit could reach firm conclusions. Speed is excellent.
Restart recovery, implemented during this milestone, closes a real M3.0a condition.

**What was confusing.** `status: "draft"` with a populated `assetId` and `fixture: false`
reads as success. It is not. Separately, `status: "completed_with_errors"` returned under
HTTP 200, with no error list in the response, gives a caller no way to learn what failed.

**Weak assumptions.** Three, and each would mislead a beta user. First, that a single
hard-coded emotional arc can stand in for story analysis across every genre. Second, that
`modelUsed: "gemma"` is a safe thing to report when `modelId` is `null` on every
specialist. Third, that the mock-path label `Heuristic specialist output (E2E/mock path)`
is only ever seen in E2E - it appeared in a run with `STUDIO_E2E` explicitly unset.

**Department disagreement.** None observed, and that is the problem rather than a
reassurance. `conflicts.count` was `0` in all twelve runs because all ten specialists
returned the same recommendation. A conflict-synthesis system that never sees disagreement
has not been tested.

**UI friction.** The M2.14 Unified Experience workspace cannot render at all: the provider
health payload the frontend reads omits `unifiedExperienceEnabled`, so `CoDirectorShell`
always takes the false branch (blocker B2). Everything described above was reachable only
through the API.

**Context loss.** The brief survives into the context pack and is echoed back, but it does
not reach any analytical output. That is worse than losing it, because it looks retained.

**Manual correction required.** Every generated audio cue would need a stem supplied by
hand. Every shot would need a frame supplied by hand.

**Races and persistence.** No races observed across 12 sequential runs. Persistence is
solid: projects, scenes, profiles, handoffs, concepts, messages, cues, decisions and
traces all survive and re-read correctly.

**Generation quality.** Not assessable. Nothing was generated.

**Recovery.** Now a strength. Non-terminal jobs are resumed or honestly marked interrupted
at startup, with the action recorded in job history and a configurable staleness cutoff.

**Fixes before Manual User Beta.** See `FINAL_BETA_BLOCKERS.md`. The ordered short list is:
stop minting asset IDs for artifacts that do not exist (B1); make the M2.14 workspace
reachable (B2); fix the audio-process contract so mix revise is not a silent no-op (B3);
land generated cues on the timeline (B4); install or wire at least one real generative
provider (B5).


## Post-fix update -  2026-07-27

The twelve situations remain **0 EXECUTED / 12 PARTIAL / 0 FAILED / 0 NOT_RUN**. Real component
evidence now exists: local Z-Image, reused Seedance registration, imported WAV timeline placement,
ffmpeg normalization, and Bible approval. These are not silently upgraded into full scenario
passes. See `docs/m3.0-completion/SITUATION_RERUN_RESULTS.md`.

**B4 is closed for real imported audio. B10 is fixed for the covered character proposal.**
No paid fal job was submitted during completion.
