# MiniMax H3 Canada License Clearance

Reviewed on `2026-08-03`.

**Unified task report:** [`docs/release-gate/minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md`](../../release-gate/minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md)

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Pinned authoritative sources

- Hugging Face model repository: `MiniMaxAI/MiniMax-H3`
- Pinned repository revision: `5d9b308a59ab12e67147f191e184baf704185bd1`
- Pinned LICENSE URL: `https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/5d9b308a59ab12e67147f191e184baf704185bd1/LICENSE`
- LICENSE SHA-256: `59b99642b95ea21630e311198ddbfffbfe05aadba0c2f5d884cbdf4efcc90f44`
- Pinned model-card revision: `README.md` at `5d9b308a59ab12e67147f191e184baf704185bd1`
- Official MiniMax license Q&A: `docs/QA-about-License.md` at `5d9b308a59ab12e67147f191e184baf704185bd1`
- Official MiniMax docs reviewed:
  - `https://platform.minimax.io/docs/api-reference/video-generation-v2-create`
  - `https://platform.minimax.io/docs/api-reference/video-generation-v2-h3-context-ir`

## Source excerpts that control this gate

### LICENSE

- Section I.3: `"Applicable Territory" means worldwide, excluding the Excluded Territories.`
- Section I.5: `"Excluded Territories" means the European Union, the United Kingdom, the Republic of Korea and the United States of America.`
- Section II: `Solely within the Applicable Territory, we grant you ... a limited license to use, reproduce, distribute, create derivative works ... and modify the Materials ...`
- Section III: distribution to third parties is allowed only `solely within the Applicable Territory` and under the listed notice / agreement conditions.
- Section IV.1: prior written MiniMax authorization is required if commercial products or services exceed `20 million US dollars` in yearly revenue.
- Section IV.2: commercial products or services using H3 must prominently display `MiniMax H3` on the user interface.
- Section V.2: before providing access to H3 works or products/services/hosted services incorporating them, each recipient or user must be bound to enforceable terms at least as protective as Section V and Exhibit A.
- Section V.4: `You may not use, reproduce, modify, distribute, or display the MiniMax H3 Works or any of their Outputs or results outside the Applicable Territory.`
- Section V.5: if offering a product, service, or hosted service that permits H3 outputs, the operator must implement, maintain, test, and review safeguards, reporting, and mitigation controls.

### Official Q&A

- `Why is MiniMax-H3's open-weight license currently limited to the EU, UK, South Korea, and US?`
- `The current limitation means "not yet", not "not ever."`
- `API: Globally available with built-in safeguards and responsible-use controls.`
- `Open weights: Temporarily limited in certain regions until the regulatory and compliance framework becomes clearer.`
- `Organizations in these regions can apply for a formal license.`

### Official docs

- The global API docs list server `https://api.minimax.io`.
- The create endpoint currently supports model `MiniMax-H3`.
- The H3 Context-IR docs state that the hosted Context-IR system is not open sourced and may be used `in production workflows`.

## Phase 1 - Territory interpretation

### 1. Licensee location

- ANOINT Inc. is being treated here as a Canadian entity.
- This audit stores no street address or unnecessary personal-address data.
- On the pinned license text, Canada is **not** named in `Excluded Territories`.
- On that pinned text alone, a Canadian legal person is inside the default `Applicable Territory`.

### 2. Runtime location

- The relevant spike assumption for this audit is a Canadian RTX 5090 workstation.
- If weight download, storage, execution, caching, and output handling all remain in Canada, the pinned community license does **not** block that runtime on territory grounds.
- If any open-weight runtime moves onto physical infrastructure in the United States, European Union, United Kingdom, or Republic of Korea, the community-license territory grant no longer clearly covers that runtime.

### 3. Hosted deployment location

- Corporate nationality is not enough by itself.
- The license is territorial, so physical hosting location still matters.
- A Canadian company using Canadian infrastructure is materially different from a Canadian company running open weights on US-hosted GPUs.
- Official Q&A distinguishes:
  - API: globally available under MiniMax-operated safeguards
  - Open weights: territorially limited
- Therefore:
  - Canadian-hosted open-weight deployment can proceed only within the community-license conditions.
  - Excluded-territory infrastructure for open weights requires MiniMax authorization.
  - MiniMax-operated API use is a separate path and is not automatically blocked by the open-weight territory list.

### 4. User location

- The pinned community license says: `You may not use, reproduce, modify, distribute, or display the MiniMax H3 Works or any of their Outputs or results outside the Applicable Territory.`
- The official Q&A separately says the `API` is globally available.
- The pinned public sources reviewed here do **not** clearly state, in one sentence, whether a Canada-hosted open-weight service may lawfully serve end users located inside an Excluded Territory.
- Because the license text speaks about use / distribution / display of outputs outside the Applicable Territory, any open-weight product path aimed at excluded-territory users should be treated as a separate compliance question and not silently assumed lawful.

### 5. Distribution

- A Canadian developer may download the official weights in Canada under the pinned community license, because Canada is within the `Applicable Territory`.
- A Canadian workflow that tells users to obtain weights directly from the official Hugging Face repository is lower risk than redistributing copies.
- Redistributing weights or modified weight packages to third parties is allowed by Section III only `solely within the Applicable Territory` and only with the required agreement / notice conditions.
- Quantized or otherwise modified model packages are still likely `Model Derivatives` under the pinned definition, so the same territorial and notice obligations apply.
- Adept UI Cloud must not silently ship H3 weights into excluded-territory infrastructure.
- Workflow support, planning UX, or hosted API connectors can exist without shipping open weights, but those flows still need accurate disclosure of whether they use local open weights or MiniMax-hosted API.

**CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS**

## Phase 2 - Commercial obligations

### Attribution

Section IV.2 requires commercial products or services using H3 to prominently display `MiniMax H3` on the user interface.

Recommended Adept UI placement:

1. Engine picker label: `MiniMax H3`
2. Plan panel header: `MiniMax H3 Plan`
3. Model / provider badges in model library or deployment surfaces
4. Job receipts / provenance / export metadata where model identity is shown

Do not hide H3 behind a generic label such as `Advanced Video`.

### User terms

Section V.2 requires Adept to bind each recipient or user to terms at least as protective as the license restrictions in Section V and Exhibit A before giving access to H3 works or services incorporating them.

Minimum product implication:

- gated acceptance flow or product terms covering territorial restrictions, prohibited uses, output restrictions, and safeguard enforcement before creators can run H3-backed generations.

### Revenue authorization

If commercial products or services using H3 exceed `20 million USD` equivalent in yearly revenue, prior written MiniMax authorization is required.

### Output restrictions

Important pinned restrictions include:

- no use outside the `Applicable Territory`
- no using H3 works or outputs to improve another AI model except H3 or its derivatives
- no unlawful or rights-infringing use
- no bypassing safeguards
- no military use
- no undisclosed machine-generated public content
- no unauthorized professional activity

### Derivatives

- MiniMax permits derivative works and `Model Derivatives` within the Applicable Territory.
- Fine-tunes, quantizations, distillations, and synthetic-data transfer paths are likely covered by the Model Derivatives definition.
- Outputs themselves are not deemed `Model Derivatives`.

### Redistribution

Section III conditions apply to third-party distribution of H3 works:

1. provide the agreement
2. mark modified files
3. include the required `NOTICE` text for non-hosted distributions
4. stay within the Applicable Territory

### Hosted-service duties

Section V.5 requires the operator to implement and maintain safeguards, reporting, and mitigation measures for any product or hosted service that permits H3 output generation.

Product implication for Adept:

- no silent rollout
- no missing abuse-report path
- no disabled safety controls
- documented takedown / mitigation / repeat-violator handling

## Phase 3 - Territory enforcement design

### Design goals

- do not hard-block Canadian local development
- continue blocking open-weight runtime in excluded territories
- keep hosted MiniMax API as a separately disclosed path
- preserve LTX as explicit fallback only

### Practical gate design

1. Treat the current H3 `territory` field as the runtime / deployment territory for open-weight checks.
2. Default the development surface to a configurable territory, not a hardcoded `US`.
3. Fail closed when territory is blank or unknown.
4. Keep `api` deployment distinct from `local_weights`, because MiniMax's own Q&A says API availability is global and differently controlled.
5. Do not silently reinterpret a Canadian company on US-hosted GPU infrastructure as permitted.
6. For open-weight production serving outside Canada, require a follow-up compliance decision rather than assuming the user-location question is solved.

### Repo implementation performed in this task

- Removed H3 UI hardcoded `US` assumptions from:
  - `studio-web/src/components/FrameModes.tsx`
  - `studio-web/src/components/Txt2VidPanel.tsx`
  - `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx`
  - `studio-web/src/components/minimax-h3/MiniMaxH3PlanPanel.tsx`
  - `studio-web/src/api.ts`
- Added `studio-web/src/core/minimaxH3Territory.ts`
  - explicit prop wins
  - `VITE_MINIMAX_H3_TERRITORY` override supported
  - audited development default is `CA`
- Added a backend test proving `CA` is not license-blocked:
  - `studio-api/app/minimax_h3/test_minimax_h3_surfaces.py`

## Phase 4 - Runtime reopening

### Reopened

Yes, the legal gate for a **Canada-only local spike** is reopened by this audit.

### Current runtime evidence

- Spike worktree branch: `spike/minimax-h3-33b-rtx5090`
- GPU observed on `2026-08-03`: `NVIDIA GeForce RTX 5090`
- Visible VRAM: `32607 MiB`
- Pinned Hugging Face repo size: `499 GB`
- Pinned `FL2VA/` subtree size: `144 GB`
- Pinned `Ref2VA/` subtree size: `144 GB`
- Official SGLang examples in the pinned README use `--num-gpus 4`

### Honest status

- The isolated spike has now completed the audited `FL2VA/` minimum download in the dedicated
  Canada worktree.
- A local isolated CUDA env and a separate isolated ComfyUI server were both started without
  touching production Comfy Desktop.
- Released Diffusers on the spike machine still did not expose `MiniMaxH3Pipeline` or
  `MiniMaxH3ModularPipeline`.
- The secondary isolated ComfyUI path reached GPU execution, but the official H3 template expects
  single-file Comfy weights that are not present in the local Diffusers-sharded `FL2VA` payload, and
  the queued job failed at `MiniMaxH3ImageToVideo` with `Cannot copy out of meta tensor; no data!`.
- No genuine local H3 video-and-audio generation proof has been produced.
- Law 26 therefore remains unsatisfied for local proof.
- The runtime question is no longer blocked **by the Canadian territory reading**, but it is still unproven on single-machine feasibility, download cost, dependency setup, and real GPU execution evidence.

## Operational conclusion

- Canadian local H3 development is reopened under the pinned public license.
- Excluded-territory open-weight deployment remains blocked or authorization-gated.
- MiniMax-hosted API remains a distinct path with official global availability claims.
- Adept should not claim local Canadian media GO until a real GPU run is completed with no silent CPU fallback.

## Clarifications still worth obtaining from MiniMax

1. Whether a Canada-hosted open-weight deployment may lawfully serve users physically located in excluded territories
2. Whether output display to excluded-territory viewers is treated as prohibited `display` under Section V.4 for open-weight deployments
3. Whether Canadian redistribution of quantized H3 derivatives to other applicable-territory users needs any extra approval beyond Section III
