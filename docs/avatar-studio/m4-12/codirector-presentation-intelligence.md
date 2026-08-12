# M4.12 Co-Director Presentation Intelligence

## Scope

This pass adds Co-Director support for Avatar Studio presentation planning and keeps all write actions proposal-gated.

Included:

- Presentation planning for long-form avatar sessions
- Script sectioning and creator-facing section notes
- Delivery, gaze, gesture, pacing, emphasis, posture, and pronunciation guidance
- Background and framing recommendations
- Continuity checks and section comparison reads
- Proposal-gated plan creation, section adjustment, retake requests, voice replacement, assembly, and Timeline handoff preparation

Not included:

- Silent provider execution or fake Ready states
- Automatic Timeline writes
- MuseTalk deep repair execution

## Co-Director Tool Surface

### Read tools

- `avatar.inspect`
- `avatar.get_provider_status`
- `avatar.get_script_context`
- `avatar.get_voice_context`
- `avatar.get_job`
- `avatar.get_section`
- `avatar.compare_sections`
- `avatar.check_continuity`

### Proposal-gated tools

- `avatar.create_plan`
- `avatar.create_job`
- `avatar.adjust_section`
- `avatar.request_retake`
- `avatar.repair_lipsync`
- `avatar.replace_voice`
- `avatar.assemble`
- `avatar.prepare_timeline`

## Creator UX

Avatar Studio now exposes a creator-facing `Presentation Plan` section inside `AvatarStudioWorkspace.tsx`.

Creators can:

- Edit the high-level plan summary and sectioning strategy
- Adjust section length targets
- Tune delivery, gaze, gesture, pacing, transitions, emphasis, posture, pronunciation, background, framing, continuity, and retake guidance
- Edit per-section summary, delivery, emphasis, transition, and retake focus notes
- Use `Ask Co-Director to Plan` to open Co-Director with an avatar-planning prompt
- Use `Create Plan Proposal` to create an approval-gated `avatar.create_plan` proposal
- Use `Propose Retake` on completed sections to create an approval-gated `avatar.request_retake` proposal

The workspace shows only creator-facing notes. It does not expose hidden chain-of-thought or internal reasoning.

## Data Flow

- Session data now carries a durable `presentation_plan`
- Session reload normalizes and preserves the saved plan target length
- Long-form job creation consumes the saved presentation plan and stamps creator-facing presentation notes onto each generated section
- Timeline preparation stores a handoff package only; it does not place clips automatically

## Build Fix

The frontend `SetupComponentStatus` type now includes `category`, which matches the existing API payload, and the unused `componentStateLabel` import was removed from `AvatarRuntimeInstallPanel.tsx`.

## Verification

- `npm run build` in `studio-web`: passed
- `pytest tests/test_m412_codirector_avatar_tools.py` in `studio-api` with `PYTHONPATH=.`: passed

Targeted test coverage added for:

- Avatar Co-Director tool registration
- Proposal-gated `avatar.create_plan`
- Proposal-gated `avatar.request_retake`

## Notes For Primary

- The legacy broad suite in `studio-api/tests/test_codirector_tools.py` still has pre-existing contract drift unrelated to this pass, so verification here was kept to the new M4.12-targeted test file.
- The new backend handler lives in `studio-api/app/codirector/tools/handlers/avatar_m412.py`.
