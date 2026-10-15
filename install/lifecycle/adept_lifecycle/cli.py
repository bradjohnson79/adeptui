"""Command interface shared by Windows, Linux, and macOS."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .detect import SystemProfile, live_profile
from .manager import Hooks, Layout, Lifecycle, package_install_plan
from .registry import read_registry


def main(argv: list[str] | None = None, profile: SystemProfile | None = None, key: bytes | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adeptui", description="Install, update, and remove Adept UI.")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--key")
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--no-shortcut", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Confirm uninstall in a noninteractive session.")
    parser.add_argument("--remove-models", action="store_true")
    parser.add_argument("--remove-settings", action="store_true")
    parser.add_argument("command", nargs="?", choices=("install", "update", "uninstall", "doctor", "repair"))
    args = parser.parse_args(argv)
    root = args.root or Path(os.environ.get("ADEPT_LIFECYCLE_ROOT") or Path.home() / ".adept-ui")
    layout = Layout(root)
    system = profile or live_profile(str(root))
    signing = key if key is not None else (args.key.encode("utf-8") if args.key else None)
    hooks = Hooks()
    if args.command is None and not args.version and args.catalog is None:
        hooks = _launch_hooks()
    lifecycle = Lifecycle(layout, system, signing, hooks)
    if args.version or args.command is None and not args.catalog:
        registry = read_registry(layout.registry_path)
        if args.version:
            if not registry or not registry.get("installedVersion"):
                print(f"adept-lifecycle {__version__} (not installed)")
                return 0
            print(f"Adept UI {registry['installedVersion']} ({registry.get('channel') or 'beta'})")
            return 0
        if args.command is None:
            result = lifecycle.launch()
            if os.environ.get("ADEPT_HANDOFF_MODE") == "check" and result.code == "UPDATE_AVAILABLE":
                return 10
            print(result.message)
            return 0 if result.ok else 1
        parser.print_help()
        return 0
    catalog = None
    if args.catalog:
        try:
            catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print("The release catalog could not be read.")
            return 1
    if args.command == "doctor":
        result = lifecycle.doctor()
    elif args.command == "repair":
        result = lifecycle.repair(args.payload)
    elif args.command == "uninstall":
        result = lifecycle.uninstall(
            remove_app=True,
            remove_models=bool(args.remove_models),
            remove_settings=bool(args.remove_settings),
            confirmed=bool(args.yes or not args.noninteractive and _confirm("Continue with uninstall? [y/N] ", default_no=True)),
        )
    elif args.command == "update":
        if catalog is None:
            print("An approved release catalog is required.")
            return 1
        result = lifecycle.update(catalog, args.payload, apply=bool(args.apply))
    elif args.command == "install":
        if catalog is None or args.payload is None:
            print("An approved catalog and release file are required.")
            return 1
        shortcut = not args.no_shortcut
        if not args.noninteractive:
            shortcut = _confirm("Create a desktop shortcut? [Y/n] ", default_no=False)
        result = lifecycle.install(catalog, args.payload, shortcut=shortcut, launch=bool(args.launch))
    else:
        parser.print_help()
        return 0
    print(result.message)
    return 0 if result.ok else 1


def _fetch_official_catalog() -> dict | None:
    import urllib.request

    from .trust import OFFICIAL_CATALOG_URL, OFFICIAL_SIGNATURE_URL

    try:
        with urllib.request.urlopen(OFFICIAL_CATALOG_URL, timeout=20) as response:
            raw = response.read()
        with urllib.request.urlopen(OFFICIAL_SIGNATURE_URL, timeout=20) as response:
            signature = response.read().decode("utf-8").strip()
    except OSError:
        return None
    try:
        catalog = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(catalog, dict) or not signature:
        return None
    if not signature.startswith("rsa-sha256:"):
        signature = "rsa-sha256:" + signature
    signed = dict(catalog)
    signed["signature"] = signature
    return signed


def _install_native(payload: Path, artifact: dict) -> None:
    import subprocess

    plan = package_install_plan(str(artifact.get("kind") or ""), payload)
    if not plan or plan[0] == "hdiutil":
        raise OSError("This package is not replaced by a second installer. Gatekeeper is left unchanged.")
    subprocess.run(plan, check=True)


def _launch_hooks() -> Hooks:
    return Hooks(fetch_catalog=_fetch_official_catalog, show_updater=True, install_package=_install_native)


def _confirm(prompt: str, *, default_no: bool) -> bool:
    if not sys.stdin.isatty():
        return not default_no
    answer = input(prompt).strip().lower()
    if not answer:
        return not default_no
    return answer in {"y", "yes"}
