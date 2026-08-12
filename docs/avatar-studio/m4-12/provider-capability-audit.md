# M4.12 Provider Capability Audit

Status: audit-only, no installs, no runtime implementation, no UX rebuild.

Cross-links:

- Repository/workflow audit: `docs/release-gate/m412/M412_REPOSITORY_AND_AVATAR_WORKFLOW_AUDIT.md`
- Pointer: `docs/avatar-studio/m4-12/repository-audit.md`

Scope:

- Official sources only
- Exact revision pin recommendations for code and model repos
- No provider marked Ready
- All creative-role recommendations remain **Experimental** until live benchmarks

## Executive summary

`LongCat-Video-Avatar 1.5` is the strongest flagship candidate on paper: it is the most complete official release for long-form, multi-person, stylized, and continuation-heavy avatar generation, but it is also the heaviest by far and should be treated as a dedicated high-VRAM runtime.

`InfiniteTalk` is the clearest secondary long-form alternative: it explicitly supports streaming/unlimited-length generation, sparse-frame dubbing, and image-to-video, but its official install footprint is still partially opaque because the upstream model hosts did not expose a full storage tree during this audit.

`MuseTalk 1.5` is the best repair-oriented candidate from official docs: it is smaller, officially documented for both Windows and Linux, and purpose-built for real-time lip-sync/video dubbing rather than full avatar synthesis.

`EchoMimicV2` is the clearest half-body candidate: it is explicitly designed for semi-body / half-body human animation, but it is Linux-first in official documentation and still depends on pose assets plus heavier diffusion-style runtime components.

## Shared conclusions

1. None of the four providers should be labeled Ready yet.
2. `LongCat-Video-Avatar 1.5` is the only audited candidate whose official materials clearly position it as a broad flagship avatar runtime rather than a repair or niche specialist.
3. `MuseTalk 1.5` and `EchoMimicV2` are not direct substitutes for a flagship long-form avatar runtime:
   - `MuseTalk 1.5` is a lip-sync/video-dubbing system.
   - `EchoMimicV2` is a half-body human-animation system with pose conditioning.
4. `InfiniteTalk` has attractive long-form claims, but its official install matrix is less stable than `LongCat-Video-Avatar 1.5` because it layers custom weights on top of Wan 2.1 and leaves some storage details unpublished in accessible upstream metadata.
5. Official licensing is not equally clean across providers:
   - `LongCat-Video-Avatar 1.5`: clean MIT signal in code and model card.
   - `InfiniteTalk`: clean Apache-2.0 signal in code and model card.
   - `MuseTalk 1.5`: code/model license signals conflict across official sources and need legal clarification before adoption.
   - `EchoMimicV2`: code repo is Apache-2.0, but the linked official-by-reference Hugging Face model repo does not publish a clear license tag in the fetched model card.

## Provider summary matrix

| Provider | Proposed Adept provider ID | Recommended creative role | Official install readiness | Primary unknowns |
| --- | --- | --- | --- | --- |
| LongCat-Video-Avatar 1.5 | `longcat-video-avatar-1-5-local` | `flagship` (Experimental) | Not ready for implementation yet | No official numeric VRAM floor; Windows support not documented; very large storage footprint |
| InfiniteTalk | `infinitetalk-local` | `secondary` (Experimental) | Not ready for implementation yet | Exact total storage still opaque from official hosts; Windows support not documented; no official resumable recovery workflow |
| MuseTalk 1.5 | `musetalk-1-5-local` | `repair` (Experimental) | Not ready for implementation yet | Official license signals conflict; model repo is version-mixed; not a full-body flagship runtime |
| EchoMimicV2 | `echomimic-v2-local` | `half-body` (Experimental) | Not ready for implementation yet | Model-license clarity incomplete; Windows support not documented; pose-asset pipeline is heavier than a simple lip-sync tool |

## 1. LongCat-Video-Avatar 1.5

### Official sources

- Official model page: `https://www.longcatai.org/models/video-avatar`
- Official code repository: `https://github.com/meituan-longcat/LongCat-Video`
- Official model repository: `https://huggingface.co/meituan-longcat/LongCat-Video-Avatar-1.5`
- Required base model repository: `https://huggingface.co/meituan-longcat/LongCat-Video`
- Official technical report: `https://arxiv.org/abs/2605.26486`

### License

- Code repo: MIT
- Model repo: MIT

### Latest stable / appropriate revision

- Upstream does not publish a separate versioned code tag for Avatar 1.5 in the official GitHub repo.
- Appropriate install target is the current `main` tip that already contains Avatar 1.5 docs and demos.

### Exact pin recommendation

- Code commit: `6b3f4b8582a8bc3f20f795735f5383716c4ba794` (`main` HEAD, 2026-05-27 UTC)
- Avatar model revision: `92016c71d5d318d0f5d84e4db30015a571484ab6`
- Required base model revision: `03b55529b1d1d4045f5fbe14d65c8c6e8116b278`

### Runtime requirements

- Python: 3.10
- PyTorch: `torch==2.6.0`, `torchvision==0.21.0`, `torchaudio==2.6.0`
- CUDA / wheel guidance: official install example uses `cu124`
- Additional runtime stack:
  - `flash_attn==2.7.4.post1`
  - `librosa`
  - `ffmpeg`
  - `requirements.txt`
  - `requirements_avatar.txt`

### VRAM / RAM / storage

- Official docs do **not** publish a numeric minimum VRAM figure.
- Official examples use multi-GPU `torchrun --nproc_per_node=2` even for demo commands.
- Official docs provide:
  - `--use_int8` support for Avatar 1.5
  - distillation mode required for `avatar-v1.5`
  - design goal of reduced VRAM via shared base + LoRA instead of three parallel models
- Working interpretation: this is a **high-end GPU runtime** and should be planned as such until live profiling proves otherwise.
- Published first-party checkpoint storage from official Hugging Face trees:
  - `LongCat-Video`: ~`77.59 GiB`
  - `LongCat-Video-Avatar-1.5`: ~`69.75 GiB`
  - Combined first-party model storage: ~`147.34 GiB`
- System RAM requirement is not explicitly published in the fetched official docs.

### Supported inputs and outputs

- Native modes:
  - Audio-Text-to-Video (`AT2V`)
  - Audio-Text-Image-to-Video (`ATI2V` / effectively audio-image-to-video with text conditioning)
  - Video continuation
- Audio modes:
  - single-stream audio
  - multi-stream audio
  - dual-audio merge (`audio_type=para`)
  - dual-audio concatenation (`audio_type=add`)
- Character scope:
  - single-person
  - multi-person
- Visual scope:
  - realistic
  - anime
  - virtual idols
  - animals
- Output resolution:
  - `480P`
  - `720P`
- Output frame rate:
  - technical report explicitly resamples audio features to target video frame rate `25 FPS`

### Long-form / chunking / continuation behavior

- Strong official long-form story.
- Official materials describe:
  - native video continuation
  - cross-chunk latent stitching
  - stable `5-minute+` sequences in the v1.0 foundation carried forward into v1.5
- Demo commands expose segmented continuation via `--num_segments=5`.
- This is the strongest audited provider for long-horizon continuity from official sources.

### Interruption recovery

- No official crash-resume or interrupted-job recovery workflow was found.
- Continuation exists as a generation mode, but official docs do not describe resumable recovery from a failed partial render.

### Identity / lip-sync / body / multi-person / stylized fit

- Identity consistency: strong official emphasis
- Lip-sync: strong official emphasis; Whisper-large-v3 upgrade is the major v1.5 change
- Full vs half body: explicitly positions itself as full-body synchronized avatar generation
- Multi-person: yes
- Stylized: yes, including anime and animals

### Windows + Linux compatibility

- Linux-style setup is clearly documented.
- Windows-specific setup is **not** documented in fetched official sources.
- Recommendation: treat as **Linux-supported, Windows-undocumented** until proven.

### ComfyUI availability

- No official ComfyUI workflow or branch was found in the fetched official sources.

### Isolated-runtime suitability

- Architecturally yes, operationally heavy.
- Best fit is a dedicated isolated Linux GPU runtime with strong storage planning.
- Unsuitable as a lightweight sidecar.

### Adept recommendation

- Provider ID: `longcat-video-avatar-1-5-local`
- Creative role: `flagship` (**Experimental**)

### Primary adoption risks

1. Very large first-party storage footprint.
2. No published numeric VRAM floor.
3. Windows support is not officially documented.
4. Should not be wired until the M4.12 avatar identity / approved-voice / section assembly contract is frozen.

## 2. InfiniteTalk

### Official sources

- Official code repository: `https://github.com/MeiGen-AI/InfiniteTalk`
- Official model repository: `https://huggingface.co/MeiGen-AI/InfiniteTalk`
- Official project page: `https://meigen-ai.github.io/InfiniteTalk/`
- Official technical report: `https://arxiv.org/abs/2508.14033`
- Required base model repository from official README: `https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P`
- Required audio encoder repository from official README: `https://huggingface.co/TencentGameMate/chinese-wav2vec2-base`

### License

- Code repo: Apache-2.0
- Model repo: Apache-2.0

### Latest stable / appropriate revision

- Upstream does not publish a versioned release branch for the current public build.
- Appropriate install target is the current `main` branch snapshot that ships the post-release README, multi-person path, TeaCache notes, quant path, and ComfyUI references.

### Exact pin recommendation

- Code commit: `50aa0a94184315407a991ae804d9b58d6d311ba8` (`main` HEAD, 2026-05-22 UTC)
- InfiniteTalk model revision: `d59847ebdacf19245bfca3fb23311c0cada8378a`
- Required Wan base model revision: `6b73f84e66371cdfe870c72acd6826e1d61cf279`
- Required wav2vec repo:
  - repository root should be pinned before install, but the fetched official APIs did not return a stable root SHA during this audit
  - official README explicitly requires downloading `model.safetensors` from revision `refs/pr/1`

### Runtime requirements

- Python: 3.10
- PyTorch: `torch==2.4.1`, `torchvision==0.19.1`, `torchaudio==2.4.1`
- CUDA / wheel guidance: official install example uses `cu121`
- Additional runtime stack:
  - `xformers==0.0.28`
  - `flash_attn==2.7.4.post1`
  - `librosa`
  - `ffmpeg`
  - `requirements.txt`

### VRAM / RAM / storage

- Official docs do **not** publish a numeric VRAM minimum.
- Official docs do publish lower-memory paths:
  - `--num_persistent_param_in_dit 0` for very low VRAM
  - FP8 quantized path
  - multi-GPU inference
  - TeaCache acceleration
- Storage:
  - official wav2vec dependency tree size: ~`1.42 GiB`
  - exact total size for `MeiGen-AI/InfiniteTalk` and `Wan2.1-I2V-14B-480P` could not be fully enumerated from accessible upstream Hugging Face tree endpoints during this audit
- Result: **install-readiness storage remains an official-source unknown**
- System RAM requirement is not explicitly published in the fetched official docs.

### Supported inputs and outputs

- Native modes:
  - audio-driven video-to-video sparse-frame dubbing
  - image-audio-to-video
- Operational modes:
  - `--mode streaming` for long video generation
  - `--mode clip` for one-chunk short generation
- Character scope:
  - single-person
  - multi-person via separate checkpoint path
- Output resolution:
  - `480P`
  - `720P`
- Output frame rate:
  - official README says default `--max_frame_num` equals `1000 frames` and `40 seconds`
  - that implies an official working rate of `25 FPS`

### Long-form / chunking / continuation behavior

- Strong official long-form claim.
- Official README explicitly states:
  - unlimited-length generation
  - long video generation via `streaming`
  - video-to-video mode best supports unlimited length
  - image-to-video quality is good up to roughly `1 minute`, then color shift becomes more pronounced
- This makes it a serious long-form secondary candidate.

### Interruption recovery

- No official crash-resume workflow was found.
- Streaming/chunking exists, but upstream docs do not describe resuming a failed run from a partial artifact boundary.

### Identity / lip-sync / body / multi-person / stylized fit

- Identity consistency: explicit official goal
- Lip-sync: explicit official goal and positioning
- Full vs half body: explicitly aligns lips, head, body posture, and facial expressions
- Multi-person: yes
- Stylized: less explicitly positioned than LongCat, though it inherits Wan-based generation flexibility

### Windows + Linux compatibility

- Linux-style environment is documented.
- Windows-specific installation or launch instructions were not found in fetched official sources.
- Recommendation: treat as **Linux-supported, Windows-undocumented** until proven.

### ComfyUI availability

- Yes, but mixed:
  - official README says the official `comfyui` branch has been released
  - official README also thanks a community WanVideoWrapper integration

### Isolated-runtime suitability

- Potentially suitable as a dedicated Linux GPU runtime.
- Heavier and less predictable than `MuseTalk 1.5`.
- Better treated as a separate worker class from lighter repair runtimes.

### Adept recommendation

- Provider ID: `infinitetalk-local`
- Creative role: `secondary` (**Experimental**)

### Primary adoption risks

1. Exact total install size remains opaque from accessible official metadata.
2. No official Windows support documentation.
3. No official interrupted-run recovery story.
4. Depends on an external Wan 14B base model and additional audio encoder assets.

## 3. MuseTalk 1.5

### Official sources

- Official code repository: `https://github.com/TMElyralab/MuseTalk`
- Official model repository: `https://huggingface.co/TMElyralab/MuseTalk`
- Official space: `https://huggingface.co/spaces/TMElyralab/MuseTalk`
- Official technical report: `https://arxiv.org/abs/2410.10122`

### License

- Code repo: official README says MIT for code
- Model repo: Hugging Face model card frontmatter says `creativeml-openrail-m`
- Official README also says trained model is available for any purpose, even commercially

Interpretation: official license signals are **internally inconsistent** and need legal clarification before install or productization.

### Latest stable / appropriate revision

- Upstream uses one repository for both v1.0 and v1.5 assets.
- Appropriate install target is the current `main` tip because that is where official 1.5 inference and training docs live.

### Exact pin recommendation

- Code commit: `0a89dec45a0192b824e3cf4daf96c239440c5ed8` (`main` HEAD, 2025-09-26 UTC)
- Model revision: `3ef28bc5cff08c90ad8178a25f1b570cd800170f`
- Version-specific artifact note:
  - use the `musetalkV15` weight path within the official model repo
  - specifically the official README points to `models/musetalkV15/unet.pth` and `models/musetalkV15/musetalk.json`

### Runtime requirements

- Python: 3.10 recommended
- PyTorch: `torch==2.0.1`, `torchvision==0.15.2`, `torchaudio==2.0.2`
- CUDA / wheel guidance:
  - official recommendation says CUDA 11.7
  - official install examples use `cu118` / `pytorch-cuda=11.8`
- Additional runtime stack:
  - `openmim`
  - `mmengine`
  - `mmcv==2.0.1`
  - `mmdet==3.1.0`
  - `mmpose==1.1.0`
  - `requirements.txt`
  - ffmpeg on PATH

### VRAM / RAM / storage

- Official inference performance:
  - `30fps+` on NVIDIA Tesla V100
  - official Gradio note says an 8-second clip was tested on Windows with RTX 3050 Ti Laptop GPU `4GB VRAM`, taking roughly `5 minutes` in fp16 mode
- Storage visible from official sources:
  - `TMElyralab/MuseTalk`: ~`6.33 GiB`
  - `stabilityai/sd-vae-ft-mse`: ~`0.62 GiB`
  - `yzd-v/DWPose`: ~`1.99 GiB`
  - subtotal from enumerated official model repos: ~`8.94 GiB`
- Additional required artifacts from official README are outside that subtotal:
  - Whisper tiny
  - face-parse-bisent
  - resnet18
- System RAM requirement is not explicitly published in the fetched official docs.

### Supported inputs and outputs

- Native task:
  - video dubbing / lip-sync repair
- Inputs:
  - source video + replacement audio
  - image input in the normal inference path
  - directory-of-images input
  - real-time avatar prep path for repeated reuse
- Output shape:
  - modifies an unseen face in a `256 x 256` face region
  - final rendered output is a dubbed video over the source media
- Frame-rate notes:
  - official docs recommend `25fps` inputs for best results
  - real-time path advertises `30fps+` on V100

### Long-form / chunking / continuation behavior

- Not a long-form sectioned avatar generator in the same sense as `LongCat` or `InfiniteTalk`.
- Official real-time path allows:
  - one-time avatar preparation
  - repeated generation using `audio_clips`
- There is no official continuation/chunk-assembly model for long-form presenter generation.

### Interruption recovery

- No official crash-resume workflow was found.
- Reusable avatar preparation exists:
  - `preparation: True` for first setup
  - set `preparation: False` to reuse an existing prepared avatar
- This helps repeat work, but it is not a documented partial-render resume system.

### Identity / lip-sync / body / multi-person / stylized fit

- Identity consistency: improved in 1.5, but official limitations still mention details like mustache, lip shape, and lip color may drift
- Lip-sync: core strength
- Full vs half body: not a full-body or half-body avatar runtime; primarily face/talking-head dubbing
- Multi-person: official README does not position it as a multi-person generation system
- Stylized: not a primary official positioning

### Windows + Linux compatibility

- Best official cross-platform story of the four providers.
- Official Windows and Linux instructions are both present in the fetched README.

### ComfyUI availability

- Community only.
- Official README links `ComfyUI-MuseTalk` as third-party integration and explicitly says third-party integrations are not verified, maintained, or updated by the authors.

### Isolated-runtime suitability

- Strong candidate for a focused isolated repair runtime.
- Smallest and clearest fit for dedicated lip-sync repair / dubbing jobs.
- Not a flagship avatar runtime.

### Adept recommendation

- Provider ID: `musetalk-1-5-local`
- Creative role: `repair` (**Experimental**)

### Primary adoption risks

1. Official model-license signal conflicts with official README claims.
2. Versioned 1.5 assets are mixed into a broader repo rather than a dedicated 1.5 model repo.
3. This is a dubbing/lip-sync runtime, not the main long-form presenter engine.

## 4. EchoMimicV2

### Official sources

- Official code repository: `https://github.com/antgroup/echomimic_v2`
- Official model repository linked by official README: `https://huggingface.co/BadToBest/EchoMimicV2`
- Official paper: `https://arxiv.org/abs/2411.10061`
- Official project page referenced from model card: `https://antgroup.github.io/ai/echomimic_v2/`

### License

- Code repo: Apache-2.0
- Model repo: no clear license tag was present in the fetched official Hugging Face model card

Interpretation: code licensing is clear; model-license clarity still needs confirmation before install.

### Latest stable / appropriate revision

- No separate versioned release branch was found for the public V2 runtime.
- Appropriate install target is the current `main` snapshot that includes the accelerated inference path and current docs.

### Exact pin recommendation

- Code commit: `38c86809efa041884c774ee31d984a9577c0e0aa` (`main` HEAD, 2026-02-23 UTC)
- Model revision: `8648078a20057a7cdff6ccd6e91251fe19210533`

### Runtime requirements

- Python:
  - recommended 3.10
  - officially tested on 3.8 / 3.10 / 3.11
- PyTorch: `torch==2.5.1`, `torchvision==0.20.1`, `torchaudio==2.5.1`
- CUDA / wheel guidance:
  - official setup says `CUDA >= 11.7`
  - manual install example uses `cu124`
- Additional runtime stack:
  - `xformers==0.0.28.post3`
  - `torchao` nightly `cu124`
  - `requirements.txt`
  - `facenet_pytorch==2.6.0`
  - ffmpeg via `FFMPEG_PATH`

### VRAM / RAM / storage

- Official tested GPUs:
  - A100 80G
  - RTX4090D 24G
  - V100 16G
- Official accelerated claim:
  - about `50s / 120 frames` on A100
  - roughly `9x` faster than the non-accelerated path in their example
- Storage visible from official sources:
  - `BadToBest/EchoMimicV2`: ~`10.40 GiB`
  - `stabilityai/sd-vae-ft-mse`: ~`0.62 GiB`
  - `lambdalabs/sd-image-variations-diffusers`: ~`5.78 GiB`
  - subtotal from enumerated official model repos: ~`16.80 GiB`
- Additional required artifact outside that subtotal:
  - Whisper tiny audio processor
- System RAM requirement is not explicitly published in the fetched official docs.

### Supported inputs and outputs

- Native task:
  - audio-driven semi-body / half-body human animation
- Inputs from official configs:
  - reference image
  - driving audio
  - pose directory / pose sequence
- Output defaults from official inference entrypoints:
  - default width: `768`
  - default height: `768`
  - default clip length: `240` frames
  - default fps: `24`
- The official paper and repo consistently frame the system as half-body, not full-body.

### Long-form / chunking / continuation behavior

- No official long-form continuation system comparable to `LongCat` or `InfiniteTalk` was found.
- It is clip-based diffusion inference with pose-sequence input.
- Good for expressive half-body clips, not yet an official long-form assembly engine.

### Interruption recovery

- No official crash-resume workflow was found.
- Official docs describe rerunning inference or accelerated inference, not resuming a partial failed render.

### Identity / lip-sync / body / multi-person / stylized fit

- Identity consistency: explicit reference-image conditioning
- Lip-sync: yes, but as part of broader half-body animation
- Full vs half body: explicitly half-body / semi-body
- Multi-person: no official multi-person positioning found
- Stylized: not a primary official positioning

### Windows + Linux compatibility

- Official docs explicitly test Linux environments:
  - CentOS 7.2
  - Ubuntu 22.04
- Windows instructions were not found in fetched official sources.
- Recommendation: treat as **Linux-supported, Windows-undocumented** until proven.

### ComfyUI availability

- Community only.
- Official README links `ComfyUI_EchoMimic` as an external integration.

### Isolated-runtime suitability

- Reasonable candidate for a dedicated Linux half-body worker.
- Heavier and more pose-pipeline-dependent than `MuseTalk 1.5`.
- Not a clean flagship substitute.

### Adept recommendation

- Provider ID: `echomimic-v2-local`
- Creative role: `half-body` (**Experimental**)

### Primary adoption risks

1. Model-license clarity is incomplete.
2. Official Windows support is absent.
3. Pose-sequence dependency makes it operationally heavier than a simple audio+image repair tool.

## Final recommendation order

1. `longcat-video-avatar-1-5-local` -> **flagship** (Experimental)
2. `infinitetalk-local` -> **secondary** (Experimental)
3. `musetalk-1-5-local` -> **repair** (Experimental)
4. `echomimic-v2-local` -> **half-body** (Experimental)

## Blockers before implementation

1. Freeze the M4.12 contract first using the repository audit:
   - approved avatar identity
   - approved voice handoff
   - section/retake/final-assembly model
2. Resolve official license ambiguity for `MuseTalk 1.5`.
3. Confirm official model-license terms for `EchoMimicV2`.
4. Measure real GPU floors for `LongCat-Video-Avatar 1.5` and `InfiniteTalk`; official docs are descriptive, not deployment-precise.
5. Determine whether Windows support is a requirement for any runtime other than `MuseTalk 1.5`.

**READY FOR PRIMARY REVIEW**
