# M42 W45 — Audio Studio Test Report

## Unit / API

Suite: `studio-api/tests/test_m42_w45_audio_studio.py`

Coverage:

- Contracts importable (mix, stems, intents)
- Provider resolver local ready + no silent switch
- Select ≠ approve
- Mix persistence reload (gain/mute/solo/LUFS)
- No fake stems on expand
- Taxonomy audio roles
- Gate shape (binary, no Conditional GO)
- Co-Director `audio.*` tool registration

## Playwright

Suite: `tests/e2e/m42/m42-w45-audio-studio.spec.ts`

- Tab shell: Music / SFX / Ambience / Project Audio
- Gate endpoint binary + non-mock
- Mix GET/PUT persistence

## Primary workflows (certify script)

`scripts/m42_w45_certify.py` → stamps `artifacts/m42/w45/*`

| Workflow | Focus |
|---|---|
| A–C | Music / SFX / Ambience generate batches |
| D | Select ≠ Approve |
| E | Library registration |
| F–G | Timeline place + providers |
| H | Mix gain/pan/mute/solo/fade + reload |
| I | Stem honesty when unsupported |

## Evidence directory

`artifacts/m42/w45/`
