# Generation Prompt Knowledgebase

**Path:** `studio-api/knowledgebase/generation/`

## Architecture
1. **Shared** language (camera, motion, negatives, validation)
2. **Video models** — per-model manifests (`model.json`) + markdown guidance
3. **Workflows** — task recipes (dialogue, I2V, master sheet → video, …)
4. **Project overrides** — optional project-local notes (see `project_overrides/`)

## Compile pipeline
Intention → Structured Scene Spec → capability check → retrieve relevant markdown
(not the entire library) → model-specific compiler → Generation Package
(with citations + `knowledge_version`).

## Precedence
user instruction > shot overrides > master sheet > spatial > script/storyboard >
project rules > profiles > model KB > shared > defaults

## Scaffold a new model
```bash
python scripts/add_video_model_knowledge.py new_model_id "Display Name"
```
