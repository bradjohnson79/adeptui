from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backup import BackupError, create_backup, restore_backup, verify_backup


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root (default: detected from this module)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Application data directory (default: <repo-root>/data)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.safety",
        description="Create, verify, and restore Adept Phase 0 backups.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create and verify a backup")
    create.add_argument("archive", type=Path, help="New .zip archive path")
    _common_paths(create)

    verify = commands.add_parser("verify", help="Verify an existing backup")
    verify.add_argument("archive", type=Path, help="Backup archive path")

    restore = commands.add_parser(
        "restore", help="Restore into a new isolated directory"
    )
    restore.add_argument("archive", type=Path, help="Backup archive path")
    restore.add_argument(
        "destination", type=Path, help="New destination directory (must not exist)"
    )
    _common_paths(restore)
    return parser


def _summary(action: str, archive: Path, manifest: dict[str, object]) -> str:
    entries = manifest.get("entries")
    total_size = sum(
        int(item["size"])
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("size"), int)
    ) if isinstance(entries, list) else 0
    return json.dumps(
        {
            "status": "ok",
            "action": action,
            "archive": str(archive.expanduser().resolve()),
            "created_at_utc": manifest.get("created_at_utc"),
            "files": len(entries) if isinstance(entries, list) else 0,
            "uncompressed_bytes": total_size,
            "sqlite_databases": len(manifest.get("sqlite", [])),
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            repo_root = args.repo_root.expanduser().resolve()
            data_dir = (
                args.data_dir.expanduser().resolve()
                if args.data_dir is not None
                else repo_root / "data"
            )
            manifest = create_backup(
                args.archive, repo_root=repo_root, data_dir=data_dir
            )
            print(_summary("create", args.archive, manifest))
        elif args.command == "verify":
            manifest = verify_backup(args.archive)
            print(_summary("verify", args.archive, manifest))
        else:
            repo_root = args.repo_root.expanduser().resolve()
            data_dir = (
                args.data_dir.expanduser().resolve()
                if args.data_dir is not None
                else repo_root / "data"
            )
            manifest = restore_backup(
                args.archive,
                args.destination,
                repo_root=repo_root,
                data_dir=data_dir,
            )
            print(_summary("restore", args.archive, manifest))
            print(
                json.dumps(
                    {"restored_to": str(args.destination.expanduser().resolve())},
                    indent=2,
                )
            )
        return 0
    except (BackupError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
