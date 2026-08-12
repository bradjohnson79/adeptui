# Co-Director Final Optimization — Pipeline Manifest

Authoritative stage contracts live in code:

`studio-api/app/codirector/conversation/pipeline_manifest.py`

## Flow (foreground vs background)

```mermaid
flowchart TD
  userMsg[UserMessage] --> receipt[RECEIVING]
  receipt --> classify[IntentPlusComplexity]
  classify --> rel[RelationshipOwnership]
  rel --> momentum[MomentumAndConfidenceRead]
  momentum --> cache[ProjectCacheRead]
  cache --> retrieve[BoundedRetrieval]
  retrieve --> selectSpec[SpecialistSelectionIfNeeded]
  selectSpec --> prompt[PromptAssembly]
  prompt --> dispatch[WAITING_FOR_MODEL]
  dispatch --> stream[STREAMING_RESPONSE]
  stream --> fastGround[FastGrounding]
  fastGround --> persist[ConversationPersist]
  persist --> nextSteps[NextStepOptions]
  nextSteps --> complete[COMPLETE]
  stream -.-> bgWiki[BackgroundWikiBrief]
  stream -.-> bgMomentum[BackgroundMomentumUpdate]
  stream -.-> bgConfidence[BackgroundConfidenceUpdate]
  selectSpec -.-> bgSpec[BackgroundSpecialists]
  bgWiki -.-> bgCache[CacheRevision]
```

## Rules

- Background stages never block first SSE token.
- Specialists are subordinate (`creatorFacingAllowed: false`); Co-Director synthesizes.
- Wiki enrichment succeeds only after read-back.
- Momentum / Creative Confidence update after stream begins.
