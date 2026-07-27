# M3.0b Production Scenario Matrix

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-27 (rerun; original M3.0b date 2026-07-26) |
| Configuration | Production flags on; `STUDIO_E2E` and `ADEPT_M29_FIXTURE_MODE` unset |
| Evidence | `artifacts/m30-situations/`; narrative in `docs/m3.0-completion/SITUATION_RERUN_RESULTS.md` |
| Prior evidence | `artifacts/functional-audit/m30b-12-situations.json` (kept for comparison) |

## 1. Headline

All twelve situations were driven again with fixtures OFF against a real ComfyUI Z-Image
provider and a Ready Ollama model. Every call answered.

**Zero situations reached `EXECUTED`.** All twelve remain `PARTIAL`, because every brief is a
moving-image brief and no situation produced a moving image of its own. Local video failed
12/12, both native engines fail inside their ComfyUI workflows, and fal was deliberately not
re-run.

The same headline count as M3.0b, with a different substrate underneath it. Every situation
now has a real still, a real imported audio cue on the Director timeline, a Co-Director
vision inspection of the actual pixels, and an approval-gated handoff. M3.0b had none of that.

| Status | Count |
| --- | --- |
| EXECUTED | 0 |
| PARTIAL | 12 |
| FAILED | 0 |
| NOT_RUN | 0 |

## 2. The finding that dominates every row

**The M2.11 orchestration output is still independent of the brief**, for a new reason.

The M3.0 `use_provider` fix made the model path reachable. Ollama ran - 112 specialist
invocations over about 30 minutes of wall clock. Direct capture of the same prompt
(`artifacts/functional-audit/m30-ollama-raw.json`) shows the model producing real story
analysis. `SpecialistRunner._validate_or_repair` then discards that analysis because the
model nests it under `specialist-finding-v1` and uses different field names, and replaces
every finding with the specialist's display name. The eight runs that kept all ten
specialists collapse to a single content digest. Filed as B15.

Because the findings are sparse, `_heuristic_enrichment` fills the gap with a hard-coded
lab-corridor scaffold. All twelve briefs were told they were missing a containment cylinder
and emergency strobes. Filed as B16.

M2.14 Storyteller and Sound Producer remain structurally unbound
(`honesty: "unavailable"`) and still return the constant arc
`spark -> tension -> turn` / `intimate` / `personal`.

## 3. Scenario matrix

In the Sound/score column, `REQ` means the situation cannot be judged without sound.

### 3.1 Situations 1-6

| # | Situation | Format | Technical demands | Departments engaged | Native platforms | Providers needed | fal.ai use | Sound/score | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Live-action dramatic | Single scene, 8s | Performance beat, held silence, shot-reverse-shot | Storyteller, Story Analyst, Bible Manager, Continuity, Director, Cinematographer, Sound Designer, Music Supervisor, Editor, QA | M2.14 Unified, M2.11 Intelligence, M2.9 image/video/audio, Director Timeline, Export, M2.5 Vision | Local ImageGen (working) + video engine | Reused Seedance asset; no resubmit | REQ | PARTIAL |
| 2 | Suspense/thriller | Single scene, 8s | Sustained tension, long take, sound-led dread | same 10 specialists | M2.14, M2.11, M2.9, Director Timeline, Export, M2.5 Vision | Local ImageGen + fal I2V | Not re-run | REQ | PARTIAL |
| 3 | Music video | Sequence, 8s sample | Beat sync, tempo-locked cuts, continuous move | same 10 specialists | M2.14, M2.11, M2.9 audio + video, Director Timeline, M2.5 Vision | Local ImageGen + music source | Reused Seedance asset | REQ | PARTIAL |
| 4 | Animated | Single scene, 8s | Non-photoreal styling held across frames | same 10 specialists | M2.14, M2.11, M2.9 image/video, M2.5 Vision | Local ImageGen (working) + fal I2V | Reused Seedance asset | REQ | PARTIAL |
| 5 | Commercial | 30s spot, 8s sample | Product accuracy, brand-safe framing, tight cut | same 10 specialists | M2.14, M2.11, M2.9, Editing, Export, M2.5 Vision | Local ImageGen + fal I2V | Not re-run | REQ | PARTIAL |
| 6 | Dialogue-heavy two-person | Single scene, 8s | Lipsync, dialogue mix, eyeline continuity | same 10 + Lipsync path | M2.14, M2.11, M2.9 audio + lipsync, Director Timeline, M2.5 Vision | TTS/dialogue engine + I2V + lipsync | Not re-run | REQ | PARTIAL |

### 3.2 Situations 7-12

| # | Situation | Format | Technical demands | Departments engaged | Native platforms | Providers needed | fal.ai use | Sound/score | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Action/chase | Sequence, 8s sample | Fast motion, spatial coherence across cuts | same 10 specialists | M2.14, M2.11, M2.9 video, Editing, M2.5 Vision | Local or fal I2V | Not re-run | REQ | PARTIAL |
| 8 | Fantasy/sci-fi | Single scene, 8s | World-building consistency, large camera moves | same 10 specialists | M2.14, M2.11, M2.9, M2.13 Environment Studio, M2.5 Vision | Local ImageGen + fal I2V | Not re-run | REQ | PARTIAL |
| 9 | Documentary/interview | Single scene, 8s | Static realism, long-lens, room tone | same 10 specialists | M2.14, M2.11, M2.9 audio + video, M2.5 Vision | Local ImageGen; ambience source | Not re-run | REQ | PARTIAL |
| 10 | Stylized 2D/anime | Single scene, 8s | Flat-shade consistency, stylised motion | same 10 specialists | M2.14, M2.11, M2.9 image/video, M2.5 Vision | Local ImageGen + fal I2V | Not re-run | REQ | PARTIAL |
| 11 | Product/location reconstruction | Single scene, 8s | Reference fidelity, camera spin, geometry | same 10 + Virtual Production Coordinator | M2.14, M2.11, M2.13 Environment Studio, M2.9, M2.5 Vision | Local ImageGen + fal I2V + reference photos | Reused Seedance asset | REQ | PARTIAL |
| 12 | Full short-form capstone | 3-minute short | All of the above, plus cross-sequence continuity | all specialists | Every platform above + Export | Local ImageGen + video | Reused Seedance asset | REQ | PARTIAL |

### 3.3 What PARTIAL resolves to per situation (this rerun)

| Sub-step | Result |
| --- | --- |
| Project + scene created | HTTP 200 |
| Idea intake, discovery questions | HTTP 200, `honesty: unavailable` |
| Storyteller arc | HTTP 200, constant output, `honesty: unavailable` |
| Handoff + approval gate | HTTP 200, `approved: true`, persisted |
| M2.11 orchestration | HTTP 200, provider path, findings reduced to display names, `completed_with_errors` |
| Sonic plan + approval | HTTP 200, constant output, `honesty: unavailable` |
| Audio generate | HTTP 200, `providerMissing: true`, cue `queued`, `assetId: null` |
| Audio import + place-cue | HTTP 200, real WAV, `timelinePlaced: true` (B4 closed for import) |
| Image generate | HTTP 200 → job Completed, real PNG via ComfyUI, Asset row + file on disk |
| Image Co-Director inspect | HTTP 200, M2.5 local vision, measured OpenCV metrics |
| Image approve + publish-reference | HTTP 200, version `approved`, `publishedReference: true` |
| Video generate (M2.9) | Job Failed: `image_to_video requires sceneId with frame assets` (B17) |
| fal motion handoff | Reused existing Seedance asset in S01/S03/S04/S11/S12; no job submitted |
| Timeline apply before approval | HTTP 403 in all twelve |
| Timeline apply after approval | HTTP 200, `applied` |
| Export | HTTP 200, pack of real assets; pack omits `director_json` (B18) |

## 4. Per-situation evaluation

Ratings are `Strong`, `Adequate`, `Weak`, `Absent`, or `Not observable`.

### 4.1 Ratings common to all twelve

| # | Category | Rating | Basis |
| --- | --- | --- | --- |
| 1 | Story understanding | Absent | Model analysis discarded (B15); M2.14 arc is a constant |
| 2 | Emotional intelligence | Absent | Same constant emotional profile across all 12 |
| 3 | Production planning | Adequate | 8-stage plan and DAG are real, persisted, ordered |
| 4 | Department coordination | Weak | 10 specialists run; 3 never register; findings are display names |
| 5 | Asset creation | Partial | Still images real; video and generated audio still absent |
| 6 | Visual consistency | Weak | One real frame per brief; no multi-frame consistency to judge |
| 7 | Audio quality | Not observable | No audio generated; import path works |
| 8 | Continuity | Weak | Continuity analyst emits display-name findings; enrichment is wrong-film |
| 9 | Editing | Weak | Timeline model is real; tempo sync is unimplemented (B13) |
| 10 | Interface clarity | Weak | Honesty labels mislead when analysis was discarded (`honesty: provider`) |
| 11 | Automation reliability | Adequate | 12/12 completed unattended; all report `completed_with_errors` |
| 12 | Error recovery | Adequate | Queue restart recovery still implemented and tested |
| 13 | Speed | Mixed | Image path 6-15s; orchestration 1-4.5 minutes for discarded analysis |
| 14 | User control | Strong | Approval gates hold; no silent mutation of Bible or timeline |
| 15 | Final result quality | Weak | Competent stills; no cut |

### 4.2 Situation-specific findings

**1. Live-action dramatic.** Strongest still of the twelve. Both native video engines failed
when probed directly (LTX null CLIP; WAN VAE path). Held performance beat cannot be judged
from a still.

**2. Suspense/thriller.** Sound-led dread with no sound department. Imported tone is a harness
artifact.

**3. Music video.** Bar-line placement is exact when the harness computes the grid.
`syncEvent` is accepted by `plan/propose` and absent from `place-cue`.

**4. Animated.** One frame; style consistency across frames untestable. Two specialists timed
out (8 of 10 completed).

**5. Commercial.** Product accuracy judgeable on the still; nothing validates against a product
reference. No 30s block structure.

**6. Dialogue-heavy two-person.** Lipsync NOT_RUN - no TTS/dialogue provider.

**7. Action/chase.** Worst specialist survival (7 of 10). Audio landed on the SFX track.

**8. Fantasy/sci-fi.** Image carries world-building; camera moves untestable. 8 of 10 specialists.

**9. Documentary/interview.** Closest to judgeable on a still. Ambience still
`providerMissing: true`.

**10. Stylized 2D/anime.** One frame; stylised motion untestable. 9 of 10 specialists.

**11. Product/location reconstruction.** Honest scope: the brief requires three reference
photographs and none were supplied. A diner interior was generated from a text prompt. That
is not a reconstruction.

**12. Full short-form capstone.** Full chain driven and approved. Export pack carries three
real assets and neither the approved timeline nor a rendered cut (B18). Soft-frame vision
report banded `reject` and was still approved with `override: false` (B19).

## 5. Strong qualitative feedback

**What worked.** Local Z-Image generation is real, fast, and on-prompt. B4 holds for the
import path across twelve projects. Approval gates refused apply-before-approve twelve times
out of twelve. Vision validation measured real pixels and reported different scores for
different images. Persistence is durable out of process. The fal reuse path proves motion
handoff without re-spending.

**What was confusing.** `honesty: "provider"` on findings that are the specialist's display
name. A `reject`-band vision report that accepts a non-override approve. An export pack that
says `Export pack ready` and omits the timeline.

**Weak assumptions.** That discarding a model response and labelling the result `provider` is
honest. That a hard-coded lab-corridor scaffold is a safe fill-in for every brief. That an
export of assets is an export of the edit.

**Department disagreement.** Still none observed - findings are identical display names, so
the conflict-synthesis path remains untested under real disagreement.

**UI friction.** Not re-audited in this API-only rerun. B2 was fixed in the working tree
(provider health now serialises `unifiedExperienceEnabled`); browser confirmation is still
owed.

**Generation quality.** Stills: competent and on-prompt. Video: not generated. Audio: not
generated.

**Fixes before Manual User Beta.** See `FINAL_BETA_BLOCKERS.md`. The ordered short list after
this rerun is: stop discarding model analysis (B15); pass `sceneId` through to `run_video`
(B17); keep B1-B3 honesty fixes; close B10 Bible-apply; disclose scaffolded intelligence in
the UI.
