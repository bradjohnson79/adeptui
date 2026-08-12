# M42 W45 — Foundation Audit

| Field | Value |
|---|---|
| **Starting tip** | `f758744` (`phase2/m42-voice-performance-system` → `phase2/m42-audio-studio-completion`) |
| **Audit date** | 2026-07-31 |

## Prerequisites

| Gate | Status | Evidence |
|---|---|---|
| wave6pGo | true | `M42_W6P_FINAL_CERTIFICATION.md` |
| characterCreatorGo | true | `M42_W43_FINAL_CERTIFICATION.md` |
| voicePerformanceGo | true | `M42_W44_FINAL_CERTIFICATION.md` |
| Voice Studio M43 | IMPLEMENTATION GO / MANUAL UX PENDING | `docs/release-gate/m43/M43_VOICE_STUDIO_UX_REPORT.md` — do not fabricate beginner PASS |

```text
wave6pGo ∧ characterCreatorGo ∧ voicePerformanceGo → AudioStudioMayBegin = true
```

## Existing assets

| Layer | Finding |
|---|---|
| UI | `AudioStudioWorkspace.tsx` — monolithic sandbox generate/upload/Editor handoff |
| Music | ACE-Step adapter + worker (`m2101-music-045`), sandboxOnly |
| SFX | MMAudio adapter + worker (`m2101-sfx-031`) |
| Jobs | `AUDIO_GENERATE` → `AudioService` / `run_audio_generate` |
| Library | `audio.music`, `audio.sfx`, `audio.ambience`, `audio.dialogue` |
| Timeline | director `audio_clips` / `sfx_clips`; editor music/sfx/ambience/dialogue tracks |
| Hosted audio | Missing (image/video only) |
| Mix / stems | Not a first-class workspace |
| Co-Director | `propose_music_generate`, `propose_sfx_generate` |

## Gaps for GO

- Creator UX split (Music / SFX / Ambience / Project Audio)
- Persistent candidate batches + select≠approve
- Hosted audio adapters + honest switch approval
- Production path beyond sandboxOnly labeling
- Timeline Audio Mixer (4.5A)
- Stem lineage when providers support
- Full `audio.*` Co-Director suite
- Gate `/api/audio-studio/gate/w45` + artifacts/reports
