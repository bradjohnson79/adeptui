# Spin Camera + ERS Spin Package — Governing Architecture & Contract

**Status:** GOVERNING DESIGN (milestone: Spatial Map Spin Camera + ERS Spin Package)
**Date:** 2026-09-11
**Authority:** Owner mission directive (2026-09-11). Single governing doc for this milestone (Build Law #30).

---

## 1. Architecture (mission §1)

```
Spatial Map (spatial authority — unchanged)
   ↓
Spin Camera (dedicated document field, NOT a C1–C4 camera)
   ↓ one synchronized action
Spin Package (Center / North / East / South / West + manifest)
   + Spatial Map JSON
   ↓
ERS (assembled FROM the spin package — never independently invented)
```

## 2. Audit-driven decisions

| Decision | Ruling | Evidence |
|---|---|---|
| Coordinate system | Reuse `adept-world-v1` (meters, Y-up, origin `(0,0,0)`, bounds ±5m). No second system. | `spatial_map/schemas.py:143-154,440-490` |
| Room center | World origin `(0,0,0)`; center tolerance derived from bounds (default: within 15% of half-extent, i.e. ≤0.75m on a 10m map) | audit §1.1 |
| Spin Camera storage | **Dedicated `spinCamera` field on `SpatialMapDocument`** — NOT an entry in `document.cameras`. C1–C4/hero/movement logic iterates `cameras`; mixing would risk §33 regression and violate "do not merge roles" (§2). | audit §1.3, gap table |
| Spin Camera model | `SpinCameraPlacement`: `id, x, z (map plane), sceneId, mapId, cameraHeight=1.6, fov=75, lensMm=35` — defaults from existing `SpatialCamera` policy (`y=1.6`, `lensMm=35`) | `schemas.py:250-288` |
| Package storage | New `ProjectTraitRow` category `spatial_spin_package` (established ERS/batch/prop pattern — no new table) | `ers_persistence.py:35-55` |
| Lineage | `asset_versions` + `asset_edges` (`derived_from` map atlas → each view; `used_in_scene` where applicable) | `asset_graph.py:25-55` |
| ERS integration | When a current Spin Package exists, ERS assembly CONSUMES its 5 views + map JSON instead of generating its own directionals. ERS keeps its human composite + structured package (§18). Spin change → ERS marked stale (§25). | `ers_component_pipeline.py`, `ers_contracts.py` |
| Co-Director | New tools in the existing registry: `spatial.place_spin_camera`, `spatial.get_spin_camera`, `spin.generate_package`, `spin.regenerate_direction`, `spin.build_ers` (+ context pillar fields) | `tools/definitions.py`, `project_context.py:50-60` |

## 3. Provider reality (mission §7/§12 — honest labels, no fake readiness)

| Mission name | Reality | Status |
|---|---|---|
| GPT Image 2 | `openai/gpt-image-2` (fal, verified key) + `gpt-image-2-text-to-image` (Kie, accessible) | **AVAILABLE** — reference image via `image_urls`/`input_urls`, edit endpoint exists |
| GPT Image 2.5 | No registry/catalog entry anywhere | **UNAVAILABLE — omitted from dropdown** (discovery-driven UX only shows live models) |
| Google Nano Banana Pro | No such model. Closest real: `fal-ai/nano-banana-2` (fal, edit-capable, configured). The `nano_banana_pro` pack is QUARANTINED (`product_approval_required`) — not shown. | Dropdown shows **Nano Banana 2** (its real name — no relabeling) |

Classification (from adapter code): all providers are single-image-output, single-reference-through-worker, no built-in chaining. **Strategy: 5 sequential jobs** — Center first (from Spatial Map atlas reference), then N/E/S/W each with the SAME map atlas reference + direction-specific prompt. Sequential keeps provenance clean and matches worker reality (one ref image). Parallel is safe for hosted APIs but sequential is the certified-first path; per-direction retry is independent (§29).

Spend: all are paid hosted calls — reuse `confirmPaidCloud`/`spendApiCredits` gate; UI shows "uses credits" (§30 progress + honesty).

## 4. Direction contract (§10/§15)

Canonical, mapped through `adept-world-v1` (NOT screen coordinates):
- **North = yaw 0°** = looking toward −Z (map "up" per `backgroundAlignment`); East = +90° (toward +X); South = +180°; West = +270°.
- **Center** = neutral reference view toward the map's default forward (North) at a slightly wider framing role: it is the canonical establishing perspective from the origin. Stored as its own asset — not a duplicate of North (Center prompt emphasizes full-room establishing framing; North is the directional wall view).

## 5. Prompt contract (§13/§14/§26)

Generator-neutral semantic template, compiled per provider at the edge:

> First-person environment view from the Spin Camera origin (x, z) at camera height H. Direction: {NORTH|EAST|SOUTH|WEST|CENTER}. The Spatial Map reference image is the spatial authority — preserve exact environment identity: architecture, room proportions, materials, decor, lighting, doors, windows, furniture placement, floor layout. Do not redesign the room. Do not add people. Do not move architectural elements.

No MiniMax-specific syntax in the core JSON (§26). Later generator adapters (H3 `<Picture n>` binding etc.) compile FROM the manifest (§27).

## 6. Manifest (§16) — stored in the trait row JSON

```jsonc
{
  "spinPackageId": "…", "version": 1,
  "sceneId": "…", "mapId": "…",
  "provider": "gpt-image-2-fal",
  "origin": {"x": 0.0, "z": 0.0},
  "cameraHeight": 1.6, "fov": 75, "lensMm": 35,
  "spatialMapAssetId": "…",           // atlas anchor
  "views": {
    "center": {"assetId": "…", "status": "done"},
    "north":  {"assetId": "…", "status": "done"},
    "east":   {"assetId": null, "status": "failed", "error": "…"},
    "south":  {"assetId": "…", "status": "done"},
    "west":   {"assetId": "…", "status": "done"}
  },
  "ersStale": false,
  "createdAt": "…", "completedAt": "…"
}
```

Versioning (§24): provider change or full regenerate → NEW trait row, version+1; prior versions preserved (§23 — no silent provider mixing inside one package; single-direction regen records that view's provider in its view entry and marks provenance).

## 7. Frontend surfaces

- **Placement**: Spatial Map placement mode "Spin Camera" (distinct marker, crosshair+compass glyph). Guidance chip when absent: "Place the Spin Camera near the center of the scene before creating the ERS directional views." — non-blocking (§3).
- **Center validation (§5)**: status on the card: `Centered ✓` / `Move closer to scene center` from origin distance vs tolerance.
- **Compass overlay (§6)**: when selected — N↑ E→ S↓ W← overlay oriented to map convention (N = −Z = map up).
- **Spin Camera card (§7/§8)**: position, status, provider dropdown (live discovery only), Create Spin Images gated on: camera exists + placement valid + provider selected + provider readiness + map atlas exists.
- **Progress (§30)**: per-view checklist (✓ / Generating… / Pending / FAILED + Retry).
- **Scene Creator Mini (§20/§21)**: SPIN CAMERA REFERENCES section (Center/N/E/S/W thumbs + View / Open in Library / Replace / Regenerate Direction) ABOVE the existing SCENE CAMERAS C1–C4 section. No merging.
- **ERS staleness (§25)**: "Spin Package changed — [Rebuild ERS]".

## 8. Live E2E target (§31)

**Venture Mess Hall does not exist** in the DB (audit §7). The only populated real map is **"Venture Corridor Walk"** (map `7c7aac85-6932-4945-a13f-4a11fd69b79f`, scene `b5282a4c-07eb-40db-9d5b-1512eac74dca`, 10m×10m, 2 characters, 1 camera). Certification runs on that real map with this disclosure, unless the owner directs otherwise.

## 9. Test plan

- Backend unit: spin placement validation (center tolerance), manifest build, direction prompt compile (all 5), per-direction retry preserving others, version bump on provider change, ERS stale flag, Co-Director tool handlers.
- Frontend vitest: gating logic, progress states, guidance chip, compass render, Mini section ordering.
- Live E2E: real package on Venture Corridor Walk (or owner-chosen map), consistency acceptance (§32), single-direction regen, ERS build, 19 verdicts.
