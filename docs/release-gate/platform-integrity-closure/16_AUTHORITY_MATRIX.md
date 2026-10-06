# 16 — Authority matrix

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

| Domain | Write authority | Projection / view | Must not |
|---|---|---|---|
| Asset bytes | `/api/projects/{projectId}/assets/{assetId}/file` + `resolve_data_file_path` | Library / Character / Timeline URLs | Unscoped `/api/assets/{id}/file` (403) |
| Generator identity | Production Control `_CATALOG` + hosted discovery | `generator_authority` join | Second Timeline catalog |
| Generator executable | Adapter registry AND install/runtime | Timeline / Footer / Inspector presenters | Certified ⇒ Ready |
| Runtime / GPU | Same Python supervisor | Local Runtime card | Second supervisor; silent second Comfy spawn |
| Timeline | `timelineMaster` in `scenes.director_json` | Legacy DirectorTracks | Auto-approve; silent projection swallow |
| Spatial scene | `spatial_scenes` (`save_spatial_doc`) | `project.spatial_map_json` | Two write authorities |
| Jobs | Install / Render / H3 families | Queue UI | Mega-job abstraction |
| MiniMax duration | Route A frames/fps (`5/24`) | Timeline maxDurationSec | 15s claim without measured media |
| Prompt compile | `compile_for_generator` on W46 request | Inspector preview | Decorative `<subject N>` |
| Comfy cert | Stdio `comfy-mcp.exe` | HTTP `/history` supplementary | HTTP labeled as MCP |
