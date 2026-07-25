---
id: review-visual-criteria
version: 1.0.0
type: playbook
display_name: Review visual criteria
description: Criteria text used by M2.5 vision validators for structured checks.
output_schema: none
allowed_context:
  - scene
  - bible
  - generation_package
may_propose_tools: false
may_execute_tools: false
default_priority: 40
enabled: true
---

# Visual review criteria

Inspectors evaluate identity, continuity, technical quality, lighting, camera, composition, color, and motion (video).

Rules:

- Never claim certainty when models are absent.
- Blocking technical or identity failures cannot be averaged away.
- Corrections are proposals only; never regenerate or mutate the Bible silently.
