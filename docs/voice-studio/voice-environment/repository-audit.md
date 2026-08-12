# Voice Environment — Repository Audit (M5.2 Phase 0)

## Baseline

- Canonical UI: `studio-web/src/components/VoiceStudioWorkspace.tsx`
- Stages before M5.2: Voice Identity → Voice Performance → Scene Dialogue → Takes
- Embedded only in Character Creator (`CharacterProfileWorkspace.tsx`)
- No `WORKSPACES.voicestudio`, no Production Creative Studios entry
- Performance truth path: M410 (`voice_performance/m410_*`)
- Audio Studio: generation/mix/placement; no convolution DSP before M5.2
- Co-Director: `voice.*` / `voice_performance.*` tools; no `voice_environment.*` before M5.2
- Avatar “Open Voice Studio” previously misrouted to `audiostudio`

## Frozen contracts (Law 16)

| Artifact | Path |
| --- | --- |
| TS contracts + timing + tool IDs | `studio-web/src/contracts/voiceEnvironment.ts` |
| Frontend presets | `studio-web/src/components/voiceStudio/environment/presets.ts` |
| Python contracts | `studio-api/app/voice_environment/contracts.py` |
| DSP preset maps | `studio-api/app/voice_environment/presets.py` |
| API prefix | `/api/voice-environment/*` |

### VoiceEnvironmentTiming (required)

```ts
type VoiceEnvironmentTiming = {
  speechStartOffsetMs: number;
  processingLatencyMs: number;
  tailDurationMs: number;
  dryDurationMs: number;
  processedDurationMs: number;
};
```

Rules: dry-aligned speech start; Lip Sync ignores tails; Timeline preserves spoken start; environment replace must not shift mouth timing.

## Architecture decision

- One shared `VoiceStudioWorkspace` for Character Creator + Production entry
- Voice Environment extends **M410 only** (not legacy W44)
- Deterministic acoustic processing (not mislabeled as AI generation)
- New module: `studio-api/app/voice_environment/`

## Gaps closed by M5.2 implementation

1. Standalone `voicestudio` workspace + Production menu
2. Voice Environment stage after Voice Performance
3. Profiles / preview / render / stems / timing persistence
4. Co-Director recommendation + proposal-gated tools
5. Timeline / Lip Sync (dry) / Audio Studio handoffs
