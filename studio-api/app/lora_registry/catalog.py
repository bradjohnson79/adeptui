"""Curated LoRA catalog (config-backed) for optional Setup Wizard downloads.

Not a marketplace: a small, reviewed list of LoRAs with source/license/size
metadata. Downloads are always user-initiated and checksum-verified when a
checksum is published. Missing config file -> empty catalog (honest degrade).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = _REPO_ROOT / "config" / "lora_catalog.json"


@dataclass(frozen=True)
class LoraCatalogItem:
    id: str
    name: str
    description: str
    category: str = "Style"
    compatible_model_families: list[str] = field(default_factory=list)
    modality: str = "image"
    source_url: str = ""
    download_url: str = ""
    file_size_mb: float = 0.0
    license: str = "Check source"
    version: str = "1.0"
    recommended_strength: float = 0.8
    strength_min: float = 0.0
    strength_max: float = 1.5
    checksum_sha256: str = ""
    notes: str = ""

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_items(path: Path | None = None) -> list[LoraCatalogItem]:
    p = Path(path or DEFAULT_CATALOG_PATH)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    out: list[LoraCatalogItem] = []
    for entry in items:
        if not isinstance(entry, dict) or not str(entry.get("id") or "").strip():
            continue
        try:
            out.append(LoraCatalogItem(**{k: v for k, v in entry.items() if k in LoraCatalogItem.__dataclass_fields__}))
        except Exception:
            continue
    return out


_CACHE: list[LoraCatalogItem] | None = None


def catalog_items() -> list[LoraCatalogItem]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_items()
    return list(_CACHE)


def get_catalog_item(item_id: str) -> LoraCatalogItem | None:
    for item in catalog_items():
        if item.id == item_id:
            return item
    return None
