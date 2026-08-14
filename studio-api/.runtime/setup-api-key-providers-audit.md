# Setup API Key Providers — Architecture Audit

**Verdict: READY TO IMPLEMENT**

Date: 2026-08-14 (PT). Read-only. No product files edited. No commit/push/deploy. No API bounce. Character Creator consume-only.

No architectural blockers. Secret store, non-billable probes, connect-then-discover, and app consumption already exist. The gap is Setup information architecture: Kie / fal / WaveSpeed are first-class on a parallel "Hosted API Providers" panel, while the Setup catalog only lists `fal_key` under category **"API Providers"** (Optional / credential). There is no exact string **"API KEY PROVIDERS"**. "Requires Setup" is a Production Dock *model readiness* label, not a Setup category.

---

## 1. Setup UI information architecture

### Surfaces

| Surface | File | How providers are grouped |
|---|---|---|
| Setup Wizard (Guided / Manual) | `studio-web/src/components/SetupWizard.tsx` | Catalog cards split **Required** vs **Optional** (not by `category`). Separate first-class section: `<HostedProvidersSetupPanel />`. |
| Hosted API Providers panel | `studio-web/src/components/HostedProvidersSetupPanel.tsx` | Own section heading **"Hosted API Providers"**. Card badge `"Hosted API Provider"`. Hardcoded trio: kie, wavespeed, fal. |
| Settings → AI Providers | `studio-web/src/components/HostedProvidersPanel.tsx` | **"Hosted AI Providers"**. Same trio + preferred-provider radios. |
| Production Dock modal | `studio-web/src/components/production-dock/ProviderSetupModal.tsx` | Connect/test via `/api/hosted-providers/*`. |
| AI-Guided Setup | `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx` | Catalog `surfaceGroups` + separate **"Cloud Providers"** from `api.setupLifecycleCloudProviders()`. Status copy: **"Configured" / "Needs credentials"**. |
| Setup catalog (backend) | `studio-api/app/setup/catalog.py` | Categories: Core, Video Models, Still Image Models, **API Providers**, Music Runtimes, Creative Packs, Reference & Identity Models, Character Voice Models, ComfyUI Extensions, Avatar Runtimes. |

### Catalog grouping (live GET `/api/setup/status`)

- 46 components. Categories as above. **API Providers = 1 card: `fal_key` only.**
- Kie and WaveSpeed are **not** catalog components.
- SetupWizard does **not** render a heading named "API Providers". `fal_key` lands in **Optional** with badge `"Optional"` (or `"Required"`).
- `component_kind === "credential"` → primary action label **"Configure API Key"** (`component_kinds.py`). Click goes to `api.setupRecommendedAction` → orchestrator checkpoint *"Configure {name} in the secure credentials screen."* — **no key input on the catalog card.**

### Status / copy strings (exact)

| Location | Unconfigured | Configured | Verified |
|---|---|---|---|
| HostedProvidersSetupPanel | `"Needs API key"` | `"Configured"` | `"Ready"` |
| HostedProvidersPanel | `"not configured"` | hint or `"configured"` | `connectionStatus` / `healthStatus` |
| AiGuidedSetupPanel | `"Needs credentials"` | `"Configured"` | `provider.statusLabel` |
| Catalog fal_key card | component `status` (missing / not_installed) | `"ready"` / lifecycle `"Ready"` | same |
| Production Dock models | capabilityLabel **`"Requires Setup"`** | `"Certified"` / `"Unsupported"` | — |
| productionAvailability.ts | `"Requires setup"` (local runtime / missing models / audio) | — | — |

**"Requires Setup" is not a Setup category.** It is assigned in `hosted_providers/discovery.py` `_classify()` when the account is not accessible (invalid/inactive key), then mapped to `capabilityLabel` for dock rows. Default fallback in `production_control/model_inventory.py` is also `"Requires Setup"`.

---

## 2. How Kie / fal / WaveSpeed currently appear

### Hosted panel (first-class, all three)

`HostedProvidersSetupPanel.tsx` `SETUP_PROVIDERS`:

- **Kie.ai** — "Recommended hosted provider for image and video generation (BYOK)." Badge: `Hosted API Provider`. Status: Needs API key / Configured / Ready.
- **WaveSpeed.ai** — "Hosted generation alternative with WaveSpeed Access Key (BYOK)." Same badge/status.
- **fal.ai** — "Hosted fal.ai key for certified cloud video and image routes (BYOK)." Same badge/status.

Registry (`hosted_providers/registry.py`): kie = primary / recommended / Certified; wavespeed = secondary; fal = third. Priority `kie → wavespeed → fal`.

### Catalog (fal only)

`catalog.py` line 355–359:

```
id=fal_key  name="fal.ai API Key"  category="API Providers"
installer=credentials  verifier=fal_key  required=False  kind=credential
```

Live: `status=ready`, `group="API Providers"`, `subgroup="Credentials"`, `surfaceGroups=["API Providers"]`, badges `["Credentials","Cloud"]`.

**Kie / WaveSpeed have no catalog rows.** They cannot appear in Required/Optional or AI-guided catalog groups unless added.

### Dual fal UI

fal appears twice: Hosted panel card **and** Optional catalog card `fal_key`. Catalog card cannot save a key; Hosted panel can.

---

## 3. Provider-secret architecture (reuse this)

**Single encrypted store.** Do not invent another.

| Piece | Path |
|---|---|
| Encrypt / decrypt / mask / verify | `studio-api/app/secrets_store.py` |
| Secret names | `kie_api_key`, `wavespeed_api_key`, `fal_api_key` (`registry.py`) |
| Env aliases (bridge only) | KIE_API_KEY/KIE_KEY, WAVESPEED_API_KEY/WAVESPEED_KEY, FAL_KEY/FAL_API_KEY |
| On-disk | `{data_dir}/secrets/{name}.enc` Fernet + `master.key`; verification `{name}.verified.json` bound to fingerprint (never stores the key) |
| Mask | `secret_hint`: first 4 + `••••` + last 4 |
| Hosted connect/test/clear | `hosted_providers/service.py` → `set_secret` / `get_secret` / `clear_secret` / `set_secret_verification` |
| Hosted HTTP | `hosted_providers/router.py` prefix `/hosted-providers` |
| Frontend client | `studio-web/src/api.ts` `hostedProvidersConnect/Test/Clear/...` — POSTs key to API only |
| fal env import | `fal_env_bridge.py` writes the **same** `fal_api_key` |

**Legacy fal-only HTTP (same secret, do not fork):**

- `GET/PUT/DELETE /api/fal/key`, `POST /api/fal/key/validate` in `studio-api/app/routers/api.py`
- Frontend: `api.falKeyStatus/Set/Validate/Clear`

Setup diagnostics for `fal_key` already call `secret_status("fal_api_key")` (`setup/diagnostics.py`).

**Keys are never in frontend source.** Inputs are `type="password"`. Catalog JSON returns `hint` only. Sanity-checked live catalog: no raw key fields.

**Duplicate stores?** No second credential DB. One `secrets_store`. Two HTTP surfaces for fal only. Production Dock prefs also store `defaultHostedProviderId` (preference, not the key).

---

## 4. Validation probes (non-billable) and Save behavior

**Save is NOT connected-on-save.** `connect_and_verify` probes first; invalid keys are refused and **not stored**.

```
PUT /api/hosted-providers/{id}/key  { api_key }
  → probe_* (live)
  → if valid is False: 400 INVALID_KEY, no set_secret
  → set_secret + set_secret_verification
  → save_preferences(preferred=pid) + patch defaultHostedProviderId
  → discover_provider(pid)  (best-effort)
```

`POST /api/hosted-providers/{id}/test` re-probes the stored key, then rediscovers.

| Provider | Probe | Billable? | Accept | Reject |
|---|---|---|---|---|
| Kie | `GET https://api.kie.ai/api/v1/chat/credit` Bearer | No generation job | 200 / <400 → verified (optional credit balance) | 401/403 invalid; 5xx unverified |
| WaveSpeed | `GET https://api.wavespeed.ai/api/v3/predictions/adept-probe-{uuid}/result` Bearer | No POST / no job | 404 or 200 → verified | 401/403 invalid (mentions top-up); 5xx unverified |
| fal | `validate_fal_key` → `GET https://queue.fal.run/{model}/requests/{uuid}/status` | No submit | <500 (typically 404) → verified | 401/403 invalid; 5xx unverified |

Files: `adapters/kie_adapter.py`, `adapters/wavespeed_adapter.py`, `adapters/fal_adapter.py` → `fal_client.py`.

Setup catalog "Configure API Key" for `fal_key` does **not** run this probe. It only opens a credentials checkpoint pointing at the secure screen (Hosted panel).

---

## 5. Hosted-provider discovery and app consumption

**Path (already consumed — do not invent a second inventory):**

1. `hosted_providers/discovery.py` `discover_provider` — probe + classify + persist via `model_store.py`
2. Known Adept-compatible rows in `_PROVIDER_CATALOG` (not a live vendor dump)
3. `GET /api/hosted-providers/discovered-models?modality=`
4. `production_control/model_inventory.py` `dock_api_models(modality)` → Production Dock API sections
5. Frontend:
   - Dock: `useProductionDock.ts` → `api.productionControlModels(modality)` (+ one-shot `hostedProvidersDiscover` if catalog empty)
   - Character: `CharacterGeneratorPanel.tsx` + `characterGeneratorPlan.ts` → `api.hostedProvidersDiscoveredModels("image")` **CONSUME ONLY**
   - Prop: `GeneratorSourceSelector.tsx` (used by Prop Creator Express) → same `hostedProvidersDiscoveredModels("image")`
   - Scene / Avatar / 1Frame / Timeline: no direct `hostedProvidersDiscoveredModels` call; they consume Dock `productionControlModels` API sections

Primary-provider policy: only the active preferred provider populates API sections. Discovery never auto-activates a model.

Live discovery (8758 + 8761 both up, same catalog): `activeProviderId=kie`, 5 models (Seedance, Kling, FLUX, Nano Banana, Hosted Audio). Summary: video 2, image 2, audio 1, compatible 4, requiresAdapter 1. Updated 2026-08-04 9:02 PM PT.

---

## 6. Existing category to reuse

| Candidate | Exists? | Use |
|---|---|---|
| **"API KEY PROVIDERS"** | **No** exact string | Desired product name — rename, do not invent a new stack |
| **"API Providers"** | Yes — catalog `category` / `group` / `surfaceGroups` | Reuse for catalog rows if kie/wavespeed are added as credentials |
| **"Hosted API Providers"** | Yes — Setup panel `h2` | Same section; rename heading/badge |
| **"Hosted AI Providers"** | Yes — Settings panel + API `catalog().title` | Keep Settings wording or align |
| **"Cloud Providers"** | Yes — AI-Guided | Separate lifecycle list; do not replace hosted panel |

**Reuse HostedProvidersSetupPanel as the API KEY PROVIDERS section.** Optionally add catalog credential rows so AI-guided / Optional lists see all three. Do not build a third card grid.

---

## 7. Live key status (masked)

`GET http://127.0.0.1:8758/api/hosted-providers` (200). `:8761` also 200, same payload. `GET /api/setup/catalog` 404 (status is `/api/setup/status`).

| Provider | Configured | State / health | Hint (API-masked) | Verified (PT) |
|---|---|---|---|---|
| **Kie** | **YES** | verified / healthy | `46dc••••c5f9` | 2026-08-01 9:41 PM PT |
| **fal** | **YES** | verified / healthy | `99cc••••16e6` | 2026-07-27 6:40 PM PT |
| **WaveSpeed** | **NO** | missing / disconnected | — | — |

Preferences: `preferredProvider=automatic`, `budgetPreference=low_cost` (updated 2026-08-04 9:10 PM PT). No raw secrets in responses.

---

## 8. Existing tests

| File | Covers |
|---|---|
| `studio-api/tests/test_m42_hosted_providers.py` | Order, canonical names, resolver, prefs, catalog. **Does not test connect/probe persist.** |
| `studio-api/tests/test_m42_dynamic_api_discovery.py` | Dock empty/active, classify, `probe_kie` monkeypatch, no hardcoded empty catalog |
| `studio-api/tests/test_fal_credentials.py` | fal probe reject/store/mask/revalidate via **`/api/fal/key`** (legacy surface, same secret) |
| `studio-api/tests/test_m30_fal_env_bridge.py` | Env → `fal_api_key` |
| `studio-api/tests/test_production_dock.py` | Dock + hosted |
| `studio-api/tests/test_setup_refactor.py` | Catalog kinds; `test_status_exposes_first_class_ai_guided_groups` |
| `tests/e2e/setup/hosted-api-provider-setup.spec.ts` | OpenAI-compat + budget prefs; asserts secret not echoed |
| `tests/e2e/m42/m42-hosted-providers.spec.ts` | M42 hosted UI |

**Gap (not a blocker):** no unit test that `connect_and_verify` for kie/wavespeed refuses invalid keys and persists valid ones. Add beside existing m42 tests; do not invent a new harness.

---

## Verdict details

### READY TO IMPLEMENT

No missing primitive. Repair is IA + catalog alignment on top of hosted-providers.

### Current classification

- Setup panel: **Hosted API Provider** / Needs API key · Configured · Ready
- Catalog: **fal only**, category **API Providers**, Optional credential
- Dock models: **Requires Setup** when key invalid/missing
- AI-Guided: **Cloud Providers** / Needs credentials

### Secret store reuse (exact files)

`studio-api/app/secrets_store.py`  
`studio-api/app/hosted_providers/registry.py` (secret_name)  
`studio-api/app/hosted_providers/service.py` (connect/test/clear)  
`studio-api/app/hosted_providers/router.py`  
`studio-api/app/hosted_providers/adapters/{kie,fal,wavespeed}_adapter.py`  
`studio-api/app/fal_client.py` + `fal_env_bridge.py` (fal only)  
`studio-web/src/api.ts` hostedProviders*  
`studio-web/src/components/HostedProvidersSetupPanel.tsx`

### Validation probes

All three exist and are non-billable. Save = probe then store. See §4.

### Discovery path apps already consume

`discovery.py` → `model_store` → `/api/hosted-providers/discovered-models` and `production_control/model_inventory.dock_api_models` → Dock + Character + Prop. Scene/Avatar/1Frame/Timeline via Dock.

### Character Creator

**CONSUME ONLY.** Already reads `hostedProvidersDiscoveredModels("image")` in `CharacterGeneratorPanel.tsx` / `characterGeneratorPlan.ts`. **Do not list or make CC source edits.**

---

## Smallest repair plan (do not invent)

1. **Rename, don't rebuild.** In `HostedProvidersSetupPanel.tsx`: heading `"Hosted API Providers"` → **"API KEY PROVIDERS"**; badge `"Hosted API Provider"` → **"API Key Provider"**. Keep the same cards, save/test/clear, discovery summary.
2. **Single save path.** Keep `PUT /api/hosted-providers/{id}/key` + `connect_and_verify`. Do not add a third secret store or a new probe protocol.
3. **Catalog (optional, small).** If Setup Required/Optional / AI-guided must list all three: add `kie_key` / `wavespeed_key` in `setup/catalog.py` as `installer="credentials"`, `category="API Providers"` (or `"API KEY PROVIDERS"` if you rename the category string), verifiers that call `secret_status("kie_api_key")` / `secret_status("wavespeed_api_key")` the same way `fal_key` uses `secret_status("fal_api_key")`. Extend `component_kinds.py` (`verifier == "fal_key"` → also kie/wavespeed). Wire `setup/diagnostics.py` + `setup/status.py` only. **Do not** put a key input on catalog cards — point Configure at the hosted panel (orchestrator already says "secure credentials screen").
4. **Dedup fal.** Either hide `fal_key` from Optional (filter like Avatar Runtimes) **or** keep it as a status-only card. Do not wire catalog Configure to `/api/fal/key` as a second write path. Legacy `/api/fal/key` may stay; both already share `fal_api_key`.
5. **Do not invent:** new adapter protocol, new discovery store, new frontend key persistence, new "Requires Setup" category, CC edits, new probe that POSTs a generation job.
6. **Tests to add (reuse):** connect_and_verify refuse/persist for kie + wavespeed (mirror `test_fal_credentials.py`); one Setup e2e that the API KEY PROVIDERS section renders three cards with Needs API key / Ready.

### What NOT to touch

- Character Creator source
- `secrets_store.py` crypto
- Probe URLs (already non-billable)
- Canonical model registry / resolver
- Production Dock inventory shape
