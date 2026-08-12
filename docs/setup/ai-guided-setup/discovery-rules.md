# Discovery Rules

## Guiding rule

Recommendations must prefer Adept-certified recipes and creator fit. They must not chase arbitrary upstream latest versions.

## Current recommendation rules

- `photoreal` or `character` intent prefers `FLUX.1 Kontext Dev`.
- `anime` or stylized illustration intent prefers `Sana 1.5`, `Qwen-Image-2512`, or `Z-Image Turbo`.
- `fast` or `preview` intent prefers `FLUX.1 Schnell`.
- General local image work continues to surface `Qwen-Image-2512`, `FLUX.1 Dev`, and `Z-Image Turbo` depending on posture.

## Search inputs

The lifecycle search path reads:

- component id/name/description from setup catalog
- capability tags
- creator-facing badges
- best-for text
- lifecycle recommendations and certified recipe availability

## Honesty rules

- Catalogued but not verified is not `Ready`.
- Experimental entries remain `Requires Setup` or equivalent lifecycle attention until verified/certified.
- Cloud providers remain separate from local installable models.
