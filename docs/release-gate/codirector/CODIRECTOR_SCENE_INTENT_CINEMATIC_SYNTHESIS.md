# Co-Director — Scene Intent Decomposition + Cinematic Prompt Synthesis

**Governing document for this milestone.** Historical Co-Director orchestration reports remain historical (Law 30). This gate does not reopen Timeline bindings, live Production Readiness, or Spatial/3D shelf work.

| Field | Value |
| --- | --- |
| Project | Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| Request | Establishing shot: Earth Horizon + Venture + Cade's Starfighter |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Co-Director | `http://127.0.0.1:5173/project/fb24ff0f-8772-4d50-a602-ac69d14b5a6b?workspace=timeline` |

## Final verdict

**GO — SCENE INTENT CINEMATIC SYNTHESIS**

Co-Director no longer copies the creator's instruction into ACTION. The user request is Layer A. A verified `DirectorSceneIntent` is Layer B. The MiniMax H3 sectioned prompt is Layer C.

## What was wrong

`MiniMaxH3PromptCompiler` set ACTION to `spec.scene_intent or spec.source_user_prompt` after stripping a few config phrases. That made:

`I would like you to build a scene in Timeline where...`

become the on-screen ACTION. Generation could resolve `%VentureSpaceship` while the prompt still sounded like a chat request.

## Architecture

```text
Layer A  source_user_prompt          creator instruction (unchanged)
   ↓
parse_scene_intent                   generator / duration / aspect / sheet queries / scale
   ↓
resolve_project_references           FOUND / GLOBAL FOUND / MISSING / BROKEN
   ↓
Layer B  build_director_scene_intent environment, subjects, beats, scale, portal, motion
   ↓
Layer C  compile_generator_prompt    SHOT…NEGATIVE from SceneIntent, not user dump
   ↓
Timeline BatchBlock.text             Timed Prompt (H3 delivery authority)
```

No second reference resolver. Production still uses `resolve_project_references`. Prompt-facing tags use identity grammar via `prompt_facing_tag`:

| Stored / alias | Prompt tag |
| --- | --- |
| `venture-spaceship-4` | `%VentureSpaceship` |
| `cade-s-starfighter-2` | `%CadeSStarfighter` |
| `environment_reference` / `EarthHorizon2` | `#EarthHorizon` |

Collision suffixes and generic library tags are not production prompt language.

## Live Cade ACTION (measured)

> The Venture Spaceship cruises steadily in Earth orbit, dominating the frame against the planet's curved horizon. A luminous blue portal forms in open space above and slightly behind the Venture Spaceship. Cade's Starfighter bursts cleanly through the portal, immediately revealing its dramatically smaller scale beside the Venture Spaceship. Cade's Starfighter decelerates, banks with controlled precision, and settles into a covert position directly above the Venture Spaceship, matching its orbital movement while remaining unnoticed. Keep both vessels continuously readable, with the Venture Spaceship visually massive and Cade's Starfighter clearly only a tiny fraction of its size.

Absent from ACTION: I would like / build a scene / reference sheet / runtime / frame ratio / quality / MiniMax settings.

Present: orbit, portal, emerge, smaller scale, above Venture, unnoticed, both readable.

## Chat preparation (creator-visible)

Preparing scene… · Timeline selected · MiniMax H3 · 10 seconds · 21:9 · Earth Horizon — environment reference found · Venture Spaceship — Global Prop Reference Sheet found · Cade's Starfighter — Prop Reference Sheet found · Scale relationship identified · Portal entrance identified · Motion path identified · Cinematic action synthesized · Prompt compiled

## Tests

| Suite | Result |
| --- | --- |
| `test_scene_intent_cinematic_synthesis.py` + scene production + live readiness + preflight | **23 passed** |
| Playwright `codirector-scene-intent-synthesis.spec.ts` | **2 passed (7.6s)** |

Mandatory regressions:

- ACTION fails if it contains instruction-copy phrases
- `%VentureSpaceship` present; `%VentureSpaceship2/3/4` absent
- Reload/prepare does not require a Preflight seed for this prompt path

## Generation vs intent

This gate certifies **intent → verified breakdown → H3 prompt language**. If Venture is missing from a later rendered frame while bindings and this prompt are correct, that is a generator / reference-conditioning issue, not a Co-Director copy-into-ACTION issue.

## Peer review

Unanimous **AGREE**. Any DISAGREE would have been NO-GO.

| Reviewer | Verdict |
| --- | --- |
| [Kimi K3](9b4a7102-530d-4d8c-b2b5-ea206fb90cdc) | AGREE |
| [GLM 5.2](c40c3da6-5678-4db2-9d37-59d17b646aac) | AGREE |
| [GPT-5.6 Sol](9b370770-c166-4632-a3e6-9c3c154123e9) | AGREE |

## Runtime

| Check | Result |
| --- | --- |
| Studio API `http://127.0.0.1:8758/api/healthz` | **200** (PID **29064**, recycled only) |
| Vite `http://127.0.0.1:5173/` | **200** |
| **COMFY BEFORE** | PID **34484** / `:8188/system_stats` **200** |
| **COMFY AFTER** | PID **34484** / `:8188/system_stats` **200** |
| **COMFY RESTARTED?** | **NO** |

## Files

- `studio-api/app/codirector/production/scene_breakdown.py` (new)
- `studio-api/app/codirector/production/canonical_tags.py` (new)
- `studio-api/app/codirector/production/instruction_copy.py` (new)
- `studio-api/app/codirector/production/prompt_compiler.py`
- `studio-api/app/codirector/production/orchestrator.py`
- `studio-api/app/codirector/production/reference_resolver.py`
- `studio-api/app/codirector/production/contracts.py`
- `studio-api/app/codirector/production/intent_parser.py`
- `studio-api/app/codirector/capabilities/handlers/timeline_prepare_scene.py`
- `studio-web/src/components/CoDirector/SceneProductionCard.tsx`
- `studio-api/tests/test_scene_intent_cinematic_synthesis.py`
- `tests/e2e/codirector/codirector-scene-intent-synthesis.spec.ts`
