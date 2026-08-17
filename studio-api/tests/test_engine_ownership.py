"""Phase 7 — engine ownership + intent convergence tests (CDX-085, CDX-089, CDX-091).

Scope (Subagent 7C): documentation decisions + property tests, no orchestration
layer and no engine merge.

- CDX-085: scene-generation engine ownership. The Scene Creator shot flow is
  canonical; the batch REST surface is retained but gated (approval + grounding).
  Both surfaces share the single scene.generate handler, so the
  capability/provider provenance contract must match. Parity test below.
- CDX-089: Production Executive (ProductionJob store) vs execution-pack store
  (ProjectTraitRow "codirector_execution") are disjoint tables by design; each
  is idempotent on its own key. Tests assert no double-creation.
- CDX-091: four stacked intent classifiers are a documented transitional
  hybrid. Convergence property: deterministic/unified/foundation agree on
  EXECUTION vs non-EXECUTION over the routing corpus, with a FROZEN set of
  divergence exceptions; semantic-unavailable never fabricates EXECUTION.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.db import Project, ProjectTraitRow, SessionLocal, init_db
from app.codirector.routing.contracts import RouteActionClass, RouteDecision
from app.codirector.routing.deterministic import NAVIGATION_TARGETS, classify_deterministic
from app.codirector.routing.unified_intent import UnifiedIntent, UnifiedIntentKind, classify_intent, from_route_decision
from app.codirector.conversation.foundation.intent import analyze_intent

_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "codirector2_route_cases.json"
_DEFAULT_WS = frozenset(NAVIGATION_TARGETS.values())

# Frozen unified-vocabulary mapping (unified_intent.from_route_decision kind_map):
# these RouteActionClasses resolve to UnifiedIntentKind.EXECUTION.
_EXECUTION_ACTION_CLASSES: frozenset[str] = frozenset(
    {"EXECUTE_PRODUCTION", "APPROVE", "REJECT"}
)
# Foundation intents that imply execution (unified_intent._EXECUTION_FOUNDATION_INTENTS).
_EXECUTION_FOUNDATION_INTENTS: frozenset[str] = frozenset(
    {"REQUEST_GENERATION", "REQUEST_ACTION", "REQUEST_EDIT"}
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_corpus() -> list[dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _classify_kwargs(case: dict) -> dict:
    kwargs: dict = {"available_workspaces": _DEFAULT_WS}
    if case.get("pendingProposals"):
        kwargs["pending_proposal_ids"] = case["pendingProposals"]
    if case.get("stage"):
        kwargs["derived_stage"] = case["stage"]
    return kwargs


@pytest.fixture()
def db() -> Session:
    """Fresh SQLite session with production tables cleared (mirrors executive tests)."""
    from app.db import (
        ProductionJob,
        ProductionJobAttempt,
        ProductionJobAudit,
        ProductionJobDependency,
        ProductionJobEvent,
        ProductionNotification,
    )

    init_db()
    session = SessionLocal()
    session.query(ProductionJobDependency).delete()
    session.query(ProductionJobAttempt).delete()
    session.query(ProductionJobEvent).delete()
    session.query(ProductionJobAudit).delete()
    session.query(ProductionNotification).delete()
    session.query(ProductionJob).delete()
    session.query(ProjectTraitRow).delete()
    session.commit()
    session.merge(Project(id="proj-exec-1", name="Engine Ownership Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _executive_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable vision validation feature flag for executive paths. Never mock ImageGen."""
    monkeypatch.delenv("ADEPT_MOCK_IMAGEGEN", raising=False)
    monkeypatch.setenv("STUDIO_FEATURE_VISION_VALIDATION_V1", "1")
    import app.feature_flags as ff
    from app.feature_flags import FeatureFlags

    ff.feature_flags = FeatureFlags.from_env(__import__("os").environ)


def _fake_enqueue(monkeypatch: pytest.MonkeyPatch, captured: list[dict]) -> None:
    """Replace enqueue_imagegen_job with a recorder that returns fake jobs."""
    from app import storyboard_jobs as sb_mod

    def fake(db: Session, project_id: str, body: dict | None = None, **kwargs):
        captured.append(dict(body or {}))
        return SimpleNamespace(id=f"fake-job-{len(captured)}")

    monkeypatch.setattr(sb_mod, "enqueue_imagegen_job", fake)


def _scene_project_and_ers() -> tuple[Session, str, str]:
    """Create a project + ERS package; returns (db, project_id, ers_package_id)."""
    init_db()
    db = SessionLocal()
    project_id = str(uuid.uuid4())
    db.add(Project(id=project_id, name="Scene Parity Test"))
    db.commit()
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage
    from app.spatial_map.ers_persistence import save_ers_package

    pkg = EnvironmentReferencePackage(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_layout_id="layout-x",
        style_context={"visual_style": "cinematic"},
    )
    save_ers_package(db, project_id, pkg)
    db.commit()
    return db, project_id, pkg.id


# ---------------------------------------------------------------------------
# CDX-085 — scene-generation engine parity (pack vs batch provenance contract)
# ---------------------------------------------------------------------------


_SHOT_TEXT = (
    "A wide establishing shot of the glass atrium at dawn.\n"
    "A close-up of the hero turning toward the camera."
)


def test_scene_generate_pack_and_batch_share_provenance_contract(monkeypatch) -> None:
    """A shot created via the execution pack and via the batch resolves the same
    capability/provider provenance contract (model resolution parity).

    Both surfaces invoke the SAME handler (scene_generate.handle), which compiles
    each shot through entity_resolver.compile_shot_prompt and submits real
    imagegen jobs via enqueue_imagegen_job. The captured bodies must agree on
    purpose, surface_type, modelFamilyPreference, workflowKey and ERS grounding.
    """
    from app.codirector.capabilities.handlers import scene_generate as handler_mod
    from app.codirector.capabilities.registry import get_capability
    from app.codirector.execution.dispatcher import dispatch

    captured: list[dict] = []
    _fake_enqueue(monkeypatch, captured)
    db, project_id, ers_package_id = _scene_project_and_ers()
    try:
        # 1. Batch surface — the REST router calls scene_generate.handle directly.
        batch_result = handler_mod.handle(
            db,
            project_id,
            "exec_batch_surface",
            ers_package_id=ers_package_id,
            shot_requests_raw=_SHOT_TEXT,
            output_count=2,
            visual_style="",
            character_names=None,
        )
        batch_bodies = captured[:]
        captured.clear()

        # 2. Pack surface — the Co-Director execution dispatcher resolves the
        #    scene.generate capability and calls the same handler with the same
        #    compiled shot body contract.
        intent = UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="scene.generate",
            classifier_source="deterministic",
        )
        plan = asyncio.run(
            dispatch(
                db,
                project_id,
                intent,
                context={
                    "shot_requests_raw": _SHOT_TEXT,
                    "ers_package_id": ers_package_id,
                    "output_count": 2,
                    "visual_style": "",
                    "character_names": None,
                },
                pre_approved=False,
            )
        )
        pack_bodies = captured[:]

        # Provenance contract: same capability registry entry.
        cap = get_capability("scene.generate")
        assert cap is not None
        assert cap.handler_kind.value == "capability_handler"
        assert cap.surface_type == "scene_generation"

        # Same number of shots (output-count law: exactly the explicit requests).
        assert len(batch_bodies) == 2
        assert len(pack_bodies) == 2
        assert plan.capability == "scene.generate"
        assert plan.surface_type == "scene_generation"
        assert len(plan.child_jobs) == 2

        # Parity: per-shot provenance fields must match between the two surfaces.
        for idx in range(2):
            b, p = batch_bodies[idx], pack_bodies[idx]
            assert b.get("purpose") == p.get("purpose") == "scene_shot"
            # Tag embeds the run's execution_id (differs per surface by design);
            # the STRUCTURE must match: codirector_scene_<exec8>_shot<index+1>.
            assert str(b.get("tag") or "").startswith("codirector_scene_")
            assert str(p.get("tag") or "").startswith("codirector_scene_")
            assert str(b.get("tag") or "").endswith(f"_shot{idx + 1}")
            assert str(p.get("tag") or "").endswith(f"_shot{idx + 1}")
            # modelFamilyPreference resolution parity (same style/ERS inputs).
            assert b.get("modelFamilyPreference") == p.get("modelFamilyPreference")
            assert b.get("creativeContext", {}).get("workflowKey") == p.get("creativeContext", {}).get("workflowKey")
            assert b.get("creativeContext", {}).get("ersPackageId") == p.get("creativeContext", {}).get("ersPackageId")
            assert (b.get("prompt") or "").strip() == (p.get("prompt") or "").strip()

        # Both surfaces honor the ERS grounding (never zero-grounding).
        for body in batch_bodies + pack_bodies:
            assert body.get("creativeContext", {}).get("ersPackageId") == ers_package_id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-089 — Production Executive vs execution-pack store ownership
# ---------------------------------------------------------------------------


def test_executive_closed_loop_same_idempotency_key_no_double_creation(db: Session) -> None:
    from app.codirector.executive.service import ProductionExecutiveService
    from app.db import ProductionJob

    first = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="sc-1", owner="user",
        idempotency_key="k-cdx089", provider="local",
    )
    count_first = db.query(ProductionJob).filter(ProductionJob.project_id == "proj-exec-1").count()
    assert first["reused"] is False
    assert count_first == 6  # storyboard, image, validate, proposal, await, apply

    second = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="sc-1", owner="user",
        idempotency_key="k-cdx089", provider="local",
    )
    count_second = db.query(ProductionJob).filter(ProductionJob.project_id == "proj-exec-1").count()
    assert second["reused"] is True
    assert count_second == count_first, "same idempotency key must not double-create jobs"


def test_pack_store_same_execution_id_no_double_creation(db: Session) -> None:
    from app.codirector.execution.contracts import ExecutionPlan
    from app.codirector.execution.pack_store import PACK_CATEGORY, save_pack

    pack = ExecutionPlan(
        execution_id="exec-cdx089",
        capability="scene.generate",
        project_id="proj-exec-1",
    )
    save_pack(db, "proj-exec-1", pack)
    save_pack(db, "proj-exec-1", pack)

    rows = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == "proj-exec-1",
            ProjectTraitRow.category == PACK_CATEGORY,
            ProjectTraitRow.key == "exec-cdx089",
        )
        .count()
    )
    assert rows == 1, "re-saving the same execution_id must upsert, never duplicate"


def test_executive_and_pack_stores_are_disjoint_by_design(db: Session) -> None:
    """No cross-store writes: the executive never writes execution packs and the
    pack store never writes ProductionJob rows — same idempotency key cannot
    materialize in both stores."""
    from app.codirector.execution.contracts import ExecutionPlan
    from app.codirector.execution.pack_store import PACK_CATEGORY, save_pack
    from app.codirector.executive.service import ProductionExecutiveService
    from app.db import ProductionJob

    # Executive side writes ProductionJob rows only.
    ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="sc-1", owner="user",
        idempotency_key="disjoint-key", provider="local",
    )
    pack_rows = (
        db.query(ProjectTraitRow)
        .filter(ProjectTraitRow.project_id == "proj-exec-1", ProjectTraitRow.category == PACK_CATEGORY)
        .count()
    )
    assert pack_rows == 0, "Production Executive must not write execution packs"

    # Pack side writes ProjectTraitRow only.
    save_pack(
        db,
        "proj-exec-1",
        ExecutionPlan(execution_id="exec-disjoint", capability="scene.generate", project_id="proj-exec-1"),
    )
    job_rows = db.query(ProductionJob).filter(ProductionJob.project_id == "proj-exec-1").count()
    assert job_rows == 6, "pack store must not write ProductionJob rows (only the 6 executive jobs exist)"
    # No ProductionJob carries the pack execution_id as an idempotency key.
    idem_hit = (
        db.query(ProductionJob)
        .filter(
            ProductionJob.project_id == "proj-exec-1",
            ProductionJob.idempotency_key == "exec-disjoint",
        )
        .count()
    )
    assert idem_hit == 0


# ---------------------------------------------------------------------------
# CDX-091 — intent-classifier convergence property (transitional hybrid)
# ---------------------------------------------------------------------------


# Frozen divergence exceptions. If a NEW divergence appears (classifier change),
# this test fails and the exception must be explicitly documented here.
DOCUMENTED_UNIFIED_DIVERGENCES: dict[str, tuple[str | None, str, str]] = {
    # Deterministic says MODIFY_KNOWLEDGE (proposal lane); the foundation
    # REQUEST_ACTION override (classify_intent step 2) escalates to EXECUTION.
    # Documented transitional divergence — the proposal lane is bypassed.
    "case-4": (
        "MODIFY_KNOWLEDGE",
        "EXECUTION",
        "foundation REQUEST_ACTION overrides proposal-class deterministic result",
    ),
    # APPROVE/REJECT are handled by the proposal-approval lane (ProposalService),
    # NOT the execution dispatcher; the unified classifier intentionally returns
    # CONVERSATION while the deterministic action class is APPROVE/REJECT.
    "case-9": ("APPROVE", "CONVERSATION", "approval lane handled outside execution dispatch"),
    "case-10": ("REJECT", "CONVERSATION", "rejection lane handled outside execution dispatch"),
}


def test_unified_agrees_with_deterministic_on_execution_except_documented() -> None:
    divergences: dict[str, tuple[str | None, str]] = {}
    for case in _load_corpus():
        det = classify_deterministic(case["message"], **_classify_kwargs(case))
        det_action = det.actionClass.value if det else None
        det_exec = det_action in _EXECUTION_ACTION_CLASSES
        foundation = analyze_intent(case["message"])
        unified = classify_intent(case["message"], {}, route_decision=det, foundation_intent=foundation)
        if unified.is_execution != det_exec:
            divergences[case["id"]] = (det_action, unified.intent.value)

    expected = {k: (v[0], v[1]) for k, v in DOCUMENTED_UNIFIED_DIVERGENCES.items()}
    assert divergences == expected, (
        "Classifier convergence property violated: deterministic and unified "
        f"disagree on EXECUTION vs non-EXECUTION beyond the documented set. "
        f"Actual divergences: {divergences}"
    )


def test_foundation_agrees_with_unified_on_execution_over_corpus() -> None:
    divergences: list[str] = []
    for case in _load_corpus():
        det = classify_deterministic(case["message"], **_classify_kwargs(case))
        foundation = analyze_intent(case["message"])
        f_value = foundation.primary_intent.value if foundation.primary_intent else "UNKNOWN"
        f_exec = f_value in _EXECUTION_FOUNDATION_INTENTS
        unified = classify_intent(case["message"], {}, route_decision=det, foundation_intent=foundation)
        if f_exec != unified.is_execution:
            divergences.append(f"{case['id']}: foundation={f_value} unified={unified.intent.value}")
    assert divergences == [], (
        "Foundation classifier and unified classifier diverged on EXECUTION "
        f"classification over the routing corpus: {divergences}"
    )


def test_from_route_decision_adapter_execution_mapping_is_frozen() -> None:
    """The RouteDecision -> UnifiedIntent adapter maps the three execution action
    classes to EXECUTION. Frozen contract (unified_intent.from_route_decision)."""
    for action in _EXECUTION_ACTION_CLASSES:
        rd = RouteDecision(actionClass=RouteActionClass(action), confidence=0.9)
        unified = from_route_decision(rd)
        assert unified.is_execution, f"{action} must map to EXECUTION"
        assert unified.dispatch.value in {"deterministic", "curated_tools"}


def test_semantic_unavailable_never_fabricates_execution(monkeypatch) -> None:
    """When the semantic (LLM) classifier is unavailable, the fallback must NOT
    manufacture an EXECUTION decision — it returns UNKNOWN (non-execution).

    This locks the convergence property for the semantic layer without requiring
    a live provider: no provider -> classify_semantic returns None -> fallback
    yields RouteDecision(actionClass=UNKNOWN), which maps to non-EXECUTION.
    """
    from app.codirector.routing import semantic as semantic_mod

    def _no_provider(*args, **kwargs):
        raise RuntimeError("no provider configured in test environment")

    monkeypatch.setattr(semantic_mod, "get_provider", _no_provider)

    async def _run() -> RouteDecision:
        return await semantic_mod.route_with_semantic_fallback(
            "generate a scene shot now",
            deterministic_result=None,
            context={},
        )

    decision = asyncio.run(_run())
    assert decision.actionClass == RouteActionClass.UNKNOWN
    assert decision.actionClass.value not in _EXECUTION_ACTION_CLASSES
    assert decision.actionClass not in {RouteActionClass.EXECUTE_PRODUCTION}
