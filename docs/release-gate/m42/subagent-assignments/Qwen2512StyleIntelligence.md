# Assignment — Qwen2512StyleIntelligence (GPT-5.4)

```yaml
role: Style Intelligence
owned_scope: >
  Visual Style Registry profiles; identity-versus-style separation;
  style-specific Qwen-2512 prompt rules; forbidden style-drift rules.
allowed_files:
  - studio-api/app/style_intelligence/**              # NEW package
  - studio-api/tests/test_style_intelligence.py
  - artifacts/m42/w43-qwen-2512/styles/**
  - docs/release-gate/m42/M42_STYLE_INTELLIGENCE_CERTIFICATION.md
forbidden_files:
  - studio-api/app/image_prompting/**
  - studio-api/app/character_consistency/**
  - studio-api/app/workflows/**
  - config/character-canon/**
required_inputs:
  - Required styles: anime, realistic_anime, live_action, stop_motion, claymation,
    stylized_3d_animation, graphic_novel, watercolor, oil_painting, documentary_realism
required_outputs:
  - VisualStyleProfile records for all required keys
  - qwen2512PromptRules + negativeConstraints per style
  - identityPreservationRules that forbid identity mutation when style changes
tests_owned:
  - test_style_intelligence.py
dependencies: []
evidence_required:
  - style registry JSON dump
  - same-character/different-style prompt rule examples
escalation_conditions:
  - Real style certification image generation is primary-owned; provide profiles only
```
