# M42 Phase 4 — Virtual Studio Roadmap (post Wave 6P)

| Field | Value |
|---|---|
| **Baseline** | `wave6pGo: true` (Production Beta) |
| **Strategic rule** | No isolated sandbox completion — real assets, Timeline, Co-Director, persistence, provenance, binary gate |

## Sequence

```text
4.3 Character Creator  →  4.4 Voice Performance  →  4.5 Audio Studio
→  4.6 Editing Suite  →  4.7 Enhancement Studio
```

## Gates

| Phase | Gate | Status |
|---|---|---|
| 4.3 Character Creator Completion | `characterCreatorGo` | **GO** — see [`M42_W43_CHARACTER_CREATOR_COMPLETION_REPORT.md`](./M42_W43_CHARACTER_CREATOR_COMPLETION_REPORT.md) |
| 4.4 Voice Performance System | `voicePerformanceGo` | **GO** — see [`M42_W44_FINAL_CERTIFICATION.md`](./M42_W44_FINAL_CERTIFICATION.md) |
| 4.5 Audio Studio Completion | `audioStudioGo` | **GO** — see [`M42_W45_FINAL_CERTIFICATION.md`](./M42_W45_FINAL_CERTIFICATION.md) |
| 4.6 Editing Suite Final Checks | `editingSuiteGo` | Roadmap |
| 4.7 Enhancement Studio | `enhancementStudioGo` | Roadmap |

```text
wave6pGo ∧ characterCreatorGo ∧ voicePerformanceGo ∧ audioStudioGo
∧ editingSuiteGo ∧ enhancementStudioGo → phase4Complete
```

## Naming boundary

| Name | Meaning |
|---|---|
| **Timeline** | User-facing editing and sequence product |
| **Director 2.0** | Internal production prompting / directing intelligence |
| **MAGI Korri hero** | Presentation branding only — not the production CharacterProfile |

## Phase notes (roadmap-only for 4.4–4.7)

- **4.4** — Provider-neutral performance markup → normalized plan → adapters → Timeline dialogue; consumes Voice Prompt from Character Prompt Package
- **4.5** — ACE-Step music + MMAudio SFX; Co-Director propose → preview → approve → generate → register → place
- **4.6** — Subtitles, transitions, ducking, markers, grouping, replace; every edit persists, history, undo/redo, render plan
- **4.7** — Non-destructive finishing workspace; honesty rules for face/upscale/restore/relight/video
