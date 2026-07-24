"""Build release-ready Essential pack archives and companion .release.json files."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .pack_manifests import ASSET_PACK_IDS, get_pack_manifest

SOURCES_ROOT = Path(__file__).resolve().parents[2] / "pack_sources"
DIST_ROOT = Path(__file__).resolve().parents[2] / "dist" / "packs"


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def build_pack(pack_id: str, *, channel: str = "stable") -> dict:
    if pack_id not in ASSET_PACK_IDS:
        raise SystemExit(f"Unknown pack id: {pack_id}")
    source = SOURCES_ROOT / pack_id
    if not source.is_dir():
        raise SystemExit(f"Missing pack source directory: {source}")

    pack_json_path = source / "pack.json"
    if not pack_json_path.is_file():
        raise SystemExit("pack.json is required")
    pack_json = json.loads(pack_json_path.read_text(encoding="utf-8"))
    if str(pack_json.get("id") or "") != pack_id:
        raise SystemExit("pack.json id mismatch")
    version = str(pack_json.get("version") or "")
    if not version:
        raise SystemExit("pack.json version is required")

    files = _iter_files(source)
    useful = [p for p in files if p.name not in {"pack.json", "README.md"}]
    if not useful:
        raise SystemExit("Pack builder rejects empty packs: add presets/templates beyond metadata.")

    manifest = get_pack_manifest(pack_id)
    required = list(manifest.install.required_files) or ["pack.json"]
    for relative in required:
        if not (source / relative).is_file():
            raise SystemExit(f"Missing required file: {relative}")

    out_dir = DIST_ROOT / pack_id / version
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{pack_id}-{version}.zip"
    meta_name = f"{pack_id}-{version}.release.json"
    zip_path = out_dir / zip_name
    meta_path = out_dir / meta_name

    # Deterministic zip: sorted paths, fixed date.
    fixed = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    size = zip_path.stat().st_size
    release = {
        "schemaVersion": 1,
        "packId": pack_id,
        "name": pack_json.get("name") or manifest.name,
        "version": version,
        "channel": channel,
        "publishedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimumStudioVersion": "0.1.0",
        "archive": {
            "assetName": zip_name,
            "format": "zip",
            "expectedBytes": size,
            "checksumAlgorithm": "sha256",
            "checksum": digest,
        },
        "install": {
            "requiredFiles": required,
        },
    }
    meta_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    return {
        "pack_id": pack_id,
        "version": version,
        "zip_path": str(zip_path),
        "release_json_path": str(meta_path),
        "expected_bytes": size,
        "checksum": digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Gen Studio Essential pack release artifacts")
    parser.add_argument("pack_id", help="Pack id, e.g. pack_essential_photoreal")
    parser.add_argument("--channel", default="stable")
    args = parser.parse_args(argv)
    result = build_pack(args.pack_id, channel=args.channel)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
