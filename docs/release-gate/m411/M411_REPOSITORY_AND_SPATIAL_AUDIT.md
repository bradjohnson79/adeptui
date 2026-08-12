# M4.11 Wave 0 — Repository and Spatial Workflow Audit

## Audit Gate

| Field | Value |
| --- | --- |
| Mission | M4.11 Spatial Map + 360 Scene Consistency Studio |
| Starting branch | `feature/m4-10-voice-performance-index-tts2` |
| Starting SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Feature branch | `feature/m4-11-spatial-map-360-consistency` |
| Subagent law | Law #27 — specialized subagents use `gpt-5.4-medium` |
| Verdict | **AUDIT_COMPLETE — GO for Wave 1** |

---

## Trace (current)

```text
Scene
→ Project.spatial_map_json (legacy) + Scene spatial docs (spatial_scene.py)
→ SpatialSceneWorkspace / SpatialMap UI
→ spatial_prompt_builder
→ Image / Video generation (prompt notes, tags)
→ Storyboard (lens/shotSize strings)
→ Timeline (richer camera catalog, weak spatial bridge)
→ Lip Sync / Editor (downstream)
```

---

## Exists (reuse)

| Area | Path |
| --- | --- |
| Spatial scene engine | `studio-api/app/spatial_scene.py` |
| Legacy spatial map | `studio-api/app/spatial.py`, `schemas.SpatialMap` |
| Prompt builder | `studio-api/app/spatial_prompt_builder.py` |
| FE workspace | `studio-web/src/components/SpatialSceneWorkspace.tsx` |
| FE map | `studio-web/src/components/SpatialMap.tsx` |
| 360 env assets | `studio-api/app/environment_assets.py` |
| Library 360 taxonomy | `project_library/taxonomy.py` → `scenes.panoramas_360` |
| Image continuity | `image_studio/continuity.py` |
| Storyboard | `storyboard_studio/` |
| Timeline cameras | `director_timeline_w46/camera_catalog.py` |
| Nav | `workspaces.ts` Spatial (legacy badge) |

---

## Gaps for M4.11

1. No first-class **Spatial Map document** with 4-character / 4-prop / 8-camera certified limits.
2. No **360° directional collage** model (8+ views) with consistency status.
3. No Co-Director **`spatial.*` tools** or master-environment + camera-rotation capture plan.
4. No **SpatialReferenceBundle** for Image/Video Generator handoff.
5. Storyboard→Timeline camera metadata remains stringy.
6. Location is split across references/library — no Spatial Map assignment model.
7. Artist-facing language still mixed with engineering coordinates in places.

---

## Strategy

**Extend** `spatial_scene` foundations; **create** `studio-api/app/spatial_map/` as the M4.11 domain package (documents, collage, reference bundles, limits, Co-Director capture intelligence).

**Evolve** `SpatialSceneWorkspace` into Spatial Map + 360 Collage + Camera Views tabs without a disconnected app.

**Promote** Spatial from “legacy” badge to production Spatial Map workspace.

---

## Gate

Broad implementation may begin. Do not claim GO until Wave 7 certification with live image reference use and human UX stamp.
