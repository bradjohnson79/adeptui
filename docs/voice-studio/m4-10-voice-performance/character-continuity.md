# Character Continuity

## Continuity anchor

M4.10 performance records are anchored to the approved voice identity, not to ad hoc voice prompts.

Each `voice_performance_record` stores:

- `projectId`
- `sceneId`
- `scriptDocumentId`
- `scriptElementId`
- `characterId`
- `voiceIdentityId`
- `voiceIdentityVersion`
- `sceneArcId`

This lets dialogue direction stay tied to the same project, character, and voice lineage.

## Approval requirement

`m410_service.require_approved_voice_identity()` blocks record creation and take generation unless the referenced voice identity:

- exists
- belongs to the same project
- belongs to the same character
- is approved

That is the main continuity guardrail for live generation.

## Identity vs performance continuity

The approved voice identity supplies the reference voice clip used by `runtime/index_tts2.py`.

The M4.10 performance record separately stores direction continuity:

- active plan
- manual plan
- Co-Director plan
- emotion source
- emotion vector
- approved take

So the same character voice can be reused across many performance passes without losing a stable identity source.

## Scene progression continuity

`create_scene_batch()` can create multiple records in one pass and labels each item with scene progression hints such as:

- `opening pressure`
- `rising complication`
- `turning pressure`
- `late-scene payoff`

Those progression labels feed Co-Director planning without changing the underlying voice identity.

## Current scope note

`voice_reference_emotion` is currently a saved emotion-source classification in the UI and record data. The implemented runtime still derives live synthesis from the approved voice identity reference audio plus the current performance plan, rather than a separate identity-emotion control path.
