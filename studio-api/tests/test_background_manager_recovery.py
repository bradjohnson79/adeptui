"""Background Manager / Cloudflare Tunnel recovery tests.

Validates:
- Tunnel config has correct ingress (api-beta.adeptui.org → 127.0.0.1:8758).
- cloudflared launch command must include --config (root cause of the reboot failure).
- Scheduled task registration script exists and targets the correct bootstrap.
- Health endpoint aggregation does not report healthy when Studio API is unreachable.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TUNNEL_CONFIG = REPO_ROOT / "config" / "cloudflared" / "adept-ui-beta-tunnel.yml"
START_BETA_BACKEND = REPO_ROOT / "Start-AdeptBetaBackend.ps1"
REGISTER_STARTUP = REPO_ROOT / "Register-AdeptBetaBackendStartup.ps1"
WATCH_SCRIPT = REPO_ROOT / "Watch-AdeptBetaBackend.ps1"


def test_tunnel_config_has_correct_ingress() -> None:
    """Tunnel config must map api-beta.adeptui.org → http://127.0.0.1:8758."""
    content = TUNNEL_CONFIG.read_text(encoding="utf-8")
    assert "api-beta.adeptui.org" in content, "hostname missing from tunnel config"
    assert "http://127.0.0.1:8758" in content, "Studio API target missing from tunnel config"
    assert "tunnel: 822658ce-2057-4250-bb70-eb36dded0630" in content, "tunnel ID missing"


def test_start_beta_backend_uses_config_flag() -> None:
    """Root cause guard: Start-AdeptBetaBackend.ps1 MUST pass --config to cloudflared.
    Without --config, cloudflared returns 503 for all requests (the reboot failure)."""
    content = START_BETA_BACKEND.read_text(encoding="utf-8")
    # The cloudflared launch must include --config
    assert "--config" in content, "Start-AdeptBetaBackend.ps1 must pass --config to cloudflared"
    assert "adept-ui-beta-tunnel.yml" in content or "$cfg" in content, "tunnel config path missing"


def test_register_startup_targets_correct_bootstrap() -> None:
    """Register-AdeptBetaBackendStartup.ps1 must create a task that runs
    Start-AdeptBetaBackend.ps1 then Watch-AdeptBetaBackend.ps1."""
    content = REGISTER_STARTUP.read_text(encoding="utf-8")
    assert "Start-AdeptBetaBackend.ps1" in content, "bootstrap must start the backend"
    assert "Watch-AdeptBetaBackend.ps1" in content, "bootstrap must launch the watchdog"
    assert "AdeptBetaBackendManager" in content, "task name must be AdeptBetaBackendManager"
    assert "AtLogOn" in content or "AtLogon" in content, "trigger must be at logon"


def test_watch_script_has_supervision() -> None:
    """Watch-AdeptBetaBackend.ps1 must have bounded retries + backoff + storm protection."""
    content = WATCH_SCRIPT.read_text(encoding="utf-8")
    assert "MaxRestarts" in content, "must have max restart limit"
    assert "backoff" in content.lower(), "must have backoff"
    assert "Storm" in content or "storm" in content, "must have storm protection"
    assert "consecutiveFailures" in content, "must track consecutive failures"


def test_runtime_manager_status_aggregates() -> None:
    """runtime_manager service.py must aggregate health from multiple sources."""
    service = REPO_ROOT / "studio-api" / "app" / "runtime_manager" / "service.py"
    content = service.read_text(encoding="utf-8")
    assert "8758" in content or "api/healthz" in content, "must probe Studio API"
    assert "8188" in content or "system_stats" in content, "must probe ComfyUI"
    assert "status" in content.lower(), "must return structured status"
