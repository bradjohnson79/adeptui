# M42 W46 — Subagent Ownership

| SA | Scope | Checkpoint |
|----|-------|------------|
| SA2 | Persistence / migration into BatchBlocks | W46-A |
| SA3 | Prompt hierarchy + references | W46-A |
| SA4 | Generator capability registry | W46-A |
| SA25 | Timed Prompt Segments + Visual Anchors | W46-A |
| SA5 | Batch creator UX | W46-B |
| SA6 | Scene Batch Orchestrator (cancel/resume) | W46-B |
| SA7 | Local video runtime consume Dock | W46-B |
| SA8 | Hosted honesty | W46-B |
| SA9 | Assembly + snapshot provenance | W46-B |
| SA10–14 | Re-Take, masks, InPaint, background, lineage | W46-C |
| SA15–19 | Continuity, timeline tools, Preflight, Razor, multi-range | W46-D |
| SA1 | Dual-mode UX integration | W46-E |
| SA20–24 | Reviews | W46-E |
| SA23 | Playwright A–S | W46-E |

Subagents may only say `READY FOR PRIMARY REVIEW`. Primary owns checkpoint advances and `directorTimelineGo`.

Docker / custom runtime lifecycle is **W47** — not owned by any W46 SA.
