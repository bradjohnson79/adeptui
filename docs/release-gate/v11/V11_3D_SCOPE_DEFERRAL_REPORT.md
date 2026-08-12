# V1.1 — Native 3D Scope Deferral Report

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Release target** | Adept UI Version 1.1 |
| **Deferred release** | Adept UI Version 1.2 |
| **Verdict** | **GO — Native 3D deferred cleanly to Version 1.2.** |

Machine-readable inventory: [`artifacts/v11/deferred-3d-capabilities.json`](../../../artifacts/v11/deferred-3d-capabilities.json)

---

## Decision

Version 1.1 places native 3D modeling, animation, scene assembly, and import on hold by product policy (`DEFERRED_VERSION_1_2`). This is **not** a capability failure.

Supported Version 1.1 environment pipeline:

Source images → 360 collage / equirect panorama → Project Library environment → Spatial Map → character/camera blocking → camera & lighting direction → image/video generation → lip-sync → Editing Suite → final render/export.

Honest labels used: **360 Environment**, **Panoramic Environment**, **Spatial Background**, **Panoramic Spatial Map**.

---

## Surface audit outcomes

| Surface | Outcome |
|---|---|
| Nav **3D & Virtual Environment Studio** | Hidden from ordinary navigation |
| Nav **Virtual Stage** | Hidden from ordinary navigation |
| `/environment-studio`, `/virtual-stage` | Informational “Coming in Version 1.2” pages directing to 360 + Spatial Map + camera/lighting |
| `POST /api/codirector/m213/*` mutate | Backend gated → `403` + `DEFERRED_VERSION_1_2` |
| `POST/GET /api/codirector/m28/virtual-stage*` | Backend gated → same canonical deferred response |
| Library taxonomy “3D” folders | Labeled **3D (Coming in Version 1.2)** |
| Game Cinematic template | Library slot `"3D"` removed; notes panoramic + Spatial Map method |
| Co-Director tools | No executable `ve.*` / mesh / rig / mocap tools; system prompt forbids proposing them |
| M2.13 / M2.8 foundations | Preserved in-tree behind flags for Version 1.2 |

---

## Capability registry

- New status: `deferred_version_1_2` (“Coming in Version 1.2”)
- Not in `BLOCKING_STATUSES` / never Failed / Missing / Blocked / Partial / Install Required
- Excluded from Version 1.1 readiness denominator via `readinessTotal` (health `registry.total`)
- Deferred IDs listed in snapshot `deferred[]` and inventory JSON

---

## Tests

| Suite | Result |
|---|---|
| `studio-api/tests/test_v11_3d_scope_deferral.py` | **7 passed** |
| Capability vocabulary includes `deferred_version_1_2` | Covered |
| Playwright `tests/e2e/v11/version-scope.spec.ts` | V11-SCOPE-01..20 implemented |

---

## Version 1.1 vs 1.2 language

### Version 1.1
360 panoramic environments · image-collage backgrounds · Spatial Map planning · camera direction · lighting direction · AI image/video generation · lip-sync · audio · Editing Suite · final rendering/export

### Version 1.2
Native 3D importing · 3D modeling · rigging · skeletal animation · mocap · 3D scene assembly · Blender/Unreal integration · 3D export

---

## Protection

- Certified M3.2f LTX Hitchhiker scene untouched by this scope lock
- Current M3.2g WAN Test 2 output preserved (`scene_test2_wan_full_c82c2e65.mp4`)
- No destructive deletion of M2.13/M2.8 code

---

## Acceptance checklist

| # | Criterion | Met |
|---|---|---|
| 1 | Native 3D importing unavailable | Yes |
| 2 | Native 3D modeling unavailable | Yes |
| 3 | Native 3D animation/rigging unavailable | Yes |
| 4 | No broken/placeholder 3D actions exposed | Yes |
| 5 | Co-Director does not propose deferred 3D | Yes |
| 6 | Co-Director recommends 360 + Spatial Map | Yes |
| 7 | 3D labeled Coming in Version 1.2 | Yes |
| 8 | Deferred does not reduce V1.1 readiness denominator | Yes |
| 9 | Deferred does not appear as technical failure | Yes |
| 10 | Templates describe supported workflows | Yes |
| 11 | 360 environments remain available | Yes |
| 12 | Spatial/camera/lighting/ImageGen/VideoGen/lipsync/audio/editor/render/export remain | Yes |
| 13 | M3.2g WAN checkpoint preserved | Yes |
| 14 | Version 1.1 scope suite present | Yes |
| 15 | Docs separate V1.1 from V1.2 | Yes |

---

## Final verdict

### **GO — Native 3D deferred cleanly to Version 1.2.**

Owner-led Beta testing must still wait until M3.2g is promoted from `PARTIAL_GO` to full GO.
