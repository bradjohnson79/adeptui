# Assignment — ComfyWorkflowSubagent

```yaml
role: ComfyWorkflowSubagent

owned_scope:
  - zimage.txt2img / zimage.ref_edit builders
  - certified-registry fingerprints for Character Creator workflows
  - confirm no mock / placeholder graph on Character Creator path

allowed_files:
  - studio-api/app/workflows/image_tools.py
  - studio-api/app/workflows/image_edit_tools.py
  - config/image-workflows/certified-registry.json
  - studio-api/tests/test_zimage_ref_edit_latent_fix.py

forbidden_files:
  - studio-web/**
  - voice performance / voice creator
  - character_identity UI
  - certification binary verdict docs

inputs:
  - M42_SUBAGENT_SHARED_CONTRACTS.md
  - M42_CHARACTER_CREATOR_WORKFLOW_REPORT.md
  - M42_CHARACTER_CREATOR_COMFYUI_REPORT.md

required_outputs:
  - Subagent Handoff
  - confirmation of real Comfy path vs mock
  - fingerprint status

tests_owned:
  - studio-api/tests/test_zimage_ref_edit_latent_fix.py

dependencies:
  - ComfyUI runtime on :8188 for live proof (primary executes E2E)

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/ComfyWorkflowSubagent.md

escalation_conditions:
  - registry fingerprint update required without prior GO sprint context
  - builder change would alter shared contract shapes
```
