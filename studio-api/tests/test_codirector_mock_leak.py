"""Reproduction tests for mock-provider leakage (c2/D17 fail-closed).

Law 8/D17: The mock provider must never be selectable in a production run
without an explicit operator opt-in. These tests assert the three paths:
blocked without E2E, blocked in production with E2E, and active with the
explicit allow-mock hatch.
"""

from __future__ import annotations

import os
from unittest.mock import patch


def _clean_base_env() -> None:
    """Remove mock-related env vars that could pollute test isolation."""
    for key in list(os.environ):
        if key.startswith("STUDIO_E2E") or key.startswith("ADEPT_"):
            del os.environ[key]


def test_mock_provider_blocked_without_e2e() -> None:
    """Without STUDIO_E2E, mock provider must never be allowed."""
    from app.codirector.service import _mock_provider_allowed, active_provider_id

    with patch.dict(os.environ, {}, clear=True):
        os.environ["ADEPT_CODIRECTOR_MOCK_SCENARIO"] = "connection_refused"

        assert not _mock_provider_allowed()
        assert active_provider_id() != "mock"


def test_mock_provider_blocked_in_production_with_e2e() -> None:
    """STUDIO_E2E + ADEPT_ENV=production + no allow-mock -> blocked."""
    from app.codirector.service import _mock_provider_allowed

    with patch.dict(os.environ, {}, clear=True):
        os.environ["STUDIO_E2E"] = "1"
        os.environ["ADEPT_ENV"] = "production"

        assert not _mock_provider_allowed()


def test_allow_mock_hatch_active() -> None:
    """STUDIO_E2E + ADEPT_ENV=production + ADEPT_ALLOW_MOCK_PROVIDER -> allowed."""
    from app.codirector.service import _mock_provider_allowed

    with patch.dict(os.environ, {}, clear=True):
        os.environ["STUDIO_E2E"] = "1"
        os.environ["ADEPT_ENV"] = "production"
        os.environ["ADEPT_ALLOW_MOCK_PROVIDER"] = "1"

        assert _mock_provider_allowed()
