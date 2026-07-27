# Dependency and Blocker Management

## Dependency register (default)

- Environment approval (E) blocks blocking/camera/lighting work
- Blocking approval (K) blocks shot packages and concepts
- Camera/lighting approval (N) blocks shot packages and concepts

## Blockers

Blockers are appended when:

- Approval gate unmet on advance
- Explicit `add_blocker` / operational failure
- Adapter unavailable without fixture fallback

Blockers force readiness `NO-GO` until cleared by a later successful approved advance path.
