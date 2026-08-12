# Krea 2 License Notes — Adept UI Integration

**Milestone:** Krea 2 Complete Image Pipeline + Multi-Shot Integration
**Document type:** Licensing documentation (no code changes)
**Author:** k2-license agent
**Date:** 2026-08-08
**Source of truth:** `docs/release-gate/krea2/KREA2_IMAGE_PIPELINE_AUDIT.md` §14 (Verified Krea 2 Facts) and §16 (Risk 9); all external URLs accessed 2026-08-08 per that audit.

---

## 1. Model Versions Covered

These notes cover the **open-weight Krea 2 checkpoints** distributed as safetensors on Hugging Face:

| Checkpoint | File | Hugging Face repo |
|---|---|---|
| **Krea 2 Turbo** | `turbo.safetensors` | https://huggingface.co/krea/Krea-2-Turbo |
| **Krea 2 RAW** | `raw.safetensors` | https://huggingface.co/krea/Krea-2-Raw |

- Model card version **v1.0**, **Release Date June 22, 2026**.
- Krea 2 is a 12B-parameter single-stream MMDiT (DiT) flow-matching text-to-image model from Krea.ai (Qwen Image VAE + Qwen3-VL text encoder).
- Both HF repos are **gated (`gated: auto`)** and carry a `LICENSE.pdf` in-repo; the official codebase is https://github.com/krea-ai/krea-2.
- References: https://huggingface.co/krea/Krea-2-Turbo/blob/main/README.md · https://huggingface.co/krea/Krea-2-Raw/blob/main/README.md · https://www.krea.ai/krea-2-open-source · https://www.krea.ai/blog/krea-2-technical-report

## 2. License Name

**Krea 2 Community License Agreement** (the "Agreement").

- Canonical URL: https://www.krea.ai/krea-2-licensing
- Hugging Face model-card license field: `license_name: krea-2-community-license`

## 3. Local / Open-Source Adept UI Use

Adept UI's intended use — **local, open-weight inference inside the creator's own Adept UI installation** (ComfyUI runtime, weights on the creator's machine) — is **permitted under the Krea 2 Community License**, subject to the conditions in §4–§6 of this document. Because the HF repos are gated, each installer must accept the license on Hugging Face before the weights can be downloaded (see §7).

## 4. Commercial / Cloud Deployment

Commercial use of the open-weight checkpoints (including any commercial or cloud deployment of Adept UI running Krea 2 weights) is permitted **only if total company-wide annual revenue is < $1,000,000 USD**, measured as trailing-twelve-month revenue from all sources, including affiliates.

- **At or above the $1,000,000 threshold**, a separate **Enterprise/Commercial License** is required:
  - Terms: https://www.krea.ai/krea-2-commercial-license
  - Contact: **opensource@krea.ai**
- Pricing tiers (including the "Maker" tier) are published at https://www.krea.ai/open-source-pricing.

Adept UI distributors and deployers must re-check this threshold on a rolling (trailing-twelve-month) basis; crossing it converts continued commercial use into an Enterprise-license obligation.

## 5. Attribution and Distribution Obligations

When redistributing the Krea 2 model or derivatives of it (fine-tunes, LoRA-merged weights, repacks), the distribution must:

1. **Name prefix** — the model name must begin with **"Krea"**.
2. **Agreement copy** — include a copy of the Krea 2 Community License Agreement.
3. **Notice file** — retain a Notice text file reading exactly:

   > Krea 2 is licensed under the Krea 2 Community License Agreement. For more information, visit https://krea.ai/krea-2-licensing.

These obligations apply to any redistribution path — including Adept UI-managed model folders that are copied, bundled, or synced to another machine — not just to public publishing.

## 6. Acceptable Use Policy

All use of Krea 2 is subject to the Krea 2 Acceptable Use Policy:

- Policy URL: https://www.krea.ai/krea-2-use-policy
- **Deployer obligation:** deployers must implement **content filtering / review processes**. For Adept UI this means generation surfaces that expose Krea 2 must route through Adept UI's content review/filtering path; the license does not permit offering unfiltered Krea 2 generation as a deployed service.

## 7. Adept UI Product Obligations

How the Adept UI product honors the license (integration points identified in the audit):

- **Provider license hint (creator-facing):** the Image Studio provider layer surfaces per-model license text via `licenseNote` in `studio-api/app/image_studio/providers.py` (`_HINTS`, e.g. lines 23–78; threaded into provider descriptors at `:137`, `:166`, `:241`). The Krea 2 entries (`krea2-turbo-local`, and RAW if exposed) must carry a `licenseNote` naming the **Krea 2 Community License** — per the audit's registration checklist (§1 item 4 and §14 "Product obligations").
- **Gated HF repo handling:** both HF repos are `gated: auto`, so **automated download must not be assumed** — an unattended downloader would bypass license acceptance (audit §16 Risk 9). Install follows the existing **manual / guided-install precedent** used for gated IC-LoRA ingredients: a Setup catalog component (`krea2_models`, installer `path_link`) plus documented manual placement of the checkpoints under the shared model root (e.g. `D:\01_Models\krea2`), with the UI directing the creator to accept the license on Hugging Face first.
- **Notice alongside redistributed weights:** wherever Adept UI stores or redistributes Krea 2 weights (the managed model folder, backup/export bundles, or any repack), the **Notice text file from §5** must live alongside the weights, together with a copy of the Agreement, and any redistributed derivative name must begin with "Krea".

## 8. Hosted API Alternative

Separate from the open-weight checkpoint license, Krea also offers Krea 2 as a **hosted API** — models `krea-2/medium` and `krea-2/large` — under Krea's standard API terms, **without** checkpoint license acceptance:

- API overview: https://www.krea.ai/docs/developers/krea-2/overview

This is **not** the path for the local open-weight milestone, but it is useful context: a future hosted-provider integration would be governed by Krea's API terms rather than by the Community License described here.

## 9. Summary Checklist — Adept UI Distribution

Before distributing or deploying Adept UI with Krea 2 weights, confirm:

- [ ] **Name prefix** — any redistributed model or derivative name begins with "Krea".
- [ ] **Agreement copy** — a copy of the Krea 2 Community License Agreement (https://www.krea.ai/krea-2-licensing) ships with the weights.
- [ ] **Notice file** — the Notice text file (*"Krea 2 is licensed under the Krea 2 Community License Agreement. For more information, visit https://krea.ai/krea-2-licensing."*) sits alongside the weights.
- [ ] **Revenue threshold review** — commercial/cloud deployment only while total company-wide trailing-twelve-month revenue is < $1,000,000 USD; otherwise an Enterprise/Commercial License (https://www.krea.ai/krea-2-commercial-license, opensource@krea.ai; tiers at https://www.krea.ai/open-source-pricing) is in place.
- [ ] **Content filtering policy** — deployment implements content filtering/review per the Acceptable Use Policy (https://www.krea.ai/krea-2-use-policy).
- [ ] **Gated install honored** — no automated download bypassing HF license acceptance; manual/guided install only.
- [ ] **UI disclosure** — `licenseNote` for Krea 2 provider entries names the Krea 2 Community License.

---

## Appendix — External Sources (all accessed 2026-08-08)

- https://huggingface.co/krea/Krea-2-Turbo and https://huggingface.co/krea/Krea-2-Turbo/blob/main/README.md
- https://huggingface.co/krea/Krea-2-Raw and https://huggingface.co/krea/Krea-2-Raw/blob/main/README.md
- https://github.com/krea-ai/krea-2
- https://www.krea.ai/krea-2-open-source
- https://www.krea.ai/blog/krea-2-technical-report
- https://www.krea.ai/krea-2-licensing
- https://www.krea.ai/krea-2-commercial-license
- https://www.krea.ai/open-source-pricing
- https://www.krea.ai/krea-2-use-policy
- https://www.krea.ai/docs/developers/krea-2/overview
