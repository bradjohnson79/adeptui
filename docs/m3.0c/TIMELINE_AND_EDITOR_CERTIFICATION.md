# M3.0c — Timeline and Editor Certification

## Certified evidence

The native Director timeline and Editor surfaces are **GREEN** for their bounded local
contracts:

- Director timeline proposals and applications persist through scene `director_json`.
- Audio cue placement and gain updates are reflected in timeline data.
- Editor sequence read/write surfaces and the Director-to-Editor handoff exist.
- Export reads the durable scene timeline representation.

Relevant implementation surfaces include `Timeline.tsx`, `DirectorTracks.tsx`,
`EditorWorkspace.tsx`, M2.9 timeline/editing services, and
`studio-api/app/queue_worker.py`.

## Matrix

| Capability | Status | Evidence boundary |
|---|---|---|
| Read director timeline | **VERIFIED** | Existing timeline API/UI and tests. |
| Apply timeline operations | **VERIFIED** | Existing M2.9 persistence tests. |
| Audio clips remain in timeline | **VERIFIED** | M3.0 audio timeline tests. |
| Director → Editor surface | **IN_PROGRESS** | Routes and persistence exist; complete browser handoff proof is pending. |
| Editor sequence persistence | **VERIFIED** | Editor service/API contract exists. |
| Multi-scene editorial continuity | **PENDING** | No full live scenario artifact is claimed. |
| Provider-rendered motion on timeline | **PENDING** | Fal motion queue live proof remains owed. |

The certification is for data and approval boundaries, not a claim that every editor
render or provider-backed motion path has been live exercised.
