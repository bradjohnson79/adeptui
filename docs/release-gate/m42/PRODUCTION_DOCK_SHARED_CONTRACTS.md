# Production Dock — Shared Contracts (Frozen)

**Status:** Frozen before parallel SA implementation  
**Branch:** `phase2/m42-production-dock`  
**Starting SHA:** `f758744`  
**Primary certification standard:** Dock preference → persist → resolver consume → readiness → real job → provenance → reload  

Subagents may not redefine these contracts without primary approval.

---

## PreferenceScope

```text
system | user | project
```

**Precedence:** `project` override → `user` default → `system` default  

## ProductionRuntimeSource

```text
local | api | hybrid
```

Global availability only. Per-modality routing is separate.

## CpuFallbackPolicy

```text
disabled | ask | lightweight_only
```

Default: `disabled`. No silent CPU for production generation (Law 26).

## CapabilityLabel

```text
Certified | Testing | Available | Unavailable | Unsupported | Requires Setup | Loading | Error
```

## LocalLifecycle

```text
Installed | Loading | Loaded | Unloading | VRAM insufficient | Worker offline | Dependency error | CPU-only framework detected
```

Distinguish **installed** from **executable**.

## TimelineActionCapability (reserved)

```text
full_scene | start_end_frame | continuation | reference_conditioning
| native_inpaint | range_replacement | audio_generation | timeline_batch
```

## ModelDescriptor

| Field | Type | Notes |
| --- | --- | --- |
| id | string | Stable id |
| modality | llm \| video \| image \| audio |
| label | string | Creator-facing |
| locality | local \| hosted |
| providerId | string? | kie \| wavespeed \| fal \| ollama \| ace-step \| mmaudio \| … |
| capabilityLabel | CapabilityLabel | Honest |
| lifecycle | LocalLifecycle? | Local only |
| supports | string[] | Action/capability tags |
| doesNotSupport | string[] | Explicit negatives |
| estimatedVramGb | number? | |
| gpuCompatible | boolean | |
| executable | boolean | Ready to run now |

## ModelRoutingPreference

| Field | Type |
| --- | --- |
| modality | llm \| video \| image \| audio |
| preference | local_preferred \| hosted_preferred \| ask_before_switching \| manual_only |
| availableModelIds | string[] |
| activeModelId | string? |
| fallbackModelId | string? |
| allowFallback | boolean |

Checkbox ≠ active. Active / available / fallback are distinct.

## PreferenceProvenance / ResolvedSelection

| Field | Type |
| --- | --- |
| activeModelId | string? |
| activeLabel | string |
| source | PreferenceScope |
| fallbackPolicy | string |
| gpu | Ready \| Unavailable \| Unknown |
| executable | boolean |
| blockedReason | string? |
| runtime | string? |
| providerId | string? |
| cpuFallbackPolicy | CpuFallbackPolicy |

## UserGlobalPreferences

- theme: `aurora-night` \| `aurora-day` \| `system`
- dockCollapsed, dockAutoCollapse
- runtimeSource: local/api/hybrid flags
- defaultHostedProviderId
- cpuFallbackPolicy
- modality routing defaults (llm/video/image/audio)
- quality defaults

## ProjectPreferences

- active video/image/audio model ids
- project resolution / quality
- project Co-Director model
- generator locks (Timeline scenes)

## ActiveModelSelection

```json
{
  "modality": "audio",
  "activeModelId": "ace-step-local",
  "availableModelIds": ["ace-step-local"],
  "fallbackModelId": null,
  "allowFallback": false,
  "provenance": { "source": "project", "executable": true, "gpu": "Ready" }
}
```

## Gate

`GET /api/production-control/gate` → `productionDockGo` false until all required flags true. No Conditional GO. No hardcoded GO.
