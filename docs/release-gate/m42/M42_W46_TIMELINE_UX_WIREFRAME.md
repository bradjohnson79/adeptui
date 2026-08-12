# M42 W46 — Timeline UX Wireframe (SA44)

**Status:** PRIMARY APPROVED  
**Approved:** 2026-08-01  
**Visual authority:** Locked concept mockup → `artifacts/m42/w46/timeline-ux/approved_mockup.png`

## Primary instruction

Do not preserve the current Timeline layout merely because its controls are already wired. Preserve backend behavior and contracts; replace creator-facing IA and presentation per this wireframe and the locked mockup.

## Structural target (not inspiration)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Scene Header — name · generator · duration · mode                          │
│ [Image Planning | Video Finishing] [Preflight] [Generate Scene] [More ▾]   │
├───────────────┬─────────────────────────────────────────────┬──────────────┤
│ Scenes        │ Viewer (dominant, resizable)                │ Inspector    │
│ Assets        │ ─────────────────────────────────────────── │ (contextual) │
│ References    │ Timeline Toolbar (single row)               │ Co-Director  │
│               │ Batch lane + NLE tracks + playhead          │ Queue ▾      │
└───────────────┴─────────────────────────────────────────────┴──────────────┘
```

### Narrow desktop (1280)

Toolbar collapses to: `[Add ▾] [Generate ▾] [Tools ▾] [⚙]` — never unplanned wrap; never hide required actions.

## Control inventory

| Control | Location | Persistence / wiring |
|---------|----------|----------------------|
| + Batch | Toolbar | `POST` timelineMaster add_batch |
| + Image / Prompt / Audio / SFX | Toolbar | `putDirector` clips / segments |
| Preflight | Header + toolbar | Co-Director / orchestrator preflight |
| Generate Scene | Header + Generate ▾ | orchestrator generate_scene |
| Mode switch | Header | Image Planning / Video Finishing preference |
| Undo / Redo / Zoom / Snap / ⚙ | Toolbar | layout prefs + director JSON |
| Scene Prompt | Scene Inspector only | scene.prompt / director |
| Timed Instruction | Prompt track → Inspector | prompt_segments |
| Playhead | Ruler / needle | director.playhead + Preview sync |
| Queue | Compact drawer | JobPanel API |

## State transitions

```text
selection=null/scene → Scene Inspector (Scene Prompt authoritative)
selection=promptSeg → Timed Instruction Inspector
selection=image|video|audio|sfx|lipsync|batch|repair → matching Inspector
mode=image_planning | video_finishing → header + toolbar reflect mode
empty Scene → instructional empty tracks only (no persisted fillers)
```

## Forbidden improvisation

- Retain stacked-card / multi-panel webpage center layout
- “Prompt Timeline” product naming or competing Global Prompt in main Timeline
- Timeline / Prompt / Lip Sync / Scene Settings as sibling product tabs
- Fake persisted prompt/camera/audio/lipsync/image on new Scene
- UI-only toolbar buttons (must hit real APIs / ProposalService)
- Second frontend-only selection state Co-Director cannot access
- Batch management only as oversized cards under tracks (Batch lane required)
- Always-on verbose Render Queue chip wall

## Responsive collapse map

| Width | Behavior |
|-------|----------|
| ≥1920 | Full toolbar labels |
| 1280–1919 | Compact labels; overflow menus as needed |
| <1280 | Add/Generate/Tools/⚙ grouping; docks collapsible |

## Exit

PRIMARY APPROVED — SA45+ may implement production UI against this wireframe and the locked mockup.
