# M42 W47 — Subagent Ownership

Primary agent owns final GO/NO-GO. Subagents report READY FOR PRIMARY REVIEW only.

| SA | Owns | Forbidden |
| --- | --- | --- |
| SA1 | Platform detection | Lifecycle mutations, final gate |
| SA2 | Contracts + registry | Docker ops, UI styling |
| SA3 | DockerRuntimeManager backend | Wizard UI, Dock UI |
| SA4 | Manifest | Executing containers |
| SA5 | Security policy | Product layout |
| SA6 | Setup Wizard UX | React→Docker |
| SA7 | Comfy workflow import | Core Comfy install |
| SA8 | Adapter/resolver registration | Docker build |
| SA9 | GPU container preflight | Final verdict |
| SA10 | Runtime Manager UI | Daemon direct access |
| SA11 | Production Dock | Silent fallback |
| SA12 | Queue/GPU scheduling | Wizard |
| SA13 | Storage classes | Lifecycle UI |
| SA14 | Update/rollback | Uninstall |
| SA15 | Repair | Silent destructive reset |
| SA16 | Safe uninstall | Deleting assets/provenance/shared |
| SA17 | Core protection | Reclassifying without approval |
| SA18 | Co-Director runtime.* tools | — |
| SA19–22 | Reviews + tests | Final GO |

Primary executes Waves 0–5 end-to-end with ownership boundaries enforced in code review.
