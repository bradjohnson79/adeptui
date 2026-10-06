"""Seed a disposable Adept Stability Cert character for approval-gate Playwright.

Does not touch Korri / Schnick / the SenseNova Untitled Character.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.character_identity.cc_v2 import empty_state, save_state  # noqa: E402
from app.character_identity.models import CharacterProfileRow  # noqa: E402
from app.character_identity.service import create_profile  # noqa: E402
from app.character_identity.schemas import CharacterProfileCreate  # noqa: E402
from app.db import Asset, SessionLocal  # noqa: E402

CERT_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1"
FIXTURE_NAME = "Approval Gate Fixture"


def _png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 48), (40, 40, 50)).save(path)


def _find(db: Session) -> CharacterProfileRow | None:
    return (
        db.query(CharacterProfileRow)
        .filter(
            CharacterProfileRow.project_id == CERT_PROJECT_ID,
            CharacterProfileRow.name == FIXTURE_NAME,
        )
        .one_or_none()
    )


def seed(*, approve: tuple[str, ...] = ("side",)) -> dict[str, str]:
    db = SessionLocal()
    try:
        profile = _find(db)
        if profile is None:
            created = create_profile(
                db,
                CERT_PROJECT_ID,
                CharacterProfileCreate(name=FIXTURE_NAME, slug="approval-gate-fixture", role="fixture"),
            )
            profile = db.get(CharacterProfileRow, created.id)
            if profile is None:
                raise RuntimeError("Failed to create approval-gate fixture character")
        assets_root = ROOT / "data" / "assets" / CERT_PROJECT_ID / "approval-gate-fixture"
        ids = {}
        state = empty_state()
        state["views"]["front"]["approved"] = True
        state["views"]["front"]["status"] = "approved"
        state["visualLock"] = {"status": "ok", "facts": {}, "error": None}
        for name in ("front", "side", "three_quarter", "back"):
            path = assets_root / f"{name}.png"
            _png(path)
            aid = str(uuid.uuid4())
            db.add(Asset(id=aid, project_id=CERT_PROJECT_ID, filename=f"{name}.png", path=str(path)))
            ids[name] = aid
            if name == "front":
                state["views"]["front"]["assetId"] = aid
            else:
                slot = state["multiView"]["angles"][name]
                slot["assetId"] = aid
                slot["approved"] = name in approve
                slot["status"] = "approved" if name in approve else "ready"
        save_state(db, profile, state)
        db.commit()
        return {"projectId": CERT_PROJECT_ID, "characterId": profile.id, "approve": json.dumps(list(approve))}
    finally:
        db.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "side"
    mapping = {
        "none": (),
        "side": ("side",),
        "two": ("side", "three_quarter"),
        "all": ("side", "three_quarter", "back"),
    }
    print(json.dumps(seed(approve=mapping.get(mode, ("side",)))))
