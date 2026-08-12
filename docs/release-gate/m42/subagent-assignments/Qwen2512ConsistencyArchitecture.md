# Assignment — Qwen2512ConsistencyArchitecture (GPT-5.4)

```yaml
role: Character Consistency Architecture
owned_scope: >
  Reference-role schema, generation recipe persistence, seed policy,
  deviation report contracts, correction-loop contracts, multi-view method selection.
allowed_files:
  - studio-api/app/character_consistency/**           # NEW package
  - studio-api/tests/test_character_reference_roles.py
  - studio-api/tests/test_character_deviation_report.py
  - artifacts/m42/w43-qwen-2512/consistency/**
  - docs/release-gate/m42/M42_CHARACTER_CONSISTENCY_ARCHITECTURE.md
forbidden_files:
  - studio-api/app/image_prompting/**
  - studio-api/app/style_intelligence/**
  - studio-api/app/workflows/**
  - studio-web/src/components/CharacterProfileWorkspace.tsx
required_inputs:
  - Prompt: reference roles + CharacterDeviationReport interface
required_outputs:
  - ReferenceRole enum/schema
  - GenerationRecipe persistence helpers
  - SeedPolicy (explore/refine/production)
  - DeviationReport model + evaluator scaffold (honest scores, no fake precision)
  - MultiViewMethod A/B selection contract
tests_owned:
  - test_character_reference_roles.py
  - test_character_deviation_report.py
dependencies: []
evidence_required:
  - identity/reference-role manifests
  - recipe schema
  - sample deviation + correction-cycle records
escalation_conditions:
  - Needs DB migration beyond package-local storage — escalate to primary
```
