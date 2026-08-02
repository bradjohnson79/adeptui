# Co-Director Performance Intelligence

## Purpose

M4.10 adds a `voice.*` Co-Director tool surface for local voice direction.

Architecture stays fixed:

- Co-Director proposes
- Creator directs
- IndexTTS2 performs

The tools in this document sit on top of `studio-api/app/voice_performance/m410_service.py` and do not replace the existing `voice_performance.*` tool family.

## Registration

Read tools:

- `voice.performance_context`
- `voice.analyze_dialogue`
- `voice.create_performance_plan`
- `voice.create_scene_performance_plan`
- `voice.suggest_take_variations`
- `voice.compare_takes`
- `voice.adjust_performance`
- `voice.prepare_timeline_dialogue`
- `voice.prepare_lipsync`

Mutating tools:

- `voice.apply_performance_plan`
- `voice.approve_take`
- `voice.replace_timeline_dialogue`

## Runtime honesty

`voice.performance_context` reports the M4.10 IndexTTS2 runtime state honestly.

Expected states come from the local runtime inspection layer, including:

- `not_installed`
- `compatible`
- `installed`
- `ready`
- `repair_required`
- `checking`
- `verifying`
- `failed`

The new tool surface does not claim generation readiness when the local runtime is missing or incomplete.

## Tool behavior

### `voice.performance_context`

Returns the current M4.10 record, current take list, selected approved take, placement state, lip sync linkage state, and honest IndexTTS2 runtime status.

Use this first when Co-Director needs grounding before proposing changes.

### `voice.analyze_dialogue`

Analyzes a line of dialogue without persisting anything.

Returns:

- dialogue metrics
- a suggested line shape
- a proposed Co-Director plan
- a recommended take count

### `voice.create_performance_plan`

Builds a non-persisted Co-Director plan for an existing M4.10 dialogue record.

This is the main proposal tool for turning a saved record into a fresh direction pass.

### `voice.create_scene_performance_plan`

Builds non-persisted plans across all existing M4.10 records in a scene, including scene progression hints such as opening pressure or late-scene payoff.

### `voice.suggest_take_variations`

Builds alternate non-persisted takes from the current record plan so the creator can audition different reads before generation or approval.

### `voice.compare_takes`

Reads take status and comparison data without approving a winner.

### `voice.adjust_performance`

Produces an adjusted in-memory plan from the current record plan using preset, summary, pacing, delivery, breath, note, or emotion-vector overrides.

### `voice.prepare_timeline_dialogue`

Dry-runs timeline dialogue placement for the currently approved take.

Returns whether an existing clip would be replaced and the exact clip payload that would be written on confirmation.

### `voice.prepare_lipsync`

Dry-runs lip sync linkage for the currently approved take.

Returns whether scene lip sync or scene audio would be replaced before any write happens.

## Proposal and confirmation pattern

All mutating `voice.*` tools follow the existing Co-Director approval-gated pattern already used by other mutating tools in this codebase:

1. Co-Director prepares a preview.
2. The creator reviews the proposal.
3. Only an approved proposal can execute the apply step.

### `voice.apply_performance_plan`

Applies a creator-confirmed performance plan to the selected M4.10 record.

This updates direction metadata only. It does not silently generate new takes.

### `voice.approve_take`

Marks a creator-selected take as approved for the record.

This does not silently place the take on the timeline.

### `voice.replace_timeline_dialogue`

Writes the approved take into the target dialogue track and intentionally replaces matching dialogue clips for that record or script binding after approval.

The replacement behavior is shown in preview before it can be applied.

## Compatibility note

Existing `voice_performance.*` tools remain registered and unchanged in purpose.

The new `voice.*` tools are an M4.10 Co-Director-oriented layer for proposal, review, and creator confirmation around the same underlying local voice workflow.
