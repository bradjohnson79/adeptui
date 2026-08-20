# Co-Director World-State Intelligence — Implementation and Certification

**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)

## Architecture

```text
JEPA (V-JEPA 2)
→ observes / embeds / compares / predicts
        ↓
Co-Director World Intelligence Service (world_intelligence/)
→ interprets meaning, builds WorldStatePacket
        ↓
Co-Director
→ produces creator-facing advisories
        ↓
Adept UI
→ performs action (advise only — no auto-rejection)
```

## Package structure

```
studio-api/app/codirector/world_intelligence/
├── __init__.py          # Package marker
├── contracts.py         # WorldStatePacket and policy schemas
├── worker.py            # Isolated V-JEPA inference worker (CLI)
├── worker_client.py     # Spawns worker process, caches results
├── service.py           # Co-Director integration service
├── compare.py           # Similarity → recommendation logic
├── cache.py             # Embedding cache (content-addressed)
├── index.py             # World-state index (local JSON)
├── paths.py             # Model and cache paths
├── install.py           # HuggingFace model download
├── health.py            # Health probes
└── hardware_profile.py  # GPU/VRAM capability assessment
```

## WorldStatePacket

The primary contract between Revision C and Co-Director.

```python
class WorldStatePacket(BaseModel):
    schemaVersion: str = "world-state-v1"
    packetId: str
    availability: Literal["available", "unavailable", "low_confidence", "insufficient_reference"]
    source: WorldStateSource       # Asset/model provenance
    embedding: EmbeddingReference  # Cache reference (not raw tensor)
    sceneState: SceneStateSummary  # High-level scores
    comparisons: list[StateComparison]  # Per-reference comparisons
    recommendation: WorldStateRecommendation  # CD advisory
    intentionalChange: Optional[IntentionalChangeRecord]
```

The packet is:
- **Serializable** — full JSON round-trip
- **Auditable** — includes source, model, revision, preprocessing version
- **Lightweight** — no raw embeddings, just cache references
- **Versioned** — `schemaVersion` for contract evolution

## Embedding cache

Cache keys by: `assetId + contentHash + modelId + modelRevision + preprocessingVersion`

Stored as individual JSON files under `{data_dir}/cache/world_embeddings/`.

Invalidated when:
- Source image changes (content hash mismatch)
- Model changes (different modelId/revision)
- Preprocessing changes (different preprocessingVersion)

## World-state index

Simple local JSON file (`{data_dir}/cache/world_index.json`).

Contains:
- **Anchors** — approved world references (project/scoped)
- **Entries** — world-state entries with embeddings (for nearest-state lookup)

Uses linear scan with cosine similarity for nearest-state lookup. Suitable for the small-scale project scope. No external vector database.

## JEPA worker

Isolated subprocess (`worker.py`) that:
1. Loads V-JEPA 2 model from HuggingFace Transformers
2. Encodes images into embeddings
3. Computes pairwise similarity (cosine) and anomaly scores
4. Outputs structured JSON
5. Exits (frees GPU memory)

GPU lifecycle:
```text
image/video generation
      ↓
generator releases/offloads
      ↓
JEPA review (worker load → infer → exit)
      ↓
next heavy operation
```

## Co-Director advisory

The service produces creator-safe text such as:

| Condition | Advisory |
|---|---|
| Consistent | "World consistency looks strong." |
| Minor drift | "The scene remains in the established world with minor changes." |
| Major drift | "Possible world continuity issue: the environment structure differs substantially from the approved scene state." |
| Local edit preserved | "The edit preserved the environment well." |
| Intentional change | "World revision accepted." |

## Setup catalog

```python
ComponentDefinition(
    "vjepa2_world_intelligence",
    "Co-Director World Intelligence",
    "Advanced Co-Director world-state comparison. Helps preserve visual world consistency across scenes.",
    required=False,
    download_bytes=2800 * MB,
    installed_bytes=3000 * MB,
    dependencies=("python",),
    verifier="world_intelligence_files",
    installer="huggingface_snapshot",
    category="Co-Director World Intelligence",
)
```

## Implementation phases

### PHASE 0 — Architecture + license + model benchmark ✓
- [x] License research: MIT, confirmed for facebook/vjepa2-* models
- [x] Architecture audit: no duplication with Revision A/B
- [x] Model selection: ViT-L (best quality/resource trade-off)
- [x] Catalog entry added

### PHASE 1 — WorldStatePacket + cache/index ✓
- [x] WorldStatePacket schema
- [x] State comparison contracts
- [x] Embedding cache with content-addressable keys
- [x] World-state index with anchor management

### PHASE 2 — JEPA worker + Setup install ✓
- [x] Isolated worker process (CLI)
- [x] Worker client (spawn + collect results)
- [x] Model install via huggingface_hub
- [x] Health probes
- [x] GPU/VRAM capability checks
- [x] Setup catalog integration

### PHASE 3 — Scene Creator post-generation advisor [IN PROGRESS]
- [x] `evaluate_generated_image()` service method
- [ ] Scene Creator integration hook
- [ ] CD advisory propagation

### PHASE 4 — World reference retrieval / comparison [IN PROGRESS]
- [x] `compare_world_state()` service method
- [x] Nearest-state lookup in index
- [ ] Reference auto-selection logic

### PHASE 5 — Revision B integration [PENDING]
### PHASE 6 — Optional Revision A temporal augmentation [PENDING]
### PHASE 7 — UI/CD advisory polish [PENDING]
### PHASE 8 — Live cert + performance + verifiers [PENDING]

## License gate — PASSED

| Check | Status |
|---|---|
| Repository license | MIT (facebookresearch/vjepa2) |
| Checkpoint license | MIT (facebook/vjepa2-* on HF) |
| Commercial use | Permitted |
| Redistribution | Permitted |
| Derived works | Permitted |
| Transitive components | MIT/Apache-2.0 |
| Transformers support | Native (VJEPA2Model) |

**BLOCKING ISSUE — NOT CLEARED:** Only official `facebook/` namespace models are cleared. Unofficial forks with NC licenses must be excluded.

## Model benchmark matrix (PREDICTED — not yet measured)

| Model | Params | VRAM | Load | Image compare | Decision |
|---|---|---|---|---|---|
| ViT-L/16 256px | ~300M | ~2.5GB | ~5s | ~1s | ✅ PRIMARY |
| ViT-H/16 256px | ~600M | ~5GB | ~8s | ~2s | 🔲 FUTURE |
| ViT-G/14 256px | ~1B | ~8GB | ~12s | ~3s | ❌ TOO LARGE |

Actual measurements pending live worker certification.

## Tests [IN PROGRESS]

See `studio-api/tests/test_world_intelligence.py`.
