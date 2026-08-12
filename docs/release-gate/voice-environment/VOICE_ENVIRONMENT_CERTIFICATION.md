# M5.2 — Voice Environment Certification

## Certification Target

- Milestone: `M5.2 Standalone Voice Studio + Voice Environment`
- Branch: `feature/ai-guided-setup`
- Certification SHA: `fa09c99d6395c29461cdec4555055faad116c435`
- Live Beta UI: `http://127.0.0.1:8760/`
- Live Beta API: `http://127.0.0.1:8758/`
- Independent verifier: transcript `cdcc07f9-9832-4b08-814b-fa1854d6aed0` returned `READY FOR PRIMARY CERTIFICATION`
- Verdict: **GO**

## Scope Certified

- Standalone `Voice Studio` entry is exposed from the Production menu under Creative Studios.
- Shared Voice Studio shell keeps stage flow aligned across standalone and project-entry use.
- Voice Environment stage remains sequenced after Voice Performance.
- Voice Environment creator flow is wired through live UI, API, deterministic processing, and handoff endpoints.
- Co-Director mutations remain proposal-gated instead of silently mutating creator state.

## Files Spot-Checked For Primary Certification

- `studio-web/src/components/voiceStudio/environment/VoiceEnvironmentPanel.tsx`
- `studio-web/src/api.ts`
- `studio-api/app/voice_environment/router.py`
- `studio-api/app/voice_environment/service.py`
- `studio-api/tests/test_voice_environment.py`
- `tests/e2e/voice-studio/voice-environment-and-standalone-studio.spec.ts`

## Evidence

### Live Beta Health

- `GET http://127.0.0.1:8760/` -> `200`
- `GET http://127.0.0.1:8758/` -> `200`
- Beta was already up on the required ports; restart was not required.

### Runtime Status

- `GET http://127.0.0.1:8758/api/voice-environment/runtime/status` -> `200`
- Response:

```json
{"ok":true,"status":"Ready","processingKind":"deterministic_acoustic","aiGeneration":false,"reasons":[],"capabilities":{"preview":true,"render":true,"stems":true,"wallaPlaceholder":true,"roomTonePlaceholder":true}}
```

### Automated Evidence

- `cd studio-api; python -m pytest tests/test_voice_environment.py -q` -> `8 passed in 0.58s`
- `ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_PORT=8758 npx playwright test tests/e2e/voice-studio/voice-environment-and-standalone-studio.spec.ts --retries=0` -> `3 passed (4.1s)`

### Primary Wiring Spot-Check

- `VoiceEnvironmentPanel` still wires the creator-facing handoff buttons:
  - `Send to Timeline` -> `api.voiceEnvironment.placeTimeline(...)`
  - `Prepare Lip Sync` -> `api.voiceEnvironment.prepareLipsync(...)`
  - `Open in Audio Studio` -> `api.voiceEnvironment.openAudioStudio(...)`
  - `Apply to Scene` -> `api.voiceEnvironment.applyToScene(...)`
- `studio-web/src/api.ts` maps those calls to the live `/api/voice-environment/renders/{id}/...` endpoints.
- `studio-api/app/voice_environment/router.py` exposes `apply-to-scene`, `timeline`, `lipsync`, and `audio-studio` POST routes into `studio-api/app/voice_environment/service.py`.
- `studio-api/tests/test_voice_environment.py` covers dry-timing behavior for timeline/lipsync handoff helpers and the Audio Studio payload.

## Honest Limitations

- `runtime/status` is still a capability-and-`numpy` readiness signal for deterministic acoustic processing; it does not, by itself, prove a full creator session from take selection through final render handoff.
- This certification reran the focused live Voice Studio / Voice Environment Playwright spec, not an end-to-end Korri-style long-form production pass.
- Manual UX confirmation is still recommended for creator feel, reload polish, and larger-screen/smaller-screen ergonomics even though the focused automated evidence is green.

## Manual Review State

- Beta is left ready for manual review at `http://127.0.0.1:8760/`
- API remains live at `http://127.0.0.1:8758/`
- Manual review path is maintained in `docs/release-gate/voice-environment/VOICE_ENVIRONMENT_MANUAL_UX.md`

## Verdict

**GO**
