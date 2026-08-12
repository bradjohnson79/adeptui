# M4.12 Avatar Runtime Installation

Status: implementation wiring for Setup + Source Manager. Providers remain **Experimental** until live benchmark coverage exists. Do not market any provider as Certified or production-ready from this document alone.

## Runtime IDs and roots

All avatar runtimes install into isolated folders and do not share the main API virtual environment.

| Provider ID | Creative-facing name | Creative role | Recommended runtime root |
| --- | --- | --- | --- |
| `longcat-video-avatar-1-5-local` | LongCat Avatar 1.5 | Flagship full-body avatar performance | `data/runtimes/avatar/longcat-video-avatar-1-5/` |
| `infinitetalk-local` | InfiniteTalk | Secondary long-form streaming avatar | `data/runtimes/avatar/infinitetalk/` |
| `musetalk-1-5-local` | MuseTalk 1.5 | Repair / dubbing specialist | `data/runtimes/avatar/musetalk-1-5/` |
| `echomimic-v2-local` | EchoMimicV2 | Half-body performance specialist | `data/runtimes/avatar/echomimic-v2/` |

Each runtime keeps:

- `source/` pinned upstream code checkout
- `venv/` isolated Python runtime
- `models/` pinned model downloads
- `logs/` install and benchmark records
- `adept-runtime.json` install metadata, pins, and health state

## Audited pins in use

### LongCat Avatar 1.5

- Code repo: `https://github.com/meituan-longcat/LongCat-Video`
- Code pin: `6b3f4b8582a8bc3f20f795735f5383716c4ba794`
- Model repo: `meituan-longcat/LongCat-Video-Avatar-1.5`
- Model pin: `92016c71d5d318d0f5d84e4db30015a571484ab6`
- Base model repo: `meituan-longcat/LongCat-Video`
- Base model pin: `03b55529b1d1d4045f5fbe14d65c8c6e8116b278`

### InfiniteTalk

- Code repo: `https://github.com/MeiGen-AI/InfiniteTalk`
- Code pin: `50aa0a94184315407a991ae804d9b58d6d311ba8`
- Model repo: `MeiGen-AI/InfiniteTalk`
- Model pin: `d59847ebdacf19245bfca3fb23311c0cada8378a`
- Required dependency repo: `Wan-AI/Wan2.1-I2V-14B-480P`
- Required dependency pin: `6b73f84e66371cdfe870c72acd6826e1d61cf279`
- Required wav2vec file: `TencentGameMate/chinese-wav2vec2-base` at `refs/pr/1`, `model.safetensors`

### MuseTalk 1.5

- Code repo: `https://github.com/TMElyralab/MuseTalk`
- Code pin: `0a89dec45a0192b824e3cf4daf96c239440c5ed8`
- Model repo: `TMElyralab/MuseTalk`
- Model pin: `3ef28bc5cff08c90ad8178a25f1b570cd800170f`
- Required official files:
  - `models/musetalkV15/unet.pth`
  - `models/musetalkV15/musetalk.json`
- Additional official dependencies:
  - `stabilityai/sd-vae-ft-mse`
  - `yzd-v/DWPose`
  - `openai/whisper-tiny`

### EchoMimicV2

- Code repo: `https://github.com/antgroup/echomimic_v2`
- Code pin: `38c86809efa041884c774ee31d984a9577c0e0aa`
- Model repo: `BadToBest/EchoMimicV2`
- Model pin: `8648078a20057a7cdff6ccd6e91251fe19210533`
- Additional official dependencies:
  - `stabilityai/sd-vae-ft-mse`
  - `lambdalabs/sd-image-variations-diffusers`
  - `openai/whisper-tiny`

## Install flow in Setup / Source Manager

1. Open **Setup → Source Manager**.
2. In **Avatar Runtimes**, choose a provider card.
3. Click **Download and Install** or **Update**.
4. In the preflight dialog:
   - choose the destination folder
   - confirm the install
   - confirm the model download
5. Track progress in **Active Downloads** / install-job status.
6. When the install completes, the runtime remains labeled **Experimental** until live benchmarks exist.

### Other supported actions

- `Choose Install Location`: open the preflight dialog without starting immediately
- `Link Existing Folder`: attach an already-prepared runtime directory
- `Add Source URL`: save a user-supplied source override for a component
- `Verify`: re-check pins, files, launch path, environment, and GPU probe
- `Repair`: rerun the isolated install path with pinned sources
- `Benchmark`: record the benchmark hook placeholder and keep status Experimental
- `Remove`: delete the isolated runtime folder
- `Open Logs`: expose runtime log paths and benchmark/install records

## Health states

- `Not Installed`: no verified runtime files
- `Verifying`: install or explicit verification is in progress
- `Experimental`: pinned files, environment, launch path, and dependency probe passed, but live benchmark coverage is not available yet
- `Repair Required`: runtime root exists but one or more pins, files, probes, or paths failed verification

The implementation never silently upgrades an avatar runtime to a production-ready label.

## Current limitations and blockers

- `LongCat`, `InfiniteTalk`, and `EchoMimicV2` still carry official Windows-documentation gaps.
- `LongCat` and `InfiniteTalk` still need live VRAM-floor evidence from real benchmark runs.
- `MuseTalk 1.5` still carries license-review ambiguity between upstream code and model signals.
- `EchoMimicV2` still carries incomplete upstream model-license clarity.
- The benchmark action is a real hook/recording path, but not a live generation benchmark suite yet.

**READY FOR PRIMARY REVIEW**
