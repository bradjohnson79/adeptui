# Adept UI Generation Studio (Gen Studio)

Standalone local studio with a polished UI driving ComfyUI (LTX 2.3 + WAN 2.2).

## Requirements
- Windows, RTX 5090 (or similar)
- ComfyUI running on `http://127.0.0.1:8188`
- Python 3.11+, Node.js 20+
- ffmpeg on PATH (for stitch / export)

## Quick start

From the repo root (recommended — one command for API + web):

```bash
npm run install:all
npm run dev
```

- API: http://127.0.0.1:8742 (`/api/health`)
- Web: http://127.0.0.1:5173 (Vite proxies `/api` → API)

### Dev server helpers (Windows)

Stale uvicorn/vite processes are a common cause of mysterious 404s after code changes. Prefer these npm scripts:

| Command | What it does |
|---------|----------------|
| `npm run dev` | Start API (`:8742`) + web (`:5173`) together via `concurrently` |
| `npm run dev:stop` | Stop **this repo's** listeners on 8742/5173 only |
| `npm run dev:restart` | Stop, then start fresh in a new window and wait for health |
| `npm run dev:status` | Show what is listening on those ports |
| `npm run api` / `npm run web` | Start one side alone |

Equivalent PowerShell entrypoint: `.\scripts\dev.ps1 start|stop|restart|status`

### Manual (two terminals)

```bash
# API
cd studio-api
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
# from repo root:
npm run api

# Web
cd studio-web
npm install
npm run dev
```

## Features
- Director timeline with start / middle / end keyframes
- LTX 2.3 and WAN 2.2 engines (per-scene toggle)
- `@tag` asset references in prompts
- Lip-sync pass (LatentSync template)
- Spatial map editor for set consistency
- Retakes, presets, export pack

See [INVENTORY.md](INVENTORY.md) for your local ComfyUI model status.

## Character / Angles tools
In a project, open the **Character / Angles** tab:

1. **Character sheet** — pick a reference character image → generates front, side, back, front close-up, side close-up. Saves as `@name_front`, `@name_side`, etc.
2. **Multi-angle** — pick a single camera shot → generates 3 consistent alternate angles (three-quarter left, low, high).

These use your installed **Z-Image Turbo** model with Omni reference conditioning via ComfyUI.

The UI includes a Studio Assistant powered by Ollama (default model: `gemma4:12b`).

1. Keep Ollama running (`ollama serve` if needed)
2. Ensure a model is installed, e.g. `ollama pull gemma4:12b` or `ollama pull qwen3:8b`
3. Optional env overrides in `studio-api/.env`:
   - `STUDIO_OLLAMA_URL=http://127.0.0.1:11434`
   - `STUDIO_OLLAMA_MODEL=gemma4:12b`

Click **Assistant** in the bottom-right of the UI for prompt help and UI guidance.
