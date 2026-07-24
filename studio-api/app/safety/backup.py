from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable

MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "adept.phase0.backup-manifest"
MANIFEST_VERSION = 1
TOOL_VERSION = "1.0.0"
BUFFER_SIZE = 1024 * 1024


class BackupError(RuntimeError):
    """Raised when a backup cannot be safely created, verified, or restored."""


@dataclass(frozen=True)
class SourceFile:
    source: Path
    archive_path: str
    category: str
    sensitive: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(BUFFER_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _validate_member_name(name: str) -> str:
    if not name or "\\" in name or "\x00" in name:
        raise BackupError("Archive contains an invalid member path")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise BackupError("Archive contains an unsafe member path")
    if pure.parts[0].endswith(":"):
        raise BackupError("Archive contains an absolute drive path")
    normalized = pure.as_posix()
    if normalized != name:
        raise BackupError("Archive contains a non-canonical member path")
    return normalized


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return bool(mode) and stat.S_ISLNK(mode)


def _safe_zip_infos(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        name = _validate_member_name(info.filename)
        if name in infos:
            raise BackupError(f"Archive has duplicate member: {name}")
        if info.is_dir() or _is_zip_symlink(info):
            raise BackupError(f"Archive has unsupported member type: {name}")
        if info.flag_bits & 0x1:
            raise BackupError(f"Archive has unsupported encrypted member: {name}")
        infos[name] = info
    return infos


def _relative_archive_path(prefix: str, relative: Path) -> str:
    parts = PurePosixPath(prefix, *relative.parts)
    return _validate_member_name(parts.as_posix())


def _walk_source(
    root: Path,
    archive_prefix: str,
    category: str,
    *,
    sensitive: bool = False,
    exclude: Iterable[Path] = (),
) -> list[SourceFile]:
    if not root.exists():
        return []
    if root.is_symlink():
        raise BackupError(f"Refusing symbolic-link source: {root}")
    if not root.is_dir():
        raise BackupError(f"Expected a directory source: {root}")

    excluded = {path.resolve() for path in exclude}
    found: list[SourceFile] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise BackupError(f"Refusing symbolic link in backup source: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise BackupError(f"Refusing non-regular backup source: {path}")
        if path.resolve() in excluded:
            continue
        relative = path.relative_to(root)
        entry_sensitive = sensitive or (
            len(relative.parts) > 0 and relative.parts[0].casefold() == "secrets"
        )
        found.append(
            SourceFile(
                path,
                _relative_archive_path(archive_prefix, relative),
                category,
                entry_sensitive,
            )
        )
    return found


def _copy_stream(source: BinaryIO, destination: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(BUFFER_SIZE):
        destination.write(chunk)
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _write_source(
    archive: zipfile.ZipFile, source: SourceFile
) -> dict[str, object]:
    info = zipfile.ZipInfo(source.archive_path)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.create_system = 3
    with source.source.open("rb") as input_stream, archive.open(info, "w") as output_stream:
        checksum, size = _copy_stream(input_stream, output_stream)
    return {
        "path": source.archive_path,
        "size": size,
        "sha256": checksum,
        "category": source.category,
        "sensitive": source.sensitive,
    }


def _sqlite_integrity(path: Path) -> None:
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        raise BackupError(f"SQLite integrity check could not run: {exc}") from exc
    results = [str(row[0]) for row in rows]
    if results != ["ok"]:
        raise BackupError("SQLite integrity check failed: " + "; ".join(results))


def _backup_sqlite(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise BackupError("SQLite source must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source_uri = source.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as source_db:
            with closing(sqlite3.connect(destination)) as destination_db:
                source_db.backup(destination_db)
    except sqlite3.Error as exc:
        raise BackupError(f"SQLite backup failed: {exc}") from exc
    _sqlite_integrity(destination)


def _default_repo_sources(repo_root: Path) -> list[SourceFile]:
    sources: list[SourceFile] = []
    directory_specs = (
        (repo_root / "workflows", "repository/workflows", "workflow-metadata"),
        (
            repo_root / "studio-api" / "app" / "workflows",
            "repository/studio-api/app/workflows",
            "workflow-code",
        ),
        (
            repo_root / "studio-api" / "knowledgebase",
            "repository/studio-api/knowledgebase",
            "knowledgebase",
        ),
    )
    for source, prefix, category in directory_specs:
        sources.extend(_walk_source(source, prefix, category))

    file_specs = (
        ("studio-api/app/imagegen_workflows.py", "workflow-code", False),
        ("studio-api/app/config.py", "settings-definition", False),
    )
    for relative, category, sensitive in file_specs:
        source = repo_root / Path(relative)
        if source.exists():
            if source.is_symlink() or not source.is_file():
                raise BackupError(f"Refusing non-regular backup source: {source}")
            sources.append(
                SourceFile(
                    source,
                    _relative_archive_path("repository", Path(relative)),
                    category,
                    sensitive,
                )
            )

    sample_names = ("samples", "sample-projects", "sample_projects", "examples")
    for name in sample_names:
        source = repo_root / name
        sources.extend(
            _walk_source(source, f"repository/{name}", "sample-projects")
        )

    # Environment files are opaque, sensitive settings. Their bytes are never parsed.
    for parent_name in ("", "studio-api", "studio-web"):
        parent = repo_root / parent_name
        if not parent.is_dir():
            continue
        for name in (".env", ".env.local", ".env.production"):
            source = parent / name
            if source.exists():
                if source.is_symlink() or not source.is_file():
                    raise BackupError(f"Refusing non-regular settings file: {source}")
                relative = source.relative_to(repo_root)
                sources.append(
                    SourceFile(
                        source,
                        _relative_archive_path("repository", relative),
                        "settings",
                        True,
                    )
                )
    return sources


def create_backup(
    output: Path,
    *,
    repo_root: Path,
    data_dir: Path,
) -> dict[str, object]:
    """Create a verified archive without changing source data."""
    output = output.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()
    database = data_dir / "studio.db"
    if not repo_root.is_dir():
        raise BackupError(f"Repository root does not exist: {repo_root}")
    if not data_dir.is_dir():
        raise BackupError(f"Data directory does not exist: {data_dir}")
    if output.exists():
        raise BackupError(f"Refusing to overwrite existing archive: {output}")
    if output == database:
        raise BackupError("Backup output cannot be the source database")
    output.parent.mkdir(parents=True, exist_ok=True)

    temp_archive: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="adept-backup-") as temporary:
            staging = Path(temporary)
            sources = _walk_source(
                data_dir,
                "data",
                "application-data",
                exclude=(
                    database,
                    data_dir / "studio.db-wal",
                    data_dir / "studio.db-shm",
                    data_dir / "studio.db-journal",
                ),
            )
            sqlite_entries: list[dict[str, object]] = []
            if database.exists():
                staged_database = staging / "studio.db"
                _backup_sqlite(database, staged_database)
                sources.append(
                    SourceFile(
                        staged_database,
                        "data/studio.db",
                        "sqlite",
                        False,
                    )
                )
                sqlite_entries.append(
                    {"path": "data/studio.db", "integrity_check": "ok"}
                )
            sources.extend(_default_repo_sources(repo_root))

            paths: set[str] = set()
            for source in sources:
                if source.archive_path in paths:
                    raise BackupError(
                        f"Two sources map to archive path: {source.archive_path}"
                    )
                paths.add(source.archive_path)

            handle, temp_name = tempfile.mkstemp(
                prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
            )
            os.close(handle)
            temp_archive = Path(temp_name)
            entries: list[dict[str, object]] = []
            with zipfile.ZipFile(
                temp_archive,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            ) as archive:
                for source in sorted(sources, key=lambda item: item.archive_path):
                    entries.append(_write_source(archive, source))
                manifest: dict[str, object] = {
                    "schema": MANIFEST_SCHEMA,
                    "schema_version": MANIFEST_VERSION,
                    "tool_version": TOOL_VERSION,
                    "created_at_utc": _utc_now(),
                    "archive_format": "zip",
                    "hash_algorithm": "sha256",
                    "entries": entries,
                    "sqlite": sqlite_entries,
                }
                manifest_bytes = (
                    json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
                    + b"\n"
                )
                manifest_info = zipfile.ZipInfo(MANIFEST_NAME)
                manifest_info.compress_type = zipfile.ZIP_DEFLATED
                manifest_info.external_attr = (stat.S_IFREG | 0o600) << 16
                manifest_info.create_system = 3
                archive.writestr(manifest_info, manifest_bytes)

            verify_backup(temp_archive)
            os.replace(temp_archive, output)
            temp_archive = None
            return manifest
    except Exception:
        if temp_archive is not None:
            temp_archive.unlink(missing_ok=True)
        raise


def _load_manifest(
    archive: zipfile.ZipFile, infos: dict[str, zipfile.ZipInfo]
) -> dict[str, object]:
    info = infos.get(MANIFEST_NAME)
    if info is None:
        raise BackupError("Archive does not contain manifest.json")
    if info.file_size > 16 * 1024 * 1024:
        raise BackupError("Manifest is unexpectedly large")
    try:
        manifest = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise BackupError("Manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise BackupError("Manifest root must be an object")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise BackupError("Unsupported backup manifest schema")
    if manifest.get("schema_version") != MANIFEST_VERSION:
        raise BackupError("Unsupported backup manifest version")
    if manifest.get("archive_format") != "zip":
        raise BackupError("Manifest archive format does not match")
    if manifest.get("hash_algorithm") != "sha256":
        raise BackupError("Unsupported manifest hash algorithm")
    return manifest


def _validated_entries(
    manifest: dict[str, object], infos: dict[str, zipfile.ZipInfo]
) -> list[dict[str, object]]:
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise BackupError("Manifest entries must be a list")
    entries: list[dict[str, object]] = []
    manifest_paths: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise BackupError("Manifest entry must be an object")
        path = raw.get("path")
        size = raw.get("size")
        checksum = raw.get("sha256")
        if not isinstance(path, str):
            raise BackupError("Manifest entry path must be a string")
        path = _validate_member_name(path)
        if path == MANIFEST_NAME or path in manifest_paths:
            raise BackupError(f"Manifest contains duplicate path: {path}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise BackupError(f"Manifest contains invalid size for: {path}")
        if (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in "0123456789abcdef" for character in checksum)
        ):
            raise BackupError(f"Manifest contains invalid SHA-256 for: {path}")
        manifest_paths.add(path)
        entries.append(raw)

    archive_paths = set(infos) - {MANIFEST_NAME}
    if manifest_paths != archive_paths:
        missing = sorted(manifest_paths - archive_paths)
        extra = sorted(archive_paths - manifest_paths)
        details = []
        if missing:
            details.append(f"missing {len(missing)} member(s)")
        if extra:
            details.append(f"unlisted {len(extra)} member(s)")
        raise BackupError("Archive and manifest differ: " + ", ".join(details))
    return entries


def _verify_entry(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    expected_size: int,
    expected_hash: str,
) -> None:
    if info.file_size != expected_size:
        raise BackupError(f"Size mismatch for: {info.filename}")
    digest = hashlib.sha256()
    size = 0
    try:
        with archive.open(info, "r") as stream:
            while chunk := stream.read(BUFFER_SIZE):
                digest.update(chunk)
                size += len(chunk)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise BackupError(f"Could not read archive member: {info.filename}") from exc
    if size != expected_size or digest.hexdigest() != expected_hash:
        raise BackupError(f"Checksum mismatch for: {info.filename}")


def _manifest_sqlite_paths(manifest: dict[str, object]) -> list[str]:
    raw_sqlite = manifest.get("sqlite")
    if not isinstance(raw_sqlite, list):
        raise BackupError("Manifest sqlite metadata must be a list")
    result: list[str] = []
    for item in raw_sqlite:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise BackupError("Manifest SQLite metadata is invalid")
        path = _validate_member_name(item["path"])
        if item.get("integrity_check") != "ok":
            raise BackupError(f"SQLite was not healthy when backed up: {path}")
        result.append(path)
    if len(result) != len(set(result)):
        raise BackupError("Manifest has duplicate SQLite paths")
    return result


def verify_backup(archive_path: Path) -> dict[str, object]:
    """Verify member safety, manifest parity, all hashes, and SQLite integrity."""
    archive_path = archive_path.expanduser().resolve()
    if archive_path.is_symlink() or not archive_path.is_file():
        raise BackupError(f"Backup archive does not exist: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            infos = _safe_zip_infos(archive)
            manifest = _load_manifest(archive, infos)
            entries = _validated_entries(manifest, infos)
            for entry in entries:
                path = str(entry["path"])
                _verify_entry(
                    archive,
                    infos[path],
                    int(entry["size"]),
                    str(entry["sha256"]),
                )
            sqlite_paths = _manifest_sqlite_paths(manifest)
            with tempfile.TemporaryDirectory(prefix="adept-verify-") as temporary:
                root = Path(temporary)
                for index, sqlite_path in enumerate(sqlite_paths):
                    target = root / f"database-{index}.sqlite"
                    with archive.open(infos[sqlite_path], "r") as source:
                        with target.open("xb") as destination:
                            shutil.copyfileobj(source, destination, BUFFER_SIZE)
                    _sqlite_integrity(target)
            return manifest
    except zipfile.BadZipFile as exc:
        raise BackupError("Backup is not a valid ZIP archive") from exc


def _ensure_isolated_destination(
    destination: Path, *, repo_root: Path | None, data_dir: Path | None
) -> Path:
    destination = destination.expanduser().resolve()
    protected = [
        path.expanduser().resolve()
        for path in (repo_root, data_dir)
        if path is not None
    ]
    if destination in protected:
        raise BackupError("Restore destination must be separate from live paths")
    for path in protected:
        if path in destination.parents or destination in path.parents:
            raise BackupError(
                "Restore destination cannot contain, or be inside, a live path"
            )
    if destination.exists():
        raise BackupError("Restore destination must not already exist")
    return destination


def restore_backup(
    archive_path: Path,
    destination: Path,
    *,
    repo_root: Path | None = None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Restore only into an isolated, empty destination and verify the result."""
    archive_path = archive_path.expanduser().resolve()
    destination = _ensure_isolated_destination(
        destination, repo_root=repo_root, data_dir=data_dir
    )
    manifest = verify_backup(archive_path)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            infos = _safe_zip_infos(archive)
            entries = _validated_entries(manifest, infos)
            for entry in entries:
                relative = PurePosixPath(str(entry["path"]))
                target = destination.joinpath(*relative.parts)
                resolved_target = target.resolve()
                if destination != resolved_target and destination not in resolved_target.parents:
                    raise BackupError("Restore member escaped destination")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise BackupError(f"Refusing to overwrite restore file: {relative}")
                with archive.open(infos[str(entry["path"])], "r") as source:
                    with target.open("xb") as output:
                        shutil.copyfileobj(source, output, BUFFER_SIZE)

        for entry in manifest["entries"]:  # type: ignore[index]
            path = destination.joinpath(*PurePosixPath(str(entry["path"])).parts)
            checksum, size = _sha256_file(path)
            if size != entry["size"] or checksum != entry["sha256"]:
                raise BackupError(f"Restored file mismatch: {entry['path']}")
        for sqlite_path in _manifest_sqlite_paths(manifest):
            _sqlite_integrity(
                destination.joinpath(*PurePosixPath(sqlite_path).parts)
            )
        return manifest
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
