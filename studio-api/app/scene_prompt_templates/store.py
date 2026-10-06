"""SQLite persistence for project-scoped Scene Prompt Templates.

Canonical store: table ``scene_prompt_templates`` in studio.db, keyed by project_id.
prompt_text is stored and returned as exact bytes (no rewrite/enhance/strip).
generator_family / generator_id are informational metadata only.
source_scene_id is optional provenance (no FK; scene delete does NOT cascade).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, String, Text, inspect, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..db import Base, Project, engine


class ScenePromptTemplateRow(Base):
    __tablename__ = "scene_prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    source_scene_id: Mapped[str] = mapped_column(String(36), default="")
    name: Mapped[str] = mapped_column(String(200), default="")
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    generator_family: Mapped[str] = mapped_column(String(64), default="")
    generator_id: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_scene_prompt_template_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[ScenePromptTemplateRow.__table__])
    insp = inspect(engine)
    if not insp.has_table(ScenePromptTemplateRow.__tablename__):
        return
    existing = {c["name"] for c in insp.get_columns(ScenePromptTemplateRow.__tablename__)}
    with engine.begin() as conn:
        if "source_scene_id" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE scene_prompt_templates "
                    "ADD COLUMN source_scene_id VARCHAR(36) DEFAULT ''"
                )
            )


def _require_project(db: Session, project_id: str) -> None:
    if not db.get(Project, project_id):
        raise LookupError("PROJECT_NOT_FOUND")


def row_to_dict(row: ScenePromptTemplateRow, *, include_text: bool = True) -> dict[str, Any]:
    family = row.generator_family or ""
    out: dict[str, Any] = {
        "id": row.id,
        "projectId": row.project_id,
        "sourceSceneId": getattr(row, "source_scene_id", None) or "",
        "name": row.name,
        "generatorFamily": family,
        # Mission alias — same value as generatorFamily.
        "generatorFamilyUsed": family,
        "generatorId": row.generator_id or "",
        "createdAt": row.created_at.isoformat() + "Z" if row.created_at else "",
        "updatedAt": row.updated_at.isoformat() + "Z" if row.updated_at else "",
        "promptTextLength": len(row.prompt_text or ""),
    }
    if include_text:
        # Exact preserve — never rewrite/enhance/strip.
        out["promptText"] = row.prompt_text if row.prompt_text is not None else ""
    return out


def list_templates(db: Session, project_id: str) -> list[ScenePromptTemplateRow]:
    _require_project(db, project_id)
    return (
        db.query(ScenePromptTemplateRow)
        .filter(ScenePromptTemplateRow.project_id == project_id)
        .order_by(ScenePromptTemplateRow.updated_at.desc())
        .all()
    )


def get_template(db: Session, project_id: str, template_id: str) -> Optional[ScenePromptTemplateRow]:
    row = db.get(ScenePromptTemplateRow, template_id)
    if not row or row.project_id != project_id:
        return None
    return row


def create_template(
    db: Session,
    project_id: str,
    *,
    name: str,
    prompt_text: str,
    generator_family: str = "",
    generator_id: str = "",
    source_scene_id: str = "",
) -> ScenePromptTemplateRow:
    _require_project(db, project_id)
    now = datetime.utcnow()
    # Exact preserve: store prompt_text as provided (including empty string).
    row = ScenePromptTemplateRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_scene_id=str(source_scene_id or ""),
        name=str(name or "").strip() or "Untitled template",
        prompt_text=prompt_text if prompt_text is not None else "",
        generator_family=str(generator_family or ""),
        generator_id=str(generator_id or ""),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_template(
    db: Session,
    project_id: str,
    template_id: str,
    *,
    name: Optional[str] = None,
    prompt_text: Optional[str] = None,
    generator_family: Optional[str] = None,
    generator_id: Optional[str] = None,
    source_scene_id: Optional[str] = None,
) -> Optional[ScenePromptTemplateRow]:
    row = get_template(db, project_id, template_id)
    if not row:
        return None
    if name is not None:
        cleaned = str(name).strip()
        if cleaned:
            row.name = cleaned
    if prompt_text is not None:
        # Exact preserve — assign verbatim; never gate on generator metadata.
        row.prompt_text = prompt_text
    if generator_family is not None:
        row.generator_family = str(generator_family)
    if generator_id is not None:
        row.generator_id = str(generator_id)
    if source_scene_id is not None:
        # Provenance only — no FK; clearing/updating does not affect scenes.
        row.source_scene_id = str(source_scene_id)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def rename_template(db: Session, project_id: str, template_id: str, name: str) -> Optional[ScenePromptTemplateRow]:
    return update_template(db, project_id, template_id, name=name)


def delete_template(db: Session, project_id: str, template_id: str) -> bool:
    row = get_template(db, project_id, template_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
