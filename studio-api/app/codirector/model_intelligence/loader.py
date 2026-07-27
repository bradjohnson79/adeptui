"""Load and validate model knowledge packs (fail closed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schemas import PackManifest, PackStatus

PACKS_DIR = Path(__file__).resolve().parent / "packs"

REQUIRED_FILES = (
    "manifest.yaml",
    "capabilities.yaml",
    "parameters.yaml",
    "prompt_rules.yaml",
    "audio_behavior.yaml",
    "limitations.yaml",
    "workarounds.yaml",
    "evaluation_rules.yaml",
    "provenance.yaml",
)


class PackLoadError(ValueError):
    """Malformed or incomplete knowledge pack."""


def _read_yaml(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackLoadError(f"cannot read {path}: {exc}") from exc
    # Treat pack YAML as untrusted: reject executable-looking tags
    if "{{" in raw or "{%" in raw or "!!python" in raw.lower():
        raise PackLoadError(f"rejected unsafe content in {path.name}")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PackLoadError(f"invalid YAML in {path}: {exc}") from exc
    return data


def load_pack_dir(pack_dir: Path) -> dict[str, Any]:
    if not pack_dir.is_dir():
        raise PackLoadError(f"pack directory missing: {pack_dir}")
    missing = [name for name in REQUIRED_FILES if not (pack_dir / name).is_file()]
    if missing:
        raise PackLoadError(f"incomplete pack {pack_dir.name}: missing {missing}")

    manifest_raw = _read_yaml(pack_dir / "manifest.yaml")
    if not isinstance(manifest_raw, dict):
        raise PackLoadError(f"{pack_dir.name}: manifest must be a mapping")
    try:
        manifest = PackManifest.model_validate(manifest_raw)
    except Exception as exc:  # noqa: BLE001
        raise PackLoadError(f"{pack_dir.name}: invalid manifest: {exc}") from exc
    if manifest.modelId != pack_dir.name and pack_dir.name not in (
        manifest.modelId,
        manifest.modelId.replace("-", "_"),
    ):
        # Allow directory name to match modelId exactly.
        if pack_dir.name != manifest.modelId:
            raise PackLoadError(
                f"pack dir {pack_dir.name!r} does not match manifest.modelId {manifest.modelId!r}"
            )

    sections: dict[str, Any] = {"manifest": manifest}
    for name in REQUIRED_FILES:
        if name == "manifest.yaml":
            continue
        key = name.replace(".yaml", "")
        data = _read_yaml(pack_dir / name)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise PackLoadError(f"{pack_dir.name}/{name} must be a mapping")
        sections[key] = data

    examples_dir = pack_dir / "examples"
    example_texts: list[str] = []
    if examples_dir.is_dir():
        for path in sorted(examples_dir.glob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".yaml", ".yml"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "!!python" in text.lower():
                    raise PackLoadError(f"unsafe example content in {path.name}")
                example_texts.append(text)
    sections["examples"] = example_texts
    sections["packDir"] = str(pack_dir)
    return sections


def discover_packs(root: Path | None = None) -> dict[str, dict[str, Any]]:
    base = root or PACKS_DIR
    if not base.is_dir():
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        try:
            pack = load_pack_dir(child)
            loaded[pack["manifest"].modelId] = pack
        except PackLoadError as exc:
            errors.append(str(exc))
    if errors and not loaded:
        raise PackLoadError("; ".join(errors))
    # Partial discovery: keep valid packs; callers may inspect errors via validate_all
    return loaded


def validate_all(root: Path | None = None) -> dict[str, Any]:
    base = root or PACKS_DIR
    ok: list[str] = []
    failed: list[dict[str, str]] = []
    if not base.is_dir():
        return {"ok": [], "failed": [{"pack": "*", "error": "packs directory missing"}]}
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        try:
            pack = load_pack_dir(child)
            ok.append(pack["manifest"].modelId)
        except PackLoadError as exc:
            failed.append({"pack": child.name, "error": str(exc)})
    return {"ok": ok, "failed": failed}


def active_packs(root: Path | None = None) -> dict[str, dict[str, Any]]:
    all_packs = discover_packs(root)
    return {
        mid: pack
        for mid, pack in all_packs.items()
        if pack["manifest"].status in (PackStatus.ACTIVE, PackStatus.VERIFIED)
        and pack["manifest"].status != PackStatus.QUARANTINED
    }
