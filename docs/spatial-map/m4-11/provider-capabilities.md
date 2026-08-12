# Provider Capabilities

Spatial Map M4.11 is intentionally honest about what downstream generators can and cannot do today.

## Honesty default

- Default provider honesty: `approximate_translation`
- Native coordinate execution is not assumed unless a downstream provider explicitly supports it.

## Current coverage

- Image Generator: consumes plain-language spatial conditioning plus project reference assets.
- Text to Video: consumes plain-language spatial conditioning; fal-backed paths can attach best-effort still references.
- Storyboard: preserves linkage metadata only.

## Non-claims

- No provider currently receives raw `adept-world-v1` coordinates as a guaranteed native camera/blocking contract.
- Local LTX/WAN do not execute saved movement paths directly.
- fal integrations use prompt summary and optional still refs, not full geometric reconstruction.
