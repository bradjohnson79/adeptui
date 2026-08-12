"""Regression test for delete_project_residue cascade coverage.

Covers the eight indirect cascades in project_cleanup._INDIRECT_PROJECT_DELETES:
- asset_versions / asset_edges (via assets.id)
- codirector_approvals / codirector_execution_receipts (via codirector_proposals.id)
- creative_item_versions (via creative_items.id)
- m212_lesson_versions (via m212_lessons.id)
- m28_recipe_stages (via m28_recipes.id)
- m28_shot_profile_versions (via m28_shot_profiles.id)

The authoritative deletion path (DELETE /api/projects/{id}) must remove these
indirect children alongside the project-scoped rows, so that no dangling
children survive project deletion.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text

from app.asset_graph import AssetEdge, AssetVersion
from app.db import (
    Asset,
    CoDirectorApproval,
    CoDirectorExecutionReceipt,
    CoDirectorProposal,
    Project,
    Scene,
    SessionLocal,
    init_db,
)
from app.project_cleanup import delete_project_residue


def _seed_project_with_indirect_children() -> tuple[str, str, str, str, str, str]:
    """Create a project + scene + asset + version + edge + proposal + approval + receipt."""
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        scene_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        edge_id = str(uuid.uuid4())
        proposal_id = str(uuid.uuid4())
        approval_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        other_asset_id = str(uuid.uuid4())  # peer for the edge

        db.add(Project(id=project_id, name="Cascade Test"))
        db.add(Scene(id=scene_id, project_id=project_id, index=0, name="Scene 1"))
        db.add(Asset(id=asset_id, project_id=project_id, kind="image", tag="hero", filename="hero.png", path=f"/tmp/{asset_id}.png"))
        db.add(Asset(id=other_asset_id, project_id=project_id, kind="image", tag="bg", filename="bg.png", path=f"/tmp/{other_asset_id}.png"))
        # Commit parents first so SQLite FK checks pass for proposal + children.
        db.commit()
        db.add(
            CoDirectorProposal(
                id=proposal_id,
                project_id=project_id,
                proposal_type="bible_update",
                title="test proposal",
                status="approved",
            )
        )
        db.commit()
        db.add(
            AssetVersion(
                id=version_id,
                asset_id=asset_id,
                version=1,
                op="generate",
                model="test-model",
            )
        )
        db.add(
            AssetEdge(
                id=edge_id,
                from_id=asset_id,
                to_id=other_asset_id,
                relation="derived_from",
            )
        )
        db.add(
            CoDirectorApproval(
                id=approval_id,
                proposal_id=proposal_id,
                decision="approved",
            )
        )
        db.add(
            CoDirectorExecutionReceipt(
                id=receipt_id,
                proposal_id=proposal_id,
                input_hash="0" * 64,
                status="success",
            )
        )
        db.commit()
        return project_id, version_id, edge_id, proposal_id, approval_id, receipt_id
    finally:
        db.close()


def _count(db, model, **filters) -> int:
    q = db.query(model)
    for k, v in filters.items():
        q = q.filter(getattr(model, k) == v)
    return q.count()


def _seed_m20_m28_indirect_children(project_id: str) -> dict[str, str]:
    """Seed the 4 additional indirect tables (creative_items/m212/m28 chains).

    Uses raw SQL because these tables have no ORM models. Returns the seeded IDs.
    """
    db = SessionLocal()
    try:
        creative_item_id = str(uuid.uuid4())
        creative_version_id = str(uuid.uuid4())
        m212_lesson_id = str(uuid.uuid4())
        m212_lesson_version_id = str(uuid.uuid4())
        m28_recipe_id = str(uuid.uuid4())
        m28_recipe_stage_id = str(uuid.uuid4())
        m28_shot_profile_id = str(uuid.uuid4())
        m28_shot_profile_version_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # creative_items (project-scoped parent) + creative_item_versions (child)
        db.execute(text(
            "INSERT INTO creative_items (id, kind, category, subcategory, scope, name, slug, project_id) "
            "VALUES (:id, 'preset', '', '', 'project', 'ci', 'ci', :pid)"
        ), {"id": creative_item_id, "pid": project_id})
        db.commit()
        db.execute(text(
            "INSERT INTO creative_item_versions (id, item_id, version) VALUES (:id, :item_id, 1)"
        ), {"id": creative_version_id, "item_id": creative_item_id})

        # m212_lessons (project-scoped parent) + m212_lesson_versions (child)
        db.execute(text(
            "INSERT INTO m212_lessons (id, layer, status, text, project_id, created_at, updated_at) "
            "VALUES (:id, 'scene', 'draft', 'test', :pid, :ts, :ts)"
        ), {"id": m212_lesson_id, "pid": project_id, "ts": now})
        db.commit()
        db.execute(text(
            "INSERT INTO m212_lesson_versions (id, lesson_id, version, action, created_at) "
            "VALUES (:id, :lesson_id, 1, 'create', :ts)"
        ), {"id": m212_lesson_version_id, "lesson_id": m212_lesson_id, "ts": now})

        # m28_recipes (project-scoped parent) + m28_recipe_stages (child, FK)
        db.execute(text(
            "INSERT INTO m28_recipes (id, project_id, name, status, created_at) "
            "VALUES (:id, :pid, 'recipe', 'draft', :ts)"
        ), {"id": m28_recipe_id, "pid": project_id, "ts": now})
        db.commit()
        db.execute(text(
            "INSERT INTO m28_recipe_stages (id, recipe_id, stage_index, status) "
            "VALUES (:id, :recipe_id, 0, 'pending')"
        ), {"id": m28_recipe_stage_id, "recipe_id": m28_recipe_id})

        # m28_shot_profiles (project-scoped parent) + m28_shot_profile_versions (child, FK)
        db.execute(text(
            "INSERT INTO m28_shot_profiles (id, project_id, name, created_at) "
            "VALUES (:id, :pid, 'profile', :ts)"
        ), {"id": m28_shot_profile_id, "pid": project_id, "ts": now})
        db.commit()
        db.execute(text(
            "INSERT INTO m28_shot_profile_versions (id, profile_id, version, payload_json, created_at) "
            "VALUES (:id, :profile_id, 1, '{}', :ts)"
        ), {"id": m28_shot_profile_version_id, "profile_id": m28_shot_profile_id, "ts": now})

        db.commit()
        return {
            "creative_item_id": creative_item_id,
            "creative_version_id": creative_version_id,
            "m212_lesson_id": m212_lesson_id,
            "m212_lesson_version_id": m212_lesson_version_id,
            "m28_recipe_id": m28_recipe_id,
            "m28_recipe_stage_id": m28_recipe_stage_id,
            "m28_shot_profile_id": m28_shot_profile_id,
            "m28_shot_profile_version_id": m28_shot_profile_version_id,
        }
    finally:
        db.close()


def _row_exists(db, table: str, row_id: str) -> bool:
    return db.execute(text(f'SELECT 1 FROM "{table}" WHERE id = :id'), {"id": row_id}).first() is not None


def test_delete_project_residue_cleans_indirect_cascades() -> None:
    project_id, version_id, edge_id, proposal_id, approval_id, receipt_id = (
        _seed_project_with_indirect_children()
    )

    db = SessionLocal()
    try:
        # Sanity: the seeded indirect children exist before deletion.
        assert db.get(AssetVersion, version_id) is not None
        assert db.get(AssetEdge, edge_id) is not None
        assert db.get(CoDirectorApproval, approval_id) is not None
        assert db.get(CoDirectorExecutionReceipt, receipt_id) is not None
        assert db.get(CoDirectorProposal, proposal_id) is not None

        delete_project_residue(db, project_id)
        db.commit()

        # The four indirect tables must be emptied for this project.
        assert db.get(AssetVersion, version_id) is None, "asset_versions row survived deletion"
        assert db.get(AssetEdge, edge_id) is None, "asset_edges row survived deletion"
        assert db.get(CoDirectorApproval, approval_id) is None, "codirector_approvals row survived deletion"
        assert db.get(CoDirectorExecutionReceipt, receipt_id) is None, (
            "codirector_execution_receipts row survived deletion"
        )
        # The proposal itself is project-scoped and must also be gone.
        assert db.get(CoDirectorProposal, proposal_id) is None, "codirector_proposals row survived deletion"
        # And the project-scoped parents.
        assert _count(db, Asset, project_id=project_id) == 0
        assert _count(db, Scene, project_id=project_id) == 0
    finally:
        db.close()


def test_delete_project_residue_preserves_other_projects() -> None:
    """A second project's indirect children must NOT be touched when deleting the first."""
    p1 = _seed_project_with_indirect_children()
    p2 = _seed_project_with_indirect_children()
    project1_id, *_ = p1
    project2_id, v2, e2, prop2, appr2, rec2 = p2

    db = SessionLocal()
    try:
        delete_project_residue(db, project1_id)
        db.commit()

        # Project 1's children gone (already asserted above for fresh seed);
        # Project 2's children must remain intact.
        assert db.get(AssetVersion, v2) is not None, "deleted other project's asset_versions"
        assert db.get(AssetEdge, e2) is not None, "deleted other project's asset_edges"
        assert db.get(CoDirectorApproval, appr2) is not None, "deleted other project's approvals"
        assert db.get(CoDirectorExecutionReceipt, rec2) is not None, "deleted other project's receipts"
        assert db.get(CoDirectorProposal, prop2) is not None, "deleted other project's proposals"

        # Cleanup project 2 so it doesn't leak into other tests.
        delete_project_residue(db, project2_id)
        db.commit()
    finally:
        db.close()


def test_delete_project_residue_cleans_m20_m28_indirect_cascades() -> None:
    """The 4 additional indirect tables (creative/m212/m28 chains) must be cleaned."""
    project_id, *_ = _seed_project_with_indirect_children()
    ids = _seed_m20_m28_indirect_children(project_id)

    db = SessionLocal()
    try:
        # Sanity: seeded indirect children exist.
        assert _row_exists(db, "creative_item_versions", ids["creative_version_id"])
        assert _row_exists(db, "m212_lesson_versions", ids["m212_lesson_version_id"])
        assert _row_exists(db, "m28_recipe_stages", ids["m28_recipe_stage_id"])
        assert _row_exists(db, "m28_shot_profile_versions", ids["m28_shot_profile_version_id"])
        # And the project-scoped parents.
        assert _row_exists(db, "creative_items", ids["creative_item_id"])
        assert _row_exists(db, "m212_lessons", ids["m212_lesson_id"])
        assert _row_exists(db, "m28_recipes", ids["m28_recipe_id"])
        assert _row_exists(db, "m28_shot_profiles", ids["m28_shot_profile_id"])

        delete_project_residue(db, project_id)
        db.commit()

        # All 4 indirect children must be gone.
        assert not _row_exists(db, "creative_item_versions", ids["creative_version_id"]), "creative_item_versions survived"
        assert not _row_exists(db, "m212_lesson_versions", ids["m212_lesson_version_id"]), "m212_lesson_versions survived"
        assert not _row_exists(db, "m28_recipe_stages", ids["m28_recipe_stage_id"]), "m28_recipe_stages survived"
        assert not _row_exists(db, "m28_shot_profile_versions", ids["m28_shot_profile_version_id"]), "m28_shot_profile_versions survived"
        # And the project-scoped parents.
        assert not _row_exists(db, "creative_items", ids["creative_item_id"]), "creative_items survived"
        assert not _row_exists(db, "m212_lessons", ids["m212_lesson_id"]), "m212_lessons survived"
        assert not _row_exists(db, "m28_recipes", ids["m28_recipe_id"]), "m28_recipes survived"
        assert not _row_exists(db, "m28_shot_profiles", ids["m28_shot_profile_id"]), "m28_shot_profiles survived"
    finally:
        db.close()
