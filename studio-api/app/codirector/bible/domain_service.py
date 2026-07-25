"""BibleDomainService: typed domain CRUD, lifecycle, export, and conflict sync."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..errors import (
    BIBLE_VALIDATION_ERROR,
    CONCURRENT_MODIFICATION,
    ENTITY_NOT_FOUND,
    LOCKED_ENTITY_REQUIRES_APPROVAL,
    CoDirectorError,
)
from . import audit, completeness, conflicts, operations as ops
from .context_retrieval import ContextRetrievalService
from .domain.schemas import CanonRecordData, ReferenceLinkData
from .schemas import LOCKED_LIFECYCLE_STATUSES, BibleEntity, BibleMutationSet, EntityMutation
from .service import require_bible


class BibleDomainService:
    """Domain-facing Bible operations with lifecycle gates and optimistic concurrency."""

    @staticmethod
    def _current_entities(db: Session, project_id: str) -> tuple[Any, Any, list[BibleEntity]]:
        bible = require_bible(db, project_id)
        version = ops.get_current_version(db, bible)
        if not version:
            raise CoDirectorError(
                "BIBLE_NOT_FOUND",
                "This project doesn't have a Production Bible version yet.",
                details={"projectId": project_id},
                recoverable=True,
                recommended_action="create_bible",
            )
        entities = [ops.entity_row_to_schema(row) for row in ops.entities_for_version(db, version.id)]
        return bible, version, entities

    @staticmethod
    def _entity_dict(entity: BibleEntity) -> dict[str, Any]:
        return entity.model_dump(mode="json")

    @staticmethod
    def _find_by_stable_id(entities: list[BibleEntity], stable_id: str) -> Optional[BibleEntity]:
        return next((e for e in entities if e.stableId == stable_id), None)

    @staticmethod
    def _assert_editable(entity: BibleEntity) -> None:
        if entity.lifecycleStatus in LOCKED_LIFECYCLE_STATUSES:
            raise CoDirectorError(
                LOCKED_ENTITY_REQUIRES_APPROVAL,
                "This entity is locked. Create and approve a proposal to change it.",
                details={"stableId": entity.stableId, "lifecycleStatus": entity.lifecycleStatus},
                recoverable=True,
                recommended_action="create_proposal",
            )

    @staticmethod
    def _assert_revision(entity: BibleEntity, content_revision: Optional[int]) -> None:
        if content_revision is not None and content_revision != entity.contentRevision:
            raise CoDirectorError(
                CONCURRENT_MODIFICATION,
                "The entity was modified since you loaded it. Refresh and try again.",
                details={
                    "stableId": entity.stableId,
                    "expectedRevision": content_revision,
                    "actualRevision": entity.contentRevision,
                },
                recoverable=True,
                recommended_action="refresh",
            )

    @staticmethod
    def _apply_entity_mutation(
        db: Session,
        *,
        bible: Any,
        version: Any,
        project_id: str,
        mutation: EntityMutation,
        event_type: str,
        summary: str,
        actor: str = "user",
    ) -> BibleEntity:
        new_version = ops.apply_mutation_set(
            db,
            bible=bible,
            base_version=version,
            mutations=BibleMutationSet(entityMutations=[mutation], changeReason=event_type),
            created_by=actor,
        )
        created = next(
            (
                ops.entity_row_to_schema(row)
                for row in ops.entities_for_version(db, new_version.id)
                if row.entity_key == mutation.entityKey
            ),
            None,
        )
        if not created:
            raise CoDirectorError(
                "EXECUTION_FAILED",
                "Entity mutation did not produce the expected entity.",
                details={"entityKey": mutation.entityKey},
                recoverable=False,
                recommended_action="none",
            )
        audit.record_audit_event(
            db,
            project_id=project_id,
            event_type=event_type,
            summary=summary,
            actor=actor,
            entity_stable_id=created.stableId,
            entity_key=created.entityKey,
            entity_type=created.entityType,
            bible_version_id=new_version.id,
            bible_version_number=new_version.version_number,
        )
        db.commit()
        return created

    @staticmethod
    def get_summary(db: Session, project_id: str) -> dict[str, Any]:
        return ContextRetrievalService.project_summary(db, project_id)

    @staticmethod
    def list_by_type(db: Session, project_id: str, entity_type: str) -> list[dict[str, Any]]:
        _, _, entities = BibleDomainService._current_entities(db, project_id)
        normalized = ops.normalize_entity_type(entity_type)
        return [BibleDomainService._entity_dict(e) for e in entities if e.entityType == normalized]

    @staticmethod
    def get_entity(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        _, _, entities = BibleDomainService._current_entities(db, project_id)
        entity = BibleDomainService._find_by_stable_id(entities, stable_id)
        if not entity:
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No entity with stableId '{stable_id}' exists in the current Bible version.",
                details={"projectId": project_id, "stableId": stable_id},
                recoverable=False,
                recommended_action="none",
            )
        return BibleDomainService._entity_dict(entity)

    @staticmethod
    def create_entity(
        db: Session,
        project_id: str,
        *,
        entity_type: str,
        entity_key: str,
        display_name: str,
        data: Optional[dict[str, Any]] = None,
        slug: Optional[str] = None,
    ) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        if any(e.entityKey == entity_key for e in entities):
            raise CoDirectorError(
                BIBLE_VALIDATION_ERROR,
                f"Entity key '{entity_key}' already exists in the current Bible version.",
                details={"entityKey": entity_key},
                recoverable=True,
                recommended_action="none",
            )
        try:
            mutation = EntityMutation(
                entityType=entity_type,  # type: ignore[arg-type]
                entityKey=entity_key,
                displayName=display_name,
                data=data or {},
                slug=slug or entity_key,
            )
        except ValidationError as exc:
            raise CoDirectorError(
                BIBLE_VALIDATION_ERROR,
                "Entity payload failed validation.",
                details={"errors": exc.errors()},
                recoverable=True,
                recommended_action="none",
            ) from exc
        created = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="entity_created",
            summary=f"Created {entity_type} '{display_name}'",
        )
        return BibleDomainService._entity_dict(created)

    @staticmethod
    def update_entity(
        db: Session,
        project_id: str,
        stable_id: str,
        *,
        display_name: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
        content_revision: Optional[int] = None,
        lifecycle_status: Optional[str] = None,
    ) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        existing = BibleDomainService._find_by_stable_id(entities, stable_id)
        if not existing:
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No entity with stableId '{stable_id}' exists in the current Bible version.",
                details={"projectId": project_id, "stableId": stable_id},
                recoverable=False,
                recommended_action="none",
            )
        BibleDomainService._assert_editable(existing)
        BibleDomainService._assert_revision(existing, content_revision)
        merged_data = {**existing.data, **(data or {})} if data is not None else existing.data
        mutation = EntityMutation(
            entityType=existing.entityType,
            entityKey=existing.entityKey,
            displayName=display_name if display_name is not None else existing.displayName,
            data=merged_data,
            stableId=existing.stableId,
            slug=existing.slug,
            lifecycleStatus=lifecycle_status or existing.lifecycleStatus,
            contentRevision=existing.contentRevision + 1,
        )
        updated = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="entity_updated",
            summary=f"Updated {existing.entityType} '{existing.displayName}'",
        )
        return BibleDomainService._entity_dict(updated)

    @staticmethod
    def approve_entity(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        existing = BibleDomainService._find_by_stable_id(entities, stable_id)
        if not existing:
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No entity with stableId '{stable_id}' exists in the current Bible version.",
                details={"projectId": project_id, "stableId": stable_id},
                recoverable=False,
                recommended_action="none",
            )
        mutation = EntityMutation(
            entityType=existing.entityType,
            entityKey=existing.entityKey,
            displayName=existing.displayName,
            data=existing.data,
            stableId=existing.stableId,
            slug=existing.slug,
            lifecycleStatus="approved",
            contentRevision=existing.contentRevision + 1,
        )
        approved = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="entity_approved",
            summary=f"Approved {existing.entityType} '{existing.displayName}'",
        )
        return BibleDomainService._entity_dict(approved)

    @staticmethod
    def lock_entity(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        existing = BibleDomainService._find_by_stable_id(entities, stable_id)
        if not existing:
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No entity with stableId '{stable_id}' exists in the current Bible version.",
                details={"projectId": project_id, "stableId": stable_id},
                recoverable=False,
                recommended_action="none",
            )
        mutation = EntityMutation(
            entityType=existing.entityType,
            entityKey=existing.entityKey,
            displayName=existing.displayName,
            data=existing.data,
            stableId=existing.stableId,
            slug=existing.slug,
            lifecycleStatus="locked",
            contentRevision=existing.contentRevision + 1,
        )
        locked = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="entity_locked",
            summary=f"Locked {existing.entityType} '{existing.displayName}'",
        )
        return BibleDomainService._entity_dict(locked)

    @staticmethod
    def list_canon(db: Session, project_id: str) -> list[dict[str, Any]]:
        return BibleDomainService.list_by_type(db, project_id, "canon_record")

    @staticmethod
    def create_canon_record(
        db: Session,
        project_id: str,
        *,
        claim: str,
        entity_stable_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        supersedes_stable_id: Optional[str] = None,
    ) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        data = CanonRecordData(
            claim=claim,
            entityStableId=entity_stable_id,
            sceneId=scene_id,
            supersedesStableId=supersedes_stable_id,
            status="approved",
        ).model_dump(mode="json")
        entity_key = f"canon-{uuid.uuid4().hex[:8]}"
        mutation = EntityMutation(
            entityType="canon_record",
            entityKey=entity_key,
            displayName=claim[:80] or "Canon record",
            data=data,
            lifecycleStatus="approved",
        )
        created = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="canon_record_created",
            summary=f"Created canon record: {claim[:120]}",
            actor="tool:propose_canon_record",
        )
        if supersedes_stable_id:
            old = BibleDomainService._find_by_stable_id(entities, supersedes_stable_id)
            if old:
                superseded_data = {**old.data, "status": "superseded"}
                supersede_mutation = EntityMutation(
                    entityType=old.entityType,
                    entityKey=old.entityKey,
                    displayName=old.displayName,
                    data=superseded_data,
                    stableId=old.stableId,
                    slug=old.slug,
                    lifecycleStatus="superseded",
                    contentRevision=old.contentRevision + 1,
                )
                BibleDomainService._apply_entity_mutation(
                    db,
                    bible=bible,
                    version=ops.get_current_version(db, bible),
                    project_id=project_id,
                    mutation=supersede_mutation,
                    event_type="canon_superseded",
                    summary=f"Superseded canon record {supersedes_stable_id}",
                    actor="tool:propose_canon_supersession",
                )
        return BibleDomainService._entity_dict(created)

    @staticmethod
    def sync_conflicts(db: Session, project_id: str) -> list[dict[str, Any]]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        detected = conflicts.detect_all_conflicts(entities)
        existing_keys = {
            (e.data.get("conflictType"), e.data.get("description"))
            for e in entities
            if e.entityType == "conflict_record"
        }
        mutations: list[EntityMutation] = []
        for conflict in detected:
            key = (conflict.get("conflictType"), conflict.get("description"))
            if key in existing_keys:
                continue
            entity_key = f"conflict-{uuid.uuid4().hex[:8]}"
            mutations.append(
                EntityMutation(
                    entityType="conflict_record",
                    entityKey=entity_key,
                    displayName=str(conflict.get("conflictType", "conflict")),
                    data={
                        "conflictType": conflict.get("conflictType", ""),
                        "severity": conflict.get("severity", "warning"),
                        "description": conflict.get("description", ""),
                        "entityStableIds": conflict.get("entityStableIds", []),
                        "sceneIds": conflict.get("sceneIds", []),
                        "resolved": False,
                    },
                )
            )
        if mutations:
            ops.apply_mutation_set(
                db,
                bible=bible,
                base_version=version,
                mutations=BibleMutationSet(entityMutations=mutations, changeReason="conflict_sync"),
                created_by="system:conflict_sync",
            )
            db.commit()
        return detected

    @staticmethod
    def link_reference(
        db: Session,
        project_id: str,
        *,
        asset_id: str,
        target_stable_id: str,
        purpose: str = "identity",
        primary: bool = False,
    ) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        if not BibleDomainService._find_by_stable_id(entities, target_stable_id):
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No entity with stableId '{target_stable_id}' exists in the current Bible version.",
                details={"stableId": target_stable_id},
                recoverable=False,
                recommended_action="none",
            )
        data = ReferenceLinkData(
            assetId=asset_id,
            targetStableId=target_stable_id,
            purpose=purpose,  # type: ignore[arg-type]
            primary=primary,
        ).model_dump(mode="json")
        entity_key = f"ref-{uuid.uuid4().hex[:8]}"
        mutation = EntityMutation(
            entityType="reference_link",
            entityKey=entity_key,
            displayName=f"Reference {purpose}",
            data=data,
        )
        created = BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="reference_linked",
            summary=f"Linked asset {asset_id} to {target_stable_id}",
            actor="tool:propose_reference_link",
        )
        return BibleDomainService._entity_dict(created)

    @staticmethod
    def unlink_reference(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        bible, version, entities = BibleDomainService._current_entities(db, project_id)
        existing = BibleDomainService._find_by_stable_id(entities, stable_id)
        if not existing or existing.entityType != "reference_link":
            raise CoDirectorError(
                ENTITY_NOT_FOUND,
                f"No reference link with stableId '{stable_id}' exists.",
                details={"stableId": stable_id},
                recoverable=False,
                recommended_action="none",
            )
        mutation = EntityMutation(
            entityType="reference_link",
            entityKey=existing.entityKey,
            remove=True,
        )
        BibleDomainService._apply_entity_mutation(
            db,
            bible=bible,
            version=version,
            project_id=project_id,
            mutation=mutation,
            event_type="reference_unlinked",
            summary=f"Unlinked reference {stable_id}",
        )
        return {"removed": True, "stableId": stable_id}

    @staticmethod
    def list_audit(db: Session, project_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return [audit.audit_event_to_dict(row) for row in audit.list_audit_events(db, project_id, limit=limit)]

    @staticmethod
    def export_json(db: Session, project_id: str) -> dict[str, Any]:
        _, version, entities = BibleDomainService._current_entities(db, project_id)
        health = completeness.bible_health_counts(entities)
        conflict_list = conflicts.detect_all_conflicts(entities)
        return {
            "schemaVersion": "m2.3",
            "projectId": project_id,
            "exportedAt": datetime.utcnow().isoformat(),
            "bibleVersionNumber": version.version_number,
            "health": {**health, "conflictCount": len(conflict_list)},
            "entities": [BibleDomainService._entity_dict(e) for e in entities],
            "conflicts": conflict_list,
        }
