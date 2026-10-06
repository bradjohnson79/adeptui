# 00 — Workspace Freeze

**Captured:** 2026-08-29 (implementation start)  
**Mode:** Read-only snapshot. No Git mutation.

## Git

| Field | Value |
|---|---|
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` |
| Porcelain lines | 1568 |
| Surface | CURRENT DEVELOPMENT |

Dirty families (counts, not a file dump): `.runtime` 740, `studio-api` 312, `docs` 163, `tests` 105, `studio-web` 89, `scripts` 19, plus root `tmp_*.py` scratch.

**Governance:** Do not `git add -A`, reset, clean, or mix unrelated dirty work into commits.

## Worktrees (16)

| Path | SHA / branch |
|---|---|
| `C:/AdeptFilmWorks/AIVideoStudio` | `b6156455` feat/character-creator-final-closure **(this mission)** |
| `C:/AdeptFilmWorks/AIVideoStudio-timeline-release` | `6c1a3699` release/timeline-fullstack-comfy-mcp |
| `C:/AdeptFilmWorks/AIVideoStudio-h3` | `c932214a` spike/minimax-h3-33b-rtx5090 |
| `C:/AdeptFilmWorks/_wt_minimax-duration-honesty` | `0666db2b` fix/minimax-h3-duration-honesty |
| `C:/AdeptFilmWorks/_wt_timed-prompt-delete` | `2c32d882` fix/timed-prompt-x-canonical-delete |
| others | avatar, ERS persist, pack authoring, PoseCraft, PSR, M2.4, maintenance, deploy temps |

## Ports / health (observed)

| Port | Health | Process note |
|---|---|---|
| 5173 Vite | 200 | `studio-web` vite (pid via node) |
| 8758 Studio API | healthz 200 | uvicorn `app.main:app` from repo venv |
| 8188 Comfy | system_stats 200 | Comfy Desktop install (`Comfy-Desktop\...\main.py`) |
| 8192 H3 Route A | system_stats 200 | `AIVideoStudio-h3\runtime\minimax-h3\comfyui\main.py` |
| 8760 retired UI | 200 | `scripts/beta_runtime/web_server.py` still running (Law 15 violation) |
| 11434 Ollama | listening | EXTERNAL `ollama.exe serve` |

Also observed: `scripts/beta_runtime/supervisor.py run` still active (second control plane). Extra Vite on `:5174` from `_wt_timed-prompt-delete`.

## GPU

`NVIDIA GeForce RTX 5090` — 3339 MiB / 32607 MiB used, 3% util. Two Comfy stacks share `cuda:0` (Desktop `:8188` + H3 `:8192`).

## Production Control snapshot (live)

Video: `ltx-local` Available/exec; LTX 2.5 Testing/not exec; `wan-local` + Hunyuan Available/exec **without Timeline adapters**; `minimax-h3` Testing/exec; `seedance-kie`/`kling-kie` Certified/exec; `veo-kie` Testing/exec.

Audio: `ace-step-local`, `mmaudio-local` **Certified + exec=False**.

LLM: Gemma 4 Available+exec=False; live Ollama tags executable; **four `openai-compat:...:mock-chat-*` Available+exec=True**.

Projects: `GET /api/projects` count **114**.

Timeline `GET /director-timeline/generators`: 11 generators / 6 adapters. LTX 2.5 + WAN + Hunyuan listed `executable=True` in `generators` but absent from `timelineAdapters`. Adapter IDs: `minimax-h3-t2v-local`, `minimax-h3-i2v-local`, `ltx-local`, `seedance-api`, `kling-api`, `veo-api`.

## Mission constraint

Implementation stays on this dirty worktree. Evidence only under `docs/release-gate/platform-integrity-closure/`. No commit/push/deploy unless the owner later authorizes it.
