---
id: review-visual-result
version: 1.0.0
type: playbook
display_name: Review Visual Result
description: Reasoning-based visual review.
output_schema: playbook-v1
allowed_context:
  - project_overview
  - scene
  - shot
  - characters
  - locations
  - continuity
  - references
  - capabilities
may_propose_tools: true
may_execute_tools: false
default_priority: 50
enabled: true
---

# Review Visual Result

## Purpose
Reasoning-based visual review.

## Step Sequence
1. Resolve active project and scope (scene/shot).
2. Compile bounded Production Bible context.
3. Select specialists per intent and stage.
4. Collect structured specialist findings.
5. Synthesize one recommendation.
6. Build production plan mapped to registered tools.
7. Create M2.2 proposals for mutating/generation steps.
8. Await user approval before execution.
9. Record receipts and mark visual validation pending where applicable.