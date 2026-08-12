# M4.11 Coordinate System

## Canonical system

Spatial Map documents store coordinates in `adept-world-v1`.

Axis meanings:

- `X`: left / right
- `Y`: up / down
- `Z`: forward / back

## Storage policy

The backend stores only the canonical internal coordinates.

Creator-facing language remains separate and human-readable, for example:

- foreground / midground / background
- left / center / right
- high / eye level / low

This allows UI layers to stay creator-first without discarding precise internal placement.

## Provider honesty

Spatial bundles expose whether downstream systems are using:

- `native_coordinates`
- `approximate_translation`

The current backend defaults to honest approximate translation unless a native coordinate consumer is explicitly available.
