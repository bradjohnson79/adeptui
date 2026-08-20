# VideoChat3-4B License Clearance

Reviewed on `2026-08-20`. Live reconfirm `2026-08-20` (closure stage).

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

`PASS — VIDEOCHAT3 LICENSE CLEARED`

**CLEARED for required Setup essential** under Apache License 2.0, subject to the pinned sources below. The DeepSeek audit’s CC-BY-NC-4.0 weight claim does **not** match the live pinned card.

Apache 2.0 grants commercial use, reproduction, distribution, and creation of derivative works, with patent grant and notice-retention conditions. No non-commercial clause was found on the pinned model card or Hugging Face license tag.

## Pinned authoritative sources

- Hugging Face model repository: `MCG-NJU/VideoChat3-4B`
- Pinned repository revision: `37fa901ec5913f84bc31108ebc1e60ad1903634c`
- Hugging Face license tag: `apache-2.0` (`cardData.license`, `license:apache-2.0` tag)
- Live API reconfirm (`2026-08-20` closure): `sha=37fa901ec5913f84bc31108ebc1e60ad1903634c`, `gated=false`, `private=false`, `cardData.license=apache-2.0`, tag `license:apache-2.0`. No standalone `LICENSE` file at this revision (404). The card is the authority.
- Model card URL: `https://huggingface.co/MCG-NJU/VideoChat3-4B/tree/37fa901ec5913f84bc31108ebc1e60ad1903634c`
- Code repository: `https://github.com/MCG-NJU/VideoChat3`
- Paper: `https://arxiv.org/abs/2607.14935`
- Apache License 2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt`
- Apache License 2.0 SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Weight-file SHA-256 pins

Live Hugging Face tree at the pinned revision. LFS `oid` is SHA-256 of the blob.

| File | Bytes | SHA-256 |
|---|---:|---|
| `config.json` | 1765 | `d855aa0d9c6b6f223c9a293b9f1617a877a1ed0fb68a106ffcc084226ab3bf57` |
| `model.safetensors.index.json` | 75369 | `4d1a7577864c34d198fcc1812ede1d74798dd673588d085b1811f4516dc91593` |
| `model-0001-others-save_rank0.safetensors` | 4252181336 | `4c173466ec6a2c5e1544859021fbeac825067ccd54e80b887372d83b1c281654` |
| `model-0002-others-save_rank0.safetensors` | 4288942328 | `322af91f1ba81f290cee20d66bf0841be4826091e6e942688243b38bbc26e597` |
| `model-0003-others-save_rank0.safetensors` | 403726088 | `1c16eb013f0224c018db06148e28ee60bc1e2b47b1fffde0e311ed9debd63b90` |

Setup poll-safe verify hashes the two small files and checks shard **sizes**. Full shard SHA-256 runs once at install/certify, never on `/api/setup/status`.

## Code license vs weight license

- Hugging Face publishes no standalone `LICENSE` file in the sibling file list at the pinned revision. The weight license is declared on the model card as `apache-2.0`.
- The GitHub repository `MCG-NJU/VideoChat3` reports `license: null` via the GitHub API (no SPDX file). Product/code license is therefore taken from the Hugging Face model card, not from a GitHub LICENSE file.
- Custom modeling code is present (`trust_remote_code=True`). Adept UI pins the revision above and treats remote code as part of the same Apache-2.0 grant.
- Executed remote-code files (SHA-256 of the installed pinned blobs):

| File | Bytes | SHA-256 |
|---|---:|---|
| `modeling_videochat3.py` | 44545 | `853a76844c94612f350f222247983e734d70ebe37fc6778a4b3ea0e22bdc36f8` |
| `configuration_videochat3.py` | 7220 | `b2c6fe79f9fc9ac75466dc9be6cf2b95a530f6c1a06638bf87ae75289444d02e` |
| `processing_videochat3.py` | 16139 | `2cf662dca1391ad133ef80dad5cbb6505a0e30e3564881f6174dc6633e2c3696` |
| `video_processing_videochat3.py` | 18675 | `bf33cff1b70465ed3cb1e9dc748504ab2a612f54037324068aab1b487189f6d1` |
| `videochat3_utils.py` | 2897 | `fd528475338cce9969f43b65df88faf0a72455ab0eeb59cad740733060cef5ab` |

Source Manager may only snapshot `MCG-NJU/VideoChat3-4B` at this revision and the pinned `VIDEOCHAT3_REPO_FILES` list. `main` is never followed.

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
