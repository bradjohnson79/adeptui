# M4.11 Spatial Map UX

## Goal

Build an artist-facing blocking workspace for filmmakers, not an engineering console.

The Spatial Map experience should feel like a production planning board:

- the canvas is the hero
- the inspector is secondary
- camera and placement language stays plain
- advanced numeric controls stay collapsed until needed

## Locked UX

### Primary tabs

1. `Spatial Map`
2. `360° Collage`
3. `Camera Views`
4. `Export`

### Creative language

Use filmmaker-first labels:

- `Place Character`
- `Place Prop`
- `Move Camera`
- `Near Window`
- `Foreground`
- `Midground`
- `Background`

Do not lead with engineering vocabulary such as coordinates, matrices, transforms, or raw scene JSON.

### Capacity limits

- Max `4` characters
- Max `4` props
- Max `8` cameras

When a limit is reached, the block must be obvious and readable. Do not silently fail.

## Layout model

### Spatial Map

- Large top-down blocking canvas
- Optional background plate
- Drag to place and reposition
- Facing direction is always visible
- Rotation remains available, but does not dominate the interface

### 360° Collage

- Eight directional slots:
  `Front`, `Front Right`, `Right`, `Rear Right`, `Rear`, `Rear Left`, `Left`, `Front Left`
- Each slot may carry:
  - a reference image
  - a capture status
  - a creative note
- Generate 360 must call the live capture planner first, then create the collage document

### Camera Views

- Show the current camera lineup clearly
- Surface lens, movement, rig, and shot-size language in a readable way
- Help the creator understand coverage, not camera metadata for its own sake

### Export

- Build a camera brief from the map
- Queue a preview frame
- Assign the current spatial setup back to the scene

## Design constraints

- Reuse existing `Button`, `PanelHeading`, and `HelpTip` patterns
- Match the Adept design system
- Avoid neon or purple-glow visual styling
- Prefer calm cards, subtle depth, and strong whitespace

## Integration notes

- `workspace=spatial` now mounts the M4.11 studio surface
- `api.spatialMap.*` is the frontend namespace for the feature
- M4.11 now speaks directly to `/api/spatial-map/projects/{projectId}/maps/*`
- No legacy scene-spatial fallback paths should remain inside `api.spatialMap.*`
