"""Low-level Production Bible persistence: version snapshots, mutation application, hashing.

Every write goes through `apply_mutation_set`, which always creates a brand-new
`ProductionBibleVersion` row (copy-on-write) rather than mutating an existing version in
place — versions are immutable once created, which is what makes "what did the Bible say
when scene 4 was generated" answerable later.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import (
    ProductionBible,
    ProductionBibleEntity,
    ProductionBibleFact,
    ProductionBibleVersion,
)
from .domain.schemas import validate_entity_data
from .schemas import BibleEntity, BibleFact, BibleMutationSet, EntityMutation, FactMutation


def normalize_entity_type(entity_type: str) -> str:
    """Accept visual_style as alias of visual_language for storage."""

    if entity_type == "visual_style":
        return "visual_language"
    return entity_type


def _entity_meta_from_row(row: ProductionBibleEntity) -> dict:
    return {
        "stableId": row.stable_id,
        "slug": row.slug,
        "lifecycleStatus": row.lifecycle_status or "draft",
        "contentRevision": row.content_revision or 1,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def entity_row_to_schema(row: ProductionBibleEntity) -> BibleEntity:
    try:
        data = json.loads(row.data_json or "{}")
    except Exception:
        data = {}
    meta = _entity_meta_from_row(row)
    # Mirror lifecycle fields in data_json for API convenience when columns are authoritative.
    for key, val in meta.items():
        if val is not None and key not in data:
            data[key] = val
    return BibleEntity(
        entityType=row.entity_type,  # type: ignore[arg-type]
        entityKey=row.entity_key,
        displayName=row.display_name or "",
        data=data,
        stableId=row.stable_id,
        slug=row.slug,
        lifecycleStatus=row.lifecycle_status or "draft",  # type: ignore[arg-type]
        contentRevision=row.content_revision or 1,
        updatedAt=row.updated_at.isoformat() if row.updated_at else None,
    )


def get_bible(db: Session, project_id: str) -> Optional[ProductionBible]:
    return db.query(ProductionBible).filter(ProductionBible.project_id == project_id).first()


def get_version(db: Session, version_id: str) -> Optional[ProductionBibleVersion]:
    return db.get(ProductionBibleVersion, version_id)


def get_version_by_number(db: Session, bible_id: str, version_number: int) -> Optional[ProductionBibleVersion]:
    return (
        db.query(ProductionBibleVersion)
        .filter(
            ProductionBibleVersion.bible_id == bible_id,
            ProductionBibleVersion.version_number == version_number,
        )
        .first()
    )


def get_current_version(db: Session, bible: ProductionBible) -> Optional[ProductionBibleVersion]:
    if not bible.current_version_id:
        return None
    return get_version(db, bible.current_version_id)


def list_versions(db: Session, bible_id: str) -> list[ProductionBibleVersion]:
    return (
        db.query(ProductionBibleVersion)
        .filter(ProductionBibleVersion.bible_id == bible_id)
        .order_by(ProductionBibleVersion.version_number.desc())
        .all()
    )


def entities_for_version(db: Session, version_id: str) -> list[ProductionBibleEntity]:
    return (
        db.query(ProductionBibleEntity)
        .filter(ProductionBibleEntity.bible_version_id == version_id)
        .order_by(ProductionBibleEntity.entity_type, ProductionBibleEntity.entity_key)
        .all()
    )


def facts_for_version(db: Session, version_id: str) -> list[ProductionBibleFact]:
    return (
        db.query(ProductionBibleFact)
        .filter(ProductionBibleFact.bible_version_id == version_id)
        .order_by(ProductionBibleFact.created_at)
        .all()
    )


def fact_row_to_schema(row: ProductionBibleFact) -> BibleFact:
    try:
        data = json.loads(row.data_json or "{}")
    except Exception:
        data = {}
    return BibleFact(entityKey=row.entity_key, factType=row.fact_type, statement=row.statement or "", data=data)


def _merge_entity_mutation(existing: Optional[BibleEntity], m: EntityMutation, now: datetime) -> BibleEntity:
    entity_type = normalize_entity_type(m.entityType)
    stable_id = m.stableId or (existing.stableId if existing else None) or str(uuid.uuid4())
    slug = m.slug if m.slug is not None else (existing.slug if existing else m.entityKey)
    lifecycle = m.lifecycleStatus if m.lifecycleStatus is not None else (existing.lifecycleStatus if existing else "draft")
    if m.data is not None:
        validated_data = validate_entity_data(entity_type, m.data)
        content_revision = (existing.contentRevision + 1) if existing else 1
    else:
        validated_data = existing.data if existing else {}
        content_revision = existing.contentRevision if existing else 1
    if m.contentRevision is not None:
        content_revision = m.contentRevision
    return BibleEntity(
        entityType=entity_type,  # type: ignore[arg-type]
        entityKey=m.entityKey,
        displayName=m.displayName if m.displayName is not None else (existing.displayName if existing else ""),
        data=validated_data,
        stableId=stable_id,
        slug=slug,
        lifecycleStatus=lifecycle,  # type: ignore[arg-type]
        contentRevision=content_revision,
        updatedAt=now.isoformat(),
    )


def create_bible_with_first_version(
    db: Session,
    *,
    project_id: str,
    entities: list[BibleEntity],
    facts: list[BibleFact],
    summary: str,
    change_reason: str,
    created_by: str,
) -> tuple[ProductionBible, ProductionBibleVersion]:
    now = datetime.utcnow()
    bible = ProductionBible(id=str(uuid.uuid4()), project_id=project_id, created_at=now, updated_at=now)
    db.add(bible)
    db.flush()

    version = ProductionBibleVersion(
        id=str(uuid.uuid4()),
        bible_id=bible.id,
        version_number=1,
        parent_version_id=None,
        summary=summary,
        change_reason=change_reason,
        created_by=created_by,
        created_at=now,
    )
    db.add(version)
    db.flush()

    _write_entities(db, version.id, entities)
    _write_facts(db, version.id, facts)

    bible.current_version_id = version.id
    bible.updated_at = now
    db.commit()
    db.refresh(bible)
    db.refresh(version)
    return bible, version


def apply_mutation_set(
    db: Session,
    *,
    bible: ProductionBible,
    base_version: Optional[ProductionBibleVersion],
    mutations: BibleMutationSet,
    created_by: str,
) -> ProductionBibleVersion:
    """Copy-on-write: clone `base_version`'s entities/facts, apply mutations, persist a new version."""

    now = datetime.utcnow()
    next_number = (base_version.version_number + 1) if base_version else 1

    entities_by_key: dict[str, BibleEntity] = {}
    if base_version:
        for row in entities_for_version(db, base_version.id):
            entities_by_key[row.entity_key] = entity_row_to_schema(row)

    facts_list: list[BibleFact] = []
    facts_by_key: dict[str, list[BibleFact]] = {}
    if base_version:
        for row in facts_for_version(db, base_version.id):
            fact = fact_row_to_schema(row)
            fact.data = {**fact.data, "_factId": row.id}
            facts_list.append(fact)

    for m in mutations.entityMutations:
        if m.remove:
            entities_by_key.pop(m.entityKey, None)
            continue
        existing = entities_by_key.get(m.entityKey)
        entities_by_key[m.entityKey] = _merge_entity_mutation(existing, m, now)

    for fm in mutations.factMutations:
        if fm.remove:
            if fm.factId:
                facts_list = [f for f in facts_list if f.data.get("_factId") != fm.factId]
            continue
        if fm.factId:
            replaced = False
            for i, f in enumerate(facts_list):
                if f.data.get("_factId") == fm.factId:
                    facts_list[i] = BibleFact(
                        entityKey=fm.entityKey, factType=fm.factType, statement=fm.statement, data=fm.data or {}
                    )
                    replaced = True
                    break
            if not replaced:
                facts_list.append(
                    BibleFact(entityKey=fm.entityKey, factType=fm.factType, statement=fm.statement, data=fm.data or {})
                )
        else:
            facts_list.append(
                BibleFact(entityKey=fm.entityKey, factType=fm.factType, statement=fm.statement, data=fm.data or {})
            )

    version = ProductionBibleVersion(
        id=str(uuid.uuid4()),
        bible_id=bible.id,
        version_number=next_number,
        parent_version_id=base_version.id if base_version else None,
        summary=mutations.summary or (base_version.summary if base_version else ""),
        change_reason=mutations.changeReason or "proposal_applied",
        created_by=created_by,
        created_at=now,
    )
    db.add(version)
    db.flush()

    _write_entities(db, version.id, list(entities_by_key.values()))
    _write_facts(db, version.id, [BibleFact(entityKey=f.entityKey, factType=f.factType, statement=f.statement, data={k: v for k, v in f.data.items() if k != "_factId"}) for f in facts_list])

    bible.current_version_id = version.id
    bible.updated_at = now
    db.commit()
    db.refresh(version)
    return version


def _write_entities(db: Session, version_id: str, entities: list[BibleEntity]) -> None:
    now = datetime.utcnow()
    for e in entities:
        entity_type = normalize_entity_type(e.entityType)
        validated = validate_entity_data(entity_type, e.data)
        db.add(
            ProductionBibleEntity(
                id=str(uuid.uuid4()),
                bible_version_id=version_id,
                entity_type=entity_type,
                entity_key=e.entityKey,
                display_name=e.displayName,
                data_json=json.dumps(validated),
                stable_id=e.stableId or str(uuid.uuid4()),
                slug=e.slug or e.entityKey,
                lifecycle_status=e.lifecycleStatus or "draft",
                updated_at=now,
                content_revision=e.contentRevision or 1,
                created_at=now,
            )
        )
    db.flush()


def _write_facts(db: Session, version_id: str, facts: list[BibleFact]) -> None:
    now = datetime.utcnow()
    for f in facts:
        db.add(
            ProductionBibleFact(
                id=str(uuid.uuid4()),
                bible_version_id=version_id,
                entity_key=f.entityKey,
                fact_type=f.factType,
                statement=f.statement,
                data_json=json.dumps(f.data),
                created_at=now,
            )
        )
    db.flush()


def compute_input_hash(proposal_id: str, based_on_version_id: Optional[str], payload: BibleMutationSet) -> str:
    """Idempotency key: same proposal + same base version + same payload = same execution."""

    canonical = json.dumps(
        {
            "proposalId": proposal_id,
            "basedOnVersionId": based_on_version_id,
            "payload": payload.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def diff_entities(before: list[BibleEntity], after: list[BibleEntity]) -> list[dict[str, Any]]:
    before_by_key = {e.entityKey: e for e in before}
    after_by_key = {e.entityKey: e for e in after}
    diffs: list[dict[str, Any]] = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        b = before_by_key.get(key)
        a = after_by_key.get(key)
        if b is None and a is not None:
            diffs.append({"entityKey": key, "op": "add", "entityType": a.entityType, "displayName": a.displayName})
        elif b is not None and a is None:
            diffs.append({"entityKey": key, "op": "remove", "entityType": b.entityType, "displayName": b.displayName})
        elif b is not None and a is not None and b.model_dump() != a.model_dump():
            diffs.append({"entityKey": key, "op": "update", "entityType": a.entityType, "displayName": a.displayName})
    return diffs
