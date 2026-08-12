# Prompt Intelligence — V1 vs V2

- **V1** (`docs/codirector/prompt-enhancement/`): deterministic enhancement pipeline (intent → refinement → language modules → four-layer record). Offline matrix only. `bilingualCertified` remains false until V2 evidence.
- **V2** (`docs/codirector/prompt-intelligence-v2/`): evidence-driven benchmark certification, blind human review, category-scoped promote/rollback, adaptive recommendations, Analyzer V2 axes.

V1 APIs remain stable; V2 adds `/api/codirector/prompt-intelligence/v2/*` and additive fields (`strategyRecommendation`, `analyzerV2`) on enhance/analyze.
