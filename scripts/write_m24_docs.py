from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "codirector" / "intelligence"
ROOT.mkdir(parents=True, exist_ok=True)

DOCS = {
    "overview.md": """# Co-Director Production Intelligence (M2.4)

Co-Director M2.4 adds a unified production intelligence layer behind the existing chat gateway. The user speaks to one partner; internally Co-Director classifies intent, compiles Production Bible context, selects a bounded specialist team, synthesizes findings, builds auditable production plans, and creates M2.2 proposals for mutating work.

## Guiding principle

Prompts provide production experience. Code provides discipline. The Production Bible provides truth. Co-Director provides one unified voice.

## Feature flag

Enable with `STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2=1` (default off). When disabled, chat follows the M2.2 path unchanged.

## Vertical slice

Create the next storyboard shot exercises Bible context retrieval, specialist selection, synthesis, plan creation, and `propose_storyboard_generation` — visual validation is marked pending for M2.5.
""",
    "prompt-architecture.md": """# Prompt Architecture

Versioned Markdown prompts live under `studio-api/app/codirector/prompts/`:

- `core/` — Co-Director identity, synthesis, response style, policies
- `specialists/` — 19 production roles (advise only)
- `playbooks/` — recurring task procedures
- `standards/` — continuity, references, communication rules

Every file includes validated YAML front matter. Load via `PromptLibrary`; invalid files fail safely with diagnostics.

Developer commands: `npm run codirector:validate-prompts`, `npm run codirector:list-specialists`.
""",
    "specialists.md": """# Specialists

Nineteen specialists advise only. `may_execute_tools` is always false in front matter and enforced in `SpecialistRegistry`.

Selection is bounded (max 8) via `SpecialistSelector`. Findings use `specialist-finding-v1` schema.

Vision reviewer defines M2.5 validation criteria only. Casting director must not identify real people in user images.
""",
    "playbooks.md": """# Playbooks

Playbooks describe procedural guidance for recurring tasks. They inform plan steps and specialist selection but never bypass tool permissions or approvals.
""",
    "context-compiler.md": """# Context Compiler

`ContextCompiler` uses M2.3 `ContextRetrievalService` to assemble budgeted, provenance-tagged packages filtered per specialist `allowed_context`.
""",
    "synthesis.md": """# Synthesis

`SynthesisEngine` resolves conflicts using priority: locked truth, approved truth, user instruction, safety, continuity, consensus, preference, convention.
""",
    "production-plans.md": """# Production Plans

Structured plans map steps only to registered M2.2 mutating tools. `PlanExecutorBridge` creates proposals, never direct execution.
""",
    "model-routing.md": """# Model Routing

Intent classification is heuristic-first. E2E runs deterministic specialist heuristics without provider calls.
""",
    "security.md": """# Security

Project content is untrusted. User messages use explicit delimiters. Specialists cannot execute tools.
""",
    "testing.md": """# Testing

Unit: `studio-api/tests/test_codirector_intelligence.py`. Evaluation: `npm run codirector:evaluate`. E2E: `tests/e2e/codirector/intelligence-storyboard.spec.ts`.
""",
}

for name, body in DOCS.items():
    (ROOT / name).write_text(body.strip() + "\n", encoding="utf-8")

report = """# Co-Director M2.4 — Production Intelligence Completion Report

**Date:** 2026-07-24  
**Branch:** `phase2/codirector-m2-4-intelligence`

## Summary

M2.4 delivers the versioned prompt library, intelligence orchestration, gateway integration, storyboard vertical slice, frontend Production Analysis UI, evaluation harness, and tests.

## Capability table

| Capability | Status | Notes |
|------------|--------|-------|
| Prompt library (55 files) | Complete | core, specialists, playbooks, standards + loader |
| Specialist registry (19) | Complete | advise only; max 8 per run |
| Intent + stage routing | Complete | heuristic-first |
| Context compiler | Complete | M2.3 APIs, budget, provenance |
| Synthesis + plans | Complete | conflict priorities, plan validator |
| M2.2 proposal bridge | Complete | propose_storyboard_generation |
| Gateway SSE progress | Complete | intelligence_* events |
| Frontend analysis panel | Complete | expertise modes |
| Evaluation A–G | Complete | npm run codirector:evaluate |
| E2E storyboard slice | Complete | real Bible + proposal path |
| Visual comparison (M2.5) | Deferred | criteria only in M2.4 |

## Known limitations

- Specialist findings use deterministic heuristics under E2E.
- Storyboard proposal prepares packages; render depends on ComfyUI.
- Visual validation pending until M2.5.
"""

Path(__file__).resolve().parents[1].joinpath("docs/codirector/m2.4-intelligence-completion-report.md").write_text(
    report.strip() + "\n", encoding="utf-8"
)

preflight = """# Co-Director M2.4 — Production Intelligence Preflight

**Date:** 2026-07-24  
**Branch:** `phase2/codirector-m2-4-intelligence`  
**Stack note:** Python FastAPI (`studio-api/app/codirector/`). Spec TypeScript paths map to Python.

## Classification legend

not_implemented · placeholder · mock_only · partially_implemented · usable · needs_extension · conflicting · deprecated

## Subsystem scorecard

| # | Subsystem | Class |
|---|-----------|-------|
| 1 | Co-Director backend package | usable · needs_extension |
| 2 | Co-Director frontend | usable · FE planner conflicting |
| 3 | Conversation / session models | usable · needs_extension |
| 4 | Model providers | usable / mock_only |
| 5 | System prompts / prompt files | partially_implemented |
| 6 | M2.2 tool registry | usable |
| 7 | M2.1 proposals / receipts | usable |
| 8 | M2.3 Bible context APIs | usable |
| 9 | Capability registry | usable (tools) |
| 10 | Scene / shot / generation | scenes usable |
| 11 | SSE | usable · needs_extension |
| 12 | Schema validation | usable |
| 13 | Feature flags | needs_extension |
| 14 | Tests | usable |
| 15 | Mock Co-Director | mock_only / E2E |
| 16 | Packaged desktop loading | partially_implemented |

## What to reuse

Gateway, providers, M2.2 tools, M2.3 Bible, proposals, capabilities, SSE, mock provider.

## What to extend

Versioned prompt library, intelligence orchestration, SSE progress, Production Analysis panel.

## What not to invent

Second approval bus, parallel tool registry, specialist tool execution, silent mutations, visual comparison (M2.5).

## Layout

```
studio-api/app/codirector/
  prompts/
  intelligence/
  evaluation/
```

**Feature flag:** `codirector_intelligence_v2` → `STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2` (default off).
"""

Path(__file__).resolve().parents[1].joinpath("docs/codirector/m2.4-intelligence-preflight.md").write_text(
    preflight.strip() + "\n", encoding="utf-8"
)
print(f"Wrote {len(DOCS)} intelligence docs + completion report")
