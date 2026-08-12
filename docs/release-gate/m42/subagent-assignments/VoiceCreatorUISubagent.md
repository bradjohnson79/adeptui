# Assignment — VoiceCreatorUISubagent

```yaml
role: VoiceCreatorUISubagent

owned_scope:
  - Voice Creator beginner workflow / progressive disclosure
  - HelpTips on Voice Creator controls
  - Clone/upload path must call real validate/generate APIs (not UI-only staging)

allowed_files:
  - studio-web/src/components/VoiceCreatorWorkspace.tsx
  - studio-web/src/styles.css  # .voice-studio-* only

forbidden_files:
  - provider adapters
  - queue services
  - database migrations
  - Character Creator visual sheet
  - Voice Performance workspace (unless coordinated)
  - certification gate logic

inputs:
  - M42_VOICE_UX_SIMPLIFICATION_ADDENDUM.md
  - M42_SUBAGENT_SHARED_CONTRACTS.md § Voice Creator

required_outputs:
  - Subagent Handoff
  - clone/upload wiring status
  - known limitations

tests_owned:
  - coordinate with TestSubagent on m42-w43-korri-voice-creator.spec.ts

dependencies:
  - backend voice clone routes already exist (validate-reference, clone/generate)

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/VoiceCreatorUISubagent.md

escalation_conditions:
  - shared API contract must change
  - clone requires new backend endpoint
```
