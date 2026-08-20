# Grounding DINO Tiny — License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

**CLEARED for optional Testing / Co-Director Scene Perception** under Apache License 2.0.

Not Essential. Not `required=True`. Not in `REQUIRED_FOR_GENERATION`. Prepare My Studio must not force-download this component.

Apache 2.0 grants commercial use, reproduction, distribution, and creation of derivative works, with patent grant and notice-retention conditions. No non-commercial clause was found on the pinned Hugging Face card.

## Pinned authoritative sources

- Hugging Face model repository: `IDEA-Research/grounding-dino-tiny`
- Pinned repository revision: `a2bb814dd30d776dcf7e30523b00659f4f141c71`
- Hugging Face license tag: `apache-2.0` (`cardData.license`, `license:apache-2.0` tag)
- Live API reconfirm (`2026-08-20`): `gated=false`, `private=false`, card license `apache-2.0`
- Model card: `https://huggingface.co/IDEA-Research/grounding-dino-tiny`
- Apache License 2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt`

## Marker files (install / verify)

Poll-safe Setup verify checks presence only. Full shard hashing runs at install/certify, never on `/api/setup/status`.

| File | Role |
|---|---|
| `config.json` | Install marker |

## Code license vs weight license

- Transformers-native Grounding DINO Tiny. Adept loads via Hugging Face Transformers — no Deformable Attention compile, no Grounded-SAM-2 vendor.
- Grounded-SAM 2 (IDEA-Research glue repo + 1.5 / DINO-X) is **rejected** as a product dependency.

## Commercial use / redistribution

| Question | Finding |
|---|---|
| Commercial use | Permitted under Apache 2.0 |
| Redistribution | Permitted with license notice and NOTICE retention |
| Derivative works | Permitted |
| Cloud/service restriction | None found on the pinned card |

## Adept UI treatment

- Setup catalog id: `grounding_dino_tiny`
- `required=False`
- Lifecycle badge: Testing / Co-Director Scene Perception
- Isolated install root: `{data_dir}/models/stills_perception/grounding_dino_tiny`
- Isolated venv: `{data_dir}/venvs/stills-perception-worker`
- Installer: `stills_perception_hf` — never Hunyuan fallback, never VideoChat3 dest
- Capability: Testing until a later Windows live-load promotion gate

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face card license tag changes.
- Do not promote to Essential without a later named Setup decision.
