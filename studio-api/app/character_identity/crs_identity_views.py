"""Deterministic CRS identity-view extraction (G10 + G13/G25).

The approved multi-panel Character Reference Sheet remains visual authority.
Scene generation consumes a single identity VIEW, never the composed document.

Derived crops are reproducible, lineage-linked to the original CRS, and are
not new canon: they do not change approvedHeroIdentity or crsRevision.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset
from .models import CharacterProfileRow, CharacterReferenceAssetRow
from .roles import ALL_REFERENCE_ROLES


EXTRACTOR_ID = "crs_identity_views/v1"
SOURCE_TYPE = "crs_derived_crop"
LINEAGE_KIND = "crs_derived_crop"

# Legacy unlabeled 2x2 (visual_sheet._compose_character_sheet_grid).
# Row-major: front, side / back, close-up. No 3/4 tile on this layout.
FOUR_PANEL_ROLES: tuple[str, ...] = (
    "full_body_front",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)
FOUR_PANEL_LABELS: tuple[str, ...] = ("Front", "Side", "Back", "Close-Up")

# Camera role -> preferred reference_role order (first usable non-sheet wins).
CAMERA_ROLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "front": (
        "full_body_front",
        "hero_identity",
        "closeup_front",
        "full_body_three_quarter_front",
    ),
    "three_quarter": (
        "full_body_three_quarter_front",
        "full_body_front",
        "hero_identity",
        "closeup_front",
    ),
    "side": (
        "full_body_side_left",
        "full_body_side_right",
        "closeup_side_left",
        "closeup_side_right",
    ),
    "back": (
        "full_body_back",
        "closeup_back",
    ),
}

DEFAULT_IDENTITY_FALLBACK: tuple[str, ...] = (
    "hero_identity",
    "closeup_front",
    "full_body_front",
    "full_body_three_quarter_front",
)

IDENTITY_VIEW_ROLES: frozenset[str] = frozenset(
    {
        "full_body_front",
        "full_body_side_left",
        "full_body_side_right",
        "full_body_back",
        "full_body_three_quarter_front",
        "closeup_front",
        "closeup_side_left",
        "closeup_side_right",
        "closeup_back",
        "hero_identity",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_camera_role(camera: str | None = None, framing: str | None = None) -> str:
    """Map scene camera / framing language onto a CRS view role family."""
    blob = f"{camera or ''} {framing or ''}".strip().lower().replace("-", "_")
    compact = blob.replace(" ", "_")
    tokens = set(blob.replace("/", " ").replace("_", " ").split())

    if any(k in compact for k in ("profile", "side_view", "side_left", "side_right")) or tokens & {
        "profile",
        "side",
        "left",
        "right",
    }:
        if tokens & {"back", "rear", "behind"}:
            return "back"
        return "side"
    if any(k in compact for k in ("3/4", "3_4", "three_quarter", "threequarter")) or tokens & {
        "threequarter",
    }:
        return "three_quarter"
    if tokens & {"back", "rear", "behind"} or any(
        k in compact for k in ("back_view", "from_behind", "rear_view")
    ):
        return "back"
    return "front"


def prefer_closeup(framing: str | None = None, camera: str | None = None) -> bool:
    blob = f"{framing or ''} {camera or ''}".lower()
    return any(k in blob for k in ("close", "portrait", "head", "bust", "cu"))


def detect_crs_sheet_layout(width: int, height: int) -> str:
    """Square composed sheets are legacy 2x2. Wider G11 documents are labeled 3x2."""
    w, h = int(width or 0), int(height or 0)
    if w <= 0 or h <= 0:
        return "four_panel_2x2"
    if abs(w - h) <= max(8, int(0.03 * max(w, h))):
        return "four_panel_2x2"
    return "law_views_labeled"


def plan_crs_view_regions(
    width: int,
    height: int,
    *,
    layout: str | None = None,
) -> list[dict[str, Any]]:
    """Deterministic crop boxes in image pixel space."""
    w, h = int(width), int(height)
    kind = layout or detect_crs_sheet_layout(w, h)
    if kind == "law_views_labeled":
        from .character_sheet_compose import plan_labeled_character_sheet

        plan = plan_labeled_character_sheet(5)
        sx = w / float(plan["width"])
        sy = h / float(plan["height"])
        views: list[dict[str, Any]] = []
        for cell in plan["views"]:
            x0, y0, x1, y1 = [int(v) for v in cell["bbox"]]
            # Drop the Adept-drawn label bar so identity pixels are character-only.
            label = cell.get("labelBbox")
            if isinstance(label, list) and len(label) == 4:
                y1 = min(y1, int(label[1]))
            views.append(
                {
                    "role": str(cell["role"]),
                    "label": str(cell.get("label") or cell["role"]),
                    "bbox": [
                        max(0, int(x0 * sx)),
                        max(0, int(y0 * sy)),
                        min(w, int(x1 * sx)),
                        min(h, int(y1 * sy)),
                    ],
                    "layout": kind,
                }
            )
        return views

    tw, th = w // 2, h // 2
    boxes = (
        [0, 0, tw, th],
        [tw, 0, w, th],
        [0, th, tw, h],
        [tw, th, w, h],
    )
    return [
        {
            "role": role,
            "label": label,
            "bbox": list(box),
            "layout": "four_panel_2x2",
        }
        for role, label, box in zip(FOUR_PANEL_ROLES, FOUR_PANEL_LABELS, boxes)
    ]


@dataclass
class ExtractedView:
    role: str
    label: str
    bbox: list[int]
    layout: str
    image: Any
    width: int
    height: int


def extract_crs_identity_views(sheet_path: str | Path) -> list[ExtractedView]:
    """Crop identity views from an approved multi-panel CRS. Pure. No DB writes."""
    from PIL import Image

    path = Path(sheet_path)
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        width, height = int(rgb.size[0]), int(rgb.size[1])
        regions = plan_crs_view_regions(width, height)
        out: list[ExtractedView] = []
        for region in regions:
            x0, y0, x1, y1 = [int(v) for v in region["bbox"]]
            if x1 <= x0 or y1 <= y0:
                continue
            crop = rgb.crop((x0, y0, x1, y1)).copy()
            out.append(
                ExtractedView(
                    role=str(region["role"]),
                    label=str(region["label"]),
                    bbox=[x0, y0, x1, y1],
                    layout=str(region["layout"]),
                    image=crop,
                    width=crop.size[0],
                    height=crop.size[1],
                )
            )
        return out


def derived_crop_request(
    *,
    sheet_asset_id: str,
    sheet_path: str | Path | None = None,
    width: int | None = None,
    height: int | None = None,
    camera: str | None = None,
    framing: str | None = None,
    crs_revision: int = 0,
) -> dict[str, Any]:
    """Marked request: scene must crop a view, never use the composed sheet."""
    w, h = int(width or 0), int(height or 0)
    if (not w or not h) and sheet_path:
        try:
            from PIL import Image

            with Image.open(sheet_path) as im:
                w, h = int(im.size[0]), int(im.size[1])
        except Exception:
            w, h = 0, 0
    layout = detect_crs_sheet_layout(w, h) if w and h else "four_panel_2x2"
    regions = plan_crs_view_regions(w, h, layout=layout) if w and h else []
    camera_role = normalize_camera_role(camera, framing)
    wanted = list(CAMERA_ROLE_CANDIDATES.get(camera_role, CAMERA_ROLE_CANDIDATES["front"]))
    if prefer_closeup(framing, camera) and camera_role == "front":
        wanted = ["closeup_front", *wanted]
    chosen = None
    for role in wanted:
        for region in regions:
            if region["role"] == role:
                chosen = region
                break
        if chosen:
            break
    if chosen is None and regions:
        # Hero close-up is the last-resort identity region on a 2x2 sheet.
        for region in regions:
            if region["role"] == "closeup_front":
                chosen = region
                break
        if chosen is None:
            chosen = regions[0]
    return {
        "kind": "derived_crop_request",
        "extractor": EXTRACTOR_ID,
        "sourceCrsAssetId": sheet_asset_id,
        "sourceCrsRevision": int(crs_revision or 0),
        "layout": layout,
        "cameraRole": camera_role,
        "requestedRole": (chosen or {}).get("role"),
        "bbox": (chosen or {}).get("bbox"),
        "regions": regions,
        "newCanon": False,
        "useComposedSheet": False,
    }


def _lineage_dict(row: CharacterReferenceAssetRow) -> dict[str, Any]:
    try:
        data = json.loads(row.generation_lineage_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_derived_from(row: CharacterReferenceAssetRow, sheet_asset_id: str) -> bool:
    lineage = _lineage_dict(row)
    if lineage.get("kind") == LINEAGE_KIND and str(lineage.get("sourceCrsAssetId") or "") == sheet_asset_id:
        return True
    return row.source_type == SOURCE_TYPE and sheet_asset_id in (row.notes or "")


def list_identity_view_rows(
    db: Session,
    character_id: str,
    *,
    sheet_asset_id: str | None = None,
) -> list[CharacterReferenceAssetRow]:
    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .order_by(CharacterReferenceAssetRow.created_at.asc())
        .all()
    )
    out: list[CharacterReferenceAssetRow] = []
    for row in rows:
        role = str(row.reference_role or "")
        if role not in IDENTITY_VIEW_ROLES:
            continue
        if sheet_asset_id and row.asset_id == sheet_asset_id:
            continue
        out.append(row)
    return out


def pick_identity_view_row(
    db: Session,
    character_id: str,
    *,
    camera: str | None = None,
    framing: str | None = None,
    sheet_asset_id: str | None = None,
) -> CharacterReferenceAssetRow | None:
    camera_role = normalize_camera_role(camera, framing)
    wanted = list(CAMERA_ROLE_CANDIDATES.get(camera_role, CAMERA_ROLE_CANDIDATES["front"]))
    if prefer_closeup(framing, camera) and camera_role == "front":
        wanted = ["closeup_front", *wanted]
    for extra in DEFAULT_IDENTITY_FALLBACK:
        if extra not in wanted:
            wanted.append(extra)
    rows = list_identity_view_rows(db, character_id, sheet_asset_id=sheet_asset_id)
    by_role: dict[str, list[CharacterReferenceAssetRow]] = {}
    for row in rows:
        by_role.setdefault(str(row.reference_role), []).append(row)

    def _usable(row: CharacterReferenceAssetRow) -> bool:
        if sheet_asset_id and row.asset_id == sheet_asset_id:
            return False
        status = str(row.approval_status or "").lower()
        derived = str(row.source_type or "") == SOURCE_TYPE or _lineage_dict(row).get("kind") == LINEAGE_KIND
        return bool(row.canonical or status == "approved" or derived)

    for role in wanted:
        for row in by_role.get(role, []):
            if _usable(row):
                return row
    return None


def persist_derived_identity_views(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    sheet_asset_id: str,
    sheet_path: str | Path | None = None,
    crs_revision: int = 0,
    commit: bool = True,
) -> list[dict[str, Any]]:
    """Additive derived-view rows. Does not touch approvedHeroIdentity / CRS rev.

    Reversible: delete the returned reference + asset ids. Never overwrites
    the approved sheet PNG or existing non-derived role rows.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if profile is None or str(profile.project_id) != str(project_id):
        raise ValueError("character not found in project")
    sheet = db.get(Asset, sheet_asset_id)
    if sheet is None or str(sheet.project_id) != str(project_id):
        raise ValueError("CRS sheet asset not found in project")
    path = Path(sheet_path or sheet.path)
    if not path.is_file():
        raise FileNotFoundError(f"CRS sheet file missing: {path}")

    extracted = extract_crs_identity_views(path)
    existing = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    occupied_roles = {
        str(row.reference_role)
        for row in existing
        if str(row.reference_role) in IDENTITY_VIEW_ROLES
        and row.asset_id != sheet_asset_id
        and not _is_derived_from(row, sheet_asset_id)
        and (
            row.canonical
            or str(row.approval_status or "").lower() == "approved"
        )
    }
    already_derived = {
        str(row.reference_role)
        for row in existing
        if _is_derived_from(row, sheet_asset_id)
    }

    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, Any]] = []
    for view in extracted:
        role = view.role
        # Front tile on a labeled 5-view sheet is hero_identity. Store the
        # derived crop as full_body_front so we never replace approved hero.
        if role == "hero_identity":
            role = "full_body_front"
        if role not in ALL_REFERENCE_ROLES:
            continue
        if role in occupied_roles or role in already_derived:
            continue
        asset_id = str(uuid.uuid4())
        filename = f"crs_view_{character_id[:8]}_{role}_{asset_id[:8]}.png"
        out_path = dest_dir / filename
        view.image.save(str(out_path), format="PNG")
        lineage = {
            "kind": LINEAGE_KIND,
            "extractor": EXTRACTOR_ID,
            "sourceCrsAssetId": sheet_asset_id,
            "sourceCrsRevision": int(crs_revision or 0),
            "role": role,
            "bbox": list(view.bbox),
            "layout": view.layout,
            "reproducible": True,
            "newCanon": False,
        }
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag=f"crs_view_{role}",
                kind="image",
                filename=filename,
                path=str(out_path),
                parent_asset_id=sheet_asset_id,
                prompt_meta_json=json.dumps(lineage),
            )
        )
        ref_id = str(uuid.uuid4())
        db.add(
            CharacterReferenceAssetRow(
                id=ref_id,
                character_profile_id=character_id,
                character_version_id=profile.active_version_id,
                asset_id=asset_id,
                reference_role=role,
                view_angle=role,
                framing="closeup" if role.startswith("closeup_") else "full_body",
                approval_status="approved",
                canonical=False,
                source_type=SOURCE_TYPE,
                generation_lineage_json=json.dumps(lineage),
                notes="Derived crop from approved CRS (not new canon)",
                created_at=_now(),
            )
        )
        written.append(
            {
                "referenceId": ref_id,
                "assetId": asset_id,
                "referenceRole": role,
                "bbox": list(view.bbox),
                "layout": view.layout,
                "path": str(out_path),
                "sourceCrsAssetId": sheet_asset_id,
            }
        )
        already_derived.add(role)

    if commit:
        db.commit()
    else:
        db.flush()
    return written


def scene_identity_source_asset_id(
    *,
    view_asset_id: str | None,
    sheet_asset_id: str | None,
) -> str | None:
    """Identity pixels for SCENE_GENERATION. Never the composed CRS sheet."""
    view = str(view_asset_id or "").strip()
    sheet = str(sheet_asset_id or "").strip()
    if not view or (sheet and view == sheet):
        return None
    return view
