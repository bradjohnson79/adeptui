# Testing

M4.11 currently relies on focused backend tests plus a mocked Playwright creator flow.

## Code paths

- Spatial backend tests: `studio-api/tests/test_m411_spatial_map.py`
- Image contract/product tests: `studio-api/tests/test_m48_m49_contracts.py`, `studio-api/tests/test_m42_w3_image_product.py`
- Playwright creator flow: `tests/e2e/m411/m411-spatial-map-360-consistency.spec.ts`

## Coverage focus

- Character, prop, and camera limits
- Spatial bundle generation and compile-preview merge
- Storyboard metadata persistence
- Creator flow through Spatial Map workspace, 360 planning, scene assignment, and Image Generator selection
