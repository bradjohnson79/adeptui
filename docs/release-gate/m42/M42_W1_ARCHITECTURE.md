# M42 W1-5 — Image Runtime Architecture

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Phase** | M42 Phase 4.2 Wave 1 |

---

## 1. Official execution path

```text
User
  → Co-Director / Director / Generate Studio
  → CreativeContext          (product / planning only)
  → ImageIntent              (product → runtime language)
  → Workflow Resolver        (modality=image domain)
  → Canonical Image Workflow Contract
  → QueueWorker
  → Image Runtime
  → Output Validation
  → Asset Registration
  → Project Library
```

No alternate execution path is permitted once Wave 2 enforces this chain.

---

## 2. CreativeContext vs Image Runtime (hard boundary)

| Layer | May know | Must not know |
|---|---|---|
| CreativeContext | story, characters, cinematography, Production Bible, continuity | Comfy graphs, builders |
| ImageIntent | operation, prompt, referenceIds, prefs, digests | Bible blobs |
| Image Runtime | contract, inputs, seed, settings, reference asset IDs | story, specialists, Bible services |

---

## 3. Unified Workflow Resolver (locked)

```text
Workflow Resolver
├── Video Registry     config/video-workflows/
├── Image Registry     config/image-workflows/
├── Audio Registry     (future Phase 4.3)
└── 3D Registry        (future SceneCraft)
```

Facade: `studio-api/app/workflow_runtime/resolve_workflow(..., modality=...)`.  
Video resolve remains stable. Image domain uses Draft registry in Wave 1.

HTTP:

- `POST /api/video-runtime/resolve` with `modality: "image"`
- `POST /api/image-runtime/resolve`
- `GET /api/image-runtime/registry|gate|identities|reference-types`

---

## 4. Workflow categories

Generation · Editing · Reference · Restoration · Utility · Training · Identity · Compositing · Publishing

---

## 5. Asset lifecycle

Draft → Queued → Generating → Validating → Registered → Approved → Versioned → Archived → Deleted

---

## 6. Forbidden in product code

- Direct Comfy builders / `queue_prompt`
- Provider-specific logic in UI
- Simulated image completion
- Silent provider substitution
- Asset registration bypass of Output Gate (Wave 2 enforcement)

---

## 7. Wave 2 Ownership

Wave 2 is solely responsible for:

- Certified Image Workflow Library (Draft → Certified)
- Live Comfy certification
- Fingerprints / graph drift
- Image Output Gate enforcement before job `done`
- QueueWorker execute-only path for image jobs
- Unified Workflow Resolver enforcement for image intents
- Image Consumer Contract (no builders / `queue_prompt` from product)
- Live smoke
- Deep cancellation for image jobs
- Output validation + asset certification
- Writing ImageProvenance on every successful generation
- Binding ReferenceAsset IDs into certified workflows (IC-LoRA / multi-ref)

Wave 5 owns Identity Preservation Registry enforcement (`config/image-identities/`).

Wave 1 must not claim any of the above complete.
