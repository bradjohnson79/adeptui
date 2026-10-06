# Schema and API

`MovementSegment` fields: stable `id`, `segmentNumber` 1–5, `beatName`,
placement snapshots, `cameraStateRefs`, `userDirection`, `productionPrompt`,
`actions`, `dialogue`, `continuity`, `timingHintSeconds`, `revision`.

Alias `M{n}` is derived.

Routes:

- `POST /maps/{id}/movements`
- `PATCH /maps/{id}/movements/{segmentId}`
- `POST /maps/{id}/movements/{segmentId}/activate`
- `DELETE /maps/{id}/movements/{segmentId}`
- `GET /maps/{id}/movement-arrows`

Missing/stale movement returns a typed error. The system never substitutes M1.
