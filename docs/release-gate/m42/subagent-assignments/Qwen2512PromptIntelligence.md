# Assignment — Qwen2512PromptIntelligence (GPT-5.4)

```yaml
role: Qwen Prompt Intelligence
owned_scope: >
  Qwen-Image-2512-specific Co-Director prompt compiler, identity locks,
  negative constraints, prompt validation, correction prompt generation.
allowed_files:
  - studio-api/app/image_prompting/**                 # NEW package
  - studio-api/tests/test_qwen_2512_prompt_compiler.py
  - studio-api/tests/test_character_identity_lock.py
  - studio-api/tests/test_character_correction_compiler.py
  - artifacts/m42/w43-qwen-2512/prompts/**
  - docs/release-gate/m42/M42_QWEN_2512_PROMPT_INTELLIGENCE_REPORT.md
forbidden_files:
  - studio-api/app/workflows/**
  - studio-api/app/style_intelligence/**
  - studio-api/app/image_runtime/**
  - studio-web/**
  - config/image-workflows/**
required_inputs:
  - config/character-canon/korri.v1.json
  - Official Qwen prompt guidance (no unverified community claims as facts)
required_outputs:
  - compiler.py, identity_lock.py, style_grammar.py (hooks only), composition_grammar.py,
    character_sheet_grammar.py, continuity_rules.py, negative_constraints.py,
    prompt_validator.py, deviation_corrector.py
  - CharacterImagePromptPackage assembly from structured identity
  - Stable 13-block prompt order
  - Reject blonde/blue-eyed/human-ear Korri traits
tests_owned:
  - test_qwen_2512_prompt_compiler.py
  - test_character_identity_lock.py
  - test_character_correction_compiler.py
dependencies: []
evidence_required:
  - compiled Korri prompts
  - rejection samples
  - correction examples
escalation_conditions:
  - Needs Style Registry concrete profiles (owned by Style subagent) — use hooks/interfaces only
```
