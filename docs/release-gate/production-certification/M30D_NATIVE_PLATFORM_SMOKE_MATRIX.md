# M3.0d Native Platform Smoke Matrix

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Source inventory | `docs/m3.0a/NATIVE_PLATFORM_INVENTORY.md` |
| Prior matrix | `docs/m3.0c/NATIVE_PLATFORM_GREEN_MATRIX.md` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

Evaluates 18 native platforms. **GREEN** = code and/or recorded test proves bounded capability. **NOT_PRODUCTION_READY** = explicitly excluded from Manual User Beta production routes.

## Matrix

| Platform | M3.0d status | Evidence / boundary |
|----------|--------------|---------------------|
| image | **GREEN** | Local ComfyUI Z-Image stills; fresh PNG in all 12 situation exports |
| video | **GREEN** | fal Seedance T2V via Studio queue (`M30D_FAL_MOTION_PROOF.md`) |
| animation | **BLOCKED** | No dedicated native animation workspace/service proven |
| refs | **GREEN** | References API, visual/timeline UI, `references.*` capabilities |
| 3D | **BLOCKED** | M2.13 environment path flag-gated; no completed 3D production proof |
| VP (virtual production) | **BLOCKED** | Virtual-stage APIs exist; `virtual_stage.render` unavailable |
| blocking | **GREEN** | Spatial/blocking workspace and spatial scene APIs present |
| camera | **BLOCKED** | Camera-spin / shot-profile code exists; full native proof incomplete |
| lighting | **BLOCKED** | Specialist references exist; no native lighting workspace proven |
| storyboard | **GREEN** | Script/storyboard workspace and generation path present |
| screenplay | **GREEN** | Script segments, panels, import path present |
| sound | **GREEN** | Import/place/gain/normalize/syncEvent proven; generative audio unavailable |
| timeline | **GREEN** | Timeline UI/API; director_json in exports |
| edit | **GREEN** | Editor workspace; Director→Editor handoff API proven |
| color | **UNSUPPORTED_BY_DESIGN** | No color-grade UI in inventory |
| comp | **BLOCKED** | VFX/compositing specialists without native workspace |
| subs | **UNSUPPORTED_BY_DESIGN** | No subtitle/SRT/VTT generation |
| delivery | **GREEN** | Export pack with director_json; 12/12 situation packs validated |

## LTX / WAN (B20)

| Engine | Status | Production route |
|--------|--------|------------------|
| LTX native Comfy | **NOT_PRODUCTION_READY** | Do not offer as beta motion path |
| WAN native Comfy | **NOT_PRODUCTION_READY** | Do not offer as beta motion path |
| fal Seedance | **PRODUCTION_READY** | Primary motion path for Manual User Beta |

Knowledge base and setup wizard retain LTX/WAN install paths for future work; they are not certified for beta delivery.

## Counts

| Label | Count |
|-------|------:|
| GREEN | 9 |
| BLOCKED | 6 |
| UNSUPPORTED_BY_DESIGN | 2 |
| NOT_PRODUCTION_READY (engines) | 2 (LTX, WAN) |

## Interpretation

GREEN is limited to evidence named above. The matrix does not silently upgrade M3.0a PRESENT/PARTIAL labels to full production claims.

## Related documents

- `M30D_FAL_MOTION_PROOF.md` — video GREEN evidence
- `M30D_AUDIO_CAPABILITY_REPORT.md` — sound GREEN with generative boundary
- `M30D_TIMELINE_EXPORT_CERTIFICATION.md` — timeline + delivery
