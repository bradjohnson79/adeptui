"""Gen P4 architecture guards — Execution Windows consume CD plan; creator batch CRUD gated.

Additive to test_timeline_architecture_guard.py (live WAVE5 15 PASS). Prefer merging
these assertions into the main guard file on apply.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W46 = ROOT / "app" / "director_timeline_w46"
CD_EW = ROOT / "app" / "codirector" / "production" / "execution_windows.py"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_gen_materialize_module_exists_and_imports_cd_plan():
    path = W46 / "execution_window_materialize.py"
    assert path.is_file(), "Gen-owned execution_window_materialize.py missing"
    text = path.read_text(encoding="utf-8")
    assert "plan_execution_windows" in text
    assert "app.codirector.production.execution_windows" in text
    assert "build_generator_switch_handoff" in text or "generator_switch_plan_delta" in text
    assert "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE" in text
    assert "CREATOR_BATCH_MUTATION_DISABLED" in text
    assert "rematerialize_batch_blocks_from_plan" in text
    # Gen must NOT embed projector PRIMARY/CARRY logic
    assert "PRIMARY start-in-window" not in text or "CD" in text  # comment OK
    assert "def plan_execution_windows" not in text


def test_service_gates_creator_batch_mutations():
    text = _read("app/director_timeline_w46/service.py")
    assert "CREATOR_BATCH_MUTATION_DISABLED" in text or "creator_batch_mutation_blocked" in text
    assert "rematerialize_execution_windows" in text
    # add/dup/delete must early-return via gate helper
    for name in ("add_batch", "duplicate_batch", "delete_batch"):
        assert f'creator_batch_mutation_blocked("{name}")' in text or (
            "creator_batch_mutation_blocked" in text and name in text
        )


def test_orchestrator_blocks_planned_duration_and_topology_switch():
    text = _read("app/director_timeline_w46/orchestrator.py")
    assert "plannedDuration" in text
    assert "CREATOR_BATCH_MUTATION_DISABLED" in text or "creator_batch_mutation_blocked" in text
    assert "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE" in text


def test_router_rematerialize_entrypoint():
    text = _read("app/director_timeline_w46/router.py")
    assert "execution-windows/rematerialize" in text
    assert "allowSceneTakeId" in text


def test_timeline_tools_add_batch_not_bypassed():
    text = _read("app/director_timeline_w46/timeline_tools.py")
    assert "service.add_batch" in text  # still routes through gated service


def test_cd_execution_windows_projector_owned_elsewhere():
    # CD file may exist on live; if present, Gen must not edit it — just assert Gen imports.
    mat = (W46 / "execution_window_materialize.py").read_text(encoding="utf-8")
    assert "from app.codirector.production.execution_windows import" in mat
