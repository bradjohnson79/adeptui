# Certified Recipes

## Current registry

Recipes live under `config/setup/certified-recipes/`.

Current certified recipes added in this branch:

- `index_tts2.local.certified`
- `hunyuan_video_15.local.certified`

## Recipe responsibilities

Each recipe provides:

- target `componentId`
- certified version/date
- trusted source metadata
- dependency expectations
- calibration defaults
- notes and guardrails

## Preference rule

When a component has a certified recipe, AI-Guided Setup should recommend that recipe first and treat it as the authoritative update target.

## Non-goal

Recipes do not allow Co-Director to execute custom install logic. They annotate and constrain trusted install flows.
