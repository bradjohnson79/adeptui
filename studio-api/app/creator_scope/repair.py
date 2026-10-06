"""One-time production repair for Global creator wiring. Not a second schema."""

from __future__ import annotations

from sqlalchemy.orm import Session

import re

from .contract import (
    ENTITY_ENVIRONMENT,
    ENTITY_PROP,
    is_ephemeral_creator_fixture,
    is_placeholder_character_name,
)

_TEST_LEAK_RE = re.compile(
    r"^(korriwire|keepwire|venture wire|marker ship|shared ship|detach ship|earth horizon wire|venturespaceshipwire)|testglobal(?:character|prop|env)[a-f0-9]{4,}",
    re.IGNORECASE,
)
from .service import CreatorAssetScopeRow, delete_scope


def purge_ephemeral_creator_fixtures(db: Session) -> dict[str, list[str]]:
    """Delete leftover WiringSmoke / GlobalTest / placeholder New Character rows."""
    removed: dict[str, list[str]] = {"character": [], "prop": [], "environment": [], "scope": []}

    from ..character_identity.models import CharacterProfileRow
    from ..character_identity.service import delete_profile

    for row in list(db.query(CharacterProfileRow).all()):
        if not (
            is_ephemeral_creator_fixture(row.name or row.slug)
            or is_placeholder_character_name(row.name)
            or _TEST_LEAK_RE.search(str(row.name or ""))
        ):
            continue
        try:
            delete_profile(db, row.project_id, row.id, confirm_cross_project=True)
        except Exception:
            try:
                db.delete(row)
                db.commit()
            except Exception:
                db.rollback()
                continue
        removed["character"].append(row.id)

    from ..db import Project
    from ..spatial_map.ers_persistence import delete_prop_entity, list_prop_entities

    for project in db.query(Project).all():
        for prop in list_prop_entities(db, project.id):
            if not (
                is_ephemeral_creator_fixture(prop.display_label or prop.tag)
                or _TEST_LEAK_RE.search(str(prop.display_label or prop.tag or ""))
            ):
                continue
            delete_prop_entity(db, project.id, prop.id)
            delete_scope(db, entity_type=ENTITY_PROP, entity_id=prop.id)
            removed["prop"].append(prop.id)

    from ..environment_reference_sheet.store import list_sheets, sheets_dir

    for project in db.query(Project).all():
        for sheet in list_sheets(project.id):
            if not (
                is_ephemeral_creator_fixture(sheet.name)
                or _TEST_LEAK_RE.search(str(sheet.name or ""))
            ):
                continue
            path = sheets_dir(project.id) / f"{sheet.sheetId}.json"
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            delete_scope(db, entity_type=ENTITY_ENVIRONMENT, entity_id=sheet.sheetId)
            removed["environment"].append(sheet.sheetId)

    for row in list(db.query(CreatorAssetScopeRow).all()):
        label = str(row.name or row.tag or "")
        if not (is_ephemeral_creator_fixture(label) or _TEST_LEAK_RE.search(label)):
            continue
        delete_scope(db, entity_type=row.entity_type, entity_id=row.entity_id)
        removed["scope"].append(f"{row.entity_type}:{row.entity_id}")
    return removed


def sanitize_leaked_prop_descriptions(db: Session) -> list[str]:
    from ..db import Project
    from ..prop_creator.service import _sanitize_prop_human_fields
    from ..spatial_map.ers_persistence import list_prop_entities, save_prop_entity

    touched: list[str] = []
    for project in db.query(Project).all():
        for prop in list_prop_entities(db, project.id):
            before = (prop.description, prop.notes)
            _sanitize_prop_human_fields(prop)
            if (prop.description, prop.notes) != before:
                save_prop_entity(db, prop.project_id, prop)
                touched.append(prop.id)
    return touched
