from __future__ import annotations

"""Curated Adept Marketplace + LoRA registry (approve-before-install)."""

import hashlib
import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import settings


@dataclass
class MarketItem:
    id: str
    category: str  # models | loras | embeddings | styles | packs | workflows | nodes
    name: str
    description: str
    creator: str = "Adept Curated"
    license: str = "Check source"
    version: str = "1.0"
    file_size_mb: float = 0
    recommended_weight: float = 0.8
    compatible_models: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_url: str = ""
    preview_url: str = ""
    verified: bool = True
    trigger_words: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    rating: float = 4.5


CATALOG: list[MarketItem] = [
    MarketItem(
        id="lora_photoreal_faces",
        category="loras",
        name="Photoreal Faces",
        description="Excellent realistic portraits and skin detail.",
        compatible_models=["flux", "sdxl", "sd3.5"],
        tags=["characters", "photoreal", "faces"],
        recommended_weight=0.75,
        file_size_mb=180,
        trigger_words=["photoreal face"],
        rating=5.0,
    ),
    MarketItem(
        id="lora_anime_expressions",
        category="loras",
        name="Anime Expressions",
        description="High-quality facial expressions for anime styles.",
        compatible_models=["flux", "sdxl"],
        tags=["anime", "characters"],
        recommended_weight=0.7,
        file_size_mb=120,
        trigger_words=["anime expression"],
        rating=5.0,
    ),
    MarketItem(
        id="lora_cinematic_lighting",
        category="loras",
        name="Cinematic Lighting",
        description="Hollywood-style dramatic lighting.",
        compatible_models=["flux", "hidream", "sdxl", "sd3.5"],
        tags=["cinematic", "lighting"],
        recommended_weight=0.6,
        file_size_mb=95,
        trigger_words=["cinematic lighting"],
        rating=4.5,
    ),
    MarketItem(
        id="pack_essential_photoreal",
        category="packs",
        name="Essential Photoreal Pack",
        description="Starter LoRAs for photoreal productions.",
        compatible_models=["flux", "sdxl"],
        tags=["pack", "photoreal"],
        file_size_mb=400,
        depends_on=["lora_photoreal_faces", "lora_cinematic_lighting"],
        verified=True,
    ),
    MarketItem(
        id="pack_essential_anime",
        category="packs",
        name="Essential Anime Pack",
        description="Starter LoRAs for anime productions.",
        compatible_models=["flux", "sdxl"],
        tags=["pack", "anime"],
        file_size_mb=250,
        depends_on=["lora_anime_expressions"],
    ),
    MarketItem(
        id="pack_essential_cinematic",
        category="packs",
        name="Essential Cinematic Pack",
        description="Lighting and film-look starters.",
        compatible_models=["flux", "hidream", "sd3.5"],
        tags=["pack", "cinematic"],
        file_size_mb=200,
        depends_on=["lora_cinematic_lighting"],
    ),
    MarketItem(
        id="model_flux_placeholder",
        category="models",
        name="FLUX.1 (link your Comfy checkpoint)",
        description="Primary ImageGen default family — link installed FLUX weights.",
        compatible_models=["flux"],
        tags=["image", "flux"],
        file_size_mb=0,
        verified=True,
    ),
    MarketItem(
        id="model_hidream_placeholder",
        category="models",
        name="HiDream-I1 (link)",
        description="Photoreal / cinematic portraits option.",
        compatible_models=["hidream"],
        tags=["image", "photoreal"],
        file_size_mb=0,
    ),
]


def state_path() -> Path:
    return settings.data_dir / "marketplace_state.json"


def load_state() -> dict[str, Any]:
    p = state_path()
    if not p.exists():
        return {"installed": {}, "favorites": {"global": [], "projects": {}}, "stacks": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": {}, "favorites": {"global": [], "projects": {}}, "stacks": {}}


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def list_catalog(category: str | None = None, base_model: str | None = None, q: str = "") -> list[dict[str, Any]]:
    state = load_state()
    installed = state.get("installed") or {}
    out = []
    term = (q or "").lower().strip()
    for item in CATALOG:
        if category and item.category != category:
            # packs under creative assets still show when filtering loras? keep strict
            if not (category == "loras" and item.category == "packs"):
                continue
        if base_model and item.compatible_models and base_model.lower() not in [m.lower() for m in item.compatible_models]:
            # still include but mark incompatible
            pass
        if term and term not in (item.name + item.description + " ".join(item.tags)).lower():
            continue
        d = asdict(item)
        d["installed"] = item.id in installed
        d["install_path"] = (installed.get(item.id) or {}).get("path", "")
        d["compatible"] = (
            True
            if not base_model or not item.compatible_models
            else base_model.lower() in [m.lower() for m in item.compatible_models]
        )
        out.append(d)
    # Empty slots for future categories
    if category in ("workflows", "nodes", "embeddings", "styles") and not out:
        return []
    return out


def approve_install(item_id: str, *, path: str = "", approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Marketplace install requires explicit approval.")
    item = next((c for c in CATALOG if c.id == item_id), None)
    if not item:
        raise KeyError(f"Unknown marketplace item {item_id}")
    state = load_state()
    dest_root = settings.data_dir / "marketplace" / item.category
    dest_root.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "id": item_id,
        "status": "pending",
        "message": "",
        "path": path or "",
        "version": item.version,
        "approved_at": datetime.utcnow().isoformat(),
    }
    if path:
        src = Path(path)
        if not src.exists():
            entry["status"] = "failed"
            entry["message"] = f"Path not found: {path}"
        else:
            dest = dest_root / src.name
            if dest.exists():
                bak = dest.with_suffix(dest.suffix + f".bak-{uuid.uuid4().hex[:6]}")
                shutil.copy2(dest, bak)
                entry["rollback_path"] = str(bak)
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            entry["path"] = str(dest)
            entry["status"] = "installed"
            entry["message"] = "Linked/copied into Adept marketplace store. Point ComfyUI LoRA folder or symlink as needed."
            try:
                h = hashlib.sha256(dest.read_bytes()[:1024 * 1024]).hexdigest()
                entry["checksum_sample"] = h
            except Exception:
                pass
    else:
        # Register intent without binary (curated placeholder / pack marker)
        marker = dest_root / f"{item_id}.installed.json"
        marker.write_text(json.dumps({"id": item_id, "name": item.name}, indent=2), encoding="utf-8")
        entry["path"] = str(marker)
        entry["status"] = "registered"
        entry["message"] = (
            "Approved and registered. Provide a local .safetensors path to complete file install, "
            "or use Setup Wizard Creative Assets packs."
        )
    state.setdefault("installed", {})[item_id] = entry
    save_state(state)
    return entry


def set_stack(scope_key: str, stack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = load_state()
    state.setdefault("stacks", {})[scope_key] = stack
    save_state(state)
    return stack


def get_stack(scope_key: str) -> list[dict[str, Any]]:
    return list((load_state().get("stacks") or {}).get(scope_key) or [])
