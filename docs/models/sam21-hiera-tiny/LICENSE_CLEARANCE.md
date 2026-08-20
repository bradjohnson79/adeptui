# SAM 2.1 Hiera Tiny — License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

**CLEARED for optional Testing / Co-Director Scene Perception** under Apache License 2.0.

Not Essential. Not `required=True`. Not in `REQUIRED_FOR_GENERATION`. Prepare My Studio must not force-download this component.

## Pinned authoritative sources

- Hugging Face model repository: `facebook/sam2.1-hiera-tiny`
- Pinned repository revision: `de431c4043854a71d8101e17995dfe596bf101a5`
- Hugging Face license tag: `apache-2.0` (`cardData.license`, `license:apache-2.0` tag)
- Live API reconfirm (`2026-08-20`): `gated=false`, `private=false`, card license `apache-2.0`
- Model card: `https://huggingface.co/facebook/sam2.1-hiera-tiny`
- Apache License 2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt`

## Marker files (install / verify)

| File | Role |
|---|---|
| `config.json` | Install marker |

## Explicit exclusions

- **SAM 3** — custom gated SAM License. Rejected as Essential. Not cataloged.
- Grounded-SAM 2 demo path and non-public 1.5 / DINO-X weights — rejected.

## Commercial use / redistribution

| Question | Finding |
|---|---|
| Commercial use | Permitted under Apache 2.0 |
| Redistribution | Permitted with license notice and NOTICE retention |
| Derivative works | Permitted |
| Cloud/service restriction | None found on the pinned card |

## Adept UI treatment

- Setup catalog id: `sam21_hiera_tiny`
- `required=False`
- Lifecycle badge: Testing / Co-Director Scene Perception
- Isolated install root: `{data_dir}/models/stills_perception/sam21_hiera_tiny`
- Isolated venv: `{data_dir}/venvs/stills-perception-worker`
- Installer: `stills_perception_hf` — never Hunyuan fallback
- Auto-mask stays **Testing** until a real `maskAssetId` is persisted. Boxes are not masks.

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face card license tag changes.
- Do not promote to Essential without a later named Setup decision.
