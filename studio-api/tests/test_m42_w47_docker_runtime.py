"""M42 W47 Docker Runtime Extensions — unit / contract tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ADEPT_DOCKER_RUNTIME_SIMULATE", "1")
os.environ.setdefault("STUDIO_E2E", "1")


def test_security_rejects_privileged_and_docker_sock_and_latest():
    from app.docker_runtime.manifest import default_manifest_from_image
    from app.docker_runtime.security import scan_manifest

    m = default_manifest_from_image(runtime_id="u1", name="u1", image="user/x:latest")
    m.security.privileged = True
    m.security.dockerSocket = True
    from app.docker_runtime.contracts import RuntimeMountPolicy

    m.mounts["sock"] = RuntimeMountPolicy(
        hostClass="private",
        containerPath="/var/run/docker.sock",
        access="read_write",
    )
    report = scan_manifest(m)
    assert not report.ok
    assert "privileged_mode" in report.blocked
    assert "docker_socket" in report.blocked or "docker_socket_mount" in report.blocked
    assert "unpinned_image_tag" in report.blocked


def test_core_mandatory_uninstall_blocked():
    from app.docker_runtime.service import preview_uninstall

    plan = preview_uninstall("core-comfyui", "container_image_and_private")
    assert plan.blockedReason == "core_mandatory_uninstall_blocked"


def test_workflow_import_never_mutates_core():
    from app.docker_runtime.service import import_comfy_workflow

    report = import_comfy_workflow(
        {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "hi"}},
            "3": {"class_type": "SaveVideo", "inputs": {}},
        }
    )
    assert report["ok"] is True
    assert report["mutatesCoreComfy"] is False
    assert report["buildsIsolatedRuntime"] is True
    assert report["isolatedInstallPlan"]["mutatesCoreComfy"] is False


def test_shared_preserve_and_failed_uninstall_rollback(tmp_path, monkeypatch):
    from app.docker_runtime import registry as reg_mod
    from app.docker_runtime import service
    from app.docker_runtime.contracts import DockerRuntimeDescriptor

    monkeypatch.setenv("ADEPT_DOCKER_RUNTIME_SIMULATE", "1")
    # Install a user runtime in simulate mode
    result = service.install_runtime(
        {"image": "library/adept-custom:1.0.0", "name": "Rollback Test", "runtimeId": "user-rollback-test"}
    )
    assert result.ok, result.error
    rid = "user-rollback-test"
    before = reg_mod.get_runtime(rid)
    assert before is not None

    failed = service.uninstall_runtime(rid, "container_image_and_private", force_fail_step="registry")
    assert failed.ok is False
    assert failed.rolledBack is True
    restored = reg_mod.get_runtime(rid)
    assert restored is not None
    assert restored.id == rid

    # Clean uninstall
    ok = service.uninstall_runtime(rid, "ui_only")
    assert ok.ok is True
    assert reg_mod.get_runtime(rid) is None


def test_resolver_no_silent_substitute_for_docker():
    from app.production_control.contracts import ModelDescriptor
    from app.production_control.resolve import _refresh_docker_executable
    from app.production_control.contracts import ResolvedSelection

    selection = ResolvedSelection(modality="video", activeModelId="docker-runtime:missing-rt", activeLabel="Missing")
    descriptor = ModelDescriptor(
        id="docker-runtime:missing-rt",
        modality="video",
        label="Missing",
        locality="local",
        executionClass="docker_local",
        runtimeId="missing-rt",
        capabilityLabel="Unavailable",
        supports=[],
        executable=False,
    )
    out = _refresh_docker_executable(selection, descriptor)
    assert out.executable is False
    assert out.blockedReason
    assert "not registered" in (out.blockedReason or "").lower() or "Docker" in (out.blockedReason or "")


def test_dock_models_include_execution_class():
    from app.production_control.model_registry import list_models

    models = list_models("video")
    assert any(m.executionClass == "native_local" for m in models)
    # Hosted stamped
    all_models = list_models()
    assert all(m.executionClass is not None for m in all_models)


def test_queue_hook_no_silent_fallback():
    from app.docker_runtime.queue_hooks import ensure_docker_runtime_ready

    gate = ensure_docker_runtime_ready("docker-runtime:does-not-exist")
    assert gate["ok"] is False
    assert gate["noSilentFallback"] is True


def test_codirector_runtime_tools_bound():
    from app.codirector.tools import registry

    for tid in (
        "runtime.list",
        "runtime.inspect",
        "runtime.install",
        "runtime.uninstall",
        "runtime.start",
    ):
        assert registry.find(tid) is not None


def test_gate_binary_flag_present():
    from app.docker_runtime.gate import evaluate_gate

    g = evaluate_gate()
    assert "dockerRuntimeExtensionsGo" in g
    assert isinstance(g["dockerRuntimeExtensionsGo"], bool)
