# IndexTTS2 Model Manager Notes

## What Source Manager shows

`studio-api/app/source_manager/voice_models.py` exposes IndexTTS2 beside the existing Qwen voice models.

For IndexTTS2 it reports:

- `componentId`: `index_tts2`
- `registryId`: `index-tts2-local`
- `sourceKey`: `IndexTeam/IndexTTS-2`
- live runtime `status` from `inspect_installation()`
- Setup verification + diagnostic summaries

## Install action

The current Source Manager install action calls:

`runtime.install(confirm=True, confirm_download_models=False)`

That means the default product action prepares the pinned repo and isolated environment first, without forcing the large model download during the same request.

## Uninstall action

The Source Manager uninstall action calls:

`runtime.remove()`

This removes the managed runtime root after stopping the local adapter process.

## Honest capability messaging

The runtime exposes the following creator-facing guidance:

- English: `recommended`
- Chinese: `recommended`
- Accent transfer: `experimental`
- Mixed-language use: `not_recommended`
- Emotion control: `strong`
- Voice cloning: `strong`

The provider wrapper lives at:

`studio-api/app/voice_performance/providers/index_tts2.py`
