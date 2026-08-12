# M42 W45 — Subagent Ownership Matrix

| Field | Value |
|---|---|
| **Controller model** | GPT-5.4 |
| **Primary agent** | Sole integrator + certification authority |
| **Branch** | `phase2/m42-audio-studio-completion` |

## Rules

- One owner per file/subsystem at a time
- Subagents may report: Scope complete / Tests passed / Ready for integration review
- Subagents may **not** report: Phase GO / Production certified / Audio Studio complete / Blocker resolved

## Matrix

| SA | Role | Allowed | Forbidden |
|---|---|---|---|
| 1 | Creator UX | `studio-web/src/components/audio-studio/**`, `styles/audio-studio/**` | providers, DB, queue, Timeline model, gates |
| 2 | Music runtime | music intents + ACE-Step path + stems capture | SFX UI, mixer UI, CD UI, gate |
| 3 | SFX + Ambience | MMAudio categories + ambience beds | dialogue/voice, music mixdown, gate |
| 4 | Hosted adapters | Kie/WaveSpeed/fal audio + stem caps | local runtime internals |
| 5 | Local runtime | ACE-Step/MMAudio execute/cancel/timeout | hosted adapters, UI, cert |
| 6 | Project Library | audio asset roles + history | unrelated product |
| 7 | Timeline + Mixer 4.5A | placement + mix + stems UI + Preview + render-plan | generation providers |
| 8 | Co-Director audio | `audio.*` tools approval-gated | silent mutate/switch; Audio Director |
| 9 | Security | read-only review + tests | product features |
| 10 | Test engineering | unit/API/e2e | production code unless reassigned |
| 11 | UX review | read-only | code |
| 12 | Audio review | read-only | code |
| 13 | Eng review | read-only | final cert |

## Execution order

contracts → SA2+SA3 → SA4+SA5 → SA6 → SA7 placement → SA7 mixer → SA8 → SA1 → reviews → Workflows → primary cert
