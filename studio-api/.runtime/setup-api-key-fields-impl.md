# Setup API key fields implementation

Date: 2026-08-14 (PT)

## Defect

Hosted beta (`https://adeptui.vercel.app`) showed status-only catalog cards in an **API Providers** accordion (fal.ai / Kie.ai / WaveSpeed.ai READY or REPAIR RECOMMENDED, no input). Cloud Providers still listed the same three as REQUIRES SETUP / Needs credentials / Configured.

## What the user sees now

- **API Providers** accordion is `HostedProvidersSetupPanel` (`data-testid=setup-api-key-providers`).
- Each of Kie.ai, WaveSpeed.ai, fal.ai has:
  - masked `type=password` input
  - placeholder `????last4` when a key exists (never the full key)
  - **Update** ? `PUT /api/hosted-providers/{id}/key` (`api.hostedProvidersConnect`) which probes then stores
  - success flash: `{title} API key updated` (e.g. `WaveSpeed.ai API key updated`)
  - invalid probe: status **INVALID CREDENTIALS**, copy does **not** say updated
  - **Remove** ? `DELETE /api/hosted-providers/{id}/key` (`api.hostedProvidersClear`)
  - success flash: `API key removed` ? **NOT CONFIGURED**
- Catalog credential cards `fal_key` / `kie_key` / `wavespeed_key` are hidden by id, category, group, and `surfaceGroups`. One write path only.

## Cloud Providers filter

Shared helper `filterCloudProviders` / `isApiKeyCloudProvider` in `hostedProviderSetupCopy.ts`.

Dropped ids (and aliases): `kie`, `kie.ai`, `kie_key`, `fal`, `fal.ai`, `fal_key`, `wavespeed`, `wavespeed.ai`, `wavespeed_key`.

Applied in:

- `AiGuidedSetupPanel` Cloud Providers grid
- `AiGuidedSetupPanel` grouped catalog + recommended list (`isApiKeyCatalogComponent`)
- `SetupWizard` Required/Optional catalog
- Backend `list_cloud_providers()` so the lifecycle API never returns the three

Other cloud providers (OpenAI, Replicate, Imagen, ?) stay. The Cloud Providers section is not hidden.

## Wiring

- Update ? `hostedProvidersConnect` ? `PUT /api/hosted-providers/{id}/key` ? `connect_and_verify` (probe, then `set_secret`). HTTP 400 on invalid. No key in URL.
- Remove ? `hostedProvidersClear` ? `DELETE /api/hosted-providers/{id}/key`.
- Discovered models still come from the same hosted-providers store after a successful probe.
- No second secret store. No Character Creator edits. Full keys are never logged or rendered.

## Confirmation copy

| Action | Copy |
| --- | --- |
| Update success | `{title} API key updated` |
| Update invalid | error message + **INVALID CREDENTIALS** (no "updated") |
| Remove success | `API key removed` |

## Tests

`node --experimental-strip-types --test studio-web/src/components/hostedProviderSetupCopy.test.ts`

- three cards have password input + Update + Remove
- Cloud Providers list excludes the three and aliases
- Update success copy
- invalid does not say updated
