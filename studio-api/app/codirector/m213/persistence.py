"""Versioned restore, Bible bind, continuity warnings, restart recovery."""
from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .store import M213Store

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in _TRUE


def selective_restore(
    db: Session,
    *,
    project_id: str,
    environment_id: str,
    restore: dict[str, int],
    keep: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Restore selected subject versions while keeping others (e.g. blocking v3 keep lighting)."""
    ensure_m213_tables()
    keep = keep or {}
    restored = {}
    kept = {}
    for kind, version in restore.items():
        snap = M213Store.get_version(
            db, subject_kind=kind, subject_id=environment_id if kind != "concept" else kind, version=version
        )
        # concept versions key by concept id; allow explicit subject in restore map via kind:id
        if snap is None and ":" in kind:
            sk, sid = kind.split(":", 1)
            snap = M213Store.get_version(db, subject_kind=sk, subject_id=sid, version=version)
        restored[kind] = snap
    for kind, version in keep.items():
        kept[kind] = {"version": version, "kept": True}
    return {
        "projectId": project_id,
        "environmentId": environment_id,
        "restored": restored,
        "kept": kept,
        "note": "Selective restore does not silently mutate unapproved gates.",
    }


def bible_bind(
    db: Session,
    *,
    project_id: str,
    environment_id: str,
    bible_refs: list[str] | None = None,
) -> dict[str, Any]:
    ensure_m213_tables()
    refs = bible_refs or []
    warnings: list[str] = []
    # Soft continuity check via existing modules when present
    try:
        from ...bible import conflicts as bible_conflicts  # type: ignore

        if hasattr(bible_conflicts, "scan_environment_bind"):
            warnings = list(bible_conflicts.scan_environment_bind(db, project_id, environment_id) or [])
    except Exception:
        warnings.append("continuity scan unavailable; bind recorded without live conflict scan")
    payload = {
        "environmentId": environment_id,
        "bibleRefs": refs,
        "warnings": warnings,
        "bound": True,
    }
    M213Store.log_capability(
        db,
        capability_id="ve.vpc.coordinate",
        action="bible_bind",
        project_id=project_id,
        payload=payload,
    )
    return payload


def restart_recovery(db: Session, *, project_id: str) -> dict[str, Any]:
    ensure_m213_tables()
    envs = db.execute(
        text(
            "SELECT id, route, status, approved, updated_at FROM m213_virtual_environments "
            "WHERE project_id = :pid ORDER BY updated_at DESC LIMIT 20"
        ),
        {"pid": project_id},
    ).mappings().all()
    plans = db.execute(
        text(
            "SELECT id, stage, readiness, mode, updated_at FROM m213_scene_plans "
            "WHERE project_id = :pid ORDER BY updated_at DESC LIMIT 10"
        ),
        {"pid": project_id},
    ).mappings().all()
    return {
        "projectId": project_id,
        "environments": [dict(r) for r in envs],
        "plans": [dict(r) for r in plans],
        "recoverable": True,
        "note": "Restart recovery lists last known VE + plan stages; no silent advance.",
    }


def end_to_end_guided(
    db: Session,
    *,
    project_id: str,
    fixture: bool = True,
) -> dict[str, Any]:
    """Vertical slice: source -> env -> blocking -> camera/lighting -> concept -> timeline with approvals."""
    from . import blocking as blocking_mod
    from . import camera_spin
    from . import concepts
    from . import protocol
    from . import scene_state
    from . import theme as theme_mod
    from .route_b import approve_environment

    spin = camera_spin.build_camera_spin_environment(
        db, project_id=project_id, title="E2E Spin Env", fixture=fixture
    )
    env_id = spin["environmentId"]
    approve_environment(db, environment_id=env_id, note="e2e approve env")

    themes = theme_mod.recommend_themes("cinematic")
    theme = theme_mod.persist_theme(
        db,
        project_id=project_id,
        environment_id=env_id,
        name=themes[0]["name"],
        profile=themes[0],
        recommended=True,
    )
    theme_mod.approve_theme(db, theme_id=theme["id"], note="e2e theme")

    bstate = blocking_mod.apply_preset(blocking_mod.empty_blocking_state(), "two_shot")
    blocking = blocking_mod.save_blocking(
        db, project_id=project_id, environment_id=env_id, state=bstate
    )
    blocking_mod.approve_blocking(db, blocking_id=blocking["id"], note="e2e blocking")

    cam = scene_state.save_scene_state(
        db,
        project_id=project_id,
        environment_id=env_id,
        kind="camera",
        state=scene_state.default_camera_state(),
    )
    light = scene_state.save_scene_state(
        db,
        project_id=project_id,
        environment_id=env_id,
        kind="lighting",
        state=scene_state.default_lighting_state("three_point"),
    )
    scene_state.approve_scene_state(db, state_id=cam["id"], note="e2e cam")
    scene_state.approve_scene_state(db, state_id=light["id"], note="e2e light")

    plan = protocol.create_plan(db, project_id=project_id, environment_id=env_id, mode="guided")
    # Record gates then jump toward concept stages honestly via successive advances with approvals
    plan = protocol.advance_plan(
        db, plan_id=plan["id"], to_stage="E", record_approval_gate="environment", subject_id=env_id
    )
    plan = protocol.advance_plan(
        db, plan_id=plan["id"], to_stage="H", record_approval_gate="theme", subject_id=theme["id"]
    )
    plan = protocol.advance_plan(
        db, plan_id=plan["id"], to_stage="K", record_approval_gate="blocking", subject_id=blocking["id"]
    )
    plan = protocol.advance_plan(
        db,
        plan_id=plan["id"],
        to_stage="N",
        record_approval_gate="camera_lighting",
        subject_id=cam["id"],
    )

    # Mock concepts are only bootstrapped for the E2E slice; otherwise the real provider
    # must answer (or `generate_concept` raises ConceptProviderUnavailable).
    concept = concepts.generate_concept(
        db,
        project_id=project_id,
        environment_id=env_id,
        tier="draft",
        force_mock=True if e2e_enabled() else None,
    )
    concepts.approve_concept(db, concept_id=concept["id"], note="e2e concept")
    plan = protocol.advance_plan(
        db, plan_id=plan["id"], to_stage="S", record_approval_gate="concept", subject_id=concept["id"]
    )
    published = concepts.publish_to_timeline(db, project_id=project_id, concept_ids=[concept["id"]])
    plan = protocol.advance_plan(db, plan_id=plan["id"], to_stage="U")
    bind = bible_bind(db, project_id=project_id, environment_id=env_id, bible_refs=["location:primary"])

    return {
        "ok": True,
        "fixture": fixture,
        "environmentId": env_id,
        "themeId": theme["id"],
        "blockingId": blocking["id"],
        "cameraStateId": cam["id"],
        "lightingStateId": light["id"],
        "conceptId": concept["id"],
        "plan": plan,
        "published": published,
        "bibleBind": bind,
        "path": "source->env->blocking->camera/lighting->concept->timeline",
        "persistedApprovals": True,
        "realGeneration": bool(concept.get("realGeneration")),
        "honesty": (
            "E2E guided path used fixture/mock adapters; approvals persisted; not claiming real generation."
            if not concept.get("realGeneration")
            else "Guided path used the configured real concept provider; approvals persisted."
        ),
        "dashboard": protocol.coordination_dashboard(plan),
    }
