# Assignment — LibraryScopeSubagent

```yaml
role: LibraryScopeSubagent

owned_scope:
  - One-project / one-library policy for Korri certs and character work
  - Stable project reuse (Korri Character Production / ADEPT_PROJECT_ID)
  - Prevent disposable multi-project spam from cert scripts

allowed_files:
  - scripts/m42_w43_korri_visual_sheet_cert.py
  - scripts/m33j_korri_create_from_brief.py
  - .cursor/rules/creator-first-ui.mdc
  - studio-web/src/components/CharacterProfileWorkspace.tsx  # copy only if coordinated
  - studio-web/src/components/TimelineCharacterCreatorPanel.tsx  # copy only if coordinated

forbidden_files:
  - workflow builders
  - voice provider adapters
  - queue / DB migrations
  - certification binary verdicts

inputs:
  - M42_SUBAGENT_SHARED_CONTRACTS.md § Project & library scoping
  - creator-first UI rule

required_outputs:
  - Subagent Handoff
  - proof cert script reuses stable project

tests_owned: []

dependencies:
  - KorriPipelineSubagent for product UI projectId usage

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/LibraryScopeSubagent.md

escalation_conditions:
  - product API creates projects per generation (architecture issue)
```
