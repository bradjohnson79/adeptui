"""Download Sources orchestration: detect, verify, overrides, guided CLI install."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..pack_manifests import set_source_override
from ..state import load_state, update_state
from .cli_detect import (
    detect_github_cli,
    detect_huggingface_cli,
    detect_package_managers_windows,
)
from .overrides import get_override, list_overrides, remove_override, save_override
from .security import SourceSecurityError, assert_host_not_private_after_dns, validate_remote_url
from .url_parse import NormalizedSource, parse_source_url

# Re-export override helpers for package API
save_source_override = save_override
remove_source_override = remove_override


def detect_download_sources(*, force: bool = False) -> dict[str, Any]:
    github = detect_github_cli()
    huggingface = detect_huggingface_cli()
    payload = {
        "github": github.to_dict(),
        "huggingface": huggingface.to_dict(),
        "package_managers": detect_package_managers_windows() if os.name == "nt" else [],
        "overrides": list_overrides(),
        "messages": {
            "discovery_failed": (
                "Automatic source discovery did not find a compatible download."
            ),
            "add_source_help": (
                "Paste a GitHub or Hugging Face repository, release, asset, or file URL. "
                "Adept UI will inspect it before downloading."
            ),
        },
    }
    if force or True:
        update_state(
            lambda state: state.setdefault("download_sources", {}).update(
                {
                    "github": {
                        "status": github.status,
                        "last_verified_at": github.last_verified_at,
                        "cli_detected": github.cli_detected,
                        "authenticated": github.authenticated,
                    },
                    "huggingface": {
                        "status": huggingface.status,
                        "last_verified_at": huggingface.last_verified_at,
                        "cli_detected": huggingface.cli_detected,
                        "authenticated": huggingface.authenticated,
                    },
                }
            )
        )
    return payload


def start_cli_sign_in(provider: str) -> dict[str, Any]:
    """Return a guided sign-in command; does not capture tokens."""
    provider = (provider or "").strip().lower()
    if provider == "github":
        gh = detect_github_cli()
        exe = gh.executable_path or "gh"
        return {
            "provider": "github",
            "command": [exe, "auth", "login"],
            "command_summary": "gh auth login",
            "requires_confirmation": True,
            "message": (
                "Sign in with GitHub CLI in a terminal. Adept UI never displays or stores your token."
            ),
            "cli": gh.to_dict(),
        }
    if provider in {"huggingface", "hf"}:
        hf = detect_huggingface_cli()
        exe = hf.executable_path or hf.executable_name or "hf"
        return {
            "provider": "huggingface",
            "command": [exe, "auth", "login"],
            "command_summary": f"{hf.executable_name or 'hf'} auth login",
            "requires_confirmation": True,
            "message": (
                "Sign in with the Hugging Face CLI in a terminal. Adept UI never displays or stores your token."
            ),
            "cli": hf.to_dict(),
        }
    raise ValueError(f"Unknown provider: {provider}")


def install_cli(provider: str, *, confirm: bool = False, method: str | None = None) -> dict[str, Any]:
    """Guided CLI install. Requires confirm=True. Captures exit code; redacts secrets."""
    if not confirm:
        plan = _install_plan(provider, method=method)
        plan["requires_confirmation"] = True
        plan["executed"] = False
        return plan

    plan = _install_plan(provider, method=method)
    cmd = plan.get("command") or []
    if not cmd:
        raise ValueError(plan.get("message") or "No install command available.")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            shell=False,
        )
        code = proc.returncode
        # Redact anything that looks like a token
        stdout = _redact(proc.stdout or "")
        stderr = _redact(proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return {
            **plan,
            "executed": True,
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": _redact(str(exc)[:500]),
            "detection": detect_download_sources(force=True),
        }
    detection = detect_download_sources(force=True)
    return {
        **plan,
        "executed": True,
        "ok": code == 0,
        "exit_code": code,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "detection": detection,
    }


def _install_plan(provider: str, *, method: str | None = None) -> dict[str, Any]:
    provider = (provider or "").strip().lower()
    managers = detect_package_managers_windows() if os.name == "nt" else []
    if provider == "github":
        if method == "winget" or (not method and "winget" in managers):
            cmd = ["winget", "install", "--id", "GitHub.cli", "-e", "--accept-source-agreements", "--accept-package-agreements"]
            return {
                "provider": "github",
                "method": "winget",
                "command": cmd,
                "command_summary": "winget install --id GitHub.cli -e",
                "target_environment": "system (winget)",
                "may_require_elevation": True,
                "message": "Install GitHub CLI via winget.",
            }
        if method == "choco" or (not method and "choco" in managers):
            return {
                "provider": "github",
                "method": "choco",
                "command": ["choco", "install", "gh", "-y"],
                "command_summary": "choco install gh -y",
                "target_environment": "system (Chocolatey)",
                "may_require_elevation": True,
                "message": "Install GitHub CLI via Chocolatey.",
            }
        return {
            "provider": "github",
            "method": "manual",
            "command": [],
            "command_summary": None,
            "target_environment": None,
            "may_require_elevation": False,
            "message": "Install GitHub CLI from https://cli.github.com/ then click Detect CLI.",
            "help_url": "https://cli.github.com/",
        }
    if provider in {"huggingface", "hf"}:
        python = sys.executable
        cmd = [python, "-m", "pip", "install", "--upgrade", "huggingface_hub[cli]"]
        return {
            "provider": "huggingface",
            "method": "pip_venv",
            "command": cmd,
            "command_summary": f"{python} -m pip install --upgrade 'huggingface_hub[cli]'",
            "target_environment": python,
            "may_require_elevation": False,
            "message": "Install Hugging Face Hub CLI into the Adept UI Python environment.",
        }
    raise ValueError(f"Unknown provider: {provider}")


def verify_source_url(
    *,
    url: str,
    component_id: str | None = None,
    revision: str | None = None,
    asset_name: str | None = None,
    selected_files: list[str] | None = None,
) -> dict[str, Any]:
    """Parse + inspect a source URL without downloading payloads."""
    warnings: list[str] = []
    blocking: list[str] = []
    try:
        normalized = parse_source_url(url)
    except SourceSecurityError as exc:
        return {
            "ok": False,
            "blocking_errors": [{"code": exc.code, "message": exc.message}],
            "warnings": [],
            "source": None,
            "files": [],
            "compatibility": "blocked",
            "message": exc.message,
        }

    if revision:
        if normalized.provider == "huggingface":
            normalized.revision = revision
        elif normalized.provider == "github":
            normalized.release_tag = revision
    if asset_name:
        normalized.asset_name = asset_name
    if selected_files:
        normalized.include_patterns = list(selected_files)

    host = urlparse(normalized.source_url).hostname
    try:
        if host and host not in {"localhost", "127.0.0.1"}:
            assert_host_not_private_after_dns(host)
    except SourceSecurityError as exc:
        blocking.append(exc.message)

    files: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    auth_required = False
    size = None

    if normalized.provider == "github":
        files, metadata, auth_required, size, warnings, blocking = _verify_github(
            normalized, warnings, blocking
        )
    elif normalized.provider == "huggingface":
        files, metadata, auth_required, size, warnings, blocking = _verify_huggingface(
            normalized, warnings, blocking
        )

    if normalized.kind in {"branch_archive", "tag_archive"}:
        warnings.append(
            "This looks like a source archive. Packaged release assets are preferred for Essential packs."
        )
        if component_id and component_id.startswith("pack_"):
            blocking.append(
                "Source archives are not accepted as verified Essential packs. "
                "Choose a release asset or use Link Existing Folder."
            )

    fingerprint = hashlib.sha256(
        f"{normalized.provider}|{normalized.source_url}|{normalized.release_tag or normalized.revision}|{normalized.asset_name or normalized.file_path}".encode()
    ).hexdigest()[:24]

    ok = not blocking
    return {
        "ok": ok,
        "compatibility": "compatible" if ok else "blocked",
        "source": normalized.to_dict(),
        "provider": normalized.provider,
        "repository": normalized.repository_id
        or (f"{normalized.owner}/{normalized.repository}" if normalized.owner else None),
        "revision": normalized.revision or normalized.release_tag or normalized.branch,
        "selected_file": normalized.asset_name or normalized.file_path,
        "size": size,
        "checksum": metadata.get("checksum"),
        "authentication_status": "required" if auth_required else "not_required",
        "authentication_required": auth_required,
        "expected_destination": None,
        "installation_method": _install_method_for(normalized),
        "files": files,
        "warnings": warnings,
        "blocking_errors": [{"code": "verify_blocked", "message": m} for m in blocking],
        "verification_fingerprint": fingerprint,
        "message": (
            "Source looks valid. Review the summary before downloading."
            if ok
            else "Source verification found problems that must be fixed before install."
        ),
        "component_id": component_id,
    }


def list_source_files(url: str, *, revision: str | None = None) -> dict[str, Any]:
    result = verify_source_url(url=url, revision=revision)
    return {
        "ok": result.get("ok"),
        "files": result.get("files") or [],
        "source": result.get("source"),
        "warnings": result.get("warnings") or [],
        "blocking_errors": result.get("blocking_errors") or [],
    }


def apply_verified_override(component_id: str, verification: dict[str, Any]) -> dict[str, Any]:
    """Persist override + dual-write normalized Source Manager records (Phase 1A)."""
    if not verification.get("ok"):
        raise ValueError("Cannot save an unverified source override.")
    source = verification.get("source") or {}
    url = source.get("source_url") or source.get("resolved_download_url")
    if not url:
        raise ValueError("Verified source is missing a URL.")
    validate_remote_url(url)
    try:
        from ...source_manager.service import save_verified_source_for_component

        result = save_verified_source_for_component(component_id, verification)
        return result.get("override") or {}
    except Exception:
        # Fallback preserves Phase 0.5 behavior if Source Manager import fails
        set_source_override(component_id, url)
        return save_override(
            component_id,
            {
                "provider": source.get("provider"),
                "sourceUrl": url,
                "repository": verification.get("repository"),
                "revision": verification.get("revision"),
                "selectedFiles": [verification["selected_file"]] if verification.get("selected_file") else [],
                "assetName": source.get("asset_name"),
                "installMethod": verification.get("installation_method"),
                "verifiedAt": None,
                "verificationFingerprint": verification.get("verification_fingerprint"),
            },
        )


def _install_method_for(source: NormalizedSource) -> str:
    if source.provider == "github":
        gh = detect_github_cli()
        if gh.cli_detected and gh.authenticated:
            return "github_cli"
        return "github_api" if source.kind != "release_asset" else "direct_http"
    if source.provider == "huggingface":
        hf = detect_huggingface_cli()
        if hf.cli_detected:
            return "hf_cli"
        return "direct_http"
    return "direct_http"


def _verify_github(
    source: NormalizedSource,
    warnings: list[str],
    blocking: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], bool, int | None, list[str], list[str]]:
    files: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    auth_required = False
    size = None
    owner, repo = source.owner, source.repository
    if not owner or not repo:
        blocking.append("GitHub owner/repository could not be determined.")
        return files, metadata, auth_required, size, warnings, blocking

    # Prefer gh api when available
    gh = detect_github_cli()
    if source.kind == "release_asset" and source.resolved_download_url:
        files.append(
            {
                "name": source.asset_name,
                "path": source.asset_name,
                "size": None,
                "kind": "release_asset",
                "download_url": source.resolved_download_url,
            }
        )
        # HEAD request for size (no body)
        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                resp = client.head(source.resolved_download_url)
                if resp.status_code in {301, 302, 303, 307, 308}:
                    loc = resp.headers.get("location") or ""
                    loc_host = urlparse(loc).hostname
                    from .security import validate_redirect_host

                    validate_redirect_host(loc_host)
                if resp.status_code == 404:
                    blocking.append("Release asset was not found (HTTP 404).")
                elif resp.status_code in {401, 403}:
                    auth_required = True
                    warnings.append("This asset may require GitHub authentication.")
                cl = resp.headers.get("content-length")
                if cl and cl.isdigit():
                    size = int(cl)
                    if size < 64:
                        warnings.append("Download is unexpectedly small; it may be an error page.")
        except SourceSecurityError as exc:
            blocking.append(exc.message)
        except httpx.HTTPError as exc:
            warnings.append(f"Could not probe asset headers: {exc}")
        return files, metadata, auth_required, size, warnings, blocking

    # List releases via gh or anonymous API
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AdeptUI-DownloadSources/1.0"}
    try:
        if gh.cli_detected and gh.executable_path:
            proc = subprocess.run(
                [gh.executable_path, "api", f"repos/{owner}/{repo}/releases", "--jq", ".[:10]"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json

                releases = json.loads(proc.stdout)
            else:
                releases = None
                if proc.returncode != 0:
                    warnings.append("GitHub CLI release listing failed; trying anonymous API.")
        else:
            releases = None
        if releases is None:
            with httpx.Client(timeout=20.0, headers=headers) as client:
                resp = client.get(api_url)
                if resp.status_code in {401, 403}:
                    auth_required = True
                    blocking.append("Repository releases require authentication.")
                    return files, metadata, auth_required, size, warnings, blocking
                if resp.status_code == 404:
                    blocking.append("Repository was not found or has no public releases.")
                    return files, metadata, auth_required, size, warnings, blocking
                resp.raise_for_status()
                releases = resp.json()
        if not releases:
            blocking.append("Repository has no releases.")
            return files, metadata, auth_required, size, warnings, blocking
        selected = None
        if source.release_tag:
            selected = next((r for r in releases if r.get("tag_name") == source.release_tag), None)
            if selected is None:
                blocking.append(f"Release tag '{source.release_tag}' was not found.")
        else:
            selected = releases[0]
        if selected:
            metadata["tag_name"] = selected.get("tag_name")
            assets = selected.get("assets") or []
            if not assets:
                warnings.append("Selected release has no assets.")
            for asset in assets:
                files.append(
                    {
                        "name": asset.get("name"),
                        "path": asset.get("name"),
                        "size": asset.get("size"),
                        "kind": "release_asset",
                        "download_url": asset.get("browser_download_url"),
                    }
                )
            if source.asset_name:
                match = next((f for f in files if f.get("name") == source.asset_name), None)
                if not match:
                    blocking.append(f"Asset '{source.asset_name}' was not found in the release.")
                else:
                    size = match.get("size")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"GitHub verification incomplete: {exc}")
    return files, metadata, auth_required, size, warnings, blocking


def _verify_huggingface(
    source: NormalizedSource,
    warnings: list[str],
    blocking: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], bool, int | None, list[str], list[str]]:
    files: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    auth_required = False
    size = None
    repo_id = source.repository_id
    if not repo_id:
        blocking.append("Hugging Face repository id could not be determined.")
        return files, metadata, auth_required, size, warnings, blocking

    rev = source.revision or "main"
    api = f"https://huggingface.co/api/models/{repo_id}/tree/{rev}"
    headers = {"User-Agent": "AdeptUI-DownloadSources/1.0"}
    try:
        with httpx.Client(timeout=25.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(api)
            if resp.status_code in {401, 403}:
                auth_required = True
                warnings.append("This repository may be gated or private — sign in to Hugging Face.")
            if resp.status_code == 404:
                # try dataset
                api = f"https://huggingface.co/api/datasets/{repo_id}/tree/{rev}"
                resp = client.get(api)
            if resp.status_code >= 400:
                blocking.append(f"Hugging Face repository lookup failed (HTTP {resp.status_code}).")
                return files, metadata, auth_required, size, warnings, blocking
            entries = resp.json()
            if not isinstance(entries, list):
                blocking.append("Unexpected Hugging Face API response.")
                return files, metadata, auth_required, size, warnings, blocking
            for entry in entries[:200]:
                if not isinstance(entry, dict):
                    continue
                path = entry.get("path") or entry.get("rfilename")
                if not path:
                    continue
                files.append(
                    {
                        "name": path.split("/")[-1],
                        "path": path,
                        "size": entry.get("size"),
                        "kind": entry.get("type") or "file",
                    }
                )
            if source.file_path:
                match = next((f for f in files if f.get("path") == source.file_path), None)
                if not match:
                    # Still allow — file list may be truncated; probe resolve URL
                    resolve = (
                        f"https://huggingface.co/{repo_id}/resolve/{rev}/{source.file_path}"
                    )
                    head = client.head(resolve)
                    if head.status_code == 404:
                        blocking.append(f"File '{source.file_path}' was not found.")
                    elif head.status_code in {401, 403}:
                        auth_required = True
                    else:
                        files.append(
                            {
                                "name": source.file_path.split("/")[-1],
                                "path": source.file_path,
                                "size": int(head.headers["content-length"])
                                if head.headers.get("content-length", "").isdigit()
                                else None,
                                "kind": "file",
                            }
                        )
                else:
                    size = match.get("size")
                    # Detect tiny LFS pointer sizes (~130 bytes)
                    if isinstance(size, int) and 50 <= size <= 200:
                        warnings.append(
                            "Selected file size looks like a Git LFS pointer. "
                            "Use the Hugging Face CLI so LFS content is fetched."
                        )
    except httpx.HTTPError as exc:
        warnings.append(f"Hugging Face verification incomplete: {exc}")
    return files, metadata, auth_required, size, warnings, blocking


def _redact(text: str) -> str:
    import re

    out = text
    out = re.sub(r"(?i)(authorization:\s*)\S+", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)(token[\"'=\s:]+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", out)
    out = re.sub(r"ghp_[A-Za-z0-9]{20,}", "[REDACTED]", out)
    out = re.sub(r"hf_[A-Za-z0-9]{20,}", "[REDACTED]", out)
    return out
