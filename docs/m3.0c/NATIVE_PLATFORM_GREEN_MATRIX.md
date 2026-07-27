# M3.0c — Native Platform Green Matrix

This matrix evaluates the 18 platforms listed in
`docs/m3.0a/NATIVE_PLATFORM_INVENTORY.md`. **GREEN** means repository code and/or an
existing recorded test proves the bounded capability. It does not imply every provider
or production scenario is live-proven.

| Platform | M3.0c status | Evidence / boundary |
|---|---|---|
| image | **GREEN** | M3.0a inventory, local ComfyUI image path, and M2.9 production services. |
| video | **GREEN** | Fal Seedance T2V through Studio queue proven (job + falRequestId + Asset + Co-Director inspect). See `FAL_UNIFIED_QUEUE_PROOF.md`. |
| animation | **BLOCKED** | Specialists exist, but no dedicated native animation workspace/service is proven. |
| refs | **GREEN** | References API, visual/timeline UI, and `references.*` capabilities are present. |
| 3D | **BLOCKED** | M2.13 environment path is flag-gated; no completed 3D production proof recorded. |
| VP (virtual production / stage) | **BLOCKED** | Virtual-stage APIs exist, but `virtual_stage.render` is unavailable. |
| blocking | **GREEN** | Spatial/blocking workspace and spatial scene APIs are present; bounded blocking path is proven. |
| camera | **BLOCKED** | Camera-spin / shot-profile code exists; full native camera production proof not complete. |
| lighting | **BLOCKED** | Specialist and conditional relight references exist, but no native lighting workspace is proven. |
| storyboard | **GREEN** | Script/storyboard workspace and storyboard generation path are present. |
| screenplay | **GREEN** | Script segments, panels, and import path are present. |
| sound | **GREEN** | Import/place/gain/normalize proven for Manual User Beta; generative audio labeled unavailable. |
| timeline | **GREEN** | Timeline UI/API and director timeline persistence are covered by existing tests. |
| edit | **GREEN** | Editor workspace and M2.9 editing propose/apply path are present. |
| color | **UNSUPPORTED_BY_DESIGN** | No color-grade UI or service is in the native platform inventory. |
| comp | **BLOCKED** | VFX/compositing specialists exist without a native compositing workspace. |
| subs | **UNSUPPORTED_BY_DESIGN** | No subtitle/SRT/VTT generation UI or API is present. |
| delivery | **GREEN** | Export pack includes `director_json` (B18); asset pack path covered by existing export tests/cert doc. |

## Status interpretation

The prior inventory’s PRESENT/PARTIAL/ABSENT labels are not silently converted to
production claims. GREEN is limited to the evidence named above; BLOCKED identifies an
unmet capability or missing proof; IN_PROGRESS identifies a wired path with outstanding
live or end-to-end evidence; UNSUPPORTED_BY_DESIGN identifies an intentional scope
boundary.
