# Voice Environment Processing

## Kind

`deterministic_acoustic` — not AI generation. Generative walla/ambience may later use Audio Studio providers and must be labeled honestly.

## Pipeline

1. Load dry take WAV
2. Detect `speechStartOffsetMs` from dry energy
3. Tone / distance / device filtering
4. Room reverb with explicit tail samples
5. Direction pan (mixdown for storage)
6. Write processed + room tone + optional walla stems
7. Persist `VoiceEnvironmentTiming`

## Timing rules

- Device/distance latency → `processingLatencyMs`
- Reverb tail → `tailDurationMs`
- Lip Sync uses dry + `speechStartOffsetMs` only
- Timeline spoken start stays at dry start; tails may extend past final phoneme
- Environment replace must not shift mouth timing
