# M42 Qwen-2512 Style Intelligence Certification

## Scope

This document certifies the **style intelligence profile layer** requested in `subagent-assignments/Qwen2512StyleIntelligence.md`:

- standalone `studio-api/app/style_intelligence/` registry package
- ten required `VisualStyleProfile` records
- identity-versus-style separation rules
- detailed lock handling for `anime`, `realistic_anime`, `live_action`, `stop_motion`, and `claymation`
- focused unit proof in `studio-api/tests/test_style_intelligence.py`

This document does **not** certify live image generation and does **not** claim final GO.

## Delivered profiles

Implemented keys:

- `anime`
- `realistic_anime`
- `live_action`
- `stop_motion`
- `claymation`
- `stylized_3d_animation`
- `graphic_novel`
- `watercolor`
- `oil_painting`
- `documentary_realism`

Each profile contains:

- `key`
- `displayName`
- `identityPreservationRules`
- `renderingLanguage`
- `anatomyLanguage`
- `faceLanguage`
- `materialLanguage`
- `lightingLanguage`
- `colorLanguage`
- `cameraLanguage`
- `negativeConstraints`
- `qwen2512PromptRules`

## Identity-versus-style contract

The registry enforces that a style change is a rendering-layer transformation only. The profile rules explicitly forbid mutation of:

- eye color
- hair color / cut / silhouette
- ears and species markers
- body type / body proportions
- wardrobe structure and signature accessories
- circuitry / markings / tattoos
- personality cues and recognizable expression tendencies

The five highest-risk style transfers (`anime`, `realistic_anime`, `live_action`, `stop_motion`, `claymation`) received extra lock language so medium shifts do not become identity redesigns.

## Unit proof

Command executed:

```text
python -m pytest tests/test_style_intelligence.py
```

Result:

- `10 passed in 0.11s`

Covered assertions:

- all ten required keys exist and are returned in stable order
- every profile has all required fields populated
- identity locks explicitly cover eye color, hair, ears, body, wardrobe, circuitry, and personality
- detailed lock language exists for the five high-risk style transfers
- registry output is JSON-serializable
- unknown style lookups fail with a helpful error

## Evidence

- `studio-api/app/style_intelligence/__init__.py`
- `studio-api/app/style_intelligence/registry.py`
- `studio-api/tests/test_style_intelligence.py`
- `artifacts/m42/w43-qwen-2512/styles/style_registry_dump.json`
- `artifacts/m42/w43-qwen-2512/styles/same_character_different_style_examples.json`
- `artifacts/m42/w43-qwen-2512/styles/README.md`

## Limitation recorded

The checked-in `M42_QWEN_IMAGE_2512_DEFAULT_ADDENDUM.md` in this workspace does not currently contain the referenced sections 10-12. Implementation therefore followed:

- the assignment contract
- the addendum's explicit policy that character identity is separate from visual style
- the mandatory high-risk style locks requested in the implementation brief

## Non-claim

No live ComfyUI image-style run was performed here. No live style certification verdict and no final GO are claimed by this document.
