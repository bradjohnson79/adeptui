# M42 Wave 4C — Route Compatibility

| Field | Value |
|---|---|
| **Canonical** | `/project/:id?workspace=timeline` |
| **Legacy alias** | `/project/:id?workspace=director` → resolves to `timeline` |
| **Strategy** | `resolveWorkspace()` central alias — no second product |
| **Verdict** | **GO** |

Project ID, query params, and hash are preserved. No standalone `/director` top-level route existed; none was added as a duplicate runtime.
