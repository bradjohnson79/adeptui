# M41 4.1B-L — UI Certification

| Field | Value |
|---|---|
| **Status** | **PASS** |
| **Artifact** | `artifacts/m41/41bl/workflow_ui_results.json` |

## Honesty rules verified

- Production Ready only when registry `status === Certified` and `certificationRecordId` (or record) is present
- Deferred upscale remains Deferred / not Production Ready
- Cloud fal.* remain Blocked while `enabledCloudProductionWorkflowKeys` is empty — not advertised as ready
- WAN three-frame limitations describe dual-segment first→middle / middle→last + stitch (not native single-graph three-frame)
- Gate API exposes release-stable required sets (`requiredLocalProductionWorkflowKeys`, `requiredCloudProductionWorkflowKeys`, `enabledCloudProductionWorkflowKeys`) and inclusion fields

## Specs

- `tests/e2e/m41/m41-41bl-live-cert-ui.spec.ts`
- `tests/e2e/m41/m41-41b-certified-workflows.spec.ts`
