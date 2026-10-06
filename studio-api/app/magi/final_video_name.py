"""One MAGI Final Render title: library label and file stem.

The confirmation field, the job, the library asset, and the file share this name.
Preview renders do not use it.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
FINAL_VIDEO_NAME_MAX = 64
FINAL_VIDEO_NAME_CONFLICT = "A file with this name already exists. Choose another name."
FINAL_VIDEO_NAME_EMPTY = "Enter a final video name."
FINAL_VIDEO_NAME_INVALID = "That name uses a character a video file cannot keep."


class FinalVideoName:
    def __init__(self, title: str, filename: str) -> None:
        self.title = title
        self.filename = filename


def parse_final_video_name(raw: str | None) -> FinalVideoName:
    title = str(raw or "").strip()
    while title.lower().endswith(".mp4"):
        title = title[:-4].rstrip()
    if not title or title in {".", ".."}:
        raise ValueError(FINAL_VIDEO_NAME_EMPTY)
    if _INVALID.search(title) or title.endswith(".") or title.endswith(" "):
        raise ValueError(FINAL_VIDEO_NAME_INVALID)
    if len(title) > FINAL_VIDEO_NAME_MAX:
        raise ValueError("Use a shorter name.")
    reserved = title.split(".", 1)[0].upper()
    if reserved in _RESERVED:
        raise ValueError("That name is reserved by the computer. Choose another name.")
    return FinalVideoName(title, f"{title}.mp4")


def name_conflicts(name: FinalVideoName, rows: list[tuple[str, str]], *, path_exists: bool) -> bool:
    title = name.title.casefold()
    filename = name.filename.casefold()
    for tag, existing in rows:
        existing_name = str(existing or "").strip()
        existing_tag = str(tag or "").strip()
        stem = existing_name[:-4] if existing_name.lower().endswith(".mp4") else existing_name
        if existing_tag.casefold() == title or existing_name.casefold() == filename or stem.casefold() == title:
            return True
    return path_exists


def final_video_name_taken(db: Session, project_id: str, name: FinalVideoName) -> bool:
    rows = [
        (str(tag or ""), str(filename or ""))
        for tag, filename in db.query(Asset.tag, Asset.filename).filter(Asset.project_id == project_id).all()
    ]
    dest = Path(settings.data_dir) / "projects" / project_id / "assets" / name.filename
    return name_conflicts(name, rows, path_exists=dest.exists())
