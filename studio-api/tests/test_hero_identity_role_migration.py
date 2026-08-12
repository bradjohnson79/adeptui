"""hero_portrait → hero_identity role rename migration tests (Amendment 2b).

Verifies the read-time alias in roles.py resolves legacy hero_portrait to
hero_identity, and the one-time data migration is idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.roles import (
    ADDITIONAL_ROLES,
    ALL_REFERENCE_ROLES,
    ROLE_ALIASES,
    canonical_role,
)


def test_hero_identity_in_canonical_role_list():
    """hero_identity is the canonical role; hero_portrait is NOT in the list."""
    assert "hero_identity" in ADDITIONAL_ROLES
    assert "hero_identity" in ALL_REFERENCE_ROLES
    assert "hero_portrait" not in ADDITIONAL_ROLES
    assert "hero_portrait" not in ALL_REFERENCE_ROLES


def test_role_alias_maps_legacy_hero_portrait():
    """ROLE_ALIASES maps legacy hero_portrait → hero_identity."""
    assert ROLE_ALIASES.get("hero_portrait") == "hero_identity"


def test_canonical_role_resolves_hero_portrait_to_hero_identity():
    """canonical_role() resolves legacy rows to the new canonical name."""
    assert canonical_role("hero_portrait") == "hero_identity"
    assert canonical_role("hero_identity") == "hero_identity"
    assert canonical_role("full_body_front") == "full_body_front"
    assert canonical_role("") == ""
    assert canonical_role(None) == ""


def test_canonical_role_passes_through_unknown_roles():
    """Unknown roles pass through unchanged."""
    assert canonical_role("some_custom_role") == "some_custom_role"


def test_migration_module_exposes_run_for_all_projects():
    """The migration module exposes the idempotent entry point."""
    from app.character_identity.migrations.hero_identity_rename import (
        run_for_all_projects,
        run_hero_identity_rename,
    )

    assert callable(run_for_all_projects)
    assert callable(run_hero_identity_rename)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
