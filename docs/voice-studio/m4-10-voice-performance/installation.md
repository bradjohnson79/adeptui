# IndexTTS2 Installation

## Product rules

The IndexTTS2 runtime is isolated from the main Adept API environment.

It must:

- use the official upstream repo only
- stay pinned to `13495845e3028f0bb6ca1462ad22aa0e76349e40`
- never follow floating `main`
- never commit or vendor model weights into this repository

## Install phases

`install(confirm=True, confirm_download_models=False)` performs the scaffold phase:

1. Creates the runtime directory layout.
2. Clones the official repo into `runtimes/index-tts2/repo`.
3. Checks out the pinned SHA.
4. Creates a dedicated virtual environment in `runtimes/index-tts2/environment/venv`.
5. Installs runtime dependencies into that venv.
6. Writes an updated manifest.

This scaffold phase intentionally does not require the multi-GB model download.

## Model download phase

`install(confirm=True, confirm_download_models=True)` performs the full download path:

1. Runs the scaffold phase if needed.
2. Downloads `IndexTeam/IndexTTS-2` into `runtimes/index-tts2/models`.
3. Lets the upstream helper fetch required auxiliary assets.
4. Runs verification.

If the model download is skipped, the runtime remains `compatible` rather than `ready`.

## Setup / Source Manager surfaces

- Setup catalog component id: `index_tts2`
- Setup installer id: `index_tts2`
- Setup verifier id: `index_tts2`
- Source Manager voice model id: `index_tts2`

## Logs and manifests

- Logs: `runtimes/index-tts2/logs`
- Manifest: `runtimes/index-tts2/manifests/index-tts2-manifest.json`
- Job JSONs: `runtimes/index-tts2/manifests/jobs`
- Outputs: `runtimes/index-tts2/outputs`
