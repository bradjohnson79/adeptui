# Voice Environment Architecture (M5.2)

## Shared workspace

```text
Production → Creative Studios → Voice Studio → VoiceStudioShell → VoiceStudioWorkspace
Character Creator → Voice Studio tab → VoiceStudioWorkspace
```

Both entry points share one workspace, M410 performance records, environment profiles/renders, and project persistence.

## Stage order

Voice Identity → Voice Performance → **Voice Environment** → Scene Dialogue → Takes

## Processing

Creator presets compile to a normalized DSP plan (`compiler.py`), then deterministic local processing (`processor.py`) produces:

- Processed voice
- Room tone stem
- Walla stem (when enabled)
- `VoiceEnvironmentTiming` (speech start, latency, tail, durations)

Dry approved performance audio is never overwritten.

## API

`/api/voice-environment/*` — profiles, preview, render, approve, recommend, timeline, lipsync, audio-studio, runtime status.
