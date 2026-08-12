# M42 Production Control Dock — Unified Report

**Product UI label:** Production Dock  
**Code:** `ProductionControlDock`  
**Milestone:** M42 Production Control Dock  
**Branch:** `phase2/m42-production-dock`  
**Baseline SHA:** `f758744`  
**Beta:** http://127.0.0.1:8760/  
**API health:** http://127.0.0.1:8758/api/health  
**Gate:** `GET /api/production-control/gate`  
**Artifacts:** `artifacts/m42/production-dock/`  

---

## 1. Verdict

| Field | Value |
| --- | --- |
| **Binary verdict** | **GO** |
| `productionDockGo` | `true` |
| Conditional GO | Not used |
| Gate authority | Live `GET /api/production-control/gate` only — never hardcoded |

**Certification standard (met):**

```text
Change setting in Production Dock
→ persist preference securely
→ resolver reads preference
→ readiness check passes (or honest block)
→ real job executes with selected model/runtime
→ provenance records selection + source
→ reload preserves state
```

A decorative Dock that stores prefs but ignores them in production paths is automatic **NO-GO**. That failure mode was avoided: audio, image, video, and LLM paths consume dock selections.

---

## 2. Objective

Ship a persistent, collapsible, centered Production Dock that consolidates:

- Local / API / Hybrid runtime availability
- LLM / Video / Image / Audio model preferences
- Co-Director launch (replacing the floating FAB)
- System health + job queue indicator
- Aurora Night / Day theme
- User-global defaults vs project overrides
- Preference provenance on resolved selections
- Early degraded-mode blocks when no executable route exists

React never calls Kie / WaveSpeed / fal / LLM / video providers directly. No silent Local/API, provider, model, or CPU switches (Laws 8, 26).

---

## 3. Architecture

```text
Production Dock UI
  → user-global preferences + project overrides
  → encrypted secrets (hosted providers; never raw keys in UI)
  → SA16 migration (first launch, idempotent)
  → modality resolvers + readiness probes
  → PreferenceProvenance
  → job queue / studios / Co-Director
  → gate flags (all required for GO)
```

**Precedence (always):**

```text
Project override → user default → system default
```

Active source is visible in the Dock and in job provenance.

### Supporting docs

| Doc | Role |
| --- | --- |
| [PRODUCTION_DOCK_SHARED_CONTRACTS.md](PRODUCTION_DOCK_SHARED_CONTRACTS.md) | Frozen contracts |
| [M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md](M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md) | SA1–SA16 ownership |
| [M42_PRODUCTION_DOCK_PREFERENCE_MIGRATION.md](M42_PRODUCTION_DOCK_PREFERENCE_MIGRATION.md) | Old → new field mapping |
| [ADEPT_UI_DESIGN_SYSTEM.md](../../design/ADEPT_UI_DESIGN_SYSTEM.md) | Aurora Day semantic tokens (not inversion) |
| [M42_PRODUCTION_DOCK_FINAL_COMPLETION.md](M42_PRODUCTION_DOCK_FINAL_COMPLETION.md) | Short completion summary |

---

## 4. Implementation map

| Layer | Location |
| --- | --- |
| Backend package | `studio-api/app/production_control/**` |
| Contracts / store / resolve / gate / status / migration | same package |
| Runtime id map | `production_control/runtime_map.py` |
| Model registry | `production_control/model_registry.py` + `studio-web/src/modelRegistry/` |
| Pref wrappers | `studio-api/app/model_preferences/{image,video}.py` |
| Dock UI | `studio-web/src/components/production-dock/**` |
| Dock styles | `studio-web/src/styles/production-dock/` |
| Theme | `studio-web/src/theme/tokens.css`, `applyTheme.ts` |
| FAB removal | `CoDirectorHost.tsx` popup-only; dock launches Co-Director |
| Cert script | `scripts/m42_production_dock_certify.py` |
| Unit tests | `studio-api/tests/test_production_dock.py` |
| Playwright | `tests/e2e/m42/m42-production-dock.spec.ts` |

### Resolver consumption (non-negotiable)

| Modality | Dock preference | Runtime mapping | Consumer |
| --- | --- | --- | --- |
| Audio | `audio.activeModelId` / project override | ACE-Step / MMAudio readiness + Law 26 CPU policy | `audio_studio/service._prepare_generation` |
| Image | `image.activeModelId` / project override | e.g. `qwen-image-2512-local` → `qwen2512` | `image_product/service.generate_images` |
| Video | `video.activeModelId` / project override | e.g. `ltx-local` → `ltx` | `render_project`, `enqueue_intent` |
| LLM | `llm.activeModelId` | e.g. `ollama-gemma4-12b` → `gemma4:12b` | Co-Director `config_store` via `PUT /preferences` |

---

## 5. Preference layers

### User-global

- Theme (`aurora-night` \| `aurora-day` \| `system`)
- Dock collapsed / auto-collapse
- Default hosted provider
- Default LLM / modality routing
- General quality preferences
- CPU fallback policy (default **disabled**)

### Project

- Active video / image / audio runtime for the project
- Project-specific resolution
- Project-specific Co-Director model
- Generator locks used by Timeline scenes

Changing a project model must not alter another project's production (precedence + per-project JSON).

### CPU fallback policy

```text
○ Disabled   (default)
○ Ask every time
○ Allowed for lightweight jobs only
```

No silent CPU for production generation.

---

## 6. API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/production-control/gate` | Binary GO/NO-GO + flags |
| GET/PUT | `/api/production-control/preferences` | User-global prefs |
| GET/PUT | `/api/production-control/projects/{id}/preferences` | Project overrides |
| GET | `/api/production-control/resolve?projectId=&modality=` | Resolved selection + provenance |
| GET | `/api/production-control/models?modality=` | Capability-filtered registry |
| GET | `/api/production-control/status` | Aggregate health / runtime / GPU |
| GET | `/api/production-control/queue` | Queue snapshot |
| POST | `/api/production-control/migrate` | Idempotent preference migration |
| POST | `/api/production-control/providers/switch` | Stage provider switch |
| POST | `/api/production-control/providers/switch/confirm` | Confirm (`confirmed: true`) |

---

## 7. Gate flags (all required)

Live evaluation at certification time: **all `true`**, verdict **GO**.

| Flag | Result |
| --- | --- |
| `productionDockGo` | true |
| `contractsPassed` | true |
| `dockShellPassed` | true |
| `providerSecretsPassed` | true |
| `modelRegistryPassed` | true |
| `runtimeSourcePassed` | true |
| `llmRoutingPassed` | true |
| `videoPreferencesPassed` | true |
| `imagePreferencesPassed` | true |
| `audioDiagnosticsPassed` | true |
| `codirectorLaunchPassed` | true |
| `systemHealthPassed` | true |
| `themePassed` | true |
| `persistencePassed` | true |
| `securityPassed` | true |
| `accessibilityPassed` | true |
| `playwrightPassed` | true |
| `betaUpdated` | true |
| `noSilentFallbackPassed` | true |
| `noSecretLeakPassed` | true |
| `primaryEndToEndPassed` | true |
| `preferenceMigrationPassed` | true |
| `resolverConsumptionPassed` | true |
| `preferenceProvenancePassed` | true |
| `degradedModePassed` | true |
| `queueIndicatorPassed` | true |

Evidence directory: `artifacts/m42/production-dock/` (stamped by `scripts/m42_production_dock_certify.py` + primary Workflow I).

---

## 8. Wave delivery summary

| Wave | Scope | Status |
| --- | --- | --- |
| Wave 0 | Frozen contracts, Aurora Day design-system amendment, SA1–SA16 ownership | Complete |
| Wave 1 | Dock shell, secrets/providers, model registry, dual theme, migration scaffold | Complete |
| Wave 2 | Runtime source, modality menus, Co-Director launch, health/queue, CPU policy, degraded mode | Complete |
| Wave 2 wire | Resolvers consume prefs; FAB removed; provenance | Complete |
| Wave 3 | Gate, Playwright, Beta, migration + unified reports, binary GO | Complete |

---

## 9. SA1–SA16 ownership & review

Ownership matrix: [M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md](M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md).  
Subagents report only `READY FOR PRIMARY REVIEW`. Final GO is primary-only.

| SA | Role | Primary review result |
| --- | --- | --- |
| SA1 | Dock shell | Integrated — centered floating footer, collapse persist |
| SA2 | Runtime source + provider UX | Integrated — Local/API toggles, setup + switch confirm |
| SA3 | Secrets / hosted providers | PASS — no raw keys returned |
| SA4 | Model registry + filtering | Integrated — action-aware `/models` |
| SA5 | LLM routing | Integrated — active/available + provenance |
| SA6 | Video prefs | Integrated — project/user + resolver consume |
| SA7 | Image prefs | Integrated — project/user + resolver consume |
| SA8 | Audio + CPU policy | Integrated — ACE-Step/MMAudio + Law 26 |
| SA9 | Co-Director dock launch | Integrated — FAB removed |
| SA10 | Aurora Night/Day | Integrated — semantic tokens |
| SA11 | Health + queue | Integrated — status + queue drawer |
| SA12 | Accessibility | PASS FOR PRIMARY REVIEW |
| SA13 | Security | PASS FOR PRIMARY REVIEW |
| SA14 | Playwright / tests | PASS — unit + e2e green |
| SA15 | Architecture / evidence | PASS FOR PRIMARY END-TO-END |
| SA16 | Migration + resolver verify | READY — migration report published |

---

## 10. Tests & Workflow I

### Unit

```text
cd studio-api
PYTHONPATH=. python -m pytest tests/test_production_dock.py -q
→ 9 passed
```

Coverage includes contracts, precedence, migration idempotency, provenance, runtime map image/video consumption, gate isolation, provider-switch confirmation, CPU default.

### Playwright

```text
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
PLAYWRIGHT_API_URL=http://127.0.0.1:8758
npx playwright test tests/e2e/m42/m42-production-dock.spec.ts --project=chromium
→ 4 passed
```

| Workflow | Result |
| --- | --- |
| A — dock shell / modality menus | Pass |
| B — no floating Co-Director FAB | Pass (`fab` count = 0) |
| C — gate flags | Pass |
| D — resolve provenance (audio) | Pass |

### Workflow I (primary, live Beta — mandatory)

| Step | Evidence |
| --- | --- |
| Dock → Local audio → ACE-Step | Resolve: `ace-step-local`, `executable: true` |
| Generate real Audio Studio batch | Batch `acf5246b-67e8-497a-a2eb-c86bb7518732` |
| Provenance | Candidate `provider: local`, `runtime: ACE-Step`, `status: ready`, asset `8c5f6386-41dc-4112-af22-f19ab3784a84`, batch `status: complete` |
| Dock → Co-Director brain change | `ollama-gemma4-12b` → Co-Director `selectedModel: gemma4:12b` |
| Image/video resolver consume | `qwen-image-2512-local` → family `qwen2512`; `ltx-local` → engine `ltx` |
| Reload / persistence | User + project prefs under `data/production_control/`; migration stamp idempotent |

Full hosted-image generation against a live Kie/fal route was not re-run while ComfyUI was offline for local image; image path uses the same preference → resolve → family injection gate as production enqueue.

Stamp: `artifacts/m42/production-dock/primary_e2e_results.json`

---

## 11. Preference migration

See [M42_PRODUCTION_DOCK_PREFERENCE_MIGRATION.md](M42_PRODUCTION_DOCK_PREFERENCE_MIGRATION.md).

| Old setting | New field | Result |
| --- | --- | --- |
| Co-Director `selectedModel` / `primaryModel` | `user.llm.activeModelId` | Migrated |
| Hosted `preferredProvider` | `user.defaultHostedProviderId` | Migrated |
| Legacy theme | `user.theme` | Migrated or `aurora-night` |
| Audio preferred provider | user/project `audio` routing | Adopted; not wiped |
| Project video/image defaults | `activeVideoModelId` / `activeImageModelId` | Project overrides available |

Second migrate returns `alreadyMigrated: true` — first launch does not reset working settings.

---

## 12. Security & hard NO-GO checklist

| Hard NO-GO | Status |
| --- | --- |
| Duplicate floating Co-Director pill | Cleared — FAB removed; dock launches Co-Director |
| API keys in localStorage / browser / logs | Cleared — Fernet secrets; APIs never return raw keys |
| React → provider calls | Cleared — API-only from dock |
| Silent Local/API, provider, model, or CPU switch | Cleared — confirm + CPU default disabled |
| Prefs stored but not consumed | Cleared — audio/image/video/LLM consumers |
| Ambiguous active model / missing provenance | Cleared — resolve + provenance |
| Cross-project preference leakage | Cleared — per-project JSON + precedence |
| Aurora Day as inversion | Cleared — semantic Day palette |
| Dock covering Timeline controls | Cleared — centered floating footer, collision-aware CSS |
| Fabricated GPU / fake Ready | Cleared — probes from real diagnostics |
| Gate GO with any flag false | Cleared — all flags true |
| Subagent declares final GO | Cleared — primary only |
| Beta not updated | Cleared — http://127.0.0.1:8760/ |
| Missing unified / migration report | Cleared — this doc + migration report |
| Workflow I not proven | Cleared — live ACE-Step batch + LLM sync |

---

## 13. Known limitations

- Hosted LLM brains (GPT/Claude/Gemini/Grok) remain **Requires Setup** until gateway credentials are verified; no silent local substitute.
- Hosted audio remains largely Uncertified / Unsupported as before.
- Full live Comfy image generation was deferred while ComfyUI was offline; resolver consumption for image/video is proven.
- Some legacy pages may still hardcode Night colors; dock + semantic tokens are Day-ready.

---

## 14. How to re-verify

```text
# Unit
cd studio-api
PYTHONPATH=. python -m pytest tests/test_production_dock.py -q

# Stamp artifacts + gate
python scripts/m42_production_dock_certify.py

# Beta
.\Restart-AdeptUI-Beta.ps1
# open http://127.0.0.1:8760/

# Gate
GET http://127.0.0.1:8758/api/production-control/gate

# Playwright
set PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
set PLAYWRIGHT_API_URL=http://127.0.0.1:8758
npx playwright test tests/e2e/m42/m42-production-dock.spec.ts --project=chromium
```

---

## 15. Final statement

**GO** — Production Control Dock is certified for Beta use: preferences persist securely, resolvers consume selections with provenance, degraded routes block early, Co-Director FAB is replaced by the Dock, Workflow I audio + LLM paths are proven live, and `GET /api/production-control/gate` reports `productionDockGo: true` / `verdict: GO`.

No Conditional GO.
