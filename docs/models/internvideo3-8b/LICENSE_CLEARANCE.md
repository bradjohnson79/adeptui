# InternVideo3-8B-Instruct License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

**CLEARED for optional / hardware-gated install** under Apache License 2.0, subject to the pinned sources below.

Not a required Adept UI boot component. Absence on low-VRAM machines is honest “Deep sequence reasoning unavailable,” not a program failure.

## Pinned authoritative sources

- Official project README: `https://github.com/OpenGVLab/InternVideo/blob/main/InternVideo3/README.md`
- Official GitHub-referenced weights: `yanziang/InternVideo3-8B-Instruct` (not `OpenGVLab/` on Hugging Face)
- Pinned repository revision: `c4602918b65225650d152db2850fe34e01d21fcd`
- Hugging Face license tag: `apache-2.0`
- README license sentence: `This project is released under the Apache 2.0 License.`
- OpenGVLab InternVideo LICENSE: `https://raw.githubusercontent.com/OpenGVLab/InternVideo/main/LICENSE`
- OpenGVLab LICENSE SHA-256: `42182091dd722231018a04a0b950fcd068cbf18a535b64e06eb8b080499cb34c`
- Apache License 2.0 SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`
- Model-card README SHA-256 (fetched 2026-08-20): `ed2fad31b939e5379312aa82ce7a09ff4ab8ab25a18e2911b2f6ed309225d0b1`

## Supply-chain note

Weights are hosted under the `yanziang` Hugging Face namespace. OpenGVLab’s official InternVideo3 README lists that exact repo. Adept UI must pin revision `c4602918b65225650d152db2850fe34e01d21fcd` and must not follow an unpinned `OpenGVLab/InternVideo3-8B-Instruct` alias unless that repo is later published and re-audited.

No standalone `LICENSE` file exists in the Hugging Face sibling list. License is taken from the model-card tag plus the OpenGVLab Apache-2.0 repository LICENSE.

## Base-model inheritance

InternVideo3 is built on a Qwen3-VL 8B-class backbone. Qwen3-VL-8B-Instruct is published under Apache-2.0.

## Commercial use / redistribution

| Question | Finding |
|---|---|
| Commercial use | Permitted under Apache 2.0 |
| Redistribution | Permitted with notice retention |
| Derivative works | Permitted |
| Cloud/service restriction | None found |
| Territory restriction | None found |

## Adept UI treatment

- Setup catalog id: `internvideo3_8b`
- `required=False`, hardware-gated
- Isolated install root under `{data_dir}/models/video_understanding/internvideo3-8b`
- Recommended VRAM: 16 GB. Do not auto-install on machines that cannot run it.

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face namespace, license tag, or README license sentence changes.
