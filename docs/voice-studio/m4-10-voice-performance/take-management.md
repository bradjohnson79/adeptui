# Take Management

## Generation flow

Takes are created per saved M4.10 record through:

- `POST /api/voice-performance/m410/records/{recordId}/generate-takes`

`m410_service.create_takes()`:

- assigns sequential `takeNumber`
- stores a creator-facing `label`
- freezes the active `directionSnapshot`
- calls the local IndexTTS2 runtime
- records job, duration, asset, and error metadata

## Counts and labels

The UI offers `1` to `4` takes at a time.

The backend schema allows `1` to `8` through `GenerateTakesBody.count`, clamped server-side.

When the UI creates labels, it uses `Take N` numbering based on the latest visible take number.

## Status lifecycle

Persisted take statuses are:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`
- `approved`
- `rejected`

`poll_take_status()` updates take state from the linked `Job` row and copies back:

- `audioAssetId`
- `durationMs`
- `errorCode`
- `errorMessage`
- `generatedAt`

## Comparison and approval

`POST /api/voice-performance/m410/records/{recordId}/compare` returns a lightweight comparison payload for selected takes.

`POST /api/voice-performance/m410/records/{recordId}/takes/{takeId}/approve` enforces single-take approval:

- the chosen take becomes `approved`
- any previously approved take returns to `completed`
- the record updates `approvedTakeId`

Only completed or already approved takes can be approved.

## UI polling

`VoicePerformanceStudio.tsx` polls every 4 seconds while any take is `queued` or `running`.

The Takes panel only shows the latest four visible takes, sorted by take number and creation time.
