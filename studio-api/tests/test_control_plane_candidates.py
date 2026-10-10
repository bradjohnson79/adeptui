"""Background Services is reachable only when a control port answers."""

from runtime_supervisor.control_client import control_candidate_ports, control_plane_reachable


def test_configured_port_is_tried_before_the_packaged_fallback(monkeypatch):
    monkeypatch.setattr("runtime_supervisor.control_client.control_port", lambda: 8779)
    assert control_candidate_ports() == [8779, 8759]


def test_manager_on_8759_answers_when_config_points_at_8779(monkeypatch):
    seen: list[int] = []

    def fake(_method, _path, timeout=30.0, port=None):
        seen.append(int(port))
        if port == 8759:
            return {"ok": True, "managerPid": 104296, "serviceState": "running"}
        return {"ok": False, "error": "refused"}

    monkeypatch.setattr("runtime_supervisor.control_client.control_port", lambda: 8779)
    monkeypatch.setattr("runtime_supervisor.control_client.call_control", fake)
    assert control_plane_reachable(timeout=3) is True
    assert seen == [8779, 8759]


def test_a_rejected_token_is_not_an_adept_control_plane(monkeypatch):
    monkeypatch.setattr("runtime_supervisor.control_client.control_port", lambda: 8759)
    monkeypatch.setattr(
        "runtime_supervisor.control_client.call_control",
        lambda *_args, **_kwargs: {"ok": False, "error": "invalid or missing control token", "httpStatus": 401},
    )
    assert control_plane_reachable(timeout=3) is False


def test_a_generic_ok_response_is_not_an_adept_control_plane(monkeypatch):
    monkeypatch.setattr("runtime_supervisor.control_client.control_port", lambda: 8759)
    monkeypatch.setattr(
        "runtime_supervisor.control_client.call_control",
        lambda *_args, **_kwargs: {"ok": True},
    )
    assert control_plane_reachable(timeout=3) is False


def test_a_closed_control_port_is_not_reachable_from_a_pid_alone(monkeypatch):
    monkeypatch.setattr("runtime_supervisor.control_client.control_port", lambda: 8759)
    monkeypatch.setattr(
        "runtime_supervisor.control_client.call_control",
        lambda *_args, **_kwargs: {"ok": False, "error": "refused"},
    )
    assert control_plane_reachable(timeout=3) is False
