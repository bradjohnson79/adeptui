# 17 — Final authority matrix

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

| Domain | Write authority | Projection / view | Must not |
|---|---|---|---|
| Asset bytes | `/api/projects/{projectId}/assets/{assetId}/file` + `resolve_data_file_path` | Library / Character / Timeline URLs | Unscoped `/api/assets/{id}/file` (403) |
| Generator identity | Production Control `_CATALOG` + hosted discovery | `generator_authority` join | Second Timeline catalog |
| Generator executable | Adapter registry AND install/runtime | Timeline / Footer / Inspector presenters | Certified ⇒ Ready |
| Runtime / GPU | Same Python supervisor | Local Runtime card | Second supervisor; silent second Comfy spawn |
| Timeline | `timelineMaster` in `scenes.director_json` | Legacy DirectorTracks | Auto-approve; silent projection swallow |
| Timed Prompt delete | Shell `mutateTimeline` + master `promptSegments` patch | Legacy `prompt_segments` | X that only PUTs director and leaves master |
| Spatial scene | `spatial_scenes` (`save_spatial_doc`) | `project.spatial_map_json` | Two write authorities |
| Jobs | Install / Render / H3 families | Queue UI | Mega-job abstraction |
| MiniMax duration | Route A frames/fps (`5/24`) | Timeline `maxDurationSec` | 15s claim without measured media |
| Prompt compile | `compile_for_generator` on W46 request | Inspector preview | Decorative `<subject N>` |
| Comfy cert | Stdio `comfy-mcp.exe` | HTTP `/history` supplementary | HTTP labeled as MCP |

## Gate Q domains

| Domain | Canonical authority | Consumers | Duplicate remaining |
|---|---|---|---|
| Generator identity | PC `_CATALOG` + hosted discovery via `generator_authority` | Timeline, Footer Dock, Inspector `EngineAuthoritySelect` | Aliases only at adapter/hosted boundary |
| Generator capability | Knowledge profiles + adapter `supportedDurations` | Compiler, duration check, Inspector | Hosted profiles may be unavailable (authored prompt kept) |
| Generator readiness | Join of identity + adapter + install/runtime | Same UI presenters | Certified ≠ Ready |
| Prompt knowledge | `compile_for_generator` on W46 request | Generate path | Inspector preview is the same compiler |
| Provider routing | Adapter registry | W46 submit | None intended |
| Runtime ownership | `runtime_supervisor` (includes Route A adopt) | Local Runtime card, CLI | Retired Beta watchdog exists; not the start contract |
| GPU admission | `gpu_admission.assess_gpu_admission` | Supervisor Comfy/Route A start | Beta watchdog `ensure_comfy` can bypass |
| Assets | Project-scoped file/thumb + `resolve_data_file_path` | Library, Character, Timeline | Unscoped routes 403 |
| Characters | Project character store | Character Creator, Library | — |
| Props | Project prop store | Prop Creator | — |
| Spatial Map | `spatial_scenes` / `save_spatial_doc` | ERS, Scene Creator | `project.spatial_map_json` projection |
| Scene | Project scenes | Timeline, Co-Director | — |
| Timeline | `timelineMaster` in `director_json` | Shell, Inspector, generate | Legacy tracks as NLE view |
| Continuity | Batch continuity packets on master | Generate / retake | — |
| Jobs | Install vs render vs H3 families | Queue UI | No mega-job |
| Approval | Watcher `auto_approve=False` then explicit approve | Timeline candidate | Library `approvalState` can lag Timeline Approve |

Remaining duplication (written why):

- Legacy `prompt_segments` stay as the NLE lane. Master `promptSegments` is production. Reconcile + X-delete patch keep them from competing after a delete.
- `project.spatial_map_json` stays a projection for older readers.
- Hosted discovery can shadow PC identity at the join boundary only (aliases), not a fourth catalog.
