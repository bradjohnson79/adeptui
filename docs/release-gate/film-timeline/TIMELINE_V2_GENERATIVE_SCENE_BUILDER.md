# Timeline V2 — Generative Scene Builder

Timeline V2 builds the picture. MAGI finishes it.

The repeating loop is:

Prompt → generate a batch → Track → + → Prompt → generate the next batch → Track → repeat → stitch → hand the finished picture to MAGI.

## What Timeline owns

- Timed Prompt, references, scene, camera, color and lighting, templates
- Model, megapixels or quality, picture shape, duration, spoken language
- One generated video sequence
- Takes, Re-Take, Continue, Review & Extend
- Co-Director and Omni continuity between batches
- Preview, generation status, stitch, and the saved scene structure

Track is that sequence on one Visual lane. Clip width is the batch duration, the clips sit flush, and the ruler and playhead use the same clock as Preview. Mark In and Mark Out draw that same clock on the lane. It is not an editing timeline: there is no audio lane and no dissolve. A range inside one batch is replaced in place: the original file stays, and the lane shows the picture before the range, the new picture, and the picture after it. A range that crosses two batches is refused and the original picture stays. Track is available before the first generation. An empty lane has one plus, which opens the first shot. Once picture exists, the plus before the first clip creates the shot that happens immediately before, and the plus after the last clip continues what happens next. The earlier shot is inserted at the start of the scene after it finishes, and the existing picture shifts later. Add from Library appends an existing project video without copying that file. The preview action Send to MAGI names the assembled scene as the future post-production handoff. It does not upscale and it does not open MAGI yet.

```text
0s -------- 15s ----- 20s ----- 25s
[ Batch 1 · 15s ][ Batch 2 · 5s ][ Batch 3 · 5s ] [+]
```

Before the first finished batch, Prompt is active and Track is disabled. + does not generate and does not create an empty batch. It returns to Prompt so the filmmaker can write what happens next. After a later batch finishes, Track is shown again.

A failed or cancelled generation is not a batch. Deleting the last batch disables Track and returns to Prompt.

## Spoken language

Language sits in the Inspector after Duration. The default is English. The stored value is the authority. Speech heard in an earlier batch does not change it.

The sentence that reaches the renderer is:

> All spoken dialogue in this scene is in English. Do not introduce another spoken language unless the Timed Prompt explicitly asks for it. Speech heard in an earlier batch does not change this language. If nobody speaks, keep the scene silent.

MiniMax H3 has no language control on the reference node. The sentence is how that renderer, LTX, and the API models are told. A quiet Timed Prompt stays quiet.

## What Timeline no longer presents

Audio, SFX, music, and ambience lanes are not on Track. Those clips can still exist in the scene document. Voice Studio and Audio Studio still create the files. MAGI is where they will be placed. The soundtrack inside a generated video stays with that file.

## Models

- MiniMax H3 — Local: Ref2Video fast renderer, with the CD/Omni batch handoff already certified in `reports/TIMELINE_V2_H3_FAST_RENDERER_CONVERGENCE.md`
- LTX 2.5 — Local: LTX 2.5 Director, unchanged
- API models: their existing adapters

This screen change did not re-render the 15+5+5 or 10+7+12 seams.

## Verdicts

LTX Director modified? NO

GO — TIMELINE V2 LANGUAGE AUTHORITY CERTIFIED

GO — TIMELINE V2 GENERATIVE SCENE BUILDER REALIGNMENT CERTIFIED
