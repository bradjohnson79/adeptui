"""Boot Manager verdict fixtures. External process boundaries are the facts."""

from app.boot.evaluate import BootFacts, evaluate, healthy_facts


def _ids(report: dict) -> dict[str, str]:
    return {row["id"]: row["result"] for row in report["checks"]}


def test_healthy_system_is_go():
    report = evaluate(healthy_facts())
    assert report["verdict"] == "GO"
    assert report["headline"] == "ADEPT UI READY — GO"
    assert report["failed"] == []
    assert report["progressPct"] == 100


def test_api_unavailable_is_no_go():
    facts = healthy_facts()
    facts.api_pids = []
    facts.api_commands = {}
    facts.api_health_status = None
    report = evaluate(facts)
    assert report["verdict"] == "NO-GO"
    assert _ids(report)["studio_api_health"] == "FAIL"
    assert _ids(report)["studio_api_process"] == "FAIL"


def test_vite_unavailable_is_no_go():
    facts = healthy_facts()
    facts.vite_pids = []
    facts.vite_status = None
    facts.vite_body = ""
    report = evaluate(facts)
    assert report["verdict"] == "NO-GO"
    assert _ids(report)["vite_health"] == "FAIL"


def test_wrong_process_on_8758_is_no_go():
    facts = healthy_facts()
    facts.api_commands = {100: "python -m http.server 8758"}
    report = evaluate(facts)
    assert _ids(report)["studio_api_process"] == "FAIL"
    assert report["verdict"] == "NO-GO"


def test_wrong_process_on_5173_is_no_go():
    facts = healthy_facts()
    facts.vite_commands = {200: "python -m http.server 5173"}
    facts.vite_body = "not adept"
    report = evaluate(facts)
    assert _ids(report)["vite_process"] == "FAIL"
    assert _ids(report)["vite_health"] == "FAIL"


def test_stale_pid_with_no_listener_is_no_go():
    facts = healthy_facts()
    facts.api_pids = []
    facts.api_commands = {}
    report = evaluate(facts)
    assert _ids(report)["studio_api_owner"] == "FAIL"


def test_duplicate_api_and_vite_are_no_go():
    facts = healthy_facts()
    facts.api_pids = [1, 2]
    facts.vite_pids = [3, 4]
    report = evaluate(facts)
    assert _ids(report)["duplicate_api"] == "FAIL"
    assert _ids(report)["duplicate_vite"] == "FAIL"
    assert report["verdict"] == "NO-GO"


def test_comfy_unavailable_does_not_block_go():
    facts = healthy_facts()
    facts.comfy_healthy = False
    facts.comfy_pids = []
    report = evaluate(facts)
    assert report["verdict"] == "GO"
    assert _ids(report)["comfy"] == "OPTIONAL"


def test_codirector_and_timeline_failures_are_no_go():
    facts = healthy_facts()
    facts.codirector_tools = 0
    report = evaluate(facts)
    assert _ids(report)["codirector"] == "FAIL"
    facts = healthy_facts()
    facts.h3_legal = False
    facts.h3_width = 1920
    facts.h3_height = 1080
    report = evaluate(facts)
    assert _ids(report)["timeline"] == "FAIL"
    assert report["verdict"] == "NO-GO"


def test_library_failure_is_no_go_and_optional_provider_is_not():
    facts = healthy_facts()
    facts.library_ok = False
    facts.library_error = "library unavailable"
    assert evaluate(facts)["verdict"] == "NO-GO"
    facts = healthy_facts()
    facts.image_hosted = 0
    facts.update_source_online = False
    facts.voice_provider_optional = "External voice provider is not configured."
    report = evaluate(facts)
    assert report["verdict"] == "GO"
    assert any(row["result"] == "OPTIONAL" for row in report["optional"])


def test_timeout_and_not_run_are_no_go():
    facts = healthy_facts()
    facts.timed_out = ("timeline",)
    assert evaluate(facts)["verdict"] == "NO-GO"
    assert _ids(evaluate(facts))["timeline"] == "TIMEOUT"
    facts = healthy_facts()
    facts.not_run = ("library",)
    assert _ids(evaluate(facts))["library"] == "NOT_RUN"


def test_packaged_desktop_boot_uses_its_own_port_and_not_vite():
    facts = healthy_facts()
    facts.runtime_mode = "electron-packaged"
    facts.api_port = 8760
    facts.api_commands = {100: "python -m uvicorn app.main:app --port 8760"}
    facts.vite_pids = []
    facts.vite_status = None
    facts.vite_body = ""
    report = evaluate(facts)
    assert report["studioApi"]["port"] == 8760
    assert report["studioApi"]["baseUrl"] == "http://127.0.0.1:8760"
    assert report["studioApi"]["runtimeMode"] == "electron-packaged"
    owner = next(row for row in report["checks"] if row["id"] == "studio_api_owner")
    assert "8760" in owner["detail"]
    assert report["verdict"] == "GO"
    vite = next(row for row in report["checks"] if row["id"] == "vite_health")
    assert vite["required"] is False


def test_packaged_endpoint_reads_desktop_env(monkeypatch):
    from app.runtime_endpoint import resolve_studio_api_endpoint

    monkeypatch.setenv("ADEPT_RUNTIME_MODE", "electron-packaged")
    monkeypatch.setenv("ADEPT_STUDIO_API_PORT", "8760")
    endpoint = resolve_studio_api_endpoint()
    assert endpoint["studioApiPort"] == 8760
    assert endpoint["runtimeMode"] == "electron-packaged"
    assert endpoint["studioApiBaseUrl"] == "http://127.0.0.1:8760"


def test_dev_endpoint_stays_8758(monkeypatch):
    from app.runtime_endpoint import resolve_studio_api_endpoint

    monkeypatch.delenv("ADEPT_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("ADEPT_STUDIO_API_PORT", raising=False)
    endpoint = resolve_studio_api_endpoint()
    assert endpoint["studioApiPort"] == 8758
    assert endpoint["runtimeMode"] == "web-development"


def test_slow_passing_check_still_goes():
    report = evaluate(healthy_facts(), durations={"timeline": 2500, "total": 2600})
    timeline = next(row for row in report["checks"] if row["id"] == "timeline")
    assert timeline["result"] == "PASS"
    assert timeline["durationMs"] == 2500
    assert report["verdict"] == "GO"


def test_cloud_12_is_outside_adept_ui_11_boot():
    """Cloud 1.2 has zero authority over Adept UI 1.1 readiness."""
    import json

    for mode in ("web-development", "electron-packaged", "electron-development"):
        facts = healthy_facts()
        facts.runtime_mode = mode
        if mode == "electron-packaged":
            facts.api_port = 8760
            facts.api_commands = {100: "python -m uvicorn app.main:app --port 8760"}
            facts.vite_pids = []
            facts.vite_status = None
            facts.vite_body = ""
        report = evaluate(facts)
        blob = json.dumps(report)
        assert "Cloud 1.2" not in blob
        assert "cloud_12" not in blob
        assert "CLOUD_1_2" not in blob
        assert report["verdict"] == "GO"
        assert report["progressPct"] == 100
        assert all(row["system"] != "Cloud 1.2" and row["id"] != "cloud_12" for row in report["checks"])
        assert all(row["system"] != "Cloud 1.2" for row in report["optional"])
