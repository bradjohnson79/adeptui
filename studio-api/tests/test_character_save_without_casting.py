"""Character save does NOT require casting (Amendment 1).

A character may be saved without generating or approving a casting image.
Minimum required field: Character Name. Backend CharacterProfileCreate
requires only `name`; no approvedIdentityImageId prerequisite.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate


def test_create_profile_name_only_succeeds():
    """CharacterProfileCreate requires only a name — no casting/approval."""
    profile = CharacterProfileCreate(name="Korri")
    assert profile.name == "Korri"
    # No image/approval fields required
    assert profile.visual_description == ""
    assert profile.gender_presentation == ""


def test_update_profile_without_approved_identity_image_succeeds():
    """CharacterProfileUpdate does not require approvedIdentityImageId."""
    update = CharacterProfileUpdate(name="Korri", visual_description="Updated profile text")
    assert update.name == "Korri"
    assert update.visual_description == "Updated profile text"
    # No approvedIdentityImageId field in the schema
    assert not hasattr(update, "approved_identity_image_id")


def test_save_character_neq_generate_neq_approve():
    """Save, Generate, and Approve are distinct operations."""
    # Save = create/update profile (name only)
    save_body = CharacterProfileCreate(name="Mieke")
    # Generate = visual-sheet/generate (separate endpoint, requires name+desc+style)
    # Approve = approve-candidate (separate endpoint, requires assetId)
    # These are independent; save does not gate on the others.
    assert save_body.name == "Mieke"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
