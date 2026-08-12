# Key Files by Subsystem

## Operator
- `app/codirector/operator/contracts.py` — Tool constants, timeout, OperatorRecord dataclass
- `app/codirector/operator/service.py` — Register, ack, get_record, has_ack

## Router
- `app/codirector/routing/contracts.py` — RouteActionClass enum, RouteDecision model
- `app/codirector/routing/deterministic.py` — classify_deterministic with 8 pattern groups
- `app/codirector/routing/semantic.py` — classify_semantic, route_with_semantic_fallback
- `app/codirector/routing/context.py` — RouterContext, StageSensitiveRouter, CapabilityGate
- `app/codirector/routing/orchestrator.py` — route_turn single entry point
- `app/codirector/routing/adapter.py` — Legacy Taxonomy B compatibility

## Production State
- `app/codirector/production_state/contracts.py` — ProjectionDomain, ProvenanceField, ProductionState
- `app/codirector/production_state/projection.py` — build_production_state
- `app/codirector/production_state/stage_evidence.py` — collect_stage_evidence, get_authoritative_stage
- `app/codirector/production_state/invalidation.py` — invalidate_production_state

## Story Intelligence
- `app/codirector/story_intelligence/story_model.py` — StoryEvidenceModel, StoryFact, build_story_evidence
- `app/codirector/story_intelligence/sanitize.py` — separate_instruction, is_contamination_free
- `app/codirector/story_intelligence/compilers/logline.py` — compile_logline, validate_logline
- `app/codirector/story_intelligence/compilers/short_summary.py` — compile_short_summary
- `app/codirector/story_intelligence/compilers/long_summary.py` — compile_long_summary
- `app/codirector/story_intelligence/proposal.py` — route_compiler_output, trigger_compiler_for_artifact
- `app/codirector/story_intelligence/knowledge_card.py` — KnowledgeCard, CardType, CardStatus, create_card, add_card_to_project

## Workflow
- `app/codirector/workflow/definitions.py` — WorkflowDefinition, 4 format maps
- `app/codirector/workflow/reconciliation.py` — reconcile_workflow, WorkflowAssessment
- `app/codirector/workflow/recommendations.py` — recommend_next_actions

## Specialists
- `app/codirector/intelligence/specialist_selector.py` — SpecialistSelector, SpecialistContext
- `app/codirector/intelligence/specialist_policies.py` — enforce_specialist_permissions
- `app/codirector/intelligence/synthesis.py` — classify_conflicts, RouteDecision-aware

## Conversation
- `app/codirector/conversation/foundation/dialogue_policy.py` — build_dialogue_plan
- `app/codirector/conversation/foundation/intent.py` — analyze_intent (Taxonomy A)
- `app/codirector/conversation/planner.py` — plan_conversation
- `app/codirector/conversation/response_composer.py` — sanitize_response, operation helpers
- `app/codirector/conversation/inquiry.py` — _check_known_fact, decide_inquiry
- `app/codirector/conversation/orchestrate.py` — run_conversation_core_turn
- `app/codirector/conversation/next_steps.py` — build_workflow_next_steps
- `app/codirector/conversation/schemas.py` — ProjectIntelligenceSnapshot, ConversationPlan

## Cross-Check / Status
- `app/codirector/status/runner.py` — run_status_check, _execute_one, cache integration
- `app/codirector/status/registry.py` — 22 check definitions, 22 probes
- `app/codirector/status/probe_context.py` — TTL cache, timeout budgets, warm_shared_bundle
- `app/codirector/status/router.py` — check/registry/status endpoints

## Wiki
- `app/codirector/wiki_intelligence/orchestrator.py` — **auto-extraction DISABLED** (Phase CK)
- `app/codirector/wiki_intelligence/classification.py` — **entity detection depowered** (Phase CK)
- `app/codirector/wiki_intelligence/compiled/` — page_compiler, story_compiler, story_summary_editor

## Beta Runtime
- `scripts/beta_runtime/supervisor.py` — Process lifecycle, health monitoring, restart policy
- `scripts/beta_runtime/web_server.py` — Starlette server serving dist/, proxy to API
- `scripts/beta_runtime/envutil.py` — Environment discovery

## Hosted Beta / Infrastructure
- `config/cloudflared/adept-ui-beta-tunnel.yml` — Cloudflare Tunnel config (tunnel ID 822658ce)
- `Start-CloudflareTunnel.ps1` — Tunnel lifecycle script
- `studio-web/src/runtime/apiBase.ts` — Central API origin abstraction (VITE_API_BASE)
- `studio-web/.env.example` — Environment variable template
- `studio-web/vercel.json` — Vercel SPA rewrite config
- `docs/release-gate/hosted-beta/` — Certification reports for hosted beta

## Frontend
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — Main session hook, status check, welcome suggestions
- `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` — Wiki sidebar, dropdowns
- `studio-web/src/components/CoDirector/CoDirectorStatusPanel.tsx` — Production Assurance status
- `studio-web/src/components/CoDirector/navEntries.ts` — Tab navigation entries
- `studio-web/src/components/CoDirector/CoDirectorShell.tsx` — Shell, tab state
- `studio-web/src/runtime/studioApiConnection.ts` — Health polling, hysteresis, reconnect
- `studio-web/src/hooks/useStudioHealth.ts` — Health hook
- `studio-web/src/api.ts` — All API client functions
