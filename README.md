# Local AI Video Studio

Standalone local video studio with a polished UI driving ComfyUI (LTX 2.3 + WAN 2.2).

## Requirements
- Windows, RTX 5090 (or similar)
- ComfyUI running on `http://127.0.0.1:8188`
- Python 3.11+, Node.js 20+
- ffmpeg on PATH (for stitch / export)

## Quick start

### 1. API
```bash
cd studio-api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8742
```

### 2. Web UI
```bash
cd studio-web
npm install
npm run dev
```

Open http://127.0.0.1:5173

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
