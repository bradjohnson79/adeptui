## MiniMax H3 Surface Wiring

This surface adds a creator-safe MiniMax H3 planning package at `studio-api/app/minimax_h3/` and wires it into:

- FastAPI routes under `/api/minimax-h3`
- Production Control model registry as `minimax-h3`
- Co-Director tool definitions and handler registry

### Runtime truth

- Local MiniMax H3 is territory-gated and fail-closed on unknown territory.
- Local open-weight territory checks use the H3 runtime territory, not a hardcoded US-host assumption.
- The current audited development default is Canada (`CA`), with `VITE_MINIMAX_H3_TERRITORY` available as an override.
- Three-frame native support is false.
- Adept defaults three-frame work to Strategy A segmented assembly:
  - `Start -> Middle`
  - `Middle -> End`
- LTX is the permanent fallback, but only through explicit creator approval.
- This surface never claims local or hosted generation succeeded when no runtime actually queued.

### Surface list

- `GET /api/minimax-h3/capability`
- `POST /api/minimax-h3/prepare-plan`
- `POST /api/minimax-h3/preflight`
- `POST /api/minimax-h3/three-frame/plan`
- `POST /api/minimax-h3/jobs`
- `POST /api/minimax-h3/fallback/ltx`
- `GET /api/minimax-h3/plans/{project_id}/{plan_id}`

### Creator language guardrails

- Surface copy avoids ComfyUI, node graphs, workflow JSON, checkpoint filenames, and filesystem paths.
- Planning copy speaks in creator terms: prompt, frames, approvals, fallback, assembly plan, and timeline.
- Advanced metadata may preserve internal trace data, but primary creator summaries stay clean.

### License summary

- Canada is within the pinned Community License `Applicable Territory`; excluded open-weight territories remain the US, EU, UK, and Republic of Korea.
- MiniMax H3 local weights are blocked only when the runtime territory falls inside an excluded territory.
- Unknown territory is treated as blocked until the territory is supplied explicitly.
- This implementation does not mark local MiniMax H3 as GO and does not download weights.
- Clearance record: `docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md`
