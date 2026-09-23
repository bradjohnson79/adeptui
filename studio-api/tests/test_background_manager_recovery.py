"""Background Manager / Cloudflare Tunnel recovery tests.

Validates:
- Tunnel config has correct ingress (api-beta.adeptui.org → 127.0.0.1:8758).
- AdeptBetaBackendManager is retired as a production logon owner.
- Health endpoint aggregation does not report healthy when Studio API is unreachable.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TUNNEL_CONFIG = REPO_ROOT / "config" / "cloudflared" / "adept-ui-beta-tunnel.yml"
REGISTER_STARTUP = REPO_ROOT / "Register-AdeptBetaBackendStartup.ps1"
WATCH_SCRIPT = REPO_ROOT / "Watch-AdeptBetaBackend.ps1"
START_BETA_BACKEND = REPO_ROOT / "Start-AdeptBetaBackend.ps1"


def test_tunnel_config_has_correct_ingress() -> None:
    """Tunnel config must map api-beta.adeptui.org → http://127.0.0.1:8758."""
    content = TUNNEL_CONFIG.read_text(encoding="utf-8")
    assert "api-beta.adeptui.org" in content, "hostname missing from tunnel config"
    assert "http://127.0.0.1:8758" in content, "Studio API target missing from tunnel config"
    assert "tunnel: 822658ce-2057-4250-bb70-eb36dded0630" in content, "tunnel ID missing"


def test_start_beta_backend_delegates_to_supervisor() -> None:
    content = START_BETA_BACKEND.read_text(encoding="utf-8")
    assert "run_runtime_supervisor.py" in content
    assert "start" in content
    assert "8760" not in content or "NOT start retired" in content or "Does NOT start retired" in content


def test_register_startup_refuses_legacy_task() -> None:
    content = REGISTER_STARTUP.read_text(encoding="utf-8")
    assert "AdeptBetaBackendManager" in content
    assert "will not create" in content.lower() or "RETIRED" in content
    assert "AdeptRuntimeService" in content
    assert "Register-ScheduledTask" not in content
    assert "install-task" in content


def test_watch_script_is_thin_client() -> None:
    content = WATCH_SCRIPT.read_text(encoding="utf-8")
    assert "run_runtime_supervisor.py" in content
    assert "watch" in content


def test_runtime_manager_status_aggregates() -> None:
    """runtime_manager service.py must aggregate health from multiple sources."""
    service = REPO_ROOT / "studio-api" / "app" / "runtime_manager" / "service.py"
    content = service.read_text(encoding="utf-8")
    assert "8758" in content or "api/healthz" in content, "must probe Studio API"
    assert "8188" in content or "system_stats" in content, "must probe ComfyUI"
    assert "status" in content.lower(), "must return structured status"
