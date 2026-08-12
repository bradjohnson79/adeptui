# Subagent Handoff

## Assignment
VoiceCreatorUISubagent — creator-first Voice Creator UI; clone/upload must call real APIs. Contract: `subagent-assignments/VoiceCreatorUISubagent.md`.

## Scope completed
- Reviewed Create / Personality / Listen / Advanced IA already landed.
- **Corrected** clone/upload path: `Review reference file` now uploads via `api.uploadAsset`, calls `validateCharacterVoiceReference` with server `path`, and exposes `Generate clone` → `cloneCharacterVoiceWorkspace` (real `/voice/clone/generate`).

## Files changed
- `studio-web/src/components/VoiceCreatorWorkspace.tsx`

## APIs consumed
- `POST /api/projects/{id}/assets`
- `POST .../voice-profiles/validate-reference`
- `POST .../voice/clone/generate`

## APIs changed
None (frozen contracts).

## Tests run
Static/lint on edited file (clean). Playwright not re-run in this handoff (see TestSubagent).

## Test results
N/A for live clone audio in this pass (requires reference WAV + consent + Qwen clone readiness).

## Manual checks
Code path no longer sets `validation: "pending_server_path"` only.

## Evidence
- Diff in `VoiceCreatorWorkspace.tsx` (validate + generate clone buttons / testids `voice-ref-validate`, `voice-clone-generate`)

## Known issues
- Clone still depends on provider readiness (`qwenVoiceClone.ready`).
- Advanced panel still shows raw JSON for power users.

## Risks
- Playwright soft-skips may not exercise clone path.

## Dependencies still pending
- TestSubagent honesty report on soft-skips.
- Approved voice required for full Voice Performance readiness.

## Recommended integration checks
- With a short WAV, consent → Review → Generate clone → Listen candidates.
- Confirm asset appears in project Library.

Ready for integration review.
