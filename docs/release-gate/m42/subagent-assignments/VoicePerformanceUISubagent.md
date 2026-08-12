# Assignment — VoicePerformanceUISubagent

```yaml
role: VoicePerformanceUISubagent

owned_scope:
  - Voice Performance beginner steps (Dialogue → Listen)
  - progressive disclosure / Advanced drawer
  - creative labels without API renames

allowed_files:
  - studio-web/src/components/VoicePerformanceWorkspace.tsx
  - studio-web/src/styles.css  # .voice-studio-* only

forbidden_files:
  - provider adapters
  - queue services
  - Character Creator generation
  - certification gate logic

inputs:
  - M42_VOICE_UX_SIMPLIFICATION_ADDENDUM.md
  - M42_W44 readiness flags

required_outputs:
  - Subagent Handoff
  - readiness integration notes (readyForPerformance)

tests_owned:
  - coordinate with TestSubagent on m42-w44-voice-performance.spec.ts

dependencies:
  - approved voice from Voice Creator for full path

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/VoicePerformanceUISubagent.md

escalation_conditions:
  - readiness false due to backend attach flags needing API change
```
