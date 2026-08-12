# Testing

## Backend tests added

`studio-api/tests/test_setup_lifecycle.py` covers:

- dual-confirm install plan behavior for large models
- certified recipe lookup
- calibration/certification persistence
- certified-registry-driven update checks
- monitor drift detection
- archive lifecycle behavior
- proposal preview not executing install mutation

## Existing tests reused

- `studio-api/tests/test_production_dock.py`

This branch also reuses existing Production Dock tests because setup-driven dock posture now depends on the new lifecycle-aware model mapping.

## Frontend validation

- `studio-web` production build (`tsc -b && vite build`)

## Playwright

- `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`

This spec covers the setup mode chooser and AI-Guided panel rendering path.
