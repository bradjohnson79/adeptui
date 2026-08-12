# Assignment — Qwen2512RuntimeIntegration (GPT-5.4)

```yaml
role: Qwen-Image-2512 Runtime Integration
owned_scope: >
  Install/validate Qwen-Image-2512 weights; dedicated ComfyUI workflow builders;
  registry entries for qwen-image-2512 / qwen2512.*; queue execution wiring for the new family.
allowed_files:
  - studio-api/app/workflows/qwen_image_2512.py   # NEW
  - studio-api/app/workflows/__init__.py           # export only if needed
  - comfyui/workflows/qwen-image-2512/**          # NEW JSON family
  - config/image-workflows/certified-registry.json  # qwen-image-2512 keys only; do not edit FLUX status
  - config/image-runtime/compatibility-catalog.json # qwen-image-2512 entries
  - studio-api/app/setup/catalog.py                 # qwen_image_2512_models component only
  - studio-api/app/setup/diagnostics.py             # verifier for qwen_image_2512_models
  - studio-api/app/config.py                        # qwen_image_2512_* path defaults only
  - studio-api/app/image_runtime/workflow_execute.py # route builder for qwen2512.* only
  - studio-api/app/image_runtime/contract.py        # resolve qwen-image-2512 family only
  - artifacts/m42/w43-qwen-2512/**                  # runtime evidence
forbidden_files:
  - studio-api/app/image_prompting/**
  - studio-api/app/style_intelligence/**
  - studio-web/src/components/CharacterProfileWorkspace.tsx
  - studio-api/app/character_identity/prompt_package.py
  - docs/release-gate/m42/*CERTIFICATION*.md
required_inputs:
  - ComfyUI 0.28.2+ with QwenLoader / TextEncode nodes
  - Official Comfy-Org split files for Qwen-Image-2512
required_outputs:
  - Working build_qwen_2512_txt2img_workflow()
  - Workflow JSON under comfyui/workflows/qwen-image-2512/
  - Registry status path to Certified when weights present
  - Real Comfy queue + output evidence in artifacts
tests_owned:
  - studio-api/tests/test_qwen_2512_registry.py
dependencies:
  - Model weights download (primary may start)
evidence_required:
  - installed model metadata JSON
  - workflow JSON
  - real queue record + logs + generated PNG
escalation_conditions:
  - Missing native nodes for 2512
  - VRAM OOM requiring architecture change
  - Need to edit Character Creator or prompt compiler
```

Do not certify. Do not relabel FLUX/Z-Image workflows.
