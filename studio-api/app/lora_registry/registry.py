"""LoRA Registry — persistent state, discovery, CRUD, compatibility, downloads.

Single authoritative store for installed LoRAs (data/lora_registry.json).
All Adept UI surfaces query this module; generation adapters resolve
selections through :func:`resolve_lora_for_generation` which refuses
incompatible / disabled / missing LoRAs (no silent substitution).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..config import settings
from . import compat
from .catalog import LoraCatalogItem, get_catalog_item

STATE_FILENAME = "lora_registry.json"
LORA_STORE_DIRNAME = "lora_store"
VALID_INSTALL_STATUSES = ("installed", "registered", "missing", "failed", "downloading")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LoraRecord:
    """One registered LoRA — only metadata required for reliable use."""

    id: str
    name: str
    # Absolute path of the installed weights file ('' when catalog-only).
    file_path: str = ""
    # Canonical LoRA model family (compat.LORA_FAMILY_*); "unassigned" = not
    # shown in any selector until the user assigns a family.
    model_family: str = compat.LORA_FAMILY_UNASSIGNED
    compatible_model_families: list[str] = field(default_factory=list)
    category: str = "Other"
    modality: str = compat.MODALITY_ANY
    version: str = "1.0"
    enabled: bool = True
    recommended_strength: float | None = 0.8
    strength_min: float | None = None
    strength_max: float | None = None
    source_url: str = ""
    license: str = ""
    download_size_bytes: int | None = None
    checksum_sha256: str = ""
    install_status: str = "registered"  # VALID_INSTALL_STATUSES
    last_validated_at: str = ""
    detected: bool = False
    catalog_id: str = ""
    installed_at: str = ""
    notes: str = ""
    # ComfyUI loras-dir-relative name (or absolute path fallback) used when
    # emitting the LoraLoader node. Computed lazily by resolve_comfy_lora_name.
    comfy_name: str = ""

    def public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["file_exists"] = bool(self.file_path) and Path(self.file_path).is_file()
        return d


# ── State persistence ────────────────────────────────────────────────────


def state_path() -> Path:
    return Path(settings.data_dir) / STATE_FILENAME


def lora_store_dir() -> Path:
    p = Path(settings.data_dir) / LORA_STORE_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_state() -> dict[str, Any]:
    p = state_path()
    if not p.is_file():
        return {"version": 1, "loras": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "loras": []}


def save_state(state: dict[str, Any]) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _records() -> list[dict[str, Any]]:
    return load_state().get("loras") or []


def list_loras(*, include_disabled: bool = True) -> list[LoraRecord]:
    out: list[LoraRecord] = []
    for raw in _records():
        try:
            rec = LoraRecord(**{k: v for k, v in raw.items() if k in LoraRecord.__dataclass_fields__})
        except Exception:
            continue
        if rec.enabled or include_disabled:
            out.append(rec)
    out.sort(key=lambda r: (r.name or "").lower())
    return out


def get_lora(lora_id: str) -> LoraRecord | None:
    for raw in _records():
        if raw.get("id") == lora_id:
            try:
                return LoraRecord(**{k: v for k, v in raw.items() if k in LoraRecord.__dataclass_fields__})
            except Exception:
                return None
    return None


def _upsert(record: LoraRecord) -> LoraRecord:
    state = load_state()
    state.setdefault("loras", [])
    state["loras"] = [r for r in state["loras"] if r.get("id") != record.id]
    state["loras"].append(asdict(record))
    save_state(state)
    return record


# ── Validation / discovery ───────────────────────────────────────────────


def validate_safetensors(path: Path) -> tuple[bool, str]:
    """Cheap structural check that a file is a safetensors weights file.

    Verifies the 8-byte little-endian header length and that the header
    parses as JSON with a tensor map. Never loads weights.
    """
    if not path.is_file():
        return False, "not a file"
    if path.stat().st_size < 16:
        return False, "file too small"
    try:
        with open(path, "rb") as fh:
            raw_len = fh.read(8)
            if len(raw_len) != 8:
                return False, "truncated header"
            header_len = int.from_bytes(raw_len, "little")
            if header_len <= 0 or header_len > 64 * 1024 * 1024:
                return False, "invalid header length"
            header = fh.read(header_len)
            if len(header) != header_len:
                return False, "truncated header payload"
            data = json.loads(header.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, f"not a valid safetensors file: {exc}"
    if not isinstance(data, dict):
        return False, "header is not an object"
    if "__models__" not in data and not any(
        k.endswith((".weight", ".alpha")) for k in data.keys()
    ):
        return False, "header has no tensor map"
    return True, "ok"


def search_roots() -> list[Path]:
    """Model directories scanned for installed LoRA files."""
    roots: list[Path] = []
    comfy_models = getattr(settings, "comfy_models_dir", None)
    if comfy_models:
        roots.append(Path(comfy_models) / "loras")
    krea_root = getattr(settings, "krea2_model_root", None)
    if krea_root:
        roots.append(Path(krea_root) / "loras")
    data_dir = getattr(settings, "data_dir", None)
    if data_dir:
        roots.append(Path(data_dir) / "models" / "loras")
    roots.append(lora_store_dir())
    marketplace = Path(getattr(settings, "data_dir", ".")) / "marketplace" / "loras"
    if marketplace.is_dir():
        roots.append(marketplace)
    seen: list[Path] = []
    for root in roots:
        root = Path(root)
        if root.is_dir() and root.resolve() not in {Path(s).resolve() for s in seen}:
            seen.append(root)
    return seen


def scan_for_loras() -> list[dict[str, Any]]:
    """Find *.safetensors files under the search roots (deduplicated).

    Returns candidate descriptors; registering them is a separate explicit
    action (detect flow) so discovery never mutates state by itself.
    """
    found: dict[str, Path] = {}
    for root in search_roots():
        try:
            for path in root.rglob("*.safetensors"):
                if path.stat().st_size > 0 and ".cache" not in path.parts:
                    found[str(path.resolve())] = path
        except Exception:
            continue
    out: list[dict[str, Any]] = []
    for _abs, path in sorted(found.items(), key=lambda kv: kv[1].name.lower()):
        out.append(
            {
                "path": str(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "size_mb": round(path.stat().st_size / (1024 * 1024), 1),
                "inferred_family": compat.infer_family_from_filename(path.name),
                "registered": get_lora_for_path(str(path)) is not None,
            }
        )
    return out


def get_lora_for_path(path: str) -> LoraRecord | None:
    try:
        target = str(Path(path).resolve())
    except Exception:
        target = str(path)
    for rec in list_loras():
        try:
            if str(Path(rec.file_path).resolve()) == target:
                return rec
        except Exception:
            if rec.file_path == target:
                return rec
    return None


# ── Registration / mutation ──────────────────────────────────────────────


def _checksum_sha256(path: Path, sample_bytes: int = 0) -> str:
    """SHA-256 of the whole file (or a head sample when sample_bytes > 0)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        if sample_bytes > 0:
            h.update(fh.read(sample_bytes))
        else:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def register_lora(
    *,
    name: str,
    file_path: str = "",
    model_family: str = compat.LORA_FAMILY_UNASSIGNED,
    compatible_model_families: Iterable[str] | None = None,
    category: str = "Other",
    modality: str = compat.MODALITY_ANY,
    version: str = "1.0",
    enabled: bool = True,
    recommended_strength: float | None = 0.8,
    strength_min: float | None = None,
    strength_max: float | None = None,
    source_url: str = "",
    license: str = "",
    download_size_bytes: int | None = None,
    checksum_sha256: str = "",
    catalog_id: str = "",
    notes: str = "",
    detected: bool = False,
) -> LoraRecord:
    """Register one LoRA. File validation is structural, not archival."""
    family = compat.normalize_app_family(model_family) or compat.LORA_FAMILY_UNASSIGNED
    if family not in compat.CANONICAL_LORA_FAMILIES:
        family = compat.LORA_FAMILY_UNASSIGNED
    existing = get_lora_for_path(file_path) if file_path else None
    if existing is not None:
        return existing
    install_status = "registered"
    last_validated = ""
    if file_path:
        ok, message = validate_safetensors(Path(file_path))
        if not ok:
            raise ValueError(f"Cannot register {Path(file_path).name}: {message}")
        install_status = "installed"
        last_validated = utcnow_iso()
        if not checksum_sha256:
            checksum_sha256 = _checksum_sha256(Path(file_path), sample_bytes=1024 * 1024)
    record = LoraRecord(
        id=uuid.uuid4().hex[:12],
        name=str(name).strip() or Path(file_path or "lora").stem,
        file_path=str(Path(file_path).resolve()) if file_path else "",
        model_family=family,
        compatible_model_families=sorted(
            {compat.normalize_app_family(f) for f in (compatible_model_families or ()) if compat.normalize_app_family(f)}
        ),
        category=category,
        modality=modality,
        version=version,
        enabled=enabled,
        recommended_strength=recommended_strength,
        strength_min=strength_min,
        strength_max=strength_max,
        source_url=source_url,
        license=license,
        download_size_bytes=download_size_bytes,
        checksum_sha256=checksum_sha256,
        install_status=install_status,
        last_validated_at=last_validated,
        detected=detected,
        catalog_id=catalog_id,
        installed_at=utcnow_iso(),
        notes=notes,
    )
    return _upsert(record)


def set_lora_enabled(lora_id: str, enabled: bool) -> LoraRecord:
    rec = get_lora(lora_id)
    if rec is None:
        raise KeyError(f"Unknown LoRA {lora_id}")
    rec.enabled = bool(enabled)
    return _upsert(rec)


def unregister_lora(lora_id: str, *, delete_file: bool = False) -> dict[str, Any]:
    """Remove a LoRA from the registry.

    delete_file=True (explicit user confirmation required by the caller)
    deletes the registered weights file when it lives inside Adept-managed
    storage (lora_store / data models / marketplace). Files under the shared
    ComfyUI models root are never deleted — they may be used by other tools.
    """
    rec = get_lora(lora_id)
    if rec is None:
        raise KeyError(f"Unknown LoRA {lora_id}")
    state = load_state()
    state["loras"] = [r for r in state["loras"] if r.get("id") != lora_id]
    save_state(state)
    deleted_path = None
    if delete_file and rec.file_path:
        path = Path(rec.file_path)
        managed = any(
            str(path.resolve()).startswith(str(root.resolve()))
            for root in (lora_store_dir(), Path(settings.data_dir) / "models" / "loras")
        )
        if managed and path.is_file():
            try:
                path.unlink()
                deleted_path = str(path)
            except OSError:
                pass
    return {"id": lora_id, "removed": True, "file_deleted": deleted_path is not None, "deleted_path": deleted_path}


def _comfy_loras_dir() -> Path:
    comfy_models = getattr(settings, "comfy_models_dir", None)
    if comfy_models:
        return Path(comfy_models) / "loras"
    return lora_store_dir()


def resolve_comfy_lora_name(record: LoraRecord) -> str:
    """ComfyUI-visible name for a registered LoRA file.

    When the file already lives under the ComfyUI loras dir the relative name
    is returned directly. Otherwise the file is linked (hardlink; copy
    fallback) into the ComfyUI loras dir so the LoraLoader node can resolve
    it. Files under the shared ComfyUI root are never duplicated.
    """
    if record.comfy_name:
        return record.comfy_name
    if not record.file_path or not Path(record.file_path).is_file():
        raise ValueError(f"LoRA unavailable: {record.name} (file missing)")
    src = Path(record.file_path)
    loras_dir = _comfy_loras_dir()
    loras_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = src.resolve().relative_to(loras_dir.resolve())
        comfy_name = str(rel)
    except ValueError:
        dest = loras_dir / _sanitize_filename(src.name)
        if not dest.exists():
            try:
                os.link(src, dest)
            except OSError:
                shutil.copy2(src, dest)
        comfy_name = dest.name
    record.comfy_name = comfy_name
    _upsert(record)
    return comfy_name


def refresh_installed_status() -> None:
    """Re-validate file existence for all registered LoRAs (non-destructive)."""
    state = load_state()
    changed = False
    for raw in state.get("loras") or []:
        fp = str(raw.get("file_path") or "")
        was = raw.get("install_status")
        if fp and Path(fp).is_file():
            raw["install_status"] = "installed"
            raw["last_validated_at"] = utcnow_iso()
        elif fp:
            raw["install_status"] = "missing"
        if raw.get("install_status") != was:
            changed = True
    if changed:
        save_state(state)


def register_detected_files(*, auto_enable: bool = True) -> list[LoraRecord]:
    """Discovery flow: register every found file that is not yet registered.

    Family inference is filename-based (compat.infer_family_from_filename);
    unassigned files are registered but excluded from selectors.
    """
    refresh_installed_status()
    created: list[LoraRecord] = []
    for candidate in scan_for_loras():
        if candidate["registered"]:
            continue
        family = candidate["inferred_family"]
        modality = compat.MODALITY_VIDEO if family in (compat.LORA_FAMILY_LTX, compat.LORA_FAMILY_WAN, compat.LORA_FAMILY_HUNYUAN) else compat.MODALITY_ANY
        try:
            rec = register_lora(
                name=Path(candidate["path"]).stem,
                file_path=candidate["path"],
                model_family=family,
                modality=modality,
                enabled=auto_enable,
                detected=True,
                notes="Discovered in shared model storage.",
            )
            created.append(rec)
        except ValueError:
            continue
    return created


# ── Compatibility queries (the single filtering entry point) ─────────────


def compatible_loras(
    model_family: str | None,
    modality: str | None = None,
    *,
    include_disabled: bool = False,
) -> list[LoraRecord]:
    """Enabled LoRAs compatible with the active Adept model family.

    This is the only filter the UI selectors and generation adapters use.
    Deterministic: family alias resolution + enabled flag + modality match.
    """
    families = compat.lora_families_for_app_family(model_family)
    if not families:
        return []
    out: list[LoraRecord] = []
    for rec in list_loras(include_disabled=include_disabled):
        if not include_disabled and not rec.enabled:
            continue
        if rec.model_family == compat.LORA_FAMILY_UNASSIGNED:
            continue
        if not compat.modality_matches(rec.modality, modality):
            continue
        rec_families = {compat.normalize_app_family(f) for f in rec.compatible_model_families}
        rec_families.add(compat.normalize_app_family(rec.model_family))
        if rec_families & set(families):
            out.append(rec)
    return out


def resolve_lora_for_generation(
    selection: Any,
    model_family: str | None,
    modality: str | None = None,
) -> LoraRecord | None:
    """Validate a UI selection at generation time.

    Returns None when no LoRA was selected. Raises a clear, honest error when
    the selection references a LoRA that is missing, disabled, or
    incompatible with the active model — never silently substitutes.
    """
    if selection is None:
        return None
    lora_id = ""
    strength: float | None = None
    if isinstance(selection, dict):
        lora_id = str(selection.get("id") or selection.get("loraId") or selection.get("lora_id") or "").strip()
        raw = selection.get("strength")
        try:
            strength = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            strength = None
    elif isinstance(selection, str):
        lora_id = selection.strip()
    if not lora_id:
        return None
    rec = get_lora(lora_id)
    if rec is None:
        raise ValueError(f"LoRA unavailable: unknown LoRA id {lora_id}")
    if not rec.enabled:
        raise ValueError(f"LoRA unavailable: {rec.name} is disabled")
    if rec.file_path and not Path(rec.file_path).is_file():
        raise ValueError(f"LoRA unavailable: {rec.name} (file missing)")
    families = compat.lora_families_for_app_family(model_family)
    rec_families = {compat.normalize_app_family(f) for f in rec.compatible_model_families}
    rec_families.add(compat.normalize_app_family(rec.model_family))
    if not (families and rec_families & set(families)):
        raise ValueError(
            f"LoRA {rec.name} is not compatible with {model_family or 'the active model'}"
        )
    if not compat.modality_matches(rec.modality, modality):
        raise ValueError(f"LoRA {rec.name} is not compatible with {modality or 'this surface'}")
    if strength is not None:
        rec.recommended_strength = strength
    return rec


# ── Downloads (optional, user-initiated, checksum-verified) ──────────────


def _sanitize_filename(name: str) -> str:
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    cleaned = "".join(ch if ch in keep else "_" for ch in str(name or ""))
    cleaned = cleaned.strip("._") or "lora"
    if not cleaned.lower().endswith(".safetensors"):
        cleaned += ".safetensors"
    return cleaned[:200]


def download_lora(catalog_id: str, *, approved: bool = False) -> dict[str, Any]:
    """Download a curated catalog LoRA into Adept-managed storage.

    Requires explicit approval (mirrors marketplace install conventions).
    Verifies the checksum when the catalog publishes one. Network failures
    surface as honest errors — nothing is downloaded silently.
    """
    if not approved:
        raise PermissionError("LoRA download requires explicit approval (approved=true).")
    item = get_catalog_item(catalog_id)
    if item is None:
        raise KeyError(f"Unknown catalog LoRA {catalog_id}")
    if not item.download_url:
        raise ValueError(
            f"{item.name} has no download URL configured. Use 'Register local file' to install "
            "an existing weights file."
        )
    dest = lora_store_dir() / _sanitize_filename(f"{item.id}_{item.name}")
    entry = {
        "catalogId": catalog_id,
        "status": "downloading",
        "dest": str(dest),
        "size_bytes": int(item.file_size_mb * 1024 * 1024),
    }
    try:
        req = urllib.request.Request(item.download_url, headers={"User-Agent": "AdeptUI/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception as exc:  # noqa: BLE001
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        entry["status"] = "failed"
        entry["message"] = f"Download failed: {exc}"
        return entry
    if not validate_safetensors(dest)[0]:
        entry["status"] = "failed"
        entry["message"] = "Downloaded file is not a valid safetensors weights file."
        try:
            dest.unlink()
        except OSError:
            pass
        return entry
    checksum = _checksum_sha256(dest)
    if item.checksum_sha256 and checksum != item.checksum_sha256.lower():
        entry["status"] = "failed"
        entry["message"] = "Checksum mismatch — downloaded file rejected."
        try:
            dest.unlink()
        except OSError:
            pass
        return entry
    rec = register_lora(
        name=item.name,
        file_path=str(dest),
        model_family=item.compatible_model_families[0] if item.compatible_model_families else compat.LORA_FAMILY_UNASSIGNED,
        compatible_model_families=item.compatible_model_families,
        category=item.category,
        modality=item.modality,
        version=item.version,
        recommended_strength=item.recommended_strength,
        strength_min=item.strength_min,
        strength_max=item.strength_max,
        source_url=item.source_url,
        license=item.license,
        download_size_bytes=int(item.file_size_mb * 1024 * 1024),
        checksum_sha256=checksum,
        catalog_id=item.id,
        notes=item.notes,
    )
    entry["status"] = "installed"
    entry["message"] = f"Installed {item.name}."
    entry["loraId"] = rec.id
    entry["checksum_sha256"] = checksum
    return entry
