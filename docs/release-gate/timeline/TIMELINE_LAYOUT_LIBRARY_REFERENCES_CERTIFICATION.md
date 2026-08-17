# Timeline Layout + Library References — Certification

> **Historical.** Superseded for Timeline chrome/layout by `docs/release-gate/timeline/TIMELINE_V2_LAYOUT_REBUILD_CERTIFICATION.md`. Keep this document for the Library references / alias-rename product gate; do not cite it as current Timeline layout truth.

**Status:** Historical for layout; still valid for Library references behavior.  
**Date:** 2026-08-16  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**HEAD:** `a62507ef2c48129e099183e7a863c363a860a95c` (working tree includes this refinement; not yet committed)  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`

Product law: Library stores media. References identify it (`@` entity, `#` image, `*` video). Timeline uses it. Prefix is UI only. Compile uses canonical Library / entity IDs, never alias text.

## Verdict

`GO — TIMELINE LAYOUT + LIBRARY REFERENCES REFINEMENT CERTIFIED END TO END`

Independent line: `VERIFIED — TIMELINE LAYOUT + LIBRARY REFERENCES REFINEMENT PASSED`

## Scope

Enhancement of the existing Timeline Generator shell. Not a rewrite. No new Library. No audio reference type. No `POST /api/projects`.

## §82 matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Resizable left/right panes persist across reload | PASS Playwright | `tests/e2e/timeline/timeline-layout-library-references.spec.ts` |
| Reset Layout restores panes + viewer, not content | PASS Playwright | `timeline-reset-layout` |
| Viewer Fit / Size / picture shape / Guides / Pause viewer in Scene header | PASS Playwright | `timeline-viewer-fit`, `timeline-viewer-preset`, `timeline-viewer-aspect`, `timeline-viewer-pause` |
| One Full Screen (workspace) | PASS Playwright | `workspace-fullscreen-controls`; `timeline-viewer-fullscreen` count 0 |
| Timeline uploads removed | PASS Playwright | no Upload image/video/audio in Timeline Library |
| Library-only add (drag / Add to Timeline / Add to References) | PASS Playwright | `asset-add-reference-*` on Schnick `KorriPoseVideo` |
| Typed chips `@ / # / *` | PASS Playwright | compact References pane chips |
| Typed autocomplete rows (token · type · duration) | PASS Playwright + unit | row contains `Video`; `referenceTokens.test.ts` |
| Wrong-type reject | PASS Playwright + unit | `#` image row on Video Reference → `timeline-reference-type-error` |
| Unsupported generator warning, binding kept, not consumed | PASS unit | `test_unsupported_video_ref_is_not_consumed` |
| Alias rename persistence (same binding id + asset id; compile by ID) | PASS Playwright + unit | rename `*KorriPoseVideo` → `*KorriDanceMotion`; clip keeps `reference_binding_id` + `asset_id`; compile tests use canonical id |
| Image reference compile by canonical ID | PASS unit | `test_image_reference_compile_canonical_id` |
| Remove chip leaves Library | PASS Playwright | chip gone; `GET /api/assets/{id}/file` not 404 |

## Unit evidence

- `studio-api/tests/test_timeline_reference_aliases.py` + scene reference + adapter tests: **42 passed**
- `studio-web` layout + token tests: **10 passed**
- `studio-web` production build: passed (`dist/assets/index-Gy6TUC_A.js`)

## Playwright

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
1 passed (6.8s)
```

Target: UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`. Schnick only.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (resize, Reset Layout, Add to References, token pick, rename, remove chip) |
| Frontend | PASS (shell splitters, Scene header viewer controls, Library-only, chips, autocomplete) |
| API | PASS (`alias`, `media_kind`, project scope; restore-on-reattach after soft delete) |
| Backend | PASS (`reference_compile.py` → canonical `assetId`) |
| Persistence | PASS (binding id on clips after hard reload; JSON `image_reference_clips`) |
| Runtime | N/A for layout; compile proof uses existing adapters (no GPU) |
| Result | PASS |
| Reload | PASS (pane widths + renamed alias + same binding/asset ids) |
| Downstream | PASS unit (request builder uses `assetId`, not alias text) |

## Limitations

- Audio cannot be a typed reference. Lip Sync / SFX / Music remain direct Library audio.
- Deploy / Vercel SHA alignment is gated on an explicit commit + push (not done in this session).
- A Schnick Library video `KorriPoseVideo` was uploaded into the existing project for the locked alias-rename gate (no `POST /api/projects`).
