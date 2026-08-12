# Automatic Production Assurance Cross-Check

## Architecture

```
Co-Director mount (500ms deferred)
  → runStatusCheck()
  → 12+ parallel probes via asyncio.gather
  → Preflight: api.health fails → stop early + cache invalidation
  → Shared warm bundle (ComfyUI + capabilities)
  → Per-check timeouts (2s - 20s depending on check)
  → Aggregate results → persist_run → UI updates
```

## Check Classification

| Criticality | Checks |
|---|---|
| Critical | api.health, session.binding, codirector.provider, tools.registry, proposal.service, library.preflight |
| High | capabilities.registry, comfy.health, production_control.status, image_runtime.readiness, video_runtime.readiness |
| Standard | voice_environment.runtime |

Global (TTL-cached): api.health, capabilities.registry, codirector.provider, comfy.health, production_control.status, image_runtime.readiness, video_runtime.readiness

## State Machine
- "Checking…" → "Ready" (all critical/required pass)
- "Ready with warnings" (non-blocking issues)
- "Action required" (creator must intervene)
- Button: "Re-check" (was "Run Cross-Check")
