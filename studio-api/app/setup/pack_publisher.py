"""Publish built Essential pack archives to a GitHub Release (explicit, offline-safe)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .pack_builder import DIST_ROOT, build_pack
from .pack_manifests import ASSET_PACK_IDS


def _verify_artifacts(pack_id: str, version: str) -> tuple[Path, Path, dict]:
    out_dir = DIST_ROOT / pack_id / version
    zip_path = out_dir / f"{pack_id}-{version}.zip"
    meta_path = out_dir / f"{pack_id}-{version}.release.json"
    if not zip_path.is_file() or not meta_path.is_file():
        raise SystemExit(f"Missing built artifacts in {out_dir}. Run pack_builder first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    size = zip_path.stat().st_size
    if digest != meta["archive"]["checksum"]:
        raise SystemExit("Checksum mismatch between ZIP and .release.json")
    if size != int(meta["archive"]["expectedBytes"]):
        raise SystemExit("Byte size mismatch between ZIP and .release.json")
    return zip_path, meta_path, meta


def _print_manual(repo: str, tag: str, zip_path: Path, meta_path: Path) -> None:
    print("GitHub CLI (gh) was not found. Manual upload steps:")
    print(f"1. Create release {tag} on https://github.com/{repo}/releases/new")
    print(f"2. Upload: {zip_path}")
    print(f"3. Upload: {meta_path}")
    print("4. Publish the release (not as draft for stable channel).")


def publish_pack(
    pack_id: str,
    *,
    repository: str,
    tag: str,
    yes: bool = False,
    build: bool = True,
    channel: str = "stable",
) -> dict:
    if pack_id not in ASSET_PACK_IDS:
        raise SystemExit(f"Unknown pack id: {pack_id}")
    if "/" not in repository:
        raise SystemExit("--repository must be owner/name")
    if build:
        built = build_pack(pack_id, channel=channel)
        version = built["version"]
    else:
        # Infer latest version directory
        versions = sorted((DIST_ROOT / pack_id).glob("*"))
        if not versions:
            raise SystemExit("No built versions found")
        version = versions[-1].name

    zip_path, meta_path, meta = _verify_artifacts(pack_id, version)
    print(f"Publishing {pack_id}@{version} to {repository} tag {tag}")
    print(f"ZIP: {zip_path.name} ({meta['archive']['expectedBytes']} bytes)")
    print(f"SHA-256: {meta['archive']['checksum']}")
    if not yes:
        answer = input("Type 'yes' to continue: ").strip().lower()
        if answer != "yes":
            raise SystemExit("Aborted.")

    gh = shutil.which("gh")
    if not gh:
        _print_manual(repository, tag, zip_path, meta_path)
        return {
            "published": False,
            "mode": "manual",
            "repository": repository,
            "tag": tag,
            "assets": [zip_path.name, meta_path.name],
        }

    # Create release if missing, then upload assets.
    view = subprocess.run(
        [gh, "release", "view", tag, "--repo", repository],
        capture_output=True,
        text=True,
        check=False,
    )
    if view.returncode != 0:
        subprocess.run(
            [
                gh, "release", "create", tag,
                "--repo", repository,
                "--title", tag,
                "--notes", f"Gen Studio pack release {tag}",
                str(zip_path),
                str(meta_path),
            ],
            check=True,
        )
    else:
        subprocess.run(
            [gh, "release", "upload", tag, str(zip_path), str(meta_path), "--repo", repository, "--clobber"],
            check=True,
        )

    verify = subprocess.run(
        [gh, "release", "view", tag, "--repo", repository, "--json", "assets,url"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(verify.stdout)
    asset_names = [item.get("name") for item in payload.get("assets") or []]
    for name in (zip_path.name, meta_path.name):
        if name not in asset_names:
            raise SystemExit(f"Published release is missing asset {name}")
    print(f"Published: {payload.get('url')}")
    return {
        "published": True,
        "mode": "gh",
        "repository": repository,
        "tag": tag,
        "url": payload.get("url"),
        "assets": asset_names,
        "checksum": meta["archive"]["checksum"],
        "expected_bytes": meta["archive"]["expectedBytes"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Gen Studio pack artifacts to GitHub Releases")
    parser.add_argument("pack_id")
    parser.add_argument("--repository", required=True, help="owner/repository")
    parser.add_argument("--tag", required=True, help="e.g. packs-v1.0.0")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    result = publish_pack(
        args.pack_id,
        repository=args.repository,
        tag=args.tag,
        yes=args.yes,
        build=not args.no_build,
        channel=args.channel,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
