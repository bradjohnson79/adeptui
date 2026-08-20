# Depth Anything V2 Small — License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

**CLEARED for optional Testing / Co-Director Scene Perception** under Apache License 2.0 — **Small weights only**.

Not Essential. Not `required=True`. Not in `REQUIRED_FOR_GENERATION`. Prepare My Studio must not force-download this component.

## Pinned authoritative sources

- Hugging Face model repository: `depth-anything/Depth-Anything-V2-Small-hf`
- Pinned repository revision: `5426e4f0f36572d16453bbda7a8389317b1bef99`
- Hugging Face license tag: `apache-2.0` (`cardData.license`, `license:apache-2.0` tag)
- Live API reconfirm (`2026-08-20`): `gated=false`, `private=false`, card license `apache-2.0`
- Model card: `https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf`
- Apache License 2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt`

## Marker files (install / verify)

| File | Role |
|---|---|
| `config.json` | Install marker |
| `preprocessor_config.json` | Install marker |

## Explicit exclusions

Depth Anything V2 **Base** and **Large** are published under **CC-BY-NC-4.0**. They are **REJECTED** for Adept UI catalog, download, or fallback. Do not add an OR between Small and Large.

Apple Depth Pro and Video-DA Base/Large are also out of scope.

Ordinal depth only. This is not metric blocking.

## Commercial use / redistribution

| Question | Finding |
|---|---|
| Commercial use (Small) | Permitted under Apache 2.0 |
| Commercial use (Base / Large) | **No** — CC-BY-NC-4.0 |
| Redistribution (Small) | Permitted with license notice and NOTICE retention |

## Adept UI treatment

- Setup catalog id: `depth_anything_v2_small`
- `required=False`
- Lifecycle badge: Testing / Co-Director Scene Perception
- Isolated install root: `{data_dir}/models/stills_perception/depth_anything_v2_small`
- Isolated venv: `{data_dir}/venvs/stills-perception-worker`
- Installer: `stills_perception_hf` — never Hunyuan fallback
- PerceptionPacket stores ordinal layers (`near` / `mid` / `far`) only

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face card license tag changes, or if a later snapshot mixes NC weights.
- Do not promote to Essential without a later named Setup decision.
