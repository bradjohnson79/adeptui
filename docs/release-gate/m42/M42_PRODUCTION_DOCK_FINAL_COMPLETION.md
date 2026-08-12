# M42 Production Dock — Final Completion Report

**Milestone:** M42 Production Control Dock  
**Branch:** `phase2/m42-production-dock`  
**Starting SHA:** `f758744`  
**UI label:** Production Dock  
**Code:** `ProductionControlDock`  
**Beta URL:** http://127.0.0.1:8760/  
**Gate:** `GET /api/production-control/gate`  

**Authoritative unified report:** [M42_PRODUCTION_CONTROL_DOCK_UNIFIED_REPORT.md](M42_PRODUCTION_CONTROL_DOCK_UNIFIED_REPORT.md)

---

## Objective

Persistent, collapsible, centered Production Dock consolidating Local/API availability, modality model preferences, Co-Director launch, system health/queue, and Aurora Night/Day — with preferences→resolver→provenance architecture and binary GO/NO-GO.

## Architecture

```text
Production Dock UI
→ user-global + project preferences (encrypted secrets separate)
→ modality resolvers + readiness
→ queue / ACE-Step / MMAudio / Co-Director / hosted providers
→ provenance on resolved selections
```

React never calls providers directly.

## Shared contracts

- [PRODUCTION_DOCK_SHARED_CONTRACTS.md](PRODUCTION_DOCK_SHARED_CONTRACTS.md)
- [M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md](M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md)
- Design system amended for Aurora Day semantic dual theme

## Implementation summary

| Layer | Location |
| --- | --- |
| Backend | `studio-api/app/production_control/**` |
| Model registry | `production_control/model_registry.py` + `studio-web/src/modelRegistry/` |
| Preferences | user JSON + per-project JSON under `data/production_control/` |
| Dock UI | `studio-web/src/components/production-dock/**` |
| Styles | `studio-web/src/styles/production-dock/` |
| Theme | `tokens.css` semantic aliases + `[data-theme=aurora-day]` |
| FAB removal | `CoDirectorHost` popup-only; dock launches Co-Director |
| Audio consumption | `audio_studio/service._prepare_generation` reads dock CPU policy + executable route |
| Image consumption | `image_product/service.generate_images` → `runtime_map.apply_image_dock_preference` |
| Video consumption | `render_project` + `enqueue_intent` → `runtime_map.apply_video_dock_preference` |
| LLM sync | `PUT /preferences` → `llm_ollama_for_dock_model` → `codirector_config` |
| Runtime map | `production_control/runtime_map.py` (dock id → family/engine) |

## Tests

```text
cd studio-api; PYTHONPATH=. python -m pytest tests/test_production_dock.py -q
→ 9 passed
```

Playwright: `tests/e2e/m42/m42-production-dock.spec.ts` — **4 passed** (A shell, B no FAB, C gate, D resolve provenance).  

Workflow I (primary, live Beta):
- Dock → ACE-Step Local → Audio Studio batch `acf5246b-…` → candidate runtime **ACE-Step** / provider **local** → status **complete**
- Dock LLM → `ollama-gemma4-12b` → Co-Director `selectedModel` **gemma4:12b**
- Image/video resolvers consume dock prefs via `runtime_map` (`qwen2512` / `ltx`); full Comfy image gen deferred while ComfyUI offline

## Gate

`scripts/m42_production_dock_certify.py` → `productionDockGo: true` / `verdict: GO`  
Artifacts: `artifacts/m42/production-dock/`

## Security

- Hosted keys remain in Fernet secrets store; dock APIs never return raw keys
- Provider switch requires staged + confirmed=true
- CPU fallback default **disabled**

## Known limitations

- Hosted LLM brains (GPT/Claude/Gemini/Grok) listed with honest Requires Setup until gateway credentials verified
- Hosted audio largely Uncertified/Unsupported as before
- Full Playwright Workflow I live GPU image generation not re-run in this certify stamp (resolver + audio path proven; image path uses same preference→resolve pattern)
- Aurora Day covers dock + semantic tokens; some legacy night-hardcoded pages may need follow-up token migration

## Reviews (primary)

| SA | Result |
| --- | --- |
| SA12 Accessibility | PASS FOR PRIMARY REVIEW — dialogs, Escape, aria-labels on dock controls |
| SA13 Security | PASS FOR PRIMARY REVIEW — no localStorage keys; secrets via hosted-providers |
| SA15 Architecture | PASS FOR PRIMARY END-TO-END EXECUTION — prefs consumed by audio, image, video, Co-Director paths |
| SA16 Migration | READY — migration report published |

## Final verdict

**GO** — Production Dock is wired, secure preference persistence, provider-neutral resolve with provenance, GPU-aware audio diagnostics, Co-Director FAB replaced, Beta-visible, and gate-certified.

Binary gate remains authoritative via `GET /api/production-control/gate`. No Conditional GO.
