"""One-off diagnostic crop for Test E. Do not use h3_identity_still.py."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
PROJECT = Path(r"C:\AdeptFilmWorks\AIVideoStudio\data\assets\beffd3d8-791d-4adf-9c4d-681ec9d4efb0")
COMFY_INPUT = Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input")

ADDEX_SRC = PROJECT / "91b82df6-6c5a-410a-bdb8-6cd3f79753c7.jpeg"
KORRI_SRC = PROJECT / "a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg"

# PIL crop box: (left, top, right, bottom). Section 1 FRONT only.
# Chosen from 50px grid overlays so the crop is one full-body person,
# original wardrobe, no FRONT label, no notes, no neighboring panels.
ADDEX_BOX = (20, 170, 200, 730)
KORRI_BOX = (15, 155, 150, 655)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _crop(src: Path, box: tuple[int, int, int, int], dest: Path) -> dict:
    image = Image.open(src)
    if image.size != (1536, 1024) and src == ADDEX_SRC:
        raise SystemExit(f"Addex CRS size changed: {image.size}")
    if image.size != (1536, 864) and src == KORRI_SRC:
        raise SystemExit(f"Korri CRS size changed: {image.size}")
    cropped = image.crop(box)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dest, format="PNG")
    return {
        "sourcePath": str(src),
        "sourceBytes": src.stat().st_size,
        "sourceSha256": _sha256(src),
        "sourceSize": list(image.size),
        "boxLeftTopRightBottom": list(box),
        "cropPath": str(dest),
        "cropBytes": dest.stat().st_size,
        "cropSha256": _sha256(dest),
        "cropSize": list(cropped.size),
        "method": "PIL.Image.crop explicit pixel box; no enhance/redraw/face-restore",
    }


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    addex_dest = FIXTURES / "addex_generation_ref_front.png"
    korri_dest = FIXTURES / "korri_generation_ref_front.png"
    record = {
        "purpose": "Test E diagnostic fixtures only. Not a production cropper.",
        "addex": _crop(ADDEX_SRC, ADDEX_BOX, addex_dest),
        "korri": _crop(KORRI_SRC, KORRI_BOX, korri_dest),
    }
    (FIXTURES / "fixture_crop_boxes.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    studio = COMFY_INPUT / "studio"
    studio.mkdir(parents=True, exist_ok=True)
    staged_addex = studio / "test_e_addex_front.png"
    staged_korri = studio / "test_e_korri_front.png"
    shutil.copy2(addex_dest, staged_addex)
    shutil.copy2(korri_dest, staged_korri)
    record["staged"] = {
        "addex": {
            "comfyName": "studio/test_e_addex_front.png",
            "path": str(staged_addex),
            "sha256": _sha256(staged_addex),
        },
        "korri": {
            "comfyName": "studio/test_e_korri_front.png",
            "path": str(staged_korri),
            "sha256": _sha256(staged_korri),
        },
        "testBCrsLeftUnchanged": [
            str(studio / "91b82df6-6c5a-410a-bdb8-6cd3f79753c7.jpeg"),
            str(studio / "a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg"),
        ],
    }
    (FIXTURES / "fixture_crop_boxes.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
