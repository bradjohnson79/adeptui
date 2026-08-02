# Security And Consent

## Project and character boundaries

M4.10 does not allow arbitrary voice reuse across projects or characters.

`require_approved_voice_identity()` checks that the selected voice identity:

- exists
- belongs to the same `projectId`
- belongs to the same `characterId`
- is already approved

Record creation also validates linked script documents and scenes against the same project.

## No silent identity creation

`VoicePerformanceStudio.tsx` shows `Voice Identity Required` when there is no approved voice identity and offers a single explicit action: `Open Voice Identity`.

The performance workspace does not create a voice identity in the background.

## Consent snapshot

The frontend creates a consent acknowledgement when it creates a fresh M4.10 record:

- `source: "voice-performance-studio"`
- `acknowledgedAt: <ISO timestamp>`

That payload is stored in `record.consentAck` and returned on reload.

## Explicit replacement confirmation

Two potentially destructive actions require explicit confirmation:

- Timeline placement when matching dialogue clips would be replaced
- Lip Sync preparation when scene audio references would be replaced

The backend returns structured errors instead of silently overwriting state.

## Local runtime safety

The M4.10 provider is local:

- provider id `index-tts2-local`
- official repo pin enforced in `runtime/index_tts2.py`

The runtime also blocks silent CPU fallback. Generation and health checks fail unless CPU fallback is explicitly approved by the caller.

## Honest scope note

Emotional reference audio is stored as project-owned metadata and intent, but the implemented M4.10 runtime path does not yet inject that asset as a separate live conditioning input. The docs and UI should continue describing it as saved workflow context, not as hidden synthesis behavior.
