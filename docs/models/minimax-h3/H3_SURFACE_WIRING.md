## MiniMax H3 Surface Wiring

This surface lives at `studio-api/app/minimax_h3/` and wires into:

- FastAPI routes under `/api/minimax-h3`
- Production Control model registry as `minimax-h3`
- CREATE 1 Frame / 3 Frame via queue worker Route A (`api.render` scene jobs)

### Runtime truth (2026-09-09 PT)

- Private local Route A (:8192) executes T2V, 1F I2V, and CREATE 3 Frame (first+last ± optional AddGuide).
- Workflow capability: `minimax-h3` `multiFrame` → `route_a.flf2va`.
- `threeFrameNative=True`; default strategy `middle-guidance-b`.
- Empty middle graph matches proven local 2-frame (no AddGuide).
- Partner Hailuo FLF is not the Adept 3 Frame middle path.
- Timeline Ref2V / CRS / Co-Director cast are out of scope for CREATE 3 Frame.

### Surface list

- `GET /api/minimax-h3/capability`
- `POST /api/minimax-h3/prepare-plan`
- `POST /api/minimax-h3/preflight`
- `POST /api/minimax-h3/three-frame/plan`
- `POST /api/minimax-h3/jobs`
- `POST /api/minimax-h3/fallback/ltx`
- `GET /api/minimax-h3/plans/{project_id}/{plan_id}`
