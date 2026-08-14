# AVATAR RUNTIME WINDOWS PIP — DEFERRED DEFECT

Official Adept UI Setup install-jobs for `infinitetalk-local`, `musetalk-1-5-local`, and `longcat-video-avatar-1-5-local`.

After `LongPathsEnabled=1` reboot, jobs used destinationRoot `D:\01_Models\<slug>` (not parent `D:\01_Models`). Clone + venv succeeded on D:.

Pip failed ~2:15–2:21 PM PT 2026-08-14:

- InfiniteTalk `ij_infinitetalk-local_f01b2de2e3`: combined `pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 xformers==0.0.28 flash_attn==2.7.4.post1 librosa` — xformers wheel build: `ModuleNotFoundError: No module named 'torch'`
- LongCat `ij_longcat-video-avatar-1-5-local_8a376437fe`: pip `-r requirements.txt` — flash-attn build: `No module named 'torch'`
- MuseTalk `ij_musetalk-1-5-local_0572abb11b`: pip `torch==2.0.1` + `mmcv==2.0.1` … — mmcv build: `No module named 'pkg_resources'`

krea2 / LLMs / Ollama / Qwen / Video on `D:\01_Models` left intact. No live pip workers after fail. Do not re-POST the same combined pip command.

## Fallback (verified earlier live traces; not a new E2E)

- Avatar Studio Generate fails honestly: `AVATAR_SECTION_PROVIDER_NOT_INSTALLED` / Not Installed badge
- Script mode can plan; no fake talking-head video
- Save Draft + New Session persist
- Approved still/voice still E2E BLOCKED (Character Creator / identity, not this pip)

## Classification

- Spatial Map / Prop / Setup deploy: **NON-BLOCKING WITH FALLBACK**
- Avatar live talking-head generate: **DEFERRED DEFECT — NOT CERTIFIED**
- Needed fix: Windows-safe installer pin (install torch first, then xformers/flash-attn; MuseTalk needs setuptools/pkg_resources before mmcv)
