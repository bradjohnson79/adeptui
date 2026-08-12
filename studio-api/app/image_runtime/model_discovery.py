"""Modern image model discovery — FLUX, Qwen Image, Imagen, Z-Image (M42 W2)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _models_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("ADEPT_MODELS_ROOT") or os.environ.get("COMFY_MODELS_PATH")
    if env:
        roots.append(Path(env))
    # Common local layouts
    for candidate in (
        _REPO_ROOT / "models",
        _REPO_ROOT / "ComfyUI" / "models",
        Path(os.environ.get("USERPROFILE", "")) / "ComfyUI" / "models",
        Path("C:/ComfyUI/models"),
        Path("D:/ComfyUI/models"),
        Path("E:/ComfyUI/models"),
    ):
        if candidate and candidate not in roots:
            roots.append(candidate)
    try:
        from ..config import settings

        md = getattr(settings, "models_dir", None) or getattr(settings, "comfy_models_dir", None)
        if md:
            roots.insert(0, Path(md))
    except Exception:
        pass
    return roots


def _scan_files(root: Path, patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if not root.is_dir():
        return found
    lower_patterns = tuple(p.lower() for p in patterns)
    for dirpath, _dirnames, filenames in os.walk(root):
        # Skip huge unrelated trees
        base = Path(dirpath).name.lower()
        if base in {".git", "node_modules", "__pycache__"}:
            continue
        for name in filenames:
            nl = name.lower()
            if any(p in nl for p in lower_patterns):
                found.append(str(Path(dirpath) / name))
    return found


def _detect_family(roots: list[Path], patterns: tuple[str, ...]) -> dict[str, Any]:
    files: list[str] = []
    for root in roots:
        files.extend(_scan_files(root, patterns))
    # Deduplicate
    uniq = sorted(set(files))
    return {
        "installed": len(uniq) > 0,
        "fileCount": len(uniq),
        "sampleFiles": uniq[:12],
    }


def _detect_krea2(roots: list[Path]) -> dict[str, Any]:
    """Krea 2 detection — tight filename patterns plus the official HF layout.

    Comfy-Org-style repacks carry krea2 in the filename; the official gated repos ship
    bare ``turbo.safetensors`` / ``raw.safetensors`` which only count inside the
    configured Krea 2 model root (the root path is the family scope, so unrelated
    ``*turbo*`` files elsewhere never false-positive).
    """
    files: list[str] = []
    for root in roots:
        files.extend(_scan_files(root, ("krea-2", "krea_2", "krea2")))
    try:
        from ..config import settings

        model_root = Path(str(getattr(settings, "krea2_model_root", "") or "").strip()).expanduser()
    except Exception:
        model_root = Path("")
    if str(model_root) and model_root.is_dir():
        official = {"turbo.safetensors", "raw.safetensors"}
        for dirpath, _dirnames, filenames in os.walk(model_root):
            base = Path(dirpath).name.lower()
            if base in {".git", "node_modules", "__pycache__"}:
                continue
            for name in filenames:
                if name.lower() in official:
                    files.append(str(Path(dirpath) / name))
    uniq = sorted(set(files))
    return {
        "installed": len(uniq) > 0,
        "fileCount": len(uniq),
        "sampleFiles": uniq[:12],
    }


def discover_modern_image_models() -> dict[str, Any]:
    roots = [r for r in _models_roots() if r.is_dir()]
    zimage = _detect_family(
        roots,
        ("z_image", "z-image", "zimage"),
    )
    flux = _detect_family(
        roots,
        ("flux1", "flux.1", "flux_", "flux-dev", "flux-schnell", "flux.kontext", "flux_fill", "flux_edit"),
    )
    qwen = _detect_family(
        roots,
        ("qwen-image", "qwen_image", "qwenimage"),
    )
    krea2 = _detect_krea2(roots)
    # Qwen text encoder used by Z-Image is not Qwen Image family
    checkpoint = _detect_family(roots, ("sdxl", "sd3", "hidream", ".safetensors"))

    imagen_creds = bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("IMAGEN_API_KEY")
        or os.environ.get("GCP_PROJECT")
    )

    families = {
        "zimage": {
            "modelFamily": "zimage",
            "variants": ["turbo"],
            **zimage,
            "statusHint": "Draft" if zimage["installed"] else "Blocked",
            "reason": "Weights present" if zimage["installed"] else "Z-Image weights not found on disk",
        },
        "flux": {
            "modelFamily": "flux",
            "variants": ["dev", "schnell", "kontext", "edit", "fill"],
            **flux,
            "statusHint": "Draft" if flux["installed"] else "Deferred",
            "reason": "FLUX weights detected" if flux["installed"] else "FLUX weights not installed — Deferred",
        },
        "qwen": {
            "modelFamily": "qwen",
            "variants": ["txt2img", "edit", "reference"],
            **qwen,
            "statusHint": "Draft" if qwen["installed"] else "Deferred",
            "reason": "Qwen Image weights detected" if qwen["installed"] else "Qwen Image weights not installed — Deferred",
            "multilingualPrompt": True,
        },
        "krea2": {
            "modelFamily": "krea2",
            "variants": ["turbo", "raw"],
            **krea2,
            "statusHint": "Draft" if krea2["installed"] else "Blocked",
            "reason": (
                "Krea 2 weights present"
                if krea2["installed"]
                else "Krea 2 weights not found on disk (gated HF repos — link an existing download)"
            ),
            "license": "krea-2-community-license",
        },
        "imagen": {
            "modelFamily": "imagen",
            "variants": ["txt2img", "edit", "reference"],
            "installed": imagen_creds,
            "fileCount": 0,
            "sampleFiles": [],
            "credentialConfigured": imagen_creds,
            "statusHint": "Draft" if imagen_creds else "Blocked",
            "reason": (
                "Credentials configured"
                if imagen_creds
                else "Provider unavailable or credentials not configured."
            ),
        },
        "checkpoint": {
            "modelFamily": "checkpoint",
            "variants": ["generic"],
            **checkpoint,
            "statusHint": "Deferred",
            "reason": "Legacy generic checkpoint adapter — prefer family keys (flux.*/qwen.*)",
        },
    }

    return {
        "phase": "M42-W2",
        "scannedRoots": [str(r) for r in roots],
        "families": families,
        "discoveryComplete": True,
    }


def write_discovery_artifact(path: Path | None = None) -> Path:
    out = path or (_REPO_ROOT / "artifacts" / "m42" / "w2" / "modern_model_discovery.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = discover_modern_image_models()
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out
