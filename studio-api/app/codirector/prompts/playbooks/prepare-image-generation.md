---
id: prepare-image-generation
version: 1.0.0
type: playbook
display_name: Prepare Image Generation
description: Image generation package and proposal.
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

# Prepare Image Generation

## Purpose
Proposal/plan playbook only. Use this when the creator is **planning** an image
package or asking for a proposal — not when they have already given a complete
visual brief and said generate/create the image now.

COMMAND + READY stills are dispatched by the execution path. Do not hand the
creator a prompt to run themselves. Optimized prompts are internal to the job.

## Step Sequence
1. Resolve active project and scope (scene/shot).
2. Compile bounded Production Bible context.
3. Select specialists per intent and stage.
4. Collect structured specialist findings.
5. Synthesize one recommendation.
6. Build production plan mapped to registered tools.
7. Create M2.2 proposals for mutating/generation steps.
8. Await user approval before execution — unless the turn is already a
   COMMAND + READY still (then the dispatcher submits the job).
9. Record receipts and mark visual validation pending where applicable.