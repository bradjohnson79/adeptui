# Provider Capability Audit (V2)

## Live-eligible (probe health at runtime)

| Provider ID | Domain | Seed | Negatives | Language | Notes |
| --- | --- | --- | --- | --- | --- |
| `ltx-local` | video | partial | yes | en | Default production; I2V-oriented |
| `wan-local` | video | partial | yes | en+zh experimental | Optional |
| `comfyui` / flux | image | yes | yes | en | FLUX.1 path |
| `audio-studio` | audio/music/sfx | n/a | no | en | ACE-Step / MMAudio |
| `qwen3-tts` / `kokoro` | voice | segment seed | no | en (+ zh experimental) | |

## Pending / not live-ready

| Provider ID | Status |
| --- | --- |
| `hunyuan-video-1.5-local` | Weights / `t2v_certified.json` typically missing → pending |
| `hunyuan-video-13b-local` | Same |
| `minimax-h3` | Disabled Coming Soon |
| FLUX 3 | Not in repo |

## Live target priority (video)

Hunyuan 1.5 → WAN → LTX → Hunyuan 13B (first healthy wins). LTX remains Adept default production model.
