# M4.8 Cinematic Image Generator — UX Specification

## Route

Replaces legacy Image Generation at `?workspace=imagegen` via `CinematicImageStudio`.

## Primary surface (always visible)

Prompt · References · Category · Shot Intent · Ratio · Resolution · Batch (1–4) · Mode (Best Match / Choose Model / All Models) · Lens · Lighting · Color · **Continuity [Inherit from scene]** · Generate

## Continuity

Minimal control only — no continuity dashboard:

```
Continuity
[ scene id ] [ Inherit from scene ]
☐ Bind generate batch to continuity session
```

Approved frames append to `VisualContinuitySession.approvedImageIds`.

## Advanced (collapsed)

Negative · Seed · Steps · Guidance — diffusion jargon stays here.

## Results

Grouped by provider/family. Actions: Add to Storyboard · Edit · Variation.
