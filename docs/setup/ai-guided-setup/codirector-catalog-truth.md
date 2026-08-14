# Co-Director Catalog Truth

## Scope

This file closes the requested Phase 6 evidence pass for AI-Guided Setup catalog truth. The requirement here is not shell execution. Co-Director must discover, explain, compare, and propose through trusted setup tools and APIs, while Source Manager / install jobs remain the execution owner.

## Trusted setup read tools available

- `setup.search_components`
- `setup.inspect_component`
- `setup.compare_components`
- `setup.inspect_hardware`
- `setup.inspect_dependencies`
- `setup.inspect_license`
- `setup.inspect_source`
- `setup.build_install_plan`
- `setup.get_install_status`
- `setup.diagnose_failure`
- `setup.list_repair_options`
- `setup.list_recipes`
- `setup.inspect_recipe`
- `setup.get_certification`
- `setup.check_updates`
- `setup.get_monitor_status`

These tools are declared in `studio-api/app/codirector/tools/definitions.py`, bound in `studio-api/app/codirector/tools/registry.py`, and implemented through `studio-api/app/codirector/tools/handlers/setup_guided.py` on top of `app.setup.lifecycle.service`.

## Requested spot checks

| Creator question | Trusted Co-Director path | Why this is truthful |
| --- | --- | --- |
| Install Hunyuan 13B | `setup.inspect_component(hunyuan_video_13b)` + `setup.build_install_plan(hunyuan_video_13b, action=install)` | Reads current readiness, source, recipe, and plan steps without executing shell work. |
| Repair IndexTTS2 | `setup.inspect_component(index_tts2)` + `setup.diagnose_failure(index_tts2)` + `setup.list_repair_options(index_tts2)` | Explains why IndexTTS2 is degraded and what trusted repair actions exist before Source Manager executes. |
| Why isn't FLUX ready? | `setup.inspect_component(flux1_dev_local)` + `setup.diagnose_failure(flux1_dev_local)` + `setup.get_monitor_status(flux1_dev_local)` | Surfaces current verification summary and drift findings instead of inventing a reason. |
| anime recommend | `setup.search_components(query="anime")` | Searches capability tags, badges, strengths, and best-fit metadata from the lifecycle catalog. |
| Compare Sana vs Qwen | `setup.compare_components([sana_15_local, qwen_image_2512_models])` | Uses the catalog's readiness, VRAM, speed, badges, and use-case metadata. |
| photoreal character | `setup.search_components(query="photoreal character")` | Returns the same catalog-truth metadata that AI-Guided Setup uses for creator recommendations. |
| make a short film | `setup.search_components(query="make a short film")` | Maps onto existing Ready video IDs (Hunyuan 1.5 first). |
| make a commercial | `setup.search_components(query="make a commercial")` | Maps onto WAN / video, not the fal.ai credential. |
| create a talking presenter | `setup.search_components(query="create a talking presenter")` | Maps onto existing avatar runtimes and reports live Repair / Not Installed honestly. |
| Repair ComfyUI | `setup.inspect_component(comfyui_hunyuan_nodes)` + `setup.diagnose_failure(comfyui_hunyuan_nodes)` + `setup.list_repair_options(comfyui_hunyuan_nodes)` | Keeps repair discussion on the trusted install-job/runtime boundary. |

## Backing APIs behind those tools

- Setup status: `GET /api/setup/status`
- Lifecycle catalog search: `GET /api/setup/lifecycle/components`
- Lifecycle install plan: `POST /api/setup/lifecycle/install-plan`
- Lifecycle monitor: `GET /api/setup/lifecycle/monitor`
- Lifecycle certify/calibrate endpoints: `POST /api/setup/lifecycle/components/{component_id}/...`
- Trusted install job execution / repair: `POST /api/setup/install-jobs/...`

## Validation

- Registry / handler evidence inspected in:
  - `studio-api/app/codirector/tools/definitions.py`
  - `studio-api/app/codirector/tools/registry.py`
  - `studio-api/app/codirector/tools/handlers/setup_guided.py`
- Backend regression run:
  - `python -m pytest tests/test_setup_refactor.py -q`
  - Result: `25 passed`

## Finding

Phase 6 is closed for the requested setup questions: Co-Director now has truthful read/comparison/diagnostic coverage through trusted setup tools and APIs only, while Source Manager remains the sole execution owner.
# Co-Director Catalog Truth

## Audit basis

- Beta API: `http://127.0.0.1:8758`
- Branch: `feature/ai-guided-setup`
- Observed HEAD: `fa09c99d6395c29461cdec4555055faad116c435`
- Project used for read-tool proofs: `4ddfd738-989b-45b7-afa8-d285d852d048`
- Tool registry proof: `GET /api/codirector/projects/{projectId}/tools` returned the full `setup.*` tool set on the live Beta after restart

This document records the Phase 6 spot-checks using only the live Co-Director setup tools. No shell-only reasoning was used for the answers below.

## Registry proof

The live Beta exposes the required setup read tools, including:

- `setup.search_components`
- `setup.inspect_component`
- `setup.compare_components`
- `setup.build_install_plan`
- `setup.get_install_status`
- `setup.list_repair_options`
- `setup.get_monitor_status`

## Query proofs

### 1. Install Hunyuan 13B

Request:

```json
{
  "toolId": "setup.inspect_component",
  "arguments": { "componentId": "hunyuan_video_13b" },
  "requestId": "install-hunyuan"
}
```

Redacted response evidence:

- `status: succeeded`
- `lifecycle.statusLabel: "Ready"`
- `installPlan.requiresRuntimeConfirmation: true`
- `installPlan.requiresModelDownloadConfirmation: true`
- `installPlan.steps`: verify hardware -> verify source -> approve runtime install -> approve model download -> run trusted install job -> calibrate -> certify
- `installPlan.notes`: "Co-Director proposes this plan." / "Source Manager performs the install."

Truthful answer:

Hunyuan 13B already verifies as `Ready` on this machine, but if the creator asks to install it, Co-Director can still present the trusted install plan and then hand execution to Source Manager. That answer comes directly from the live install-plan metadata, not an invented workflow.

### 2. Repair IndexTTS2

Requests:

```json
{
  "toolId": "setup.inspect_component",
  "arguments": { "componentId": "index_tts2" },
  "requestId": "repair-indextts2"
}
```

```json
{
  "toolId": "setup.list_repair_options",
  "arguments": { "componentId": "index_tts2" },
  "requestId": "index_repair"
}
```

Redacted response evidence:

- `lifecycle.statusLabel: "Ready"`
- `verificationSummary: "IndexTTS2 runtime is ready."`
- `data.recoveryActions: []`
- `monitorFindings: []`

Truthful answer:

The live setup catalog says IndexTTS2 does not currently need repair. A correct Co-Director answer is to say that it is already `Ready`, and there are no active repair actions to propose right now.

### 3. Why isn't FLUX ready?

Request:

```json
{
  "toolId": "setup.inspect_component",
  "arguments": { "componentId": "flux1_dev_local" },
  "requestId": "why-flux"
}
```

Redacted response evidence:

- `lifecycle.statusLabel: "Ready"`
- `verificationHealthy: true`
- `verificationSummary: "FLUX.1 Dev files are available and readable."`
- `monitorFindings: []`

Truthful answer:

The premise is false on this machine: FLUX.1 Dev is currently `Ready`. The correct catalog-truth behavior is for Co-Director to contradict the prompt and explain that there is no blocking setup issue in the live lifecycle state.

### 4. Recommend for anime

Request:

```json
{
  "toolId": "setup.search_components",
  "arguments": { "query": "anime", "group": "Image" },
  "requestId": "recommend-anime"
}
```

Redacted response evidence:

- returned 3 items
- `zimage_models`: reason `Best fit for anime or stylized illustration intent.`
- `qwen_image_2512_models`: reason `Best fit for anime or stylized illustration intent.`
- `sana_15_local`: reason `Best fit for anime or stylized illustration intent.`

Truthful answer:

The live catalog can recommend anime-capable image models directly from tagged setup metadata. On this machine the recommendation set is `Z-Image Turbo Models`, `Qwen-Image-2512 Models`, and `Sana 1.5`, all already `Ready`.

### 5. Compare Sana vs Qwen

Request:

```json
{
  "toolId": "setup.compare_components",
  "arguments": { "componentIds": "sana_15_local,qwen_image_2512_models" },
  "requestId": "sana_qwen"
}
```

Redacted response evidence:

- `sana_15_local`
  - `statusLabel: "Ready"`
  - `vramRecommendationGb: 12`
  - `typicalGenerationSpeed: "10-16s at 1024"`
  - `bestFor`: anime / illustration / stylized concept art
- `qwen_image_2512_models`
  - `statusLabel: "Ready"`
  - `vramRecommendationGb: 12`
  - `typicalGenerationSpeed: "12-18s at 1024"`
  - `bestFor`: general stills / poster design / style exploration

Truthful answer:

Sana is the more explicitly anime/stylized option, while Qwen-Image is the broader generalist with poster and style-exploration strengths. Both are `Ready`, and the comparison is coming from structured setup metadata instead of freeform model lore.

### 6. Photoreal character recommendation

Request:

```json
{
  "toolId": "setup.search_components",
  "arguments": { "query": "photoreal character", "group": "Image" },
  "requestId": "photoreal-character"
}
```

Redacted response evidence:

- returned 1 item
- `flux1_kontext_dev_local`
  - `statusLabel: "Ready"`
  - reason `Best fit for photoreal character work and reference-following edits.`

Truthful answer:

The live setup catalog recommends `FLUX.1 Kontext Dev` for photoreal character work on this machine.

### 7. Repair ComfyUI

Request:

```json
{
  "toolId": "setup.inspect_component",
  "arguments": { "componentId": "comfyui_hunyuan_nodes" },
  "requestId": "repair-comfyui"
}
```

Redacted response evidence:

- `lifecycle.statusLabel: "Ready"`
- `installJobId: "ij_comfyui_hunyuan_nodes_0074784d12"`
- `verificationSummary: "Hunyuan ComfyUI Extension is installed and required nodes are registered."`
- `monitorFindings: []`

Truthful answer:

The current live answer is that the Hunyuan ComfyUI extension does not need repair. The catalog-truth response is to report `Ready`, cite the verified node registration state, and avoid proposing a fake repair flow.

## Phase 6 verdict

**PASS**

The live Beta now exposes the setup tool registry needed for Co-Director setup truth, and the exact query set above can be answered from setup/lifecycle/catalog APIs alone. Where a prompt's premise is false (`FLUX` not ready, `IndexTTS2` repair, `ComfyUI` repair), the system now answers with the real current lifecycle state instead of forcing a bogus repair recommendation.
