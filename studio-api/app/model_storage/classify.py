"""Classify local model folders / files for Model Storage discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def classify_folder(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "runtimeType": "unknown",
            "label": p.name or path,
            "format": "missing",
            "models": [],
            "notes": "Path does not exist (drive may be disconnected).",
        }
    if p.is_file():
        return _classify_file(p)
    return _classify_dir(p)


def _classify_file(p: Path) -> dict[str, Any]:
    name = p.name.lower()
    if name.endswith(".gguf"):
        return {
            "runtimeType": "gguf",
            "label": p.stem,
            "format": "gguf",
            "models": [{"name": p.stem, "path": str(p), "format": "gguf"}],
            "notes": "GGUF weight file.",
        }
    if name.endswith(".onnx"):
        return {
            "runtimeType": "onnx",
            "label": p.stem,
            "format": "onnx",
            "models": [{"name": p.stem, "path": str(p), "format": "onnx"}],
            "notes": "ONNX model file.",
        }
    return {
        "runtimeType": "unknown",
        "label": p.name,
        "format": "file",
        "models": [{"name": p.name, "path": str(p)}],
        "notes": "Unrecognized single file.",
    }


def _classify_dir(p: Path) -> dict[str, Any]:
    blobs = p / "blobs"
    manifests = p / "manifests"
    if blobs.is_dir() and manifests.is_dir():
        models = _ollama_models_from_manifests(manifests)
        return {
            "runtimeType": "ollama",
            "label": f"Ollama store ({p.name})",
            "format": "ollama_store",
            "models": models,
            "notes": "Ollama model store — resolved via manifests, never raw blobs.",
        }
    # Hugging Face snapshot / safetensors
    safes = list(p.glob("*.safetensors")) + list(p.glob("**/*.safetensors"))
    config = p / "config.json"
    if safes or config.is_file():
        names = [s.stem for s in safes[:20]] or [p.name]
        return {
            "runtimeType": "huggingface",
            "label": p.name,
            "format": "safetensors_hf",
            "models": [{"name": n, "path": str(p), "format": "safetensors"} for n in names],
            "notes": "Hugging Face / safetensors snapshot.",
        }
    ggufs = list(p.glob("*.gguf")) + list(p.glob("**/*.gguf"))
    if ggufs:
        return {
            "runtimeType": "gguf",
            "label": p.name,
            "format": "gguf_dir",
            "models": [{"name": g.stem, "path": str(g), "format": "gguf"} for g in ggufs[:50]],
            "notes": "Directory containing GGUF files.",
        }
    mlx_marker = (p / "mlx_model.safetensors").exists() or any(p.glob("**/mlx_config.json"))
    if mlx_marker:
        return {
            "runtimeType": "mlx",
            "label": p.name,
            "format": "mlx",
            "models": [{"name": p.name, "path": str(p), "format": "mlx"}],
            "notes": "MLX model directory.",
        }
    onnx = list(p.glob("*.onnx")) + list(p.glob("**/*.onnx"))
    if onnx:
        return {
            "runtimeType": "onnx",
            "label": p.name,
            "format": "onnx_dir",
            "models": [{"name": o.stem, "path": str(o), "format": "onnx"} for o in onnx[:50]],
            "notes": "Directory containing ONNX files.",
        }
    return {
        "runtimeType": "unknown",
        "label": p.name,
        "format": "directory",
        "models": [],
        "notes": "Unrecognized folder layout.",
    }


def _ollama_models_from_manifests(manifests: Path) -> list[dict[str, Any]]:
    """Resolve model names from Ollama manifests tree — never list blob digests as models."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for registry in manifests.iterdir():
            if not registry.is_dir():
                continue
            for library in registry.rglob("*"):
                if not library.is_file():
                    continue
                # path like manifests/registry.ollama.ai/library/gemma4/31b-it-qat
                parts = library.relative_to(manifests).parts
                if len(parts) < 2:
                    continue
                # Prefer library/name:tag style
                if "library" in parts:
                    idx = parts.index("library")
                    name_parts = parts[idx + 1 :]
                    if len(name_parts) >= 2:
                        tag = f"{name_parts[0]}:{name_parts[1]}"
                    elif name_parts:
                        tag = name_parts[0]
                    else:
                        continue
                else:
                    tag = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
                if tag in seen:
                    continue
                seen.add(tag)
                out.append({"name": tag, "path": str(library), "format": "ollama_manifest"})
    except OSError:
        pass
    return out[:200]
