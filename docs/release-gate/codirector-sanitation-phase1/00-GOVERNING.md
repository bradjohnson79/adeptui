# Co-Director Sanitation Phase 1 — Governing

**Law 30:** this is the only governing document for Co-Director Sanitation Phase 1.

Completion report (later): `PHASE-1-UNIFIED-COMPLETION.md`.

Do not extend Revision A/B/C/D or PoseCraft overhaul governing docs into this program.

## Branch

- Implement on `feat/codirector-sanitation-phase1`
- Created from `feat/codirector-temporal-continuity`
- Certified PoseCraft overhaul commits integrated from `feat/posecraft-v4-human-replacement`
- Do not merge unrelated dirty-tree files

## What this is

Sanitation and certification of the unified production pipeline:

CRS + Spatial Map / ERS + PoseCraft + Working Context + Confidence + Co-Director + Vision + Scene Creator + Timeline

This is not a new v1.1 feature family. Do not rebuild PoseCraft. Do not create PoseCraft v5. Do not change the 17-joint semantic rig unless a sanitation test proves a genuine defect.

## Frozen

- Spatial Map `zones[]`
- TimeLens
- SAM 3
- MAGI fake video-inpaint
- `REQUIRED_FOR_GENERATION` inflation
- Chat `route_turn` as GPU router
- PoseCraft v5 / new pose network
- Learned preference writing Spatial Map or CRS

## One project

Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.  
Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`.

Isolation tests may use disposable projects. Generation and certification must not spawn a new project per image.

## Certified PoseCraft baseline

```text
GO — POSECRAFT FULL OVERHAUL + CO-DIRECTOR APPLY_POSE
```

Treat as starting truth: four v4 archetypes, body-region picking, selected joint handles, pose presets, manual manipulation, Visual Truth Law, save/reload, Camera mode isolation, `posecraft.apply_pose`, committed v4 runtime assets.

Record in the completion report:

```text
PoseCraft source SHA
Sanitation integration SHA
files integrated
merge/cherry-pick method
```

## Behavior law

Maximum useful autonomy. Minimum unnecessary questions.

Ask only when the answer would materially change the output.

## Confidence

Categorical only: **HIGH / MEDIUM / LOW** plus explicit reasons.

No theater floats (`0.92`).

| Level | When | Action |
| --- | --- | --- |
| HIGH | One approved active scene, request is camera/performance-only, no conflicting canon | Execute. Bind intent. |
| MEDIUM | Two plausible scenes/characters, or geography-override wording | One short production question. Bind the original instruction. On Yes, execute without re-asking. |
| LOW | No reliable scene / CRS / map | Clarify. No generation until resolved. |

Decay on scene change, project switch, tool/asset change, conflict, contradiction, or staleness.

## Memory layers

Each fact carries provenance and authority:

- PROJECT
- SCENE
- SHOT
- PERFORMANCE
- RECENT INTENT
- CANON
- OBSERVED
- USER PREFERENCE (workflow only)

## Authority ladder

```text
CURRENT FILMMAKER INSTRUCTION
        ↓
APPROVED SCENE / SHOT STATE
        ↓
CRS CHARACTER IDENTITY
        ↓
SPATIAL MAP / ERS / SCENE SPATIAL PROFILE
        ↓
POSECRAFT INTENDED PERFORMANCE / POSE
        ↓
OBSERVED GENERATED RESULT
        ↓
INFERENCE
        ↓
STALE CACHE / WORKFLOW PREFERENCE
```

- CRS = what Korri looks like
- PoseCraft = what Korri is physically doing
- Spatial Map = where Korri is
- Scene Creator = rendered production image

PoseCraft never becomes appearance canon. Learned preference never outranks the current filmmaker instruction.

## Working Context

One persisted document (`working-context-v1`) shared by chat, Scene Creator, Timeline, Character Creator, and PoseCraft.

Canonical stores remain authoritative. Working Context **references** them.

PoseCraft slice is compact:

```text
posecraft:
  sceneId
  revision
  activeFigureIds[]
  snapshotAssetId
  worldOriginMeters
  poseWorldStatePacketIds[]
```

Do not copy all 17 Euler values into conversational memory unless execution requires them.

## Visual Truth Law

```text
COMMAND / USER ACTION
        ↓
STRUCTURED STATE CHANGES
        ↓
VISIBLE GEOMETRY / SEMANTIC PERFORMANCE
        ↓
SAVE
        ↓
RELOAD
        ↓
SAME VISIBLE RESULT
```

Internal JSON alone is never PASS.

Pose-to-image preserves semantic performance intent (standing behind the counter, facing the customer), not pixel-perfect mannequin limb angles.

## Confirmation memory

A confirmation stores the original instruction plus the answer.

After Yes, execute. Do not ask again for the same bound instruction.

## Chat is not the GPU router

`route_turn` reads Working Context. It does not become the perception / GPU router.

## Observability

Diagnostics only (never creator chrome):

- `activePosecraftSceneId`
- `activePosecraftRevision`
- `resolvedFigureIds`
- `resolvedCharacterBindings`
- `poseSource`
- `posePreset`
- `poseWorldStatePacketIds`
- `poseConfidenceReasons`
- active scene, confidence level, reasons, sources, asked?, locked vs changed

## Hard gates

1. CRS sanitation must GO before Korri-in-Schnick is authoritative.
2. Certified PoseCraft commits must be on this branch before Track B2 / Track C pose claims.
3. Isolated subsystem GO is not Phase 1 GO.

## Final language

```text
GO — CRS SANITATION
GO — CO-DIRECTOR WORKING CONTEXT
GO — CONFIDENCE / CLARIFICATION BEHAVIOR
GO — POSECRAFT + CO-DIRECTOR OPERATIONAL INTEGRATION
GO — KORRI IDENTITY GROUNDING
GO — SCHNICK SPATIAL GROUNDING
GO — POSE / PERFORMANCE GROUNDING
GO — VISUAL TRUTH
GO — SCENE CREATOR HANDOFF
GO — TIMELINE HANDOFF
GO — RELOAD / API-RESTART RECOVERY

FINAL:
GO — CO-DIRECTOR SANITATION PHASE 1
```

Anything less:

```text
NO-GO — CO-DIRECTOR SANITATION PHASE 1 INCOMPLETE
```
