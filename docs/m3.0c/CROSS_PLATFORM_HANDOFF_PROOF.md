# M3.0c — Cross-Platform Handoff Proof

This is a proof map for data crossing native production platforms. A wired route is not
treated as a completed handoff until the receiving platform can consume the durable
representation.

| Handoff | Proven evidence | Status |
|---|---|---|
| Script / storyboard → scene references | Script workspace APIs and storyboard generation path exist. | **GREEN** |
| References → image generation | Reference APIs and local image queue are wired. | **GREEN** |
| Image / frame → video | Video payload preserves `sceneId`; queue/fal submission code exists. | **IN_PROGRESS** — fal motion live proof pending. |
| Spatial blocking → director timeline | Spatial scene and send-to-director surfaces exist. | **IN_PROGRESS** — full cross-workspace live proof pending. |
| Production Bible → Co-Director | Bible services, proposal approval, and B10 browser approve/reject evidence exist. | **GREEN** for the bounded tested cases. |
| Audio import → timeline | Import, placement, gain, and normalize paths are covered by M3.0 audio tests. | **GREEN** |
| Generative audio → timeline | Generative providers are sandbox/deferred and no production generation is available. | **BLOCKED** |
| Director timeline → editor | Director/editor persistence and send surface exist. | **IN_PROGRESS** — complete live handoff proof pending. |
| Editor/timeline → export | Export queue includes scene `director_json` and cue placements. | **GREEN** for the tested export contract. |
| Export → final mastered delivery | Pack/export exists, but full mastering suite is not present. | **IN_PROGRESS** |

## Required proof for a handoff

1. The source platform emits a durable ID or versioned payload.
2. The receiver reads that payload through its production route.
3. The receiving state is observable after reload or job completion.
4. Invalid, unavailable, and approval-gated states fail closed.
5. A repeatable test or artifact records the result without inventing provider output.

## Conclusion

The matrix separates local contract proof from live provider proof. The remaining
cross-platform work is primarily the fal motion path, full spatial/director/editor
browser flow, and final mastering evidence.
