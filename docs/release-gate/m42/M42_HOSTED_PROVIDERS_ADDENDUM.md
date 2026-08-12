# M42 Addendum — Multi-Provider Hosted AI Strategy

**Verdict:** Hosted AI Providers tier operational (credential + resolution + UI).  
**Mock data:** false  
**Silent provider switch:** forbidden

## Canonical Hosted Provider Tier

| Priority | Provider | Role |
| -------- | -------- | ---- |
| 1 (⭐) | Kie.ai | Recommended / Primary |
| 2 | WaveSpeed.ai | Recommended alternative |
| 3 | fal.ai | Certified alternative |

## Resolution pipeline

```
Product surface
→ Canonical Intent
→ Capability Resolver
→ Certified Provider Resolver
→ Kie.ai OR WaveSpeed.ai OR fal.ai
→ Canonical Queue
→ Asset Library → Timeline → VersionGraph → Provenance
```

No product surface communicates with a provider directly.

## Automatic Recommendation

When Automatic is enabled:

1. Can Kie.ai execute? → use Kie.ai  
2. Else WaveSpeed.ai → recommend WaveSpeed.ai  
3. Else fal.ai → recommend fal.ai  
4. Else: *No certified hosted provider currently supports this workflow.*

Retries on a different provider are presented as **new execution options** (capability + cost disclosure). Jobs never silently switch mid-flight.

## Capability honesty

| Provider | Example Certified | Example Testing / Uncertified |
| -------- | ----------------- | ----------------------------- |
| fal.ai | text_to_video, image_to_video (existing Adept queue adapters) | text_to_image inventory |
| Kie.ai | Integration + live key probe | Generation workflows (Testing) |
| WaveSpeed.ai | Integration + live key probe (non-billing GET) | Generation workflows (Testing) |

Marketing pages are not treated as Adept certification.

## Surfaces updated

- `studio-api/app/hosted_providers/` — registry, capabilities, models, resolver, adapters, API
- Setup → **AI Providers** (`HostedProvidersPanel` in Project Settings)
- Co-Director: `get_cloud_render_status`, `hosted_providers.recommend`
- JobPanel / AssetTray optgroups → Hosted AI Providers labels
- Image provider registry includes kie / wavespeed / fal tiers
- fal `/api/fal/*` retained as legacy aliases for existing fal keys

## Canonical models

Users see **FLUX**, **Seedance**, **Kling** — not `FLUX (Kie)` / `FLUX (fal)`. Provider mappings remain implementation detail.

## Tests

- `studio-api/tests/test_m42_hosted_providers.py` (9 passed)
- `tests/e2e/m42/m42-hosted-providers.spec.ts`
