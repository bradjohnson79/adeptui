"""Isolated convert worker: Blender if present, else clear error. No sculpt/rig/UV."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ConvertResult:
    ok: bool
    mode: str  # blender | passthrough | unavailable
    output_path: str | None
    message: str
    blender_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "outputPath": self.output_path,
            "message": self.message,
            "blenderDetected": self.blender_detected,
            "authoringSupported": False,
            "note": "Not a Blender replacement; conversion only.",
        }


def detect_blender() -> Optional[str]:
    env = os.environ.get("STUDIO_BLENDER_BIN") or os.environ.get("BLENDER_BIN")
    if env and Path(env).exists():
        return env
    which = shutil.which("blender")
    return which


def convert_to_glb(src: str | Path, dest_dir: str | Path) -> ConvertResult:
    src_p = Path(src)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    blender = detect_blender()
    if src_p.suffix.lower() == ".glb":
        out = dest / src_p.name
        if src_p.resolve() != out.resolve():
            shutil.copy2(src_p, out)
        return ConvertResult(True, "passthrough", str(out), "GLB passthrough (no conversion)", bool(blender))
    if not blender:
        return ConvertResult(
            False,
            "unavailable",
            None,
            "Blender binary not detected. Set STUDIO_BLENDER_BIN or install Blender to convert non-GLB meshes. "
            "Adept UI does not ship Blender and will not silently download it.",
            False,
        )
    out = dest / (src_p.stem + ".glb")
    script = (
        "import bpy,sys;"
        "bpy.ops.wm.read_factory_settings(use_empty=True);"
        f"bpy.ops.import_scene.gltf(filepath=r'{src_p}') if False else None;"
        # Prefer generic FBX/OBJ import when available; keep failure honest.
        f"src=r'{src_p}'; out=r'{out}';"
        "ext=src.lower();"
        "ok=False;"
        "\ntry:\n"
        "  if ext.endswith('.fbx'): bpy.ops.import_scene.fbx(filepath=src); ok=True\n"
        "  elif ext.endswith('.obj'): bpy.ops.wm.obj_import(filepath=src); ok=True\n"
        "  elif ext.endswith('.gltf') or ext.endswith('.glb'): bpy.ops.import_scene.gltf(filepath=src); ok=True\n"
        "except Exception as e:\n"
        "  print('IMPORT_FAIL', e); ok=False\n"
        "if ok:\n"
        "  bpy.ops.export_scene.gltf(filepath=out, export_format='GLB')\n"
        "else:\n"
        "  raise SystemExit(3)\n"
    )
    try:
        proc = subprocess.run(
            [blender, "-b", "--python-expr", script],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return ConvertResult(False, "blender", None, f"Blender convert failed: {exc}", True)
    if proc.returncode != 0 or not out.is_file():
        return ConvertResult(
            False,
            "blender",
            None,
            f"Blender convert failed (code={proc.returncode}). stderr={(proc.stderr or '')[:500]}",
            True,
        )
    return ConvertResult(True, "blender", str(out), "Converted via detected Blender CLI", True)
