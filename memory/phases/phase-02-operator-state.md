# Phase 2 — Verified Operator + Production State

## Operator (`app/codirector/operator/`)
- **contracts.py**: `OPERATOR_TOOLS` (5 tools), `OPERATOR_TIMEOUT_SEC=3.0`, `OperatorRecord`
- **service.py**: `register_operator_request`, `acknowledge_operator_request`, `get_operator_record`, `has_operator_ack`
- **Truthfulness gate**: `_operator_premature_success_claim` in service.py blocks "opened X" without ACK
- **NAVIGATE target mapping** (service.py): script_writer → workspace.open_scriptwriter, audiostudio → audio.open_studio, etc.

## Production State (`app/codirector/production_state/`)
- **contracts.py**: `ProjectionDomain` enum (14 domains), `ProvenanceField`, `ProductionState`
- **projection.py**: `build_production_state` — read-only composition over 8+ authoritative sources
- **stage_evidence.py**: `collect_stage_evidence` (7 sources → 1 authority), `get_authoritative_stage`
- **invalidation.py**: `invalidate_production_state` hooks

## Tests: 40 (operator 15, production_state 10, mock_leak 3, posecraft 20, docker 8)
## Certification: GO
