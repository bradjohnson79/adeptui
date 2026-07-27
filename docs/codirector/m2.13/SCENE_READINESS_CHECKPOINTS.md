# Scene Readiness Checkpoints

## GO

- Required approvals persisted for path in use
- No open blockers on the active plan
- Honesty labels present for fixture/mock outputs
- Manifest sha256 unchanged

## NO-GO

- Missing approval gate
- Capture coverage insufficient (Route A) without force+inferred label
- Blender/COLMAP required but absent (clear error, no silent install)
- Attempted silent stage advance

API: plan `readiness` field + `GET /api/codirector/m213/plans/{id}/dashboard`
