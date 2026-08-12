# Persistence

`PromptIntelligenceRecord` is stored on:

- Scene `director_json.promptIntelligence`
- Timeline `ExecutionSnapshot.promptIntelligence` (immutable at create)
- Image compile metadata (`promptIntel.promptIntelligence` when present)
- Audio Studio brief / batch when `runPromptIntelligence` is used

Completed generation records are never rewritten when preferences or templates change.
