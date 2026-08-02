# M4.10 Voice Performance Studio UX Specification

## Intent

M4.10 turns Voice Studio performance work into an artist-facing dialogue-direction workspace rather than a generic TTS form.

Primary design goals:

- Keep the spoken line and the performance plan visually dominant.
- Use creative direction language first: Emotion, Intensity, Delivery, Pacing, Breath, Emphasis, Subtext, Performance Reference.
- Keep raw IndexTTS2 vector controls behind `Advanced`, collapsed by default.
- Never create or imply a Voice Identity silently.
- Preserve both Co-Director and Manual direction plans when the creator switches modes.

## Information Architecture

Top IA tabs inside Voice Studio:

1. `Voice Identity`
2. `Voice Performance`
3. `Scene Dialogue`
4. `Takes`

Behavior:

- `Voice Identity` keeps the existing create / clone / approve identity flows.
- `Voice Performance`, `Scene Dialogue`, and `Takes` all render the same `VoicePerformanceStudio` workspace.
- The selected IA tab changes the creator's focus anchor inside the workspace instead of swapping to different technical panels.
- If `initialPhase` is `performance` or `voicePerformance`, Voice Studio opens on `Voice Performance`.

## Voice Identity Gate

If there is no approved Voice Identity:

- Show `Voice Identity Required`
- Show a single clear action: `Open Voice Identity`
- Do not create or infer a voice identity in the background

This keeps performance work tied to an explicit approved identity and aligns with creator trust requirements.

## Direction Model

Direction mode toggle:

- `Co-Director Recommended` (default)
- `Manual Direction`

Rules:

- Switching modes must not erase the other mode's data.
- Co-Director mode can refresh a recommended plan from the backend.
- Manual mode exposes the same creative fields but leaves wording fully in the creator's hands.

## Emotion Sources

Available emotion source options:

- `Co-Director Performance`
- `Emotion Preset`
- `Emotional Reference Audio`
- `Voice Reference Emotion`
- `Advanced Emotion Mix`

Notes:

- Preset labels must match backend-approved preset labels exactly.
- Emotional Reference Audio uploads guide emotion only and do not imply voice creation.
- Advanced Emotion Mix unlocks raw IndexTTS2 vector controls only inside `Advanced`.

## Main Workspace Areas

### Scene Dialogue

- Large multiline dialogue field
- Copy should reinforce that the line is the primary creative anchor
- Editing dialogue is allowed without losing previous takes; a fresh record is created when needed

### Performance Plan

Core creator-facing controls:

- Emotion
- Intensity
- Delivery
- Pacing
- Breath
- Emphasis
- Subtext
- Performance Reference
- Co-Director Notes

Advanced:

- Raw emotion vector sliders
- Runtime/provider honesty details

### Takes

- Generate 1-4 takes
- Compare current takes
- Approve one take
- Send approved take to Timeline
- Prepare approved take for Lip Sync

## Behavioral Rules

- Approved Voice Identity is required before take generation.
- Runtime capability messaging must stay honest. If the runtime is not ready, the UI must say so and disable live generation.
- Timeline placement must not silently replace existing dialogue. Replacement needs an explicit second confirmation.
- Lip Sync preparation must not silently replace existing scene audio references. Replacement needs an explicit second confirmation.
- Approval is per take, and only one take is primary-approved at a time.

## Test IDs

Required Playwright targets:

- `voice-studio-ia`
- `voice-identity-tab`
- `voice-performance-tab`
- `voice-scene-dialogue-tab`
- `voice-takes-tab`
- `vp-direction-codirector`
- `vp-direction-manual`
- `vp-dialogue`
- `vp-performance-plan`
- `vp-emotion`
- `vp-intensity`
- `vp-delivery`
- `vp-pacing`
- `vp-breath`
- `vp-emphasis`
- `vp-subtext`
- `vp-generate-takes`
- `vp-take-card`
- `vp-compare`
- `vp-approve-take`
- `vp-send-timeline`
- `vp-prepare-lipsync`
- `vp-advanced-toggle`
- `vp-voice-identity-required`
- `vp-open-voice-identity`
- `vp-emotion-source`
- `vp-emotion-ref-upload`

## Visual Language

- Match existing Adept UI and Voice Studio patterns.
- Reuse `PanelHeading`, `Button`, and `HelpTip`.
- Avoid technical chrome as the primary interface.
- Avoid invented neon / purple-glow AI styling.
- Use progressive disclosure: creator-facing direction first, technical controls last.
