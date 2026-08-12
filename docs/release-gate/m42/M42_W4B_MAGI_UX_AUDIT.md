# M42 Wave 4B — MAGI Editor UX Audit

| Field | Value |
|---|---|
| **Phase** | M42-W4B UI Correction |
| **Branch** | `phase2/m42-magi-editor-foundation` |
| **Baseline** | Wave 4 certified image path preserved |

## Ownership map

| Concern | Owner |
|---|---|
| Shell / layout / docks / fullscreen | `studio-web/src/components/magi/` |
| Edit enqueue / recommend / masks / versions / recipes | `api.imageProduct` → `studio-api/app/image_product/` |
| Readiness / deferred refuse / gate | `studio-api/app/magi/` |
| Korri hero | Presentation only — `/images/hero/MAGI_Editor_Banner_Korri.png` |

## Pre-rebuild issues

- Fixed CSS grid; Viewer not dominant; Timeline only under center column (~180px)
- Banner too shallow (`clamp(110px…168px)`); Korri crop risk
- Left rail single-pane switcher (not independent drawers)
- JobPanel embedded in Inspector (dominates workspace)
- History mixed deferred catalog labels (looked like fake activity)
- No SplitPane resize, docking, fullscreen, or Magi layout persistence

## Reuse candidates

- `SplitPane` (`components/ui/SplitPane.tsx`)
- Preference pattern from `workspaceLayoutPrefs.ts`
- Native `<details>` → replace with accessible `MagiAccordion`

## Runtime bindings (must preserve)

```text
CreativeContext → ImageEditIntent → Unified Resolver → pinned Runtime
→ QueueWorker → Output Gate → DerivedAsset → EditProvenance → VersionGraph
```

Forbidden: product `queue_prompt`, builder imports, fake success, Draft/Deferred/Blocked execute.

## Mock-data risks to eliminate

- Deferred surface names rendered as “History”
- Fake audio waveforms / invented timeline clips
- Always-populated UI when project has no media
