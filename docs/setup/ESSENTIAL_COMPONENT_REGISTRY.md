# Essential Component Registry

**Governing document for Essential vs peripheral classification.**  
**Version:** 2026.08.1  
**Effective date:** 2026-08-26

This is the single policy document for Essential registration, versioning, and acceptance. Historical implementation reports must not override it.

Companion notice (the document creators accept): [`ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md`](./ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md).

## What Essential means

**Essential** describes architectural role in Adept UI — not whether weights are downloadable today.

A component is Essential when a product path depends on it (for example Standard Spatial Map depends on VGGT-1B-Commercial). Gated commercial-weight access does **not** make that component peripheral.

## Status model (two facts, two fields)

`license_status` and `owner_policy` are independent.

### license_status

| Value | Meaning |
|---|---|
| `PUBLISHED_LICENSE_CONFIRMED` | Publisher license text is confirmed and recorded |
| `LICENSE_PENDING_CLARIFICATION` | Terms not yet confirmed |
| `OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION` | Adept owner permits use while weight terms await official clarification |
| `TERMS_RESTRICTED` | Terms allow use only under stated limits |
| `LICENSE_BLOCKED` | Must not install or activate |
| `REQUIRES_EXTERNAL_ACCEPTANCE` | Upstream click-through or account acceptance is still required |
| `MODEL_ACCESS_GATED` | Official model host has not granted weight access |

### owner_policy

| Value | Meaning |
|---|---|
| `PERMITTED` | Adept owner allows this Essential in product architecture |
| `NOT_PERMITTED` | Adept owner forbids install/use |

Never collapse these into one string. Code license, weights license, license status, and owner policy stay separate.

## Versioning and acceptance

- The consolidated Essential notice is versioned (`2026.08.1` and later).
- Server state is authoritative (`setup_state.json`). Browser storage is not acceptance.
- `accepted_version == current_version` is required before Essential **install** or **activation**.
- A material notice change increments the version. Prior acceptance does not grandfather the new version.
- If the notice document cannot be loaded, the UI shows “document unavailable” and **must not auto-accept**.
- Decline or exit leaves Essentials ineligible.

Persisted acceptance fields (no secrets): version, document path/URL, effective date, `accepted_at`, Adept app version.

## Independent readiness (never collapse)

Each Essential reports these facts separately:

1. Agreement Accepted
2. Source Installed
3. Runtime Ready
4. Commercial Model Access
5. Model Ready
6. GPU Ready
7. Production Certified

Rules:

- Agreement is not runtime.
- Files on disk are not agreement.
- A git clone is not model access and is not Ready.
- VGGT may be Essential and simultaneously `MODEL_ACCESS_GATED` and not Ready.
- VGGT model unavailability must not block install or use of unrelated Essentials or MoGe-2 Express.

## Peripheral exclusion

These stay **peripheral / tool-specific**. Do not silently promote them to Essential because Spatial Map or Setup exists:

- ComfyUI
- Qwen image / Qwen Image Edit families
- FLUX local families
- V-JEPA / World Intelligence (advisory same-world check; not geometry)

Per-model path-pick `license_accepted` checkpoints remain tool-specific. They do not replace the consolidated Essential notice.

## Spatial Intelligence Essentials (this version)

| component_id | Display | Role | Product class | license_status | owner_policy |
|---|---|---|---|---|---|
| `moge2_geometry` | MoGe-2 Geometry Reconstruction | Single-image geometry for Spatial Map / Atlas | ESSENTIAL | `OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION` | `PERMITTED` |
| `vggt_1b_commercial` | VGGT-1B Commercial Geometry Reconstruction | Standard Spatial Map multi-view geometry | ESSENTIAL | `REQUIRES_EXTERNAL_ACCEPTANCE` and `MODEL_ACCESS_GATED` | `PERMITTED` |

MoGe-2 weights license is **unconfirmed**. Do not label MoGe weights MIT or Apache-2.0.

VGGT production weights are **only** `facebook/VGGT-1B-Commercial`. Never substitute `facebook/VGGT-1B`.

## Supersedes

These historical audits are not current classification:

- `docs/models/vggt/LICENSE_CLEARANCE.md` (2026-08-20 OMIT / not Essential)
- `docs/release-gate/codirector-intelligent-selection/ESSENTIALS-MANIFEST.md` (Revision A–D VGGT omit row)
