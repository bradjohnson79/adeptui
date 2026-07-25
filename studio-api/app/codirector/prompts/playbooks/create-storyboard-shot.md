---
id: create-storyboard-shot
version: 1.0.0
type: playbook
display_name: Create Storyboard Shot
description: Next consistent storyboard shot — primary M2.4 vertical slice.
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

# Create Storyboard Shot

## Purpose
Next consistent storyboard shot — primary M2.4 vertical slice.

## Step Sequence
1. Resolve active project and scope (scene/shot).
2. Compile bounded Production Bible context.
3. Retrieve character appearance, wardrobe, location references, and adjacent shots.
4. Select specialists per intent and stage.
5. Collect structured specialist findings.
6. Synthesize one recommendation.
7. Build production plan mapped to registered tools.
8. Create M2.2 proposals for mutating/generation steps.
9. Await user approval before execution.
10. Record receipts and mark visual validation pending where applicable.