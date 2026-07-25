# Prompt Architecture

Versioned Markdown prompts live under `studio-api/app/codirector/prompts/`:

- `core/` — Co-Director identity, synthesis, response style, policies
- `specialists/` — 19 production roles (advise only)
- `playbooks/` — recurring task procedures
- `standards/` — continuity, references, communication rules

Every file includes validated YAML front matter. Load via `PromptLibrary`; invalid files fail safely with diagnostics.

Developer commands: `npm run codirector:validate-prompts`, `npm run codirector:list-specialists`.
