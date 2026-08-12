# Co-Director Prompt Intelligence (Bilingual v1) — Certification Report

**Date:** 2026-08-01  
**Engine:** `prompt-intelligence@1`

## Verdict

```text
GO
```

End-to-end integration is live for Co-Director tools/API, Timeline Scene Prompt UI, Image Gen, Txt2Vid, and Audio Studio music path. Provider bilingual certification remains **experimental / not certified** until generation benchmarks are recorded.

## Architecture

- Modular Prompt Intelligence pipeline (production / cinematic / motion / audio / continuity / provider)
- Language Modules: `en` + `zh` active; `ja` / `ko` / `fr` future stubs
- Provider + model + version profiles under `config/codirector/prompt-profiles/`
- Prompt Quality Analyzer with recommendations (no silent rewrite)
- Four inspectable layers: Creator · Refined English · Chinese · Final Provider Prompt
- Manual override respected; Reset returns to generated mode
- Persistence on scene `director_json`, timeline `ExecutionSnapshot`, image compile metadata, audio brief

## Provider Matrix

| Provider | Domain | English Refinement | Chinese Layer | Status |
| --- | --- | --- | --- | --- |
| LTX (`ltx-video@1.0`) | Video | Supported | Off / Not Tested | Supported |
| WAN (`wan-2.2@1.1`) | Video | Supported | Recommend Subtle | Experimental |
| HunyuanVideo 1.5 (`@1.0`) | Video | Supported | Recommend Balanced | Experimental |
| HunyuanVideo 13B (`@1.2`) | Video | Supported | Recommend Balanced | Experimental |
| MiniMax H3 (`@1.0`) | Video | Reserved | Disabled | Disabled |
| FLUX / ComfyUI (`flux-image@1.0`) | Image | Supported | Off / Not Tested | Supported |
| Audio Studio (`@1.0`) | Audio | Supported | Off / Not Tested | Supported |
| Qwen3-TTS / Kokoro | Voice | Supported | Experimental | Experimental |

`bilingualCertified: false` for all profiles until evidence.

## Files Changed (primary)

**Created**

- `studio-api/app/codirector/prompt_intelligence/**`
- `studio-api/app/codirector/prompt_enhancement/__init__.py` (alias)
- `studio-api/app/codirector/tools/handlers/prompt_intelligence.py`
- `config/codirector/prompt-profiles/**`
- `studio-web/src/components/CoDirector/PromptIntelligencePanel.tsx`
- `studio-web/src/components/CoDirector/prompt-intelligence.css`
- `studio-api/tests/codirector/prompt_intelligence/test_prompt_intelligence.py`
- `tests/e2e/m42/m42-codirector-prompt-intelligence.spec.ts`
- `scripts/codirector/prompt_intelligence_benchmark.py`
- `docs/codirector/prompt-enhancement/**`

**Modified**

- `studio-api/app/routers/codirector.py`
- `studio-api/app/codirector/tools/definitions.py`
- `studio-api/app/codirector/tools/registry.py`
- `studio-api/app/director_timeline_w46/contracts.py`
- `studio-api/app/director_timeline_w46/orchestrator.py`
- `studio-api/app/image_product/compile.py`
- `studio-api/app/audio_studio/service.py`
- `studio-web/src/api.ts`
- `studio-web/src/timelineMaster/contracts.ts`
- `studio-web/src/components/CoDirector/CoDirectorOverflowMenu.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/ImageGenPanel.tsx`
- `studio-web/src/components/Txt2VidPanel.tsx`
- `studio-web/src/components/audio-studio/AudioStudioWorkspace.tsx`

## Test Results

| Command | Outcome |
| --- | --- |
| `pytest studio-api/tests/codirector/prompt_intelligence -q` | **10 passed** |
| `python scripts/codirector/prompt_intelligence_benchmark.py` | Wrote offline matrix JSON |
| `npm --prefix studio-web run build` | **OK** (`tsc -b && vite build`) |
| Playwright `m42-codirector-prompt-intelligence.spec.ts` @ `:8760` | **3 passed** |

Lint: pre-existing `Home.tsx` hooks error unrelated to this milestone; no new Prompt Intelligence lint blockers observed in build.

## Evidence

- Offline prompt matrices: `docs/codirector/prompt-enhancement/benchmarks/offline-prompt-matrix.json`
- Live API enhance/analyze + Timeline UI apply/override/persist covered by Playwright

## Known limitations

- Chinese layer not generation-certified for any provider yet
- Strong balance labeled advanced/experimental
- Future language modules registered but return empty enhancements
- Optional Ollama polish not required for v1 (deterministic pipeline)
