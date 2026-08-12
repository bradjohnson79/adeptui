# MAGI Error & Recovery Audit

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08

## 1. Backend error handling

- **No structured error envelope.** Failures are bare `HTTPException(status_code=400, detail=<str>)` (`api.py:113, 123, 158`) or raw result dicts embedded as `detail` (render endpoint `:142` `detail=result`).
- 404 uses FastAPI default `{"detail": "Composition not found"}` (`:96`).
- `store.py` never raises for bad input — silently `setdefault`s and overwrites (`:83-96`); `get_sequence` swallows parse errors (`except Exception`, line 75).
- **Structured validation only in the composition domain:** `overlays/validate.py` → `{"ok": False, "errors": [...]}`; `composition/service.py` → `{"ok": False, "error": "<code>"}` dicts + Job flip to failed.
- No Pydantic request/response models anywhere in MAGI API.

## 2. Frontend error handling

- **Global only:** one app-wide `ErrorBoundary` (`App.tsx:43`; `components/ErrorBoundary.tsx:7-36`). No MAGI-specific boundary.
- **Load failure:** local empty-sequence fallback + message (`:418-421`). OK.
- **Save failure:** `saveState:"error"`, `saveError` message (`:541-544`), "Blocked" badge (`:1462`), message banner (`:1468`). OK.
- **Overlay persistence failure:** `persistError` shown in Graphics pane (`:1093`) + status bar (`:1462`). OK.
- **Failed media: NOT handled.** `<img>`/`<video>` have no `onError`/fallback (`:979, 1284-1286`, compare `:1260-1266`).

## 3. Error classification (mission Phase 21) — current vs required

| Error | Current behavior | Required |
|---|---|---|
| Asset missing | Silent (no validation on save) | Structured error; failed-clip badge; recoverable |
| Clip missing | Silent / stale selection possible | Structured; clear selection |
| Media decode failure | Broken image/video, no signal | onError → failed badge, editor usable |
| Persistence failure | saveState error (sequence), persistError (overlay) | Structured, retry offered |
| Unsupported operation | Disabled tabs (histogram/vectorscope) or no-op (shuttle/mask) | Honest disabled + reason |
| Invalid timeline state | N/A (no validation) | Validation errors on save |
| Render/export failure | HTTPException detail=result dict | Structured envelope |
| Provider unavailable | N/A (no provider calls in core path) | N/A — document |

## 4. Recovery requirements (mission Phase 22)

After non-fatal failure, MAGI must remain usable:
- Failed clip marked; other clips intact; editor does not reset; creator can replace/remove failed media; save still works where valid.

## 5. Required repairs (m8)

1. Backend: structured error envelope `{"error": {"code", "message", "fields"}}` (or fastapi HTTPException with consistent `detail` object) across all MAGI routes; no raw stack traces in creator-visible payloads (dev detail may keep full trace via logs).
2. Frontend: concise actionable error surface (per-pane), failed-media recovery, no editor reset.
3. Regression tests for each error class.
