# M3.0b Co-Director Beta Findings

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Configuration | Production flags on; `STUDIO_E2E` and `ADEPT_M29_FIXTURE_MODE` unset |
| Evidence | `m30b-12-situations.json`, `m30b-sound-path-smoke.json`, `m30b-artifact-honesty.json` |

## 1. What was actually exercised

The Co-Director was driven twelve times through the full production sequence and once more
through the dedicated sound path, all against the real API with fixture modes off. This is
not a code read; every claim below has an HTTP response behind it.

## 2. Orchestration coverage

### 2.1 The pipeline is real

`DEFAULT_PIPELINE` in `studio-api/app/codirector/m211/dag.py` declares thirteen stages
across twelve distinct specialists:

`storyteller`, `story-analyst`, `bible-manager`, `continuity-analyst`, `director`,
`cinematographer`, `sound-producer`, `sound-designer`, `music-supervisor`, `editor`,
`virtual-production-coordinator`, `qa-reviewer` (twice).

The graph is well formed, ordered, and exposed through `GET /api/codirector/m211/dag`.
Traces, decisions, approval boundaries and a review loop are all persisted and re-readable.
Structurally, this is a serious piece of work.

### 2.2 What actually ran

`POST /api/codirector/m211/orchestrate` returned **ten** specialists, not twelve:

| Specialist | Ran | Status | `modelId` | Confidence |
| --- | --- | --- | --- | --- |
| `story-analyst` | yes | validated | `null` | 0.82 |
| `bible-manager` | yes | validated | `null` | 0.82 |
| `continuity-analyst` | yes | validated | `null` | 0.82 |
| `director` | yes | validated | `null` | 0.82 |
| `cinematographer` | yes | validated | `null` | 0.82 |
| `sound-designer` | yes | validated | `null` | 0.82 |
| `music-supervisor` | yes | validated | `null` | 0.82 |
| `editor` | yes | validated | `null` | 0.82 |
| `qa-reviewer` | yes (x2) | validated | `null` | 0.82 |
| `storyteller` | **no** | - | - | - |
| `sound-producer` | **no** | - | - | - |
| `virtual-production-coordinator` | **no** | - | - | - |

Three declared specialists never appear in the orchestration result. Two of them,
`storyteller` and `sound-producer`, are precisely the two the M3.0b sound path depends on.
They exist instead as separate M2.14 endpoints, so the journey works, but the DAG that
claims to coordinate them does not run them. A reader of `GET /m211/dag` would reasonably
conclude otherwise.

Every specialist reported identical confidence (0.82) and the assumption
`Heuristic specialist output (E2E/mock path)`.

### 2.3 The output does not depend on the brief

Twelve briefs spanning six genres produced one analysis. Normalising UUIDs out of the
orchestration payload yields a single digest, `ce0b59f48418`, for all twelve runs. The
substantive fields - `story`, `bible`, `specialists`, `shotPlan`, `camera`, `music`, `sfx`,
`editingBeats`, `continuity`, `checklist`, `conflicts`, `explainability` - are byte
identical.

The brief text does appear in the response, inside `contextPack` and `trace`, echoed back
verbatim. So the input is carried and stored; it simply never influences an output. That is
a worse failure mode than dropping it, because the response looks contextual.

Concretely, every situation received:

- `shotPlan`: "Director recommends proceeding with bounded Production Bible context." and
  the same line from the Cinematographer.
- `music`: "Music Supervisor recommends proceeding with bounded Production Bible context."
- `sfx`: "Sound Designer recommends proceeding with bounded Production Bible context."
- `editingBeats`: "Editor recommends proceeding with bounded Production Bible context."
- `checklist`: "continuity-analyst: Match wardrobe and geography to adjacent shots."
- `missingAssets`: `[]`
- `conflicts.count`: `0`

The `missingAssets: []` is worth pausing on. Every one of those runs was missing every
asset it needed. The field that exists to report that returned empty.

### 2.4 Root cause

`ProductionIntelligenceOrchestrator.orchestrate` calls `self.runner.run_all` with
`use_provider=False`. `SpecialistRunner` only consults a model when
`use_provider and provider is not None and not _e2e_mode()`. With `use_provider` hard-coded
false, the LLM branch is unreachable regardless of environment, and every specialist falls
through to its deterministic heuristic string.

This also explains the `(E2E/mock path)` label appearing outside E2E: the heuristic branch
is shared between the mock path and the no-provider path, and it labels itself as the
former.

## 3. Storyteller and Sound Producer paths

### 3.1 Storyteller

`POST /api/codirector/m214/storyteller/analyze` returns HTTP 200 with a well-shaped
`EmotionalSceneProfile`: arc, subtext, tone, stakes, character beats, unknowns, discovery
questions, mode, honesty label. The envelope is good.

The contents are constant. All twelve briefs returned:

| Field | Value |
| --- | --- |
| `emotional_arc` | `spark -> tension -> turn` |
| `subtext` | `Unspoken need beneath dialogue` |
| `tone` | `intimate` |
| `stakes` | `personal` |
| `questions` | "What does the character want in this beat?", "What do they fear will happen if they fail?" |
| `honesty` | `unavailable` |

The only brief-dependent content is `character_beats[0].note`, which is the brief itself.

The handoff and approval mechanics, by contrast, are genuinely correct. The handoff is
created unapproved, `POST .../approve` flips `approved` to `true` and stamps `approvedBy`,
and the payload carries `approvalAware: true` and `silentMutation: false`. Nothing mutated
before approval in any of the twelve runs.

### 3.2 Sound Producer

`POST /api/codirector/m214/sound/concept` returns a `SonicConcept` with `score_brief`,
`ambience`, `cues`, `dialogue_plan`, `mix_intent`, and `honesty: "unavailable"`. Also
constant across all twelve situations, and derived from the Storyteller's constant:

- `score_brief`: `Score supports arc: spark -> tension -> turn`
- `ambience`: `Sparse room tone; lean into silence before the turn`
- `cues`: `["enter: soft pad", "turn: low pulse", "exit: residual tone"]`
- `dialogue_plan`: `Keep dialogue forward; SFX duck under key lines`
- `mix_intent`: `Intimate close perspective; music under dialogue`

The payload correctly records `coordinatesWith: ["music-supervisor", "sound-designer"]` and
`noNewProviders: true`. The coordination intent is modelled; the content is a placeholder.

### 3.3 The full sound path

The required journey ran end to end. Fifteen of sixteen hops returned HTTP 200. What the
200s mean varies a great deal:

| Hop | Result | Real? |
| --- | --- | --- |
| Open scene | 200 | Yes |
| Storyteller emotional arc | 200 | Structure yes, content no |
| Handoff and approval | 200 | Yes |
| Sound Producer sonic plan | 200 | Structure yes, content no |
| Approve sonic plan | 200 | Yes |
| Cinematographer timing message | 200 | Yes, persisted and routed |
| Editor timing message | 200 | Yes, persisted and routed |
| Score generate | 200, `providerMissing: true` | No audio |
| Ambience generate | 200, `providerMissing: true` | No audio |
| SFX generate | 200, `providerMissing: true` | No audio |
| Audio plan validate | 200, `ok: true` | Yes, real validation |
| Cues persisted | 200, 3 cues, `status: draft`, `assetId: null` | Yes, as drafts |
| Timeline | 200, `audio_clips: []` | **Cues never arrive** |
| Preview | n/a | Nothing to preview |
| Mix revise | 200 | **Silent no-op** |
| Export | 200, job queued | Yes |

Two of these deserve to be called defects rather than absences.

**Cues do not reach the timeline.** `audio/generate` writes a cue with `assetId: null`.
Only `audio/place-cue` writes to the director timeline, and it requires an `assetId`. So
generated cues are permanently stranded in the cue table. Verified directly: after
generating a music cue, `GET .../director` returned `audio_clips: []` while
`GET .../audio/cues` returned the cue. When a real asset is supplied, `place-cue` works
correctly and the clip appears with the right start, length, volume and label - so the
timeline side is sound; the join is missing.

**Mix revise silently does nothing.** `AudioProcessBody.ops` is typed `list[dict[str, Any]]`.
`process_audio_ffmpeg` tests `str(op).lower() in {"normalize", "loudnorm", "cleanup"}`. A
stringified dict never matches, so the loudnorm branch is skipped and the code falls through
to `-c copy`, then returns `status: "processed"`.

Measured on a real 3-second 44,100 Hz WAV:

| Input shape | Accepted by HTTP API | loudnorm applied | Output rate |
| --- | --- | --- | --- |
| `[{"op": "normalize"}]` (the contract) | yes | **no** | 44,100 Hz |
| `["normalize"]` (what the executor wants) | **no, HTTP 422** | yes | 48,000 Hz |

The two shapes are mutually exclusive. There is no request that both passes validation and
performs normalisation, so loudness normalisation is unreachable through the API.

Worth recording: the second row produced the only real media artifact of this milestone, a
288,078-byte normalised WAV resampled to 48 kHz. Real processing, not generation.

## 4. Authorized-range notes

The Co-Director's authority boundaries held everywhere they were tested, and this is the
strongest part of the system.

| Boundary | Declared | Observed |
| --- | --- | --- |
| May mutate Production Bible | `false` | Never mutated; approval recorded, not applied |
| May mutate timeline | `false` | Never mutated outside explicit `place-cue` |
| Requires approval for mutations | `true` | Enforced; pending approvals recorded per stage |
| May approve its own proposals | no | Approval is a separate authenticated call |
| May enqueue generation directly | no | Goes through the studio job queue |
| Silent mutation | `false` | `silentMutation: false` on handoffs; none observed |

`pendingApprovals` correctly records each approval boundary with
`mutationAllowed: false` and the note "Recorded approval boundary; bible/timeline not
mutated." Across twelve full runs, nothing was written that the user had not approved.

The M2.14 status endpoint also asserts the Provider Manifest digest on every call
(`assert_manifest_unchanged()`), and the manifest hash is unchanged at
`cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc`.

One caveat on all of the above: the Bible-apply Playwright test is failing, so the
browser-level proof of the "model never writes directly" property is currently absent even
though the API-level behaviour is correct.

## 5. Weak assumptions

Ordered by how much damage each would do to a beta user's trust.

1. **That one hard-coded emotional arc generalises.** `spark -> tension -> turn` is
   plausible enough for a two-hander that a user might not notice it is the same arc they
   were given for their coffee commercial and their anime duel.
2. **That an `assetId` in a response implies an asset.** `image/generate` and
   `video/generate` return `assetId` and `versionId` with `fixture: false` and
   `status: "draft"`, and create no `Asset` row and no file. Unlike the audio path, they
   set no `providerMissing` flag. A caller has no signal to distinguish this from success.
3. **That `modelUsed: "gemma"` is harmless to report.** Every specialist has
   `modelId: null`. No model was consulted.
4. **That `completed_with_errors` under HTTP 200 will be noticed.** All twelve runs
   returned it. The response carries no error list.
5. **That the `(E2E/mock path)` label only appears in E2E.** It appeared with `STUDIO_E2E`
   explicitly unset.
6. **That `missingAssets: []` means nothing is missing.** Everything was missing.
7. **That soft-skipping a Playwright test on a missing element implies a flag is off.** The
   M2.14 spec blames the flag for what is a wrong URL plus an unserialised field.
8. **That `syncEvent` on an audio placement does something.** Nothing reads it, so
   beat-synced editing is not merely unimplemented, it is implied by the schema.

## 6. Restart recovery, now implemented

This was an open M3.0a condition (`RST = FAIL` across queue-backed platforms) and it is
closed in code during this milestone.

`JobQueue.recover_interrupted()` in `studio-api/app/queue_worker.py` runs from the FastAPI
lifespan in `studio-api/app/main.py` before the worker starts. On startup it scans for jobs
left in `queued` or `running`, and:

- re-enqueues recent `queued` jobs so the work resumes;
- marks `running` jobs `failed` with stage `interrupted` and a message that says the work
  was interrupted by a restart rather than that it failed on its own merits, because a
  provider-side render cannot be resumed by a new process;
- marks `queued` jobs older than a configurable cutoff
  (`STUDIO_JOB_RECOVERY_MAX_AGE_HOURS`) as interrupted rather than starting stale work;
- leaves `done`, `failed` and `cancelled` untouched;
- records every action in the job's history for audit.

`studio-api/tests/test_job_queue_recovery.py` covers all seven behaviours and passes 7/7.
Confirmed not to affect the rest of the suite: the twenty pre-existing pytest failures are
identical with and without this test file present.

## 7. Summary judgement

The Co-Director's **governance** is production quality. Approval boundaries, mutation
policy, decision records, traces and persistence all behave correctly under twelve
consecutive real runs, and restart recovery now works.

The Co-Director's **intelligence** is not connected. `use_provider=False` means no
specialist has ever consulted a model, the Storyteller and Sound Producer return constants,
and three declared specialists including both sound leads never run in the DAG at all.

The system is honest about this in its own labels, and dishonest about it in three specific
places that a beta user would hit first: phantom asset IDs, `modelUsed: "gemma"`, and
`completed_with_errors` behind HTTP 200.


## Post-fix update -  2026-07-27

Completion evidence verifies a real local Z-Image through API/queue/Asset/Job/preview/library/
graph/file inspection; a reused Seedance MP4 registered with `resubmitted: false`; real WAV
import-to-Director placement; and Bible approve/reject persistence. B1-B3 are remediated, B4 is
closed for real imported audio, and B10 is fixed for the covered character proposal.

The situation tally remains **0 EXECUTED / 12 PARTIAL / 0 FAILED / 0 NOT_RUN**. Generated audio,
TTS, lipsync, broad provider coverage, M2.14 UI reachability, declared-but-unrun specialists,
contradictory orchestration fields, beat sync, vision/validation failures, and cancellation race
remain open. The reused fal Asset has no Studio Job row. No fal job was resubmitted.

---

## 8. M3.0 completion rerun (2026-07-27)

Fixtures-off rerun of all twelve situations against ComfyUI Z-Image and Ollama
`gemma4:31b-it-qat`. Full narrative: `docs/m3.0-completion/SITUATION_RERUN_RESULTS.md`.

### What changed

- **Asset creation is no longer Absent for stills.** 12/12 situations produced a real PNG via
  ComfyUI, persisted it, vision-validated it, approved the version, published it as a
  reference, and placed it on the Director timeline.
- **B4 holds under load for the import path.** Real WAVs land on the Director timeline in
  12/12 projects. Generated audio is still `providerMissing: true`.
- **The provider path runs, and the analysis is discarded.** Direct Ollama capture shows real
  story analysis. `_validate_or_repair` throws it away and substitutes the specialist display
  name, then labels the result `honesty: "provider"`. Filed as B15. Of 112 specialist runs,
  one retained any substantive recommendation text.
- **Enrichment is wrong-film.** Sparse findings trigger a hard-coded lab-corridor scaffold
  (B16). Every brief was told it was missing a containment cylinder.
- **Motion is the EXECUTED blocker.** M2.9 `image_to_video` fails 12/12 because `sceneId` is
  dropped (B17). Native LTX and WAN renders fail inside their workflows with models present
  (B20). Fal was reused, not resubmitted.
- **Export omits the timeline** (B18). Capstone pack has the three real assets and no
  `director_json`.
- **Vision approve ignores reject band** (B19). Situation 12 banded `reject` and was approved
  with `override: false`.

### Updated judgement

The skeleton is still sound and the still-image department is now real. Manual User Beta is
still blocked: a user cannot get a moving image for any of the twelve situations, and the
intelligence surface actively mislabels discarded analysis as provider-backed.

