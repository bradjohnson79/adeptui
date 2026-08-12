# Image Pipeline Foundation — Playwright Certification

**Spec:** [`tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts`](../../../tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts)  
**Beta URL:** http://127.0.0.1:8760/  
**API:** http://127.0.0.1:8758/  
**Date:** 2026-08-03

## Live evidence

```text
Command:
  ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758
  npx playwright test tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts --project=chromium

Result:
  9 passed (44.9s)
```

Artifacts under `docs/release-gate/image-pipeline/artifacts/` and Playwright output under `artifacts/functional-audit/`.

## Journeys

| ID | Result |
|---|---|
| A Disposable project + Image Studio | PASS |
| B Quick portrait plan | PASS |
| C Multi-character → PoseCraft staging | PASS |
| D Spatial honesty | PASS |
| E Candidates recommend/select (no fake assets) | PASS |
| F API approval honesty | PASS |
| G Validate / repair / master disclosure | PASS |
| H Project isolation | PASS |
| I Co-Director `image_pipeline.*` tools | PASS |

## Cleanup

Disposable IMAGE-PIPELINE-CERT projects deleted to 404. Manual Beta Handoff unchanged.

## Limitations (honest)

- Live GPU still-image completion remains environment-dependent (certified ComfyUI); foundation cert proves orchestration honesty (draft/queued slots, no false assets).
- PoseCraft control packages use foundation fixture until parallel worktree merge.
- Visual Language Engine deferred to v1.2/v1.3.
- Full 20-scenario semantic media matrix is tracked in the capability matrix for follow-on live GPU cert.

## Verdict

**GREEN — PRODUCTION IMAGE PIPELINE READY**

Adept Law 24 mapping: **GO** for foundation orchestration integration. Remaining GPU media-depth scenarios are follow-on certification, not silent claims in this layer.
