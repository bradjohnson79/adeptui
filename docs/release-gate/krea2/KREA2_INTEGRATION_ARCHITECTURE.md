# Krea 2 Integration Architecture

## Goal

Krea 2 Turbo and RAW are first-class image-generation options inside Adept UI without creating a parallel subsystem. They use the existing image pipeline's provider registry, model catalog, ComfyUI workflow registry, reference-conditioning, and asset system.

## High-Level Flow

```
Creator selects "Krea 2 Turbo" in Image Studio
    ↓
Image Studio provider layer (`app/image_studio/providers.py`)
    ↓
Production Dock model catalog (`app/production_control/model_registry.py`)
    ↓
Image runtime resolves model family → `krea2` (`app/image_runtime/model_discovery.py`)
    ↓
Certified registry returns `krea2.turbo.txt2img` workflow
    (`config/image-workflows/certified-registry.json` + `app/image_runtime/certified_registry.py`)
    ↓
Krea2 workflow adapter builds the ComfyUI graph
    (`app/workflows/krea2_image.py`)
    ↓
`prepare_executable_graph` validates topology + bindings
    (`app/image_runtime/workflow_execute.py`)
    ↓
ComfyUI queue (manual Beta; no automated GPU generation in cert)
    ↓
Output asset registered in shared Asset system
```

## Key Concepts

- **Krea 2 Turbo:** default production inference model. 8 steps, CFG 0, recommended `mu` shift.
- **Krea 2 RAW:** advanced / LoRA training base. 52 steps, CFG 3.5.
- **Official LoRA guidance:** train on RAW, run inference on Turbo.
- **Model root:** `D:\01_Models\krea2\` (shared root; no copies inside ComfyUI or project folders).
- **Provider:** `comfyui` local runtime; Krea 2 is a model family, not a new provider.

## Extension Points Touched

| Layer | Files |
|-------|-------|
| Provider registry | `config/image-runtime/provider-registry.json` |
| Model catalog | `app/production_control/model_registry.py` |
| Family discovery | `app/image_runtime/model_discovery.py` |
| UI readiness | `app/image_studio/providers.py`, `app/comfy_health.py` |
| Capabilities | `app/capabilities/registry.py` |
| Setup/install | `app/setup/catalog.py`, `app/config.py` |
| Workflows | `app/workflows/krea2_image.py`, `config/image-workflows/certified-registry.json` |
| Contracts | `app/image_runtime/contract.py`, `app/image_runtime/asset_refs.py` |

## ERS Semantic Role Law

Environmental Reference Sheet assets are tagged with the `environment` role. Normalization preserves that role and never reassigns it to another conditioning bucket, even though Krea 2's open ComfyUI path exposes only a generic reference-image interface. The role is carried in Adept metadata and node labels until provider-native role support exists.

## See Also

- `KREA2_IMAGE_PIPELINE_AUDIT.md` — initial read-only audit
- `KREA2_COMFYUI_WORKFLOW.md` — workflow builder details
- `MULTISHOT_IMAGE_PLANNING_ARCHITECTURE.md` — Multi-Shot planning details
- `KREA2_LICENSE_NOTES.md` — licensing requirements
- `KREA2_MULTISHOT_INTEGRATION_FINAL_CERTIFICATION.md` — certification verdict
