# UX, ERS, Scene Creator, Timeline, Co-Director

## Spatial Map

Movement accordion sits after the grid/inspectors and before placement slots.
One section is open. `+ Add Movement` disables at five. Trash exists only on
M2–M5. Arrows are SVG overlays from saved coordinates.

## ERS

LLM sheet stays 2560×1440. After camera overlay, a taller sheet is assembled:
core + camera band + movement refs. Mini hero crop uses the core rectangle.

## Scene Creator

Mini: Movement select beside Generator / Frame Size. Packet hydrates from the
selected segment. Provenance stores movement id/number/revision/camera/variation.

Standard: Movement select after Environment, before Cinematographer. Shot
overrides do not write back.

## Timeline

`PromptSegment.movement_segment_ref` is structured. Visible `~M1` is derived.
W46 compile injects unchanged / start / end / action / Timed Prompt layers.

## Co-Director

New tools: `spatial.save`, movement CRUD/activate, `spatial.plan_movements`
(recommend only), `scene_creator_mini.create_take`, `workspace.open_scene_creator`.
Mini generate and movement delete are never auto-approved.
