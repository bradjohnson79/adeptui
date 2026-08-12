# Assignment — KorriPipelineSubagent

```yaml
role: KorriPipelineSubagent

owned_scope:
  - Character Creator visual-sheet wiring (API + UI)
  - Korri seed → generate → advance → approve path
  - Role asset attachment / heal into Character Profile references

allowed_files:
  - studio-api/app/character_identity/visual_sheet.py
  - studio-api/app/character_identity/api.py
  - studio-api/app/character_identity/service.py
  - studio-web/src/components/CharacterProfileWorkspace.tsx
  - studio-web/src/components/TimelineCharacterCreatorPanel.tsx

forbidden_files:
  - studio-api/app/workflows/**
  - config/image-workflows/**
  - Voice Creator / Voice Performance workspaces
  - certification gate logic / binary verdict docs (primary only)
  - provider adapters outside character_identity

inputs:
  - docs/release-gate/m42/M42_SUBAGENT_GOVERNANCE.md
  - docs/release-gate/m42/M42_SUBAGENT_SHARED_CONTRACTS.md
  - existing visual_sheet + Character Creator reports

required_outputs:
  - Subagent Handoff (structured)
  - gap list (if any)
  - no certification claims

tests_owned:
  - studio-api/tests/test_m42_w43_character_creator.py (read/run; fix only if in allowed files)

dependencies:
  - ComfyWorkflowSubagent for zimage builder / registry
  - LibraryScopeSubagent for stable project policy

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/KorriPipelineSubagent.md

escalation_conditions:
  - shared API contract must change
  - required file outside allowed scope
  - Comfy workflow fingerprint mismatch
  - architecture blocks completion
```
