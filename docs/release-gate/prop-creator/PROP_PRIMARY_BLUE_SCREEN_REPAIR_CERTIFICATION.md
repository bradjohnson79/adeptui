# PROP PRIMARY PREVIEW / BLUE-SCREEN REPAIR

Governing cert for the 2026-09-16 Primary blue-rectangle defect.

## ROOT CAUSE

**L + C — stale approved pointer used for preview.**

Upload Primary and Generate Primary already wrote real Library candidates. The Advanced (and Standard) Primary `<img>` bound `primary_approved_asset_id` **before** the latest valid candidate.

On `%cade-s-starfighter-2` (`6868078f-cda7-4427-8f85-fd318cf4a141`):

- Locked Primary `01e64af7-bec3-4ff1-a7a9-05d114831c1f` was a **96×96 solid blue PNG** (RGB 18, 92, 160, 270 bytes) left from earlier smoke.
- Later Generate Primary candidates were real 768×768 images (latest `4d3a1e66-…`, 473,954 bytes, not solid).
- UI said “New Primary ready — approve to replace identity” (correct) while the box rendered the old blue approved file (wrong).

Not a missing assetId, not `/thumb`, not a stuck overlay, not a revoked blob. Canonical `/file` returned decodable PNG bytes for both the blue smoke asset and the real generated candidate.

## NETWORK PROOF (pending replacement, before approve)

| Field | Value |
| --- | --- |
| assetId | `4d3a1e66-a913-4962-88b6-02a141fd9128` |
| projectId | `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| URL | `/api/projects/{projectId}/assets/{assetId}/file` |
| HTTP | **200** |
| Content-Type | **image/png** (sniffed from bytes) |
| Dimensions | **768×768** |
| Decode | PNG, not solid |

The blue box’s own `/file` was also 200 + image/png — it was the **wrong** asset, not a broken route.

## REPAIR

- `visiblePrimaryPreviewAssetId` / `visible_primary_preview_asset_id`: pending replacement beats stale approved.
- Shared `PropAssetPreview`: canonical `/file`, `object-fit: contain`, `onLoad` / `onError`, `key` + `rev` cache bust. No thumbnail fallback.
- File serve sets MIME from magic bytes.
- Co-Director `get_views` + grounding expose `pendingAssetId` / `previewAssetId`. “Which Primary is pending?” names the same candidate.

## LIVE

Vite `http://127.0.0.1:5173/` · API `http://127.0.0.1:8758/` (recycle 21972 → 43552). Comfy PID **34484** unchanged.

Browser on Advanced `%cade-s-starfighter-2`: Primary `src` = `4d3a1e66-…/file`, natural 768×768, Approve enabled, caption “Showing the new Primary candidate.” After Approve + hard reload: same asset, status **Primary approved**, image remains.

Generate Primary was not re-run on GPU this pass. Existing generated candidates already proved deposit + decode.

Note: original Cade `8a79697b-…` still has leftover smoke candidate `691bcfb0-…` (100×100 solid blue). After this repair that **pending** candidate would preview if that prop is opened — do not Approve it.

## FINAL REPORT

| Field | Result |
| --- | --- |
| ROOT CAUSE | Preview used stale approved Primary (`01e64af7` solid blue) instead of pending candidate |
| UPLOAD PRIMARY | PASS — same bind path; Library `/file` |
| GENERATE PRIMARY | PASS — 768×768 generated candidates already on the prop; not re-queued on GPU |
| CANDIDATE ASSET ID | `4d3a1e66-a913-4962-88b6-02a141fd9128` |
| ASSET URL | `/api/projects/fb24ff0f-…/assets/4d3a1e66-…/file` |
| HTTP | 200 |
| MIME | image/png |
| DECODE | PASS 768×768 not solid |
| PREVIEW COMPONENT | `PropAssetPreview` + `visiblePrimaryPreviewAssetId` |
| LOADING OVERLAY | None after `onLoad` |
| CACHE | `rev={assetId}` |
| APPROVE PRIMARY | PASS — pointer `4d3a1e66`; image remains |
| LIBRARY | Same `/file` bytes |
| GLOBAL | Ship Primary readable from Project B; this Starfighter-2 prop is not Global |
| CO-DIRECTOR | Pending/preview ids on `get_views` + grounding |
| RELOAD | PASS |
| CONSOLE | No page errors on the live walk |
| NETWORK | 200 image/png on the previewed candidate |

**COMFY BEFORE:** PID 34484 `GET :8188/system_stats` 200  
**COMFY AFTER:** PID 34484 `GET :8188/system_stats` 200  
**COMFY RESTARTED?:** NO

## FINAL VERDICT

**GO — PROP PRIMARY PREVIEW / BLUE-SCREEN REPAIR CERTIFIED**
