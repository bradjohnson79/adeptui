"""Prepare the official Fire3D single_image on-disk layout.

Official infer expects:

    data/<scene_id>/rgb.jpeg
    data/<scene_id>/aligned_pcd.ply

Adept cannot pass a Library PNG straight to `fire3d infer`. This adapter
writes the RGB file and, when a real Pi3 point map exists, the PLY.
It never invents a point cloud.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def write_single_image_layout(
    work_root: str | Path,
    *,
    scene_id: str,
    rgb_path: str | Path | None = None,
    rgb_bytes: bytes | None = None,
    aligned_pcd_path: str | Path | None = None,
) -> Path:
    scene_dir = Path(work_root) / "data" / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)
    dest_rgb = scene_dir / "rgb.jpeg"
    if rgb_path:
        shutil.copyfile(rgb_path, dest_rgb)
    elif rgb_bytes:
        dest_rgb.write_bytes(rgb_bytes)
    else:
        raise FileNotFoundError("Library image bytes are required to write rgb.jpeg")

    dest_ply = scene_dir / "aligned_pcd.ply"
    if aligned_pcd_path and Path(aligned_pcd_path).is_file():
        shutil.copyfile(aligned_pcd_path, dest_ply)
    return scene_dir


def layout_ready(scene_dir: str | Path) -> tuple[bool, str]:
    root = Path(scene_dir)
    rgb = root / "rgb.jpeg"
    ply = root / "aligned_pcd.ply"
    if not rgb.is_file():
        return False, "rgb.jpeg is missing"
    if not ply.is_file():
        return False, (
            "aligned_pcd.ply is missing. Run Pi3 on the Library image and place "
            "the official aligned point map before fire3d infer."
        )
    return True, str(root)
