# PoseCraft — Co-Director Scene Labels

## CURRENT AUTHORITATIVE STATUS

```text
GO — POSECRAFT CO-DIRECTOR SCENE LABELS READY
```

**Implementation status:** IMPLEMENTED + INDEPENDENTLY VERIFIED — see `POSECRAFT_SCENE_LABELS_INDEPENDENT_VERIFIER_REPORT.md`.

> Independent verifier (GLM 5.2) re-ran `tests/e2e/posecraft/posecraft-scene-labels.spec.ts` against live Beta
> (Playwright exit 0, 1 passed, 4.3 s, no retries). A persistence defect was found and repaired during
> verification: `saveVersionNow` now flushes to the API via a `keepalive` PUT so an explicit Save survives
> an immediate reload. Acceptance criteria were not weakened. Beta refreshed and live at
> http://127.0.0.1:8760/ (API http://127.0.0.1:8758/).

## Product law

```text
Internal ID = permanent machine identity
Scene label = creator-editable semantic identity (figure/primitive `name`)
```

## Delivered

| Gate | Result | Independent Verify |
| --- | --- | --- |
| LABEL-1 Figure Labels Persist | IMPLEMENTED | PASS |
| LABEL-2 Furniture Labels Persist | IMPLEMENTED | PASS |
| LABEL-3 Stable Internal IDs | IMPLEMENTED | PASS |
| LABEL-4 Co-Director Semantic Labels | IMPLEMENTED | PASS |
| LABEL-5 Image Gen Package | IMPLEMENTED | PASS |
| LABEL-6 Storyboard Package | IMPLEMENTED | PASS |
| LABEL-7 Viewport Label Toggle | IMPLEMENTED | PASS |

### Surfaces

- Types/state: `role`, `showLabels`, `renamePrimitive`, `setFigureRole`
- Semantic package: `studio-web/src/posecraft/semanticLabels.ts` + export handoff
- API export preview: labels/roles/objects/`semanticSummary`
- Co-Director: `posecraft.inspect_scene`, `posecraft.list_scenes`, `posecraft.rename_object`, `posecraft.set_figure_role`
- UI: Role select, Show Labels, furniture Rename, viewport floating labels (`pointer-events: none`)

### Playwright

`tests/e2e/posecraft/posecraft-scene-labels.spec.ts`

### Verdict strings

```text
GO — POSECRAFT CO-DIRECTOR SCENE LABELS READY
```

or

```text
NO-GO — POSECRAFT CO-DIRECTOR SCENE LABELS FAILED
```
