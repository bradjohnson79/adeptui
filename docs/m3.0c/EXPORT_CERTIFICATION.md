# M3.0c — Export Certification

## B18 contract

The export worker includes the approved scene timeline representation in each exported
scene. In `studio-api/app/queue_worker.py`, `JobQueue._export` includes
`director_json` in the scene payload, alongside cue placements and their metadata.

The B18 regression coverage proves that the exported scene retains the source
`director_json` and that cue metadata is carried into the export payload.

| Export concern | Status | Evidence boundary |
|---|---|---|
| Scene metadata is collected | **VERIFIED** | `_export` scene payload construction. |
| `director_json` included | **VERIFIED** | B18 implementation and regression coverage. |
| Audio cue placements included | **VERIFIED** | Existing M2.9/M3.0 export tests. |
| Pack/export function invoked | **VERIFIED** | Queue worker export path and tests. |
| Final mastered delivery | **PENDING** | No full mastering suite or live delivery artifact is claimed. |
| Provider-backed motion in final export | **VERIFIED** | Fal Seedance Studio-queue proof produced a real MP4 Asset (`FAL_UNIFIED_QUEUE_PROOF.md`). |

No export SHA, artifact count, or provider request ID is invented here. Certification is
limited to the durable payload contract and tested local export behavior.
