# M4.12 Provider Installation Matrix

Status: audit-only. Do not install yet. Do not mark any provider Ready.

Cross-links:

- Repository/workflow audit: `docs/release-gate/m412/M412_REPOSITORY_AND_AVATAR_WORKFLOW_AUDIT.md`
- Audit pointer: `docs/avatar-studio/m4-12/repository-audit.md`
- Capability audit: `docs/avatar-studio/m4-12/provider-capability-audit.md`

## Purpose

This matrix converts the official-source research pass into install-planning inputs:

- exact pin recommendations
- dependency surfaces
- platform constraints
- storage / GPU unknowns that still block runtime implementation

## Install planning matrix

| Provider | Adept provider ID | Creative role | Official code repo | Recommended code pin | Official model repo | Recommended model pin | Required upstream model deps | Python / Torch / CUDA | Official OS signal | ComfyUI signal | Storage signal from official sources | Install readiness unknowns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LongCat-Video-Avatar 1.5 | `longcat-video-avatar-1-5-local` | `flagship` (Experimental) | `meituan-longcat/LongCat-Video` | `6b3f4b8582a8bc3f20f795735f5383716c4ba794` | `meituan-longcat/LongCat-Video-Avatar-1.5` | `92016c71d5d318d0f5d84e4db30015a571484ab6` | `meituan-longcat/LongCat-Video` @ `03b55529b1d1d4045f5fbe14d65c8c6e8116b278` | Python 3.10; torch 2.6.0; torchvision 0.21.0; torchaudio 2.6.0; official wheels shown for `cu124` | Linux documented; Windows not documented | No official ComfyUI found | First-party checkpoints ~`147.34 GiB` total (`77.59 + 69.75 GiB`) | No official numeric VRAM floor; likely dedicated high-end GPU runtime only |
| InfiniteTalk | `infinitetalk-local` | `secondary` (Experimental) | `MeiGen-AI/InfiniteTalk` | `50aa0a94184315407a991ae804d9b58d6d311ba8` | `MeiGen-AI/InfiniteTalk` | `d59847ebdacf19245bfca3fb23311c0cada8378a` | `Wan-AI/Wan2.1-I2V-14B-480P` @ `6b73f84e66371cdfe870c72acd6826e1d61cf279`; `TencentGameMate/chinese-wav2vec2-base` with official README requirement for `model.safetensors` from `refs/pr/1` | Python 3.10; torch 2.4.1; torchvision 0.19.1; torchaudio 2.4.1; xformers 0.0.28; flash-attn 2.7.4.post1; official wheels shown for `cu121` | Linux documented; Windows not documented | Official repo says `comfyui` branch released; community wrapper also referenced | Exact total not fully enumerable from accessible official metadata during audit; wav2vec dependency alone ~`1.42 GiB` | Total storage still unclear; no official numeric VRAM floor; no official interrupted-run resume story |
| MuseTalk 1.5 | `musetalk-1-5-local` | `repair` (Experimental) | `TMElyralab/MuseTalk` | `0a89dec45a0192b824e3cf4daf96c239440c5ed8` | `TMElyralab/MuseTalk` | `3ef28bc5cff08c90ad8178a25f1b570cd800170f` | `stabilityai/sd-vae-ft-mse`; `yzd-v/DWPose`; Whisper tiny; face-parse-bisent; resnet18 | Python 3.10 recommended; torch 2.0.1; torchvision 0.15.2; torchaudio 2.0.2; official guidance says CUDA 11.7 while install examples use `cu118` / `pytorch-cuda=11.8` | Windows and Linux both documented | Community only, explicitly third-party | Enumerated official model repos subtotal ~`8.94 GiB`, plus additional direct-download artifacts | Official license signals conflict between README and model card; repo mixes v1.0 and v1.5 assets |
| EchoMimicV2 | `echomimic-v2-local` | `half-body` (Experimental) | `antgroup/echomimic_v2` | `38c86809efa041884c774ee31d984a9577c0e0aa` | `BadToBest/EchoMimicV2` (linked from official README) | `8648078a20057a7cdff6ccd6e91251fe19210533` | `stabilityai/sd-vae-ft-mse`; `lambdalabs/sd-image-variations-diffusers`; Whisper tiny | Python 3.10 recommended, tested on 3.8 / 3.10 / 3.11; torch 2.5.1; torchvision 0.20.1; torchaudio 2.5.1; xformers 0.0.28.post3; `torchao`; official guidance says `CUDA >= 11.7`, install example uses `cu124` | Linux documented and tested; Windows not documented | Community only | Enumerated official model repos subtotal ~`16.80 GiB`, plus additional audio asset | Model-license clarity incomplete; no official Windows guidance; pose-sequence preprocessing/runtime complexity |

## Recommended dependency pins by provider

### LongCat-Video-Avatar 1.5

- Code:
  - `https://github.com/meituan-longcat/LongCat-Video`
  - pin `6b3f4b8582a8bc3f20f795735f5383716c4ba794`
- Models:
  - `https://huggingface.co/meituan-longcat/LongCat-Video-Avatar-1.5`
  - pin `92016c71d5d318d0f5d84e4db30015a571484ab6`
  - `https://huggingface.co/meituan-longcat/LongCat-Video`
  - pin `03b55529b1d1d4045f5fbe14d65c8c6e8116b278`
- Environment:
  - Python 3.10
  - `torch==2.6.0`
  - `torchvision==0.21.0`
  - `torchaudio==2.6.0`
  - `flash_attn==2.7.4.post1`
  - `librosa`
  - `ffmpeg`
- Deployment notes:
  - official Avatar 1.5 path requires distillation mode
  - official docs also expose INT8 loading
  - plan for Linux GPU worker, not a lightweight cross-platform addon

### InfiniteTalk

- Code:
  - `https://github.com/MeiGen-AI/InfiniteTalk`
  - pin `50aa0a94184315407a991ae804d9b58d6d311ba8`
- Models:
  - `https://huggingface.co/MeiGen-AI/InfiniteTalk`
  - pin `d59847ebdacf19245bfca3fb23311c0cada8378a`
  - `https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P`
  - pin `6b73f84e66371cdfe870c72acd6826e1d61cf279`
  - `https://huggingface.co/TencentGameMate/chinese-wav2vec2-base`
  - use the exact `model.safetensors` pull from official README revision `refs/pr/1`
- Environment:
  - Python 3.10
  - `torch==2.4.1`
  - `torchvision==0.19.1`
  - `torchaudio==2.4.1`
  - `xformers==0.0.28`
  - `flash_attn==2.7.4.post1`
  - `librosa`
  - `ffmpeg`
- Deployment notes:
  - official docs support streaming mode, TeaCache, quantization, and multi-GPU
  - total install size still needs live confirmation before runtime implementation

### MuseTalk 1.5

- Code:
  - `https://github.com/TMElyralab/MuseTalk`
  - pin `0a89dec45a0192b824e3cf4daf96c239440c5ed8`
- Models:
  - `https://huggingface.co/TMElyralab/MuseTalk`
  - pin `3ef28bc5cff08c90ad8178a25f1b570cd800170f`
  - use the official 1.5 artifact path:
    - `models/musetalkV15/unet.pth`
    - `models/musetalkV15/musetalk.json`
- Other required official assets:
  - `https://huggingface.co/stabilityai/sd-vae-ft-mse`
  - `https://huggingface.co/yzd-v/DWPose`
  - Whisper tiny
  - face-parse-bisent
  - `resnet18-5c106cde.pth`
- Environment:
  - Python 3.10
  - `torch==2.0.1`
  - `torchvision==0.15.2`
  - `torchaudio==2.0.2`
  - `mmcv==2.0.1`
  - `mmdet==3.1.0`
  - `mmpose==1.1.0`
  - `mmengine`
  - `openmim`
- Deployment notes:
  - cleanest official Windows story
  - best fit for repair / dubbing runtime, not flagship avatar generation
  - legal review required because official code and model licensing signals diverge

### EchoMimicV2

- Code:
  - `https://github.com/antgroup/echomimic_v2`
  - pin `38c86809efa041884c774ee31d984a9577c0e0aa`
- Models:
  - `https://huggingface.co/BadToBest/EchoMimicV2`
  - pin `8648078a20057a7cdff6ccd6e91251fe19210533`
- Other required official assets:
  - `https://huggingface.co/stabilityai/sd-vae-ft-mse`
  - `https://huggingface.co/lambdalabs/sd-image-variations-diffusers`
  - Whisper tiny
- Environment:
  - Python 3.10 recommended
  - `torch==2.5.1`
  - `torchvision==0.20.1`
  - `torchaudio==2.5.1`
  - `xformers==0.0.28.post3`
  - `torchao`
  - `facenet_pytorch==2.6.0`
- Deployment notes:
  - Linux-first official posture
  - default official inference output path is `768x768` at `24 fps`
  - half-body worker candidate, not flagship avatar runtime

## Role-oriented recommendation matrix

| Role | Recommended provider | Why |
| --- | --- | --- |
| `flagship` | `longcat-video-avatar-1-5-local` | Best official support for long-form continuation, multi-person, stylized domains, and full-body synchronized avatar generation |
| `secondary` | `infinitetalk-local` | Strong official long-form / streaming story with image-to-video and video-dubbing coverage, but weaker install clarity |
| `repair` | `musetalk-1-5-local` | Best official cross-platform lip-sync / dubbing specialist with reusable avatar prep |
| `half-body` | `echomimic-v2-local` | Explicitly built for semi-body / half-body human animation with audio + pose conditioning |

## Remaining blockers before any install plan becomes actionable

1. The repository audit still comes first:
   - `docs/release-gate/m412/M412_REPOSITORY_AND_AVATAR_WORKFLOW_AUDIT.md`
2. `MuseTalk 1.5` license ambiguity must be resolved from official upstream.
3. `EchoMimicV2` model-license clarity must be confirmed from official upstream.
4. `LongCat-Video-Avatar 1.5` and `InfiniteTalk` need real GPU-floor validation because official docs do not publish deployment-grade VRAM minimums.
5. If Windows support is mandatory for non-repair runtimes, `LongCat`, `InfiniteTalk`, and `EchoMimicV2` all remain blocked by official documentation gaps.

## Provisional implementation order after contract freeze

1. `longcat-video-avatar-1-5-local`
2. `musetalk-1-5-local`
3. `infinitetalk-local`
4. `echomimic-v2-local`

Reason:

- `LongCat` is the strongest flagship target.
- `MuseTalk` is the easiest specialist runtime to isolate cleanly for repair work.
- `InfiniteTalk` is valuable but should follow after the first flagship contract is proven.
- `EchoMimicV2` is best treated as a later half-body expansion runtime.

**READY FOR PRIMARY REVIEW**
