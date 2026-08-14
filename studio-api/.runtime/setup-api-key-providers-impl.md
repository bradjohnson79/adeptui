# Setup API Key Providers — Implementation

**Date:** 2026-08-14 02:59 PM PT  
**Scope:** Smallest READY-audit repair. No commit / push / deploy. :8758 not bounced. Character Creator not edited.

## Verdict

Setup now has a dedicated **API KEY PROVIDERS** accordion (Guided, Manual, and AI-Guided). Kie.ai, fal.ai, and WaveSpeed.ai are first-class key cards with masked input + Save + probe-gated connect. They do not live under Cloud Providers / Cloud Generators.

## Files changed

### Frontend
- `studio-web/src/components/hostedProviderSetupCopy.ts` **(new)** — category copy, three-provider list, status mapping
- `studio-web/src/components/hostedProviderSetupCopy.test.ts` **(new)** — category / cards / Save / states / no generic Requires Setup
- `studio-web/src/components/HostedProvidersSetupPanel.tsx` — accordion heading/badge, status labels, Save, last-probe outcome, real capabilities/balance only
- `studio-web/src/components/SetupWizard.tsx` — hide catalog category `API Providers` from Required/Optional (fal dedup)
- `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx` — render the dedicated accordion; strip kie/fal/wavespeed from Cloud Providers; hide API Providers lifecycle group

### Backend (status-only catalog alignment; no new secret store / probe / discovery)
- `studio-api/app/setup/catalog.py` — add `kie_key` / `wavespeed_key` credential rows under category **API Providers**
- `studio-api/app/setup/diagnostics.py` — same `secret_status` pattern as `fal_key` (`kie_api_key` / `wavespeed_api_key` / `fal_api_key`)
- `studio-api/app/setup/component_kinds.py` — treat `kie_key` / `wavespeed_key` as credential
- `studio-api/app/setup/lifecycle/service.py` — status-only metadata for the two new rows (group API Providers / Credentials)

### Dist
- `studio-web/dist/**` rebuilt (`tsc -b && vite build`). Live :8760 already serves the new bundle.

### Not touched
- `studio-web/src/components/character/**` (this task made no edits)
- `secrets_store.py`, hosted `service.py` connect/probe path, adapters, discovery
- Legacy `GET/PUT/DELETE /api/fal/key` (still shares `fal_api_key`)
- No commit / push / Vercel / :8758 bounce

## Exact visible copy

| Surface | Copy |
|---|---|
| Accordion / category heading | **API KEY PROVIDERS** |
| Card badge | **API Key Provider** |
| Cards | **Kie.ai**, **WaveSpeed.ai**, **fal.ai** |
| Primary action | **Save** (still `PUT /api/hosted-providers/{id}/key` → `connect_and_verify`) |
| Key input | `type="password"` (masked) |

### Provider status (separate from model readiness)

| Condition | Label |
|---|---|
| no key / missing | **NOT CONFIGURED** |
| probe verified | **CONNECTED** |
| probe invalid (401/403 / rejected) | **INVALID CREDENTIALS** |
| probe network / unverified | **UNREACHABLE** |
| rate limited (already mapped) | **RATE LIMITED** |

Not used on these three cards: “Needs API key”, “Requires Setup”, “Needs credentials”, “Configured”, “Ready”.

Save still does **not** mark CONNECTED without probe success. Invalid keys are not stored (`connect_and_verify` already refuses `valid is False`).

Capabilities shown only from the existing hosted card (`supportedModalities`, `certifiedModels`, `executableCapabilities`). Balance shown only when the live probe/card already returns it (Kie credit probe). No invented numbers.

## fal_key dedup

- Catalog still has `fal_key` (and now status-only `kie_key` / `wavespeed_key`) under category **API Providers**.
- Setup Wizard **hides the entire `API Providers` catalog category** from Required/Optional (same pattern as Avatar Runtimes). No second key input on catalog cards.
- AI-Guided hides that catalog group and filters `kie` / `fal` / `wavespeed` out of the Cloud Providers list.
- The only key write path for these three is the accordion → `PUT /api/hosted-providers/{id}/key`.
- Legacy `/api/fal/key` remains; same `fal_api_key` store. Users do not save fal twice from Setup.

## Test results

### Frontend (`node --experimental-strip-types --test hostedProviderSetupCopy.test.ts`)
**7 passed / 0 failed**
- category name API KEY PROVIDERS
- three cards Kie.ai / WaveSpeed.ai / fal.ai
- masked input + Save
- NOT CONFIGURED / CONNECTED / INVALID CREDENTIALS / UNREACHABLE (+ RATE LIMITED)
- configured-but-unverified is not CONNECTED
- no generic Requires Setup / Needs API key / Needs credentials
- classifyProbeError reject vs network vs 429

### Backend
**Passed (focused):**
- `test_setup_refactor.py::test_status_exposes_first_class_ai_guided_groups`
- `test_component_source_registry.py::test_fal_key_primary_action_is_configure_api_key`
- `test_component_source_registry.py::test_component_kind_mapping`
- `tests/test_m42_hosted_providers.py` (all)
- **12 passed**

**Broader run:** 49 passed, 2 failed (not introduced by this copy/status mapping):
- `test_fal_credentials.py::test_diagnostics_reports_the_verified_state` — `verify_component` 45s healthy cache still returns verified after a 401 revalidate. Pre-existing cache behavior; fal verifier logic unchanged (`secret_status("fal_api_key")`).
- `test_component_source_registry.py::test_manual_override_makes_pack_installable` — unrelated pack `source_available` (not credentials).

No secret leakage in tests. No new backend status strings on hosted `service.py`.

## :8760 bundle

- File: `studio-web/dist/assets/index-CVSaB5ci.js`
- Vite hash: **CVSaB5ci**
- SHA-256: `ce441ccaf612d7ca4542668a5820dcf6fb329d1e24c213c4af7b2d0f656ad6ae`
- Live `GET http://127.0.0.1:8760/` already references `/assets/index-CVSaB5ci.js`
- Bundle contains: API KEY PROVIDERS, API Key Provider, NOT CONFIGURED, CONNECTED, INVALID CREDENTIALS, UNREACHABLE
- Bundle does **not** contain: Hosted API Providers, Needs API key

## Leftover (not this task)

- **WaveSpeed still has no key** (audit live: missing / disconnected). E2E BLOCKED later until a real WaveSpeed Access Key is saved and probed. Do not invent a key or fire a paid generation.
- Settings → AI Providers panel still titled “Hosted AI Providers” (out of scope).
- Production Dock model-readiness label “Requires Setup” is unchanged (model inventory, not this Setup category).
