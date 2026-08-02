# Benchmarking

## Helper script

M4.10 includes a small runtime benchmark/helper script at:

- `scripts/voice_studio/index_tts2_benchmark.py`

Its purpose is modest and honest:

- run an IndexTTS2 health check
- optionally run a sample generation
- print JSON for inspection or automation

## CLI inputs

Supported arguments:

- `--voice` reference clip path
- `--text` sample text
- `--output` optional output wav path
- `--allow-cpu-fallback`

If only health is requested, the script returns success when the runtime health check returns `ok=true`.

If `--voice` and `--text` are both supplied, it also runs `runtime.generate_take()`.

## Exit behavior

Exit codes are simple:

- `0` for success
- `3` for failed health or failed sample generation

## Relationship to M4.10 docs

This script is not a broad performance lab harness. It is the current in-repo checkpoint for:

- runtime readiness
- pinned local setup sanity
- optional sample inference against the isolated runtime

Use the runtime and release-gate docs for installation and audit context; use this script when you want a quick executable signal from the current IndexTTS2 environment.
