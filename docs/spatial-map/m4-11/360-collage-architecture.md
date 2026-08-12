# M4.11 360 Collage Architecture

## Rule

A Spatial 360 collage represents one environment seen from multiple directions, not eight unrelated generations.

## Required directions

Minimum required views:

- `front`
- `front_right`
- `right`
- `rear_right`
- `rear`
- `rear_left`
- `left`
- `front_left`

Optional views:

- `ceiling`
- `floor`
- `hero`

## Prompt discipline

Co-Director capture must use:

- one master environment prompt
- a locked camera height
- a locked lens
- yaw rotation only across the eight required directions

The backend generates directional prompts that explicitly say:

- same environment
- same lighting
- same set dressing
- do not redesign the world

## Continuity heuristics

The backend validates continuity by checking:

- required directions are present
- adjacent directions rotate in 45 degree steps
- adjacent prompt text does not diverge into unrelated world descriptions
- missing captured neighbors are flagged as warnings

These are heuristics only. They are advisory warnings, not claims of native 3D reconstruction.
