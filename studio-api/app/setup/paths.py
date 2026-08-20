"""Suggested and browsable install paths for Setup Wizard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from ..config import settings
from ..avatar_runtimes import is_avatar_runtime_component, runtime_root as avatar_runtime_root
from .catalog import COMPONENTS, get_component


PathMode = Literal["directory", "file"]


def default_models_root() -> Path:
    """Prefer the Comfy shared models folder, otherwise studio data/models."""
    comfy_models = getattr(settings, "comfy_models_dir", None)
    if comfy_models:
        path = Path(comfy_models).expanduser()
        if path.exists():
            return path
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            pass

    comfy_input = getattr(settings, "comfy_input_dir", None)
    if comfy_input:
        shared_root = Path(comfy_input).expanduser().resolve().parent
        shared_models = shared_root / "models"
        if shared_models.exists():
            return shared_models
        # When Comfy Desktop Shared is present, create its models folder instead of
        # silently falling back to studio data/models (which looks like the wrong place).
        if shared_root.exists():
            try:
                shared_models.mkdir(parents=True, exist_ok=True)
                return shared_models
            except OSError:
                pass

    root = settings.data_dir / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def recommended_pack_path(component_id: str) -> Path:
    """Return the recommended pack destination without creating it."""
    from .pack_manifests import get_pack_manifest, is_asset_pack

    models = default_models_root()
    if is_asset_pack(component_id):
        relative = get_pack_manifest(component_id).install.recommended_path.replace("\\", "/")
        return models / Path(relative)
    return models / "creative_assets" / component_id.removeprefix("pack_")


def suggested_install_path(component_id: str) -> str:
    """Return the Adept-recommended path for a component.

    Asset packs return a recommended path string without creating empty folders.
    Other path_link components may still ensure folders exist.
    """
    component = get_component(component_id)
    if component_id == "magi_gpu_upscale" or component.installer == "realesrgan_ncnn":
        return str(Path(settings.data_dir) / "runtimes" / "realesrgan-ncnn-vulkan")
    if is_avatar_runtime_component(component_id):
        return str(avatar_runtime_root(component_id))
    if component.installer == "asset_pack":
        return str(recommended_pack_path(component_id))
    return str(ensure_suggested_path(component_id))


def ensure_suggested_path(component_id: str) -> Path:
    """Create (if needed) and return the Adept-recommended path for a component."""
    component = get_component(component_id)
    if is_avatar_runtime_component(component_id):
        root = avatar_runtime_root(component_id)
        root.mkdir(parents=True, exist_ok=True)
        return root
    if component_id == "magi_gpu_upscale" or component.installer == "realesrgan_ncnn":
        root = Path(settings.data_dir) / "runtimes" / "realesrgan-ncnn-vulkan"
        root.mkdir(parents=True, exist_ok=True)
        return root
    models = default_models_root()
    models.mkdir(parents=True, exist_ok=True)

    if component.id == "ltx_checkpoint":
        for folder in ("checkpoints", "diffusion_models"):
            candidate = models / folder
            if candidate.is_dir():
                return candidate
        checkpoints = models / "checkpoints"
        checkpoints.mkdir(parents=True, exist_ok=True)
        return checkpoints

    if component.id == "ltx_2_5_checkpoint":
        for folder in ("diffusion_models", "checkpoints"):
            candidate = models / folder
            if candidate.is_dir():
                return candidate
        diffusion = models / "diffusion_models"
        diffusion.mkdir(parents=True, exist_ok=True)
        return diffusion

    if component.id == "ltx_2_5_text_encoder":
        for folder in ("text_encoders", "clip"):
            candidate = models / folder
            if candidate.is_dir():
                return candidate
        text_encoders = models / "text_encoders"
        text_encoders.mkdir(parents=True, exist_ok=True)
        return text_encoders

    if component.id in ("ltx_2_5_video_vae", "ltx_2_5_audio_vae"):
        vae = models / "vae"
        vae.mkdir(parents=True, exist_ok=True)
        return vae

    if component.id == "ltx_2_5_spatial_upscaler":
        latent = models / "latent_upscale_models"
        latent.mkdir(parents=True, exist_ok=True)
        return latent

    if component.id == "wan_models":
        return models

    if component.id == "ltx23_ic_lora_ingredients" or component.verifier == "ic_lora_file":
        loras = models / "loras"
        loras.mkdir(parents=True, exist_ok=True)
        return loras

    if component.installer == "asset_pack" or component.id.startswith("pack_"):
        # Never mkdir empty Essential pack destinations here.
        return recommended_pack_path(component_id)

    return models


def path_selector_mode(component_id: str) -> PathMode:
    component = get_component(component_id)
    if component.verifier in ("ltx_file", "ltx_2_5_file", "ic_lora_file"):
        return "file"
    return "directory"


def uses_auto_config_path(component_id: str) -> bool:
    """True when Adept can safely invent a default configured directory.

    File-based model links (LTX), broad model roots (WAN), and downloadable
    asset packs are left unbound so empty folders are never treated as installs.
    """
    component = get_component(component_id)
    if component.installer == "asset_pack":
        return False
    return (
        component.installer == "path_link"
        and component.verifier == "linked_files"
        and path_selector_mode(component_id) == "directory"
    )


def ensure_path_exists(path: Path, *, mode: PathMode) -> Path:
    """Create missing directories for configured paths. File mode never invents files."""
    expanded = path.expanduser()
    if mode == "directory":
        expanded.mkdir(parents=True, exist_ok=True)
        return expanded
    expanded.parent.mkdir(parents=True, exist_ok=True)
    return expanded


def is_adept_managed_path(path: Path) -> bool:
    """Return True when path sits under Adept/Comfy model roots we own."""
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser()
    roots = [default_models_root(), settings.data_dir / "models"]
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def ensure_configured_paths(state: dict[str, Any]) -> dict[str, str]:
    """Auto-create and bind obvious Adept config paths; recreate missing managed dirs.

    Returns locations that were newly written into ``state["model_locations"]``.
    """
    locations = state.setdefault("model_locations", {})
    created: dict[str, str] = {}

    for component in COMPONENTS:
        component_id = component.id
        current = str(locations.get(component_id) or "").strip()

        if current:
            path = Path(current).expanduser()
            mode = path_selector_mode(component_id)
            # Asset packs must not recreate empty destinations on status refresh.
            if (
                mode == "directory"
                and not path.exists()
                and is_adept_managed_path(path)
                and component.installer != "asset_pack"
            ):
                path.mkdir(parents=True, exist_ok=True)
            continue

        if not uses_auto_config_path(component_id):
            continue

        path = ensure_suggested_path(component_id)
        value = str(path)
        locations[component_id] = value
        created[component_id] = value

    return created


def browse_path(
    *,
    mode: PathMode = "directory",
    start_dir: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Open a native OS file or folder picker and return the selected path."""
    start = Path(start_dir).expanduser() if start_dir else default_models_root()
    if start.is_file():
        start = start.parent
    if not start.exists():
        start = default_models_root()

    if sys.platform == "win32":
        selected = _browse_windows(mode=mode, start_dir=start, title=title or "Select path")
    else:
        selected = _browse_tk(mode=mode, start_dir=start, title=title or "Select path")

    if not selected:
        return {"path": None, "cancelled": True}
    return {"path": selected, "cancelled": False}


def _browse_windows(*, mode: PathMode, start_dir: Path, title: str) -> str | None:
    if mode == "directory":
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = @'
{title}
'@
$dialog.SelectedPath = @'
{str(start_dir)}
'@
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  [Console]::Out.Write($dialog.SelectedPath)
}}
"""
    else:
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = @'
{title}
'@
$dialog.InitialDirectory = @'
{str(start_dir)}
'@
$dialog.Filter = 'Model files|*.safetensors;*.ckpt;*.pt;*.bin;*.gguf|All files|*.*'
$dialog.CheckFileExists = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  [Console]::Out.Write($dialog.FileName)
}}
"""
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-STA",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    value = (completed.stdout or "").strip()
    return value or None


def _browse_tk(*, mode: PathMode, start_dir: Path, title: str) -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if mode == "directory":
            value = filedialog.askdirectory(initialdir=str(start_dir), title=title, parent=root)
        else:
            value = filedialog.askopenfilename(
                initialdir=str(start_dir),
                title=title,
                parent=root,
                filetypes=[
                    ("Model files", "*.safetensors *.ckpt *.pt *.bin *.gguf"),
                    ("All files", "*.*"),
                ],
            )
    finally:
        root.destroy()
    return value or None
