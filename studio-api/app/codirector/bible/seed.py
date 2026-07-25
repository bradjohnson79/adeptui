"""Dev seed data for the Production Bible domain layer."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..errors import BIBLE_ALREADY_EXISTS, CoDirectorError
from . import operations as ops
from .schemas import BibleEntity, BibleFact


def seed_demo_bible(db: Session, project_id: str) -> dict[str, Any]:
    """Populate a generic-fiction demo Bible for development and tests."""

    if ops.get_bible(db, project_id):
        raise CoDirectorError(
            BIBLE_ALREADY_EXISTS,
            "This project already has a Production Bible. Seed demo is for empty projects.",
            details={"projectId": project_id},
            recoverable=True,
            recommended_action="use_versions",
        )

    char_a_id = str(uuid.uuid4())
    char_b_id = str(uuid.uuid4())
    loc_parent_id = str(uuid.uuid4())
    loc_child_a_id = str(uuid.uuid4())
    loc_child_b_id = str(uuid.uuid4())
    demo_scene_a = "scene-demo-001"
    demo_scene_b = "scene-demo-002"

    entities: list[BibleEntity] = [
        BibleEntity(
            entityType="project_profile",
            entityKey="project-profile",
            displayName="Demo Production",
            data={
                "name": "Demo Production",
                "description": "Generic fiction seed for M2.3 Bible development.",
                "genre": "Neo-noir thriller",
                "tone": "Tense, rain-soaked, intimate",
                "logline": "Two rivals uncover a secret that binds their fates.",
            },
        ),
        BibleEntity(
            entityType="character",
            entityKey="mara-voss",
            displayName="Mara Voss",
            stableId=char_a_id,
            data={
                "description": "Investigative journalist with a haunted past.",
                "personality": "Determined, guarded, empathetic under pressure.",
                "motivation": "Expose the truth before the city forgets.",
                "appearanceSummary": "Dark coat, cropped hair, steady gaze.",
                "readiness": "production_ready",
            },
        ),
        BibleEntity(
            entityType="character",
            entityKey="elias-mercer",
            displayName="Elias Mercer",
            stableId=char_b_id,
            data={
                "description": "Former detective turned private fixer.",
                "personality": "Dry wit, loyal, morally flexible.",
                "motivation": "Protect Mara while settling an old debt.",
                "appearanceSummary": "Worn leather jacket, scar above the brow.",
                "readiness": "production_ready",
            },
        ),
        BibleEntity(
            entityType="relationship",
            entityKey="mara-elias-rivalry",
            displayName="Mara ↔ Elias",
            data={
                "fromStableId": char_a_id,
                "toStableId": char_b_id,
                "kind": "rival",
                "label": "Reluctant allies",
                "description": "They distrust each other but need the partnership.",
                "asymmetric": True,
            },
        ),
        BibleEntity(
            entityType="location",
            entityKey="harbor-district",
            displayName="Harbor District",
            stableId=loc_parent_id,
            data={
                "description": "Fog-bound docks and abandoned warehouses.",
                "atmosphere": "Industrial melancholy",
                "geography": "Coastal city waterfront",
                "readiness": "production_ready",
            },
        ),
        BibleEntity(
            entityType="location",
            entityKey="pier-seven",
            displayName="Pier Seven",
            stableId=loc_child_a_id,
            data={
                "description": "Rotting pier where the first clue is found.",
                "parentStableId": loc_parent_id,
                "atmosphere": "Salt air and neon spill",
                "readiness": "basic",
            },
        ),
        BibleEntity(
            entityType="location",
            entityKey="warehouse-12",
            displayName="Warehouse 12",
            stableId=loc_child_b_id,
            data={
                "description": "Locked storage with a hidden archive room.",
                "parentStableId": loc_parent_id,
                "atmosphere": "Claustrophobic, echoing",
                "readiness": "basic",
            },
        ),
        BibleEntity(
            entityType="wardrobe",
            entityKey="mara-raincoat",
            displayName="Mara's raincoat",
            data={
                "description": "Charcoal trench with reflective trim.",
                "characterStableId": char_a_id,
                "sceneIds": [demo_scene_a],
                "items": ["charcoal trench", "black boots"],
            },
        ),
        BibleEntity(
            entityType="production_object",
            entityKey="evidence-drive",
            displayName="Encrypted evidence drive",
            data={
                "description": "Small drive recovered from Pier Seven.",
                "objectKind": "prop",
                "significance": "MacGuffin for act one",
                "ownerStableId": char_a_id,
                "locationStableId": loc_child_a_id,
                "state": "intact",
                "readiness": "basic",
            },
        ),
        BibleEntity(
            entityType="visual_language",
            entityKey="global-visual-language",
            displayName="Global visual language",
            data={
                "description": "Neo-noir palette with sodium-vapor highlights.",
                "colorPalette": "Teal shadows, amber practicals",
                "lightingStyle": "Motivated streetlight with soft fill",
                "cameraStyle": "Handheld intimacy, slow push-ins",
                "moodKeywords": ["rain", "neon", "lonely", "urgent"],
            },
        ),
        BibleEntity(
            entityType="canon_record",
            entityKey="canon-mara-journalist",
            displayName="Mara is a journalist",
            lifecycleStatus="approved",
            data={
                "claim": "Mara Voss is a working investigative journalist.",
                "entityStableId": char_a_id,
                "status": "approved",
            },
        ),
        BibleEntity(
            entityType="canon_record",
            entityKey="canon-elias-former-detective",
            displayName="Elias former detective",
            lifecycleStatus="approved",
            data={
                "claim": "Elias Mercer resigned from the police force under disputed circumstances.",
                "entityStableId": char_b_id,
                "status": "approved",
            },
        ),
        BibleEntity(
            entityType="production_decision",
            entityKey="decision-no-daylight",
            displayName="No daylight exteriors",
            data={
                "decision": "Exterior scenes stay at night or blue-hour only.",
                "rationale": "Preserves the neo-noir look bible-wide.",
                "impact": "Scheduling and location scouting",
            },
        ),
        BibleEntity(
            entityType="reference_link",
            entityKey="ref-mara-identity",
            displayName="Mara identity reference",
            data={
                "assetId": "asset-demo-mara-001",
                "targetStableId": char_a_id,
                "purpose": "identity",
                "priority": 1,
                "polarity": "positive",
                "primary": True,
            },
        ),
        BibleEntity(
            entityType="reference_link",
            entityKey="ref-harbor-style",
            displayName="Harbor style reference",
            data={
                "assetId": "asset-demo-harbor-001",
                "targetStableId": loc_parent_id,
                "purpose": "style",
                "priority": 2,
                "polarity": "positive",
                "primary": False,
            },
        ),
        BibleEntity(
            entityType="continuity_state",
            entityKey="cont-mara-coat-scene-a",
            displayName="Mara coat scene A",
            data={
                "aspect": "wardrobe",
                "entityStableId": char_a_id,
                "sceneId": demo_scene_a,
                "expectedValue": "charcoal trench",
                "actualValue": "charcoal trench",
                "resolved": True,
            },
        ),
        BibleEntity(
            entityType="continuity_state",
            entityKey="cont-mara-coat-scene-b",
            displayName="Mara coat scene B mismatch",
            data={
                "aspect": "wardrobe",
                "entityStableId": char_a_id,
                "fromSceneId": demo_scene_a,
                "toSceneId": demo_scene_b,
                "expectedValue": "charcoal trench",
                "actualValue": "red jacket",
                "resolved": False,
            },
        ),
    ]

    facts = [
        BibleFact(
            entityKey=None,
            factType="scene_fact",
            statement=f"Scene '{demo_scene_a}': Mara searches Pier Seven in the rain.",
            data={"sceneId": demo_scene_a, "sceneIndex": 1},
        ),
        BibleFact(
            entityKey=None,
            factType="scene_fact",
            statement=f"Scene '{demo_scene_b}': Elias confronts Mara about the missing drive.",
            data={"sceneId": demo_scene_b, "sceneIndex": 2},
        ),
    ]

    ops.create_bible_with_first_version(
        db,
        project_id=project_id,
        entities=entities,
        facts=facts,
        summary="Seeded demo Production Bible (M2.3)",
        change_reason="seed_demo",
        created_by="seed",
    )
    return {
        "seeded": True,
        "projectId": project_id,
        "entityCount": len(entities),
        "factCount": len(facts),
    }
