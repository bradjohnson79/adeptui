# VideoChat3-4B License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

**CLEARED for required Setup essential** under Apache License 2.0, subject to the pinned sources below.

Apache 2.0 grants commercial use, reproduction, distribution, and creation of derivative works, with patent grant and notice-retention conditions. No non-commercial clause was found on the pinned model card or Hugging Face license tag.

## Pinned authoritative sources

- Hugging Face model repository: `MCG-NJU/VideoChat3-4B`
- Pinned repository revision: `37fa901ec5913f84bc31108ebc1e60ad1903634c`
- Hugging Face license tag: `apache-2.0` (`cardData.license`, `license:apache-2.0` tag)
- Model card URL: `https://huggingface.co/MCG-NJU/VideoChat3-4B/tree/37fa901ec5913f84bc31108ebc1e60ad1903634c`
- Code repository: `https://github.com/MCG-NJU/VideoChat3`
- Paper: `https://arxiv.org/abs/2607.14935`
- Apache License 2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt`
- Apache License 2.0 SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Code license vs weight license

- Hugging Face publishes no standalone `LICENSE` file in the sibling file list at the pinned revision. The weight license is declared on the model card as `apache-2.0`.
- The GitHub repository `MCG-NJU/VideoChat3` reports `license: null` via the GitHub API (no SPDX file). Product/code license is therefore taken from the Hugging Face model card, not from a GitHub LICENSE file.
- Custom modeling code is present (`trust_remote_code`, `modeling_videochat3.py`). Adept UI must pin the revision above and treat remote code as part of the same Apache-2.0 grant.

## Base-model inheritance

VideoChat3-4B uses Qwen3-4B as the language backbone. Qwen3 family weights are published under Apache-2.0. No Qwen Research / non-commercial overlay was observed for Qwen3-4B.

## Commercial use / redistribution

| Question | Finding |
|---|---|
| Commercial use | Permitted under Apache 2.0 |
| Redistribution | Permitted with license notice and NOTICE retention |
| Derivative works | Permitted |
| Cloud/service restriction | None found on the pinned card |
| Territory restriction | None found |

## Adept UI treatment

- Setup catalog id: `videochat3_4b`
- `required=True` (same Setup class as ComfyUI)
- Isolated install root under `{data_dir}/models/video_understanding/videochat3-4b`
- Do not silently upload clips to hosted VLMs

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face card license tag changes, or if a LICENSE file appears with different terms.
- Custom `trust_remote_code` modules must stay pinned to the revision above.
